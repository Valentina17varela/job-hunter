"""Multi-company aggregators: Remotive, RemoteOK, We Work Remotely, Arbeitnow, Jobicy.

Terms of use: these feeds ask for attribution and a link back to the original posting.
Every Job keeps the aggregator's own URL, and the tool is for personal use only.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any

from jobhunter.http import HttpClient
from jobhunter.models import Job
from jobhunter.sources.base import collect, from_epoch, parse_iso
from jobhunter.text import annualize, extract_salary, fix_mojibake, html_to_text, infer_remote


def _salary_fields(
    low: int | None, high: int | None, currency: str | None, fallback_text: str | None = None
) -> dict[str, Any]:
    if low and high:
        return {"salary_min": low, "salary_max": high, "salary_currency": currency or "USD"}
    found = extract_salary(fallback_text)
    if found:
        return {"salary_min": found[0], "salary_max": found[1], "salary_currency": found[2]}
    return {}


# --- Remotive -----------------------------------------------------------------------------


def _parse_remotive_one(raw: Any) -> Job | None:
    location = raw.get("candidate_required_location") or None
    return Job(
        source="remotive",
        external_id=str(raw["id"]),
        company=raw["company_name"],
        title=raw["title"],
        location=location,
        remote="remote",
        description=html_to_text(raw.get("description")),
        url=raw["url"],
        posted_at=parse_iso(raw.get("publication_date")),
        **_salary_fields(None, None, None, raw.get("salary")),
    )


def parse_remotive(data: dict[str, Any]) -> list[Job]:
    return collect(data.get("jobs", []), lambda raw: _parse_remotive_one(raw))


class RemotiveSource:
    name = "remotive"
    target = ""

    async def fetch(self, http: HttpClient) -> list[Job]:
        return parse_remotive(await http.get_json("https://remotive.com/api/remote-jobs"))


# --- RemoteOK -----------------------------------------------------------------------------


# RemoteOK appends a per-request tracking tag to each description, which would make the
# content hash change on every fetch. It is feed boilerplate, not part of the posting.
_REMOTEOK_TAG_RE = re.compile(r"\n*Please mention the word \*\*\w+\*\* and tag \S+.*$", re.S)


def _parse_remoteok_one(raw: Any) -> Job | None:
    if "position" not in raw:  # first element is a legal notice
        return None
    location = fix_mojibake(raw.get("location")) or None
    description = _REMOTEOK_TAG_RE.sub("", html_to_text(fix_mojibake(raw.get("description"))))
    return Job(
        source="remoteok",
        external_id=str(raw["id"]),
        company=fix_mojibake(raw["company"]),
        title=fix_mojibake(raw["position"]),
        location=location,
        remote="remote",
        description=description,
        url=raw.get("url") or raw["apply_url"],
        posted_at=parse_iso(raw.get("date")),
        **_salary_fields(raw.get("salary_min"), raw.get("salary_max"), "USD", description),
    )


def parse_remoteok(data: list[dict[str, Any]]) -> list[Job]:
    return collect(data, lambda raw: _parse_remoteok_one(raw))


class RemoteOkSource:
    name = "remoteok"
    target = ""

    async def fetch(self, http: HttpClient) -> list[Job]:
        return parse_remoteok(await http.get_json("https://remoteok.com/api"))


# --- We Work Remotely (RSS) -----------------------------------------------------------------


def parse_wwr(xml_text: str) -> list[Job]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid RSS: {exc}") from exc
    jobs = []
    for item in root.iter("item"):
        raw_title = (item.findtext("title") or "").strip()
        company, sep, title = raw_title.partition(": ")
        if not sep:
            company, title = "Unknown", raw_title
        link = (item.findtext("link") or item.findtext("guid") or "").strip()
        if not link or not title:
            continue
        region = (item.findtext("region") or "").strip() or None
        description = html_to_text(item.findtext("description"))
        pub = item.findtext("pubDate")
        jobs.append(
            Job(
                source="weworkremotely",
                external_id=(item.findtext("guid") or link).strip(),
                company=company.strip(),
                title=title.strip(),
                location=region,
                remote="remote",
                description=description,
                url=link,
                posted_at=parsedate_to_datetime(pub) if pub else None,
                **_salary_fields(None, None, None, description),
            )
        )
    return jobs


class WeWorkRemotelySource:
    name = "weworkremotely"

    def __init__(self, category: str) -> None:
        self.target = category

    async def fetch(self, http: HttpClient) -> list[Job]:
        xml_text = await http.get_text(f"https://weworkremotely.com/categories/{self.target}.rss")
        return parse_wwr(xml_text)


# --- Arbeitnow ------------------------------------------------------------------------------


def _parse_arbeitnow_one(raw: Any) -> Job | None:
    location = raw.get("location") or None
    description = html_to_text(raw.get("description"))
    return Job(
        source="arbeitnow",
        external_id=raw["slug"],
        company=raw["company_name"],
        title=raw["title"],
        location=location,
        remote="remote" if raw.get("remote") else infer_remote(location, raw["title"]),
        description=description,
        url=raw["url"],
        posted_at=from_epoch(raw.get("created_at")),
        **_salary_fields(None, None, None, description),
    )


def parse_arbeitnow(data: dict[str, Any]) -> list[Job]:
    return collect(data.get("data", []), lambda raw: _parse_arbeitnow_one(raw))


class ArbeitnowSource:
    name = "arbeitnow"
    target = ""

    def __init__(self, pages: int = 3) -> None:
        self.pages = pages

    async def fetch(self, http: HttpClient) -> list[Job]:
        jobs: list[Job] = []
        for page in range(1, self.pages + 1):
            data = await http.get_json(
                "https://www.arbeitnow.com/api/job-board-api", params={"page": page}
            )
            batch = parse_arbeitnow(data)
            if not batch:
                break
            jobs.extend(batch)
        return jobs


# --- Jobicy ---------------------------------------------------------------------------------


def _parse_jobicy_one(raw: Any) -> Job | None:
    description = html_to_text(raw.get("jobDescription") or raw.get("jobExcerpt"))
    low, high = raw.get("salaryMin"), raw.get("salaryMax")
    interval = raw.get("salaryPeriod")
    return Job(
        source="jobicy",
        external_id=str(raw["id"]),
        company=raw["companyName"],
        title=raw["jobTitle"],
        location=raw.get("jobGeo") or None,
        remote="remote",
        description=description,
        url=raw["url"],
        posted_at=parse_iso(raw.get("pubDate")),
        **_salary_fields(
            annualize(low, interval) if low else None,
            annualize(high, interval) if high else None,
            raw.get("salaryCurrency"),
            description,
        ),
    )


def parse_jobicy(data: dict[str, Any]) -> list[Job]:
    return collect(data.get("jobs", []), lambda raw: _parse_jobicy_one(raw))


class JobicySource:
    name = "jobicy"
    target = ""

    async def fetch(self, http: HttpClient) -> list[Job]:
        data = await http.get_json("https://jobicy.com/api/v2/remote-jobs", params={"count": 100})
        return parse_jobicy(data)
