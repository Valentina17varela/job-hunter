"""Ashby job boards: api.ashbyhq.com/posting-api/job-board/{slug}."""

from __future__ import annotations

from typing import Any

from jobhunter.http import HttpClient
from jobhunter.models import Job, RemoteMode
from jobhunter.sources.base import collect, parse_iso
from jobhunter.text import annualize, extract_salary, infer_remote, normalize_text

URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
_WORKPLACE: dict[str, RemoteMode] = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}


def _salary(raw: dict[str, Any]) -> tuple[int, int, str] | None:
    for tier in (raw.get("compensation") or {}).get("compensationTiers") or []:
        for comp in tier.get("components") or []:
            if (
                comp.get("compensationType") == "Salary"
                and comp.get("minValue")
                and comp.get("maxValue")
                and comp.get("currencyCode")
            ):
                interval = comp.get("interval")
                return (
                    annualize(comp["minValue"], interval),
                    annualize(comp["maxValue"], interval),
                    comp["currencyCode"],
                )
    return None


def _parse_one(raw: Any, company: str) -> Job | None:
    if raw.get("isListed") is False:
        return None
    location = raw.get("location")
    workplace = (raw.get("workplaceType") or "").lower()
    remote = _WORKPLACE.get(workplace)
    if remote is None:
        remote = "remote" if raw.get("isRemote") else infer_remote(location, raw["title"])
    description = normalize_text(raw.get("descriptionPlain"))
    salary = _salary(raw) or extract_salary(description)
    return Job(
        source="ashby",
        external_id=raw["id"],
        company=company,
        title=raw["title"],
        location=location,
        remote=remote,
        description=description,
        url=raw["jobUrl"],
        salary_min=salary[0] if salary else None,
        salary_max=salary[1] if salary else None,
        salary_currency=salary[2] if salary else None,
        posted_at=parse_iso(raw.get("publishedAt")),
    )


def parse(data: dict[str, Any], company: str) -> list[Job]:
    return collect(data.get("jobs", []), lambda raw: _parse_one(raw, company))


class AshbySource:
    name = "ashby"

    def __init__(self, company: str, slug: str) -> None:
        self.company = company
        self.target = slug

    async def fetch(self, http: HttpClient) -> list[Job]:
        data = await http.get_json(
            URL.format(slug=self.target), params={"includeCompensation": "true"}
        )
        return parse(data, self.company)
