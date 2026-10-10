"""Text helpers shared by sources: HTML cleaning, remote-mode and salary inference."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from jobhunter.models import RemoteMode

_BLOCK_TAGS = {
    "p", "br", "div", "ul", "ol", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section",
}  # fmt: skip
_SKIP_TAGS = {"script", "style"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n- " if tag == "li" else "\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS and tag != "li":  # <li> start already breaks the line
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str | None) -> str:
    """Convert an HTML fragment to readable plain text."""
    if not html:
        return ""
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    return normalize_text("".join(extractor.parts))


def normalize_text(text: str | None) -> str:
    """Normalize whitespace: no-break spaces, runs of spaces and 3+ blank lines."""
    if not text:
        return ""
    lines = [
        re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\xa0", " ").splitlines()
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def fix_mojibake(text: str | None) -> str | None:
    """Repair UTF-8 text that a feed double-encoded as latin-1 ('fÃ¼r' → 'für')."""
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


_HYBRID_RE = re.compile(r"\bhybrid\b", re.I)
_REMOTE_RE = re.compile(r"\b(remote|anywhere|worldwide|distributed|work from home)\b", re.I)


def infer_remote(*texts: str | None) -> RemoteMode:
    """Infer the work mode from short texts (location, title). Empty input → unknown."""
    joined = " ".join(t for t in texts if t).strip()
    if not joined:
        return "unknown"
    if _HYBRID_RE.search(joined):
        return "hybrid"
    if _REMOTE_RE.search(joined):
        return "remote"
    return "onsite"


_CURRENCY = {"$": "USD", "us$": "USD", "usd": "USD", "€": "EUR", "eur": "EUR",
             "£": "GBP", "gbp": "GBP"}  # fmt: skip
_CUR = r"(?:US\$|USD|EUR|GBP|[$€£])"
_NUM = r"\d{1,3}(?:[,.]\d{3})+|\d+(?:\.\d+)?"
_SALARY_RE = re.compile(
    rf"(?P<cur>{_CUR})\s?(?P<lo>{_NUM})\s?(?P<lok>[kK])?"
    rf"\s*(?:-|–|—|to)\s*(?:{_CUR})?\s?(?P<hi>{_NUM})\s?(?P<hik>[kK])?",
    re.I,
)
_HOURLY_RE = re.compile(r"(/\s?h(ou)?r|per hour|hourly|an hour)", re.I)
_MONTHLY_RE = re.compile(r"(/\s?mo(nth)?|per month|monthly)", re.I)
HOURS_PER_YEAR = 2080


def _to_number(raw: str, k: str | None) -> float:
    cleaned = raw.replace(",", "") if re.search(r",\d{3}", raw) else raw
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", cleaned):  # european thousands separator
        cleaned = cleaned.replace(".", "")
    value = float(cleaned)
    return value * 1000 if k else value


def annualize(amount: float, interval: str | None) -> int:
    """Convert a pay amount to an annual figure given its interval (hour/month/year)."""
    interval = (interval or "").lower()
    if "hour" in interval:
        return round(amount * HOURS_PER_YEAR)
    if "month" in interval:
        return round(amount * 12)
    return round(amount)


def extract_salary(text: str | None) -> tuple[int, int, str] | None:
    """Find an annual salary range like '$120k - $150k' in free text.

    Returns (min, max, currency) or None. Conservative: needs a currency marker and a
    plausible annual value, to avoid matching things like '2-5 years'.
    """
    if not text:
        return None
    for match in _SALARY_RE.finditer(text):
        lo = _to_number(match["lo"], match["lok"])
        hi = _to_number(match["hi"], match["hik"])
        if lo > hi:
            continue
        window = text[match.start() : match.end() + 25]
        if _HOURLY_RE.search(window):
            lo, hi = lo * HOURS_PER_YEAR, hi * HOURS_PER_YEAR
        elif _MONTHLY_RE.search(window):
            lo, hi = lo * 12, hi * 12
        if lo < 10_000:
            continue
        currency = _CURRENCY[match["cur"].lower()]
        return round(lo), round(hi), currency
    return None
