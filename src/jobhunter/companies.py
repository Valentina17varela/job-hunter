"""Company list for per-company ATS sources: load/save, slug checks and discovery.

`companies.yaml` is a discovery mechanism, not a preference: filtering by the person's
criteria happens later and ignores which company a posting came from.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

from jobhunter.http import FetchError, HttpClient

Ats = Literal["greenhouse", "lever", "ashby"]
ATS_ORDER: list[Ats] = ["greenhouse", "lever", "ashby"]
_PROBE_URLS: dict[str, str] = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json&limit=1",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}


class Company(BaseModel):
    name: str
    ats: Ats
    slug: str


def load_companies(path: Path) -> list[Company]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text()) or {}
    return [Company.model_validate(c) for c in raw.get("companies") or []]


def save_companies(path: Path, companies: list[Company]) -> None:
    ordered = sorted(companies, key=lambda c: (c.name.lower(), c.ats))
    header = (
        "# Target companies with a public ATS board. Grown by `jobhunter companies discover`.\n"
        "# The company is only a discovery mechanism; filtering ignores it (specs/03-sources.md).\n"
    )
    body = yaml.safe_dump(
        {"companies": [c.model_dump() for c in ordered]}, sort_keys=False, allow_unicode=True
    )
    path.write_text(header + body)


def read_candidates(path: Path) -> list[str]:
    """Candidate company names, one per line; blank lines and `#` comments are ignored."""
    if not path.exists():
        return []
    lines = (line.strip() for line in path.read_text().splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def slug_variants(name: str) -> list[str]:
    """Plausible board slugs for a company name, most likely first."""
    base = re.sub(r"[^a-z0-9 ]+", "", name.lower().replace("&", " and ")).strip()
    words = base.split()
    if not words:
        return []
    variants = ["".join(words), "-".join(words)]
    return list(dict.fromkeys(variants))


@dataclass
class ProbeResult:
    ok: bool
    jobs: int = 0
    error: str = ""


def _count_jobs(data: object) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        jobs = data.get("jobs")
        return len(jobs) if isinstance(jobs, list) else 0
    return 0


async def probe(http: HttpClient, ats: str, slug: str) -> ProbeResult:
    """Check whether a board exists. 404 → not ok; the job count is only for reporting."""
    url = _PROBE_URLS[ats].format(slug=slug)
    try:
        data = await http.get_json(url)
    except FetchError as exc:
        return ProbeResult(False, error=str(exc))
    return ProbeResult(True, jobs=_count_jobs(data))


async def check_companies(
    http: HttpClient, companies: list[Company]
) -> list[tuple[Company, ProbeResult]]:
    results = await asyncio.gather(*(probe(http, c.ats, c.slug) for c in companies))
    return list(zip(companies, results, strict=True))


async def discover_company(http: HttpClient, name: str) -> list[Company]:
    """Find which ATS boards (if any) exist for a company name."""
    found: list[Company] = []
    for ats in ATS_ORDER:
        for slug in slug_variants(name):
            result = await probe(http, ats, slug)
            if result.ok and result.jobs > 0:
                found.append(Company(name=name, ats=ats, slug=slug))
                break
    return found


async def discover(
    http: HttpClient, names: list[str], known: list[Company]
) -> tuple[list[Company], list[str]]:
    """Probe candidate names that are not yet known. Returns (new companies, names not found)."""
    known_names = {c.name.lower() for c in known}
    pending = [n for n in dict.fromkeys(names) if n.lower() not in known_names]
    results = await asyncio.gather(*(discover_company(http, n) for n in pending))
    new = [c for found in results for c in found]
    missing = [n for n, found in zip(pending, results, strict=True) if not found]
    return new, missing
