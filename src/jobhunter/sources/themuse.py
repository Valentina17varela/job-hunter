"""The Muse: https://www.themuse.com/api/public/jobs (public, works without a key).

Terms: the API asks for attribution; every posting keeps The Muse's landing page as its URL and
the tool is for personal use. An optional free key (THEMUSE_API_KEY) raises the rate limit.
"""

from __future__ import annotations

import os
from typing import Any

from jobhunter.http import HttpClient
from jobhunter.models import Job
from jobhunter.sources.base import collect, parse_iso
from jobhunter.sources.registry import SourceInfo, register
from jobhunter.text import extract_salary, html_to_text, infer_remote

URL = "https://www.themuse.com/api/public/jobs"
REMOTE_LOCATION = "flexible / remote"
LOW_RATE_LIMIT = 20  # stop early below this many requests left in the hour


def _parse_one(raw: dict[str, Any]) -> Job | None:
    places = [loc["name"] for loc in raw.get("locations") or [] if loc.get("name")]
    title = raw["name"]
    description = html_to_text(raw.get("contents"))
    remote = (
        "remote"
        if any(p.lower() == REMOTE_LOCATION for p in places)
        else infer_remote("; ".join(places), title)
    )
    salary = extract_salary(description)
    extra = (
        {"salary_min": salary[0], "salary_max": salary[1], "salary_currency": salary[2]}
        if salary
        else {}
    )
    return Job(
        source="themuse",
        external_id=str(raw["id"]),
        company=raw["company"]["name"],
        title=title,
        location="; ".join(places) or None,
        remote=remote,
        description=description,
        url=raw["refs"]["landing_page"],
        posted_at=parse_iso(raw.get("publication_date")),
        **extra,
    )


def parse(data: dict[str, Any]) -> list[Job]:
    return collect(data.get("results", []), _parse_one)


class TheMuseSource:
    name = "themuse"

    def __init__(
        self, category: str, levels: list[str], locations: list[str], max_pages: int = 60
    ) -> None:
        self.target = category
        self.levels = levels
        self.locations = locations
        self.max_pages = max_pages
        self.note: str | None = None  # set when the fetch stopped early; logged in fetch_log

    async def fetch(self, http: HttpClient) -> list[Job]:
        self.note = None
        jobs: list[Job] = []
        page, page_count = 1, 1
        while page <= min(page_count, self.max_pages):
            params: dict[str, Any] = {"page": page, "category": self.target}
            if self.levels:
                params["level"] = self.levels
            if self.locations:
                params["location"] = self.locations
            key = os.environ.get("THEMUSE_API_KEY")
            if key:
                params["api_key"] = key
            response = await http.get(URL, params)
            data = response.json()
            jobs.extend(parse(data))
            page_count = int(data.get("page_count") or 1)
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining is not None and int(remaining) < LOW_RATE_LIMIT and page < page_count:
                self.note = (
                    f"stopped after page {page} of {page_count}: only {remaining} requests "
                    "left this hour (the next run continues)"
                )
                break
            page += 1
        if page > self.max_pages and page_count > self.max_pages:
            self.note = f"stopped at max_pages={self.max_pages} of {page_count} pages"
        return jobs


register(
    SourceInfo(
        name="themuse",
        kind="aggregator",
        description="Jobs from The Muse, filtered by category, level and remote (optional key)",
        terms_url="https://www.themuse.com/developers/api/v2",
        fixtures=("themuse.json",),
        build=lambda cfg: [
            TheMuseSource(c, cfg.themuse.levels, cfg.themuse.locations, cfg.themuse.max_pages)
            for c in cfg.themuse.categories
        ],
        env_keys=("THEMUSE_API_KEY",),
        key_optional=True,
    )
)
