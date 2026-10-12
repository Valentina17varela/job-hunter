"""Fetch one posting page safely and extract its fields (see specs/10-manual-postings.md §5).

The server makes the request, so it must never become a way to reach internal services:
only http/https on a few ports, hosts are resolved first and **every** address must be a public
one, the connection is pinned to the checked address (no DNS rebinding), redirects are re-checked,
and the response is size- and time-limited. One GET, no cookies, no JavaScript, no crawling.
"""

from __future__ import annotations

import html as html_module
import ipaddress
import json
import re
import socket
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from jobhunter.http import USER_AGENT
from jobhunter.text import annualize, html_to_text

MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 10.0
MAX_REDIRECTS = 3
ALLOWED_PORTS = {80, 443, 8080, 8443}
TEXT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
Resolver = Callable[..., list[tuple[Any, ...]]]


class FetchPageError(Exception):
    """The page could not be fetched (message is shown to the person)."""


@dataclass
class Page:
    url: str
    html: str


def _check_ip(raw: str) -> str:
    ip = ipaddress.ip_address(raw.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if not ip.is_global or ip.is_multicast:
        raise FetchPageError(
            "that address is not a public website (internal addresses are blocked)"
        )
    return str(ip)


def public_addresses(host: str, port: int, resolver: Resolver = socket.getaddrinfo) -> list[str]:
    """Addresses of ``host`` if **all** of them are public; otherwise raise."""
    try:
        return [_check_ip(host)]  # an IP literal
    except ValueError:
        pass
    try:
        infos = resolver(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchPageError(f"could not find the site '{host}'") from exc
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not addresses:
        raise FetchPageError(f"could not find the site '{host}'")
    return [_check_ip(a) for a in addresses]  # rejects the whole host if any address is private


def _validate(url: str) -> tuple[str, str, int, str]:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https"):
        raise FetchPageError("only http:// and https:// links can be fetched")
    if parts.username or parts.password:
        raise FetchPageError("links with a user name or password are not allowed")
    host = parts.hostname
    if not host:
        raise FetchPageError("the link has no host")
    port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    if port not in ALLOWED_PORTS:
        raise FetchPageError(f"port {port} is not allowed")
    target = parts.path or "/"
    if parts.query:
        target += "?" + parts.query
    return parts.scheme.lower(), host, port, target


def fetch_page(
    url: str,
    *,
    resolver: Resolver = socket.getaddrinfo,
    transport: httpx.BaseTransport | None = None,
    max_bytes: int = MAX_BYTES,
    timeout: float = TIMEOUT,
) -> Page:
    """GET one page. ``resolver`` and ``transport`` exist so tests never touch the network."""
    current = url.strip()
    with httpx.Client(transport=transport, timeout=timeout, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            scheme, host, port, target = _validate(current)
            address = public_addresses(host, port, resolver)[0]
            shown = f"[{address}]" if ":" in address else address
            pinned = f"{scheme}://{shown}:{port}{target}"
            headers = {
                "Host": host if port in (80, 443) else f"{host}:{port}",
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            }
            try:
                with client.stream(
                    "GET", pinned, headers=headers, extensions={"sni_hostname": host}
                ) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise FetchPageError("the site redirected without saying where")
                        current = urljoin(current, location)
                        continue
                    if response.status_code >= 400:
                        raise FetchPageError(f"the site answered HTTP {response.status_code}")
                    ctype = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ctype and not ctype.startswith(TEXT_TYPES):
                        raise FetchPageError(f"that link is not a web page ({ctype})")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise FetchPageError("the page is too large")
                    charset = response.encoding or "utf-8"
            except httpx.TimeoutException as exc:
                raise FetchPageError("the site took too long to answer") from exc
            except httpx.HTTPError as exc:
                raise FetchPageError(f"could not load the page ({type(exc).__name__})") from exc
            return Page(current, bytes(body).decode(charset, errors="replace"))
    raise FetchPageError("too many redirects")


# --- extraction -------------------------------------------------------------------------------

_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S
)


class _Meta(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): v or "" for k, v in attrs}
        if tag == "meta":
            key = a.get("property") or a.get("name")
            if key and a.get("content"):
                self.meta.setdefault(key.lower(), a["content"])
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def _job_postings(data: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            found += _job_postings(item)
    elif isinstance(data, dict):
        kind = data.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "JobPosting" in kinds:
            found.append(data)
        found += _job_postings(data.get("@graph"))
    return found


def _place(loc: Any) -> str | None:
    if isinstance(loc, list):
        names = [p for p in (_place(x) for x in loc) if p]
        return "; ".join(dict.fromkeys(names)) or None
    if not isinstance(loc, dict):
        return loc if isinstance(loc, str) else None
    addr = loc.get("address", loc)
    if isinstance(addr, str):
        return addr
    if not isinstance(addr, dict):
        return loc.get("name") if isinstance(loc.get("name"), str) else None
    country = addr.get("addressCountry")
    country = country.get("name") if isinstance(country, dict) else country
    parts = [addr.get("addressLocality"), addr.get("addressRegion"), country]
    return ", ".join(str(p) for p in parts if p) or None


def _salary(base: Any) -> tuple[int | None, int | None, str | None]:
    if not isinstance(base, dict):
        return None, None, None
    currency = base.get("currency")
    value = base.get("value", {})
    if not isinstance(value, dict):
        value = {"value": value}
    unit = str(value.get("unitText") or base.get("unitText") or "YEAR")
    low = value.get("minValue", value.get("value"))
    high = value.get("maxValue", value.get("value"))
    try:
        lo = annualize(float(low), unit) if low is not None else None
        hi = annualize(float(high), unit) if high is not None else None
    except (TypeError, ValueError):
        return None, None, None
    return lo, hi, str(currency).upper() if currency else None


def _description(raw: Any) -> str:
    text = raw if isinstance(raw, str) else ""
    if "<" not in text and "&lt;" in text:
        text = html_module.unescape(text)
    return html_to_text(text)


def extract_posting(page_html: str, page_url: str) -> dict[str, Any]:
    """Best-effort fields: JSON-LD JobPosting, then Open Graph/<title>, then the page text."""
    out: dict[str, Any] = {"title": None, "company": None, "location": None, "remote": "unknown",
                           "description": "", "salary_min": None, "salary_max": None,
                           "salary_currency": None, "url": page_url}  # fmt: skip
    for block in _LD_RE.findall(page_html):
        try:
            nodes = _job_postings(json.loads(block.strip()))
        except ValueError:
            continue
        if not nodes:
            continue
        node = nodes[0]
        org = node.get("hiringOrganization")
        out["title"] = node.get("title") or node.get("name")
        out["company"] = org.get("name") if isinstance(org, dict) else org
        out["location"] = _place(node.get("jobLocation"))
        if str(node.get("jobLocationType", "")).upper() == "TELECOMMUTE":
            out["remote"] = "remote"
            req = node.get("applicantLocationRequirements")
            area = _place(req) if req else None
            out["location"] = out["location"] or (f"Remote ({area})" if area else "Remote")
        out["salary_min"], out["salary_max"], out["salary_currency"] = _salary(
            node.get("baseSalary")
        )
        out["description"] = _description(node.get("description"))
        break
    meta = _Meta()
    meta.feed(page_html)
    if not out["title"]:
        out["title"] = (meta.meta.get("og:title") or meta.title or "").strip() or None
    if not out["company"]:
        out["company"] = meta.meta.get("og:site_name")
    if not out["description"]:
        out["description"] = html_to_text(page_html)[:100_000]
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in out.items()}
