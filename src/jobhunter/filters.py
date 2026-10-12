"""Hard filter: deterministic rules applied before any LLM call (see specs/04-filtering.md).

Rules run in a fixed order and stop at the first rejection. A rejection reason has the form
``rule: detail`` so results can be grouped by rule.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from jobhunter.config import SearchConfig
from jobhunter.models import ATS_SOURCES, Job

SENIORITY_LEVELS = ("junior", "mid", "senior", "lead")
_LEAD_RE = re.compile(r"\b(staff|principal|lead|head of|architect|distinguished)\b", re.I)
_SENIOR_RE = re.compile(r"\b(senior|sr)\b", re.I)
_JUNIOR_RE = re.compile(
    r"\b(junior|jr|entry[- ]level|graduate|intern(ship)?|trainee|apprentice)\b", re.I
)

_GENERIC_LOCATION_RE = re.compile(r"\b(worldwide|anywhere|global|everywhere|remote)\b", re.I)
_ALIASES = {
    "latam": ["latin america"],
    "latin america": ["latam"],
    "usa": ["united states", "u.s.a."],
    "us": ["u.s."],
    "uk": ["united kingdom", "great britain"],
}
_PLACE = r"(?-i:[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})"
_RESTRICTION_RE = re.compile(
    r"(?:(?-i:US|USA|U\.S\.|UK|EU)|united states|canada|europe|emea|apac|germany|india)"
    r"\s*[- ]?\s*(?:only|residents?|citizens?)\b"
    r"|\bmust (?:be|reside|live|work) (?:located |based |authorized to work |resident )?"
    rf"(?:in|from)\s+(?:the\s+)?{_PLACE}"
    r"|\b(?:european|north american?|pacific|(?-i:EU|US|CET|EST|PST))\s+time\s*zones?\b",
    re.I,
)


@dataclass
class FilterResult:
    passed: bool
    reason: str | None = None
    flags: list[str] = field(default_factory=list)


def infer_seniority(title: str) -> str:
    """Seniority from the title: lead > senior > junior; no marker means mid."""
    if _LEAD_RE.search(title):
        return "lead"
    if _SENIOR_RE.search(title):
        return "senior"
    if _JUNIOR_RE.search(title):
        return "junior"
    return "mid"


_LEGAL_SUFFIXES = {"inc", "llc", "ltd", "gmbh", "sa", "sas", "corp", "co"}


def normalize_company(name: str) -> str:
    """Comparable company name: lowercase, no accents or punctuation, legal suffix dropped.

    "Acme, Inc." and "ACME Inc" both give "acme"; "Meta" and "Metamask" stay different.
    """
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    tokens = re.sub(r"[^a-z0-9]+", " ", text.replace(".", "")).split()
    while len(tokens) > 1 and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _word_regex(terms: list[str]) -> re.Pattern[str] | None:
    if not terms:
        return None
    parts = [rf"(?<![A-Za-z0-9]){re.escape(t.strip())}(?![A-Za-z0-9])" for t in terms if t.strip()]
    return re.compile("|".join(parts), re.I) if parts else None


def to_usd(amount: int, currency: str | None, fx: dict[str, float]) -> float | None:
    """Convert to USD with the configured table; None when the currency is unknown."""
    code = (currency or "USD").upper()
    if code == "USD":
        return float(amount)
    rate = fx.get(code)
    return amount * rate if rate is not None else None


class JobFilter:
    """Compiled filter for a SearchConfig; build once, evaluate many postings."""

    def __init__(self, search: SearchConfig, fx: dict[str, float] | None = None) -> None:
        self.cfg = search
        self.fx = {k.upper(): v for k, v in (fx or {}).items()}
        self._titles_exclude = _word_regex(search.titles_exclude)
        self._titles_include = _word_regex(search.titles_include)
        self._kw_exclude = _word_regex(search.keywords_exclude)
        self._kw_include = _word_regex(search.keywords_include)
        self._blocked = {n for n in map(normalize_company, search.companies_exclude) if n}
        self._allowed = [self._compile_place(t) for t in search.locations_allowed if t.strip()]

    def evaluate(self, job: Job, now: datetime | None = None) -> FilterResult:
        flags: list[str] = []
        for rule in (
            self._age,
            self._company,
            self._title_exclude,
            self._title_include,
            self._seniority,
            self._work_mode,
            self._location,
            self._keywords_exclude,
            self._keywords_include,
            self._salary,
        ):
            reason = rule(job, flags, now or datetime.now(UTC))
            if reason:
                return FilterResult(False, reason, flags)
        return FilterResult(True, None, flags)

    # -- rules: each returns a rejection reason or None --------------------------------------

    def _age(self, job: Job, flags: list[str], now: datetime) -> str | None:
        limit = self.cfg.max_age_days_ats if job.source in ATS_SOURCES else self.cfg.max_age_days
        if limit is not None and job.posted_at and job.posted_at < now - timedelta(days=limit):
            return f"max_age_days: posted {job.posted_at.date()}, older than {limit} days"
        return None

    def _company(self, job: Job, flags: list[str], now: datetime) -> str | None:
        if self._blocked and normalize_company(job.company) in self._blocked:
            return f'companies_exclude: company "{job.company}" is on your block list'
        return None

    def _title_exclude(self, job: Job, flags: list[str], now: datetime) -> str | None:
        if self._titles_exclude and (m := self._titles_exclude.search(job.title)):
            return f'titles_exclude: title contains "{m.group(0)}"'
        return None

    def _title_include(self, job: Job, flags: list[str], now: datetime) -> str | None:
        if self._titles_include and not self._titles_include.search(job.title):
            return "titles_include: title matches none of the wanted titles"
        return None

    def _seniority(self, job: Job, flags: list[str], now: datetime) -> str | None:
        if not self.cfg.seniority:
            return None
        level = infer_seniority(job.title)
        if level not in self.cfg.seniority:
            return f'seniority: title implies "{level}", wanted {self.cfg.seniority}'
        return None

    def _work_mode(self, job: Job, flags: list[str], now: datetime) -> str | None:
        if not self.cfg.work_mode:
            return None
        if job.remote == "unknown":
            flags.append("unknown_mode")
            return None
        if job.remote not in self.cfg.work_mode:
            return f'work_mode: posting is "{job.remote}", wanted {self.cfg.work_mode}'
        return None

    def _location(self, job: Job, flags: list[str], now: datetime) -> str | None:
        if not self._allowed:
            return None
        location = job.location or ""
        if self._location_matches(location):
            return None
        specific = bool(location) and not self._is_generic(location.lower())
        if specific:
            return f'locations_allowed: location "{job.location}" is not in the allowed list'
        text = f"{job.title}\n{job.description}"
        for m in _RESTRICTION_RE.finditer(text):
            # An allowed place mentioned right next to the restriction ("Colombia or US only")
            # means the posting is open to the person.
            context = text[max(0, m.start() - 60) : m.end() + 60]
            if not self._location_matches(context):
                return f'locations_allowed: description restricts location ("{m.group(0)}")'
        if not location:
            flags.append("unknown_location")
        return None

    def _keywords_exclude(self, job: Job, flags: list[str], now: datetime) -> str | None:
        if self._kw_exclude and (m := self._kw_exclude.search(f"{job.title}\n{job.description}")):
            return f'keywords_exclude: found "{m.group(0)}"'
        return None

    def _keywords_include(self, job: Job, flags: list[str], now: datetime) -> str | None:
        if self._kw_include and not self._kw_include.search(f"{job.title}\n{job.description}"):
            return "keywords_include: none of the wanted keywords appear"
        return None

    def _salary(self, job: Job, flags: list[str], now: datetime) -> str | None:
        minimum = self.cfg.salary.min_usd
        if minimum <= 0:
            return None
        top = job.salary_max if job.salary_max is not None else job.salary_min
        if top is None:
            if self.cfg.salary.on_missing == "reject":
                return "salary: no salary published"
            flags.append("no_salary")
            return None
        usd = to_usd(top, job.salary_currency, self.fx)
        if usd is None:
            flags.append("unknown_currency")
            return None
        if usd < minimum:
            return f"salary: up to ${usd:,.0f}/yr, below the ${minimum:,}/yr minimum"
        return None

    # -- helpers ---------------------------------------------------------------------------

    @staticmethod
    def _compile_place(token: str) -> re.Pattern[str]:
        """Pattern for an allowed place. Short all-caps acronyms (US, UK) are case-sensitive so
        the word "us" in "contact us" never counts as a country."""
        token = token.strip()
        aliases = _ALIASES.get(token.lower(), [])
        acronym = token.isupper() and len(token) <= 3
        parts = [f"(?-i:{re.escape(token)})" if acronym else f"(?i:{re.escape(token)})"]
        parts += [f"(?i:{re.escape(a)})" for a in aliases]
        return re.compile(rf"(?<![A-Za-z0-9])(?:{'|'.join(parts)})(?![A-Za-z0-9])")

    def _location_matches(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self._allowed)

    @staticmethod
    def _is_generic(location: str) -> bool:
        """True for 'Remote', 'Worldwide', 'Anywhere in the World' — no country named."""
        leftover = _GENERIC_LOCATION_RE.sub("", location)
        leftover = re.sub(r"\b(in|the|world|work|from|home|only|or|and|any|of)\b", "", leftover)
        return not re.sub(r"[^a-z]", "", leftover)


def job_from_row(row: sqlite3.Row) -> Job:
    return Job(
        source=row["source"],
        external_id=row["external_id"],
        company=row["company"],
        title=row["title"],
        location=row["location"],
        remote=row["remote"],
        description=row["description"],
        url=row["url"],
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
        salary_currency=row["salary_currency"],
        posted_at=datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None,
    )
