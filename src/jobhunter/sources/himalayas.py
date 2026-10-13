"""Himalayas: https://himalayas.app/jobs/api/search (public JSON, remote jobs worldwide).

The whole feed has over 100,000 postings, so the search endpoint is used with the configured
queries and seniority levels (the API takes one seniority value per request, so each level is a
separate request). An empty `locationRestrictions` means open worldwide.
Terms: every posting keeps its Himalayas page as URL; personal use only.
"""

from __future__ import annotations

import time
from typing import Any

from jobhunter.http import HttpClient
from jobhunter.models import Job
from jobhunter.sources.base import collect, from_epoch
from jobhunter.sources.registry import SourceInfo, register
from jobhunter.text import annualize, html_to_text

URL = "https://himalayas.app/jobs/api/search"


def _parse_one(raw: dict[str, Any]) -> Job | None:
    expiry = raw.get("expiryDate")
    if expiry and expiry < time.time():
        return None  # already expired
    places = [p for p in raw.get("locationRestrictions") or [] if p]
    low, high = raw.get("minSalary"), raw.get("maxSalary")
    currency = raw.get("currency")
    interval = raw.get("salaryPeriod")
    pay = (
        {
            "salary_min": annualize(low or high, interval),
            "salary_max": annualize(high or low, interval),
            "salary_currency": currency,
        }
        if (low or high) and currency  # a salary without a currency cannot be compared
        else {}
    )
    link = raw.get("applicationLink") or raw["guid"]
    return Job(
        source="himalayas",
        external_id=str(raw["guid"]),
        company=raw["companyName"],
        title=raw["title"],
        location="; ".join(places) if places else "Worldwide",
        remote="remote",  # Himalayas lists remote roles only
        description=html_to_text(raw.get("description") or raw.get("excerpt")),
        url=link,
        posted_at=from_epoch(raw.get("pubDate")),
        **pay,
    )


def parse(data: dict[str, Any]) -> list[Job]:
    return collect(data.get("jobs", []), _parse_one)


class HimalayasSource:
    name = "himalayas"

    def __init__(self, query: str, seniority: list[str], max_pages: int = 5) -> None:
        self.target = query
        self.seniority = seniority or [""]
        self.max_pages = max_pages
        self.note: str | None = None

    async def fetch(self, http: HttpClient) -> list[Job]:
        self.note = None
        jobs: dict[str, Job] = {}
        for level in self.seniority:
            for page in range(1, self.max_pages + 1):
                params: dict[str, Any] = {"q": self.target, "sort": "recent", "page": page}
                if level:
                    params["seniority"] = level
                data = await http.get_json(URL, params)
                batch = parse(data)
                for job in batch:
                    jobs.setdefault(job.external_id, job)
                if not data.get("jobs"):
                    break  # past the last page
        return list(jobs.values())


register(
    SourceInfo(
        name="himalayas",
        kind="aggregator",
        description="Himalayas: remote jobs worldwide, searched by your queries and seniority",
        terms_url="https://himalayas.app/api",
        fixtures=("himalayas.json",),
        build=lambda cfg: [
            HimalayasSource(q, cfg.himalayas.seniority, cfg.himalayas.max_pages)
            for q in cfg.himalayas.queries
        ],
    )
)
