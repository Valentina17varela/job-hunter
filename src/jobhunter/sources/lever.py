"""Lever postings: api.lever.co/v0/postings/{slug}."""

from __future__ import annotations

from typing import Any

from jobhunter.http import HttpClient
from jobhunter.models import Job, RemoteMode
from jobhunter.sources.base import collect, from_epoch
from jobhunter.text import annualize, extract_salary, infer_remote, normalize_text

URL = "https://api.lever.co/v0/postings/{slug}"
_WORKPLACE: dict[str, RemoteMode] = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}


def _description(raw: dict[str, Any]) -> str:
    parts = [raw.get("descriptionPlain") or ""]
    for section in raw.get("lists") or []:
        parts.append(section.get("text") or "")
    parts.append(raw.get("additionalPlain") or "")
    return normalize_text("\n\n".join(p.strip() for p in parts if p and p.strip()))


def _parse_one(raw: Any, company: str) -> Job | None:
    categories = raw.get("categories") or {}
    location = categories.get("location")
    remote = _WORKPLACE.get(raw.get("workplaceType") or "") or infer_remote(location, raw["text"])
    description = _description(raw)
    pay = raw.get("salaryRange")
    if pay and pay.get("min") and pay.get("max"):
        salary = (
            annualize(pay["min"], pay.get("interval")),
            annualize(pay["max"], pay.get("interval")),
            pay.get("currency"),
        )
    else:
        salary = extract_salary(description)
    return Job(
        source="lever",
        external_id=raw["id"],
        company=company,
        title=raw["text"],
        location=location,
        remote=remote,
        description=description,
        url=raw["hostedUrl"],
        salary_min=salary[0] if salary else None,
        salary_max=salary[1] if salary else None,
        salary_currency=salary[2] if salary else None,
        posted_at=from_epoch(raw.get("createdAt"), millis=True),
    )


def parse(data: list[dict[str, Any]], company: str) -> list[Job]:
    return collect(data, lambda raw: _parse_one(raw, company))


class LeverSource:
    name = "lever"

    def __init__(self, company: str, slug: str) -> None:
        self.company = company
        self.target = slug

    async def fetch(self, http: HttpClient) -> list[Job]:
        data = await http.get_json(URL.format(slug=self.target), params={"mode": "json"})
        return parse(data, self.company)
