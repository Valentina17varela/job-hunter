"""Greenhouse job boards: boards-api.greenhouse.io/v1/boards/{slug}/jobs."""

from __future__ import annotations

import html
from typing import Any

from jobhunter.http import HttpClient
from jobhunter.models import Job
from jobhunter.sources.base import collect, parse_iso
from jobhunter.sources.registry import SourceInfo, register
from jobhunter.text import extract_salary, html_to_text, infer_remote

URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def _parse_one(raw: Any, company: str) -> Job | None:
    location = (raw.get("location") or {}).get("name")
    # Greenhouse returns the description HTML-escaped.
    description = html_to_text(html.unescape(raw.get("content") or ""))
    salary = extract_salary(description)
    return Job(
        source="greenhouse",
        external_id=str(raw["id"]),
        company=raw.get("company_name") or company,
        title=raw["title"],
        location=location,
        remote=infer_remote(location, raw["title"]),
        description=description,
        url=raw["absolute_url"],
        salary_min=salary[0] if salary else None,
        salary_max=salary[1] if salary else None,
        salary_currency=salary[2] if salary else None,
        posted_at=parse_iso(raw.get("first_published") or raw.get("updated_at")),
    )


def parse(data: dict[str, Any], company: str) -> list[Job]:
    return collect(data.get("jobs", []), lambda raw: _parse_one(raw, company))


class GreenhouseSource:
    name = "greenhouse"

    def __init__(self, company: str, slug: str) -> None:
        self.company = company
        self.target = slug

    async def fetch(self, http: HttpClient) -> list[Job]:
        data = await http.get_json(URL.format(slug=self.target), params={"content": "true"})
        return parse(data, self.company)


register(
    SourceInfo(
        name="greenhouse",
        kind="ats",
        description="Company job boards on Greenhouse (boards API)",
        terms_url="https://developers.greenhouse.io/job-board.html",
        fixtures=("greenhouse.json",),
        factory=GreenhouseSource,
        probe_url="https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    )
)
