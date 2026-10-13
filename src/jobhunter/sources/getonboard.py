"""Get on Board: https://www.getonbrd.com/api/v0/categories/<category>/jobs (public JSON:API).

LATAM-heavy tech roles, often with a published salary. Salaries are monthly USD, annualized here.
Terms: every posting keeps its Get on Board page (`links.public_url`) as URL; personal use only.
"""

from __future__ import annotations

from typing import Any

from jobhunter.http import HttpClient
from jobhunter.models import Job, RemoteMode
from jobhunter.sources.base import collect, from_epoch
from jobhunter.sources.registry import SourceInfo, register
from jobhunter.text import annualize, html_to_text

URL = "https://www.getonbrd.com/api/v0/categories/{category}/jobs"
PER_PAGE = 100
_MODE: dict[str, RemoteMode] = {
    "fully_remote": "remote",
    "remote_local": "remote",
    "hybrid": "hybrid",
    "no_remote": "onsite",
}


def _location(attrs: dict[str, Any]) -> str | None:
    countries = [c for c in attrs.get("countries") or [] if c]
    if attrs.get("remote_modality") == "remote_local":
        named = [c for c in countries if c.lower() != "remote"]
        return "Remote, " + ", ".join(named) if named else "Remote (specific countries)"
    return ", ".join(countries) or None


def _description(attrs: dict[str, Any]) -> str:
    parts = []
    for body, headline in (
        ("description", "description_headline"),
        ("functions", "functions_headline"),
        ("desirable", "desirable_headline"),
        ("benefits", "benefits_headline"),
    ):
        text = html_to_text(attrs.get(body))
        if text:
            parts.append(f"{attrs.get(headline) or ''}\n{text}".strip())
    return "\n\n".join(parts)


def _parse_one(raw: dict[str, Any]) -> Job | None:
    attrs = raw["attributes"]
    company = attrs["company"]["data"]["attributes"]["name"]
    low, high = attrs.get("min_salary"), attrs.get("max_salary")
    pay = (
        {
            "salary_min": annualize(low or high, "month"),
            "salary_max": annualize(high or low, "month"),
            "salary_currency": "USD",
        }
        if low or high
        else {}
    )
    return Job(
        source="getonboard",
        external_id=str(raw["id"]),
        company=company,
        title=attrs["title"],
        location=_location(attrs),
        remote=_MODE.get(attrs.get("remote_modality") or "", "unknown"),
        description=_description(attrs),
        url=raw["links"]["public_url"],
        posted_at=from_epoch(attrs.get("published_at")),
        **pay,
    )


def parse(data: dict[str, Any]) -> list[Job]:
    return collect(data.get("data", []), _parse_one)


class GetOnBoardSource:
    name = "getonboard"

    def __init__(self, category: str, max_pages: int = 10) -> None:
        self.target = category
        self.max_pages = max_pages
        self.note: str | None = None

    async def fetch(self, http: HttpClient) -> list[Job]:
        self.note = None
        jobs: list[Job] = []
        page, total = 1, 1
        while page <= min(total, self.max_pages):
            data = await http.get_json(
                URL.format(category=self.target),
                {"per_page": PER_PAGE, "page": page, "expand": '["company"]'},
            )
            jobs.extend(parse(data))
            total = int((data.get("meta") or {}).get("total_pages") or 1)
            page += 1
        if total > self.max_pages:
            self.note = f"stopped at max_pages={self.max_pages} of {total} pages"
        return jobs


register(
    SourceInfo(
        name="getonboard",
        kind="aggregator",
        description="Get on Board: tech jobs, LATAM-heavy, monthly USD salaries",
        terms_url="https://www.getonbrd.com/api/docs",
        fixtures=("getonboard.json",),
        build=lambda cfg: [
            GetOnBoardSource(c, cfg.getonboard.max_pages) for c in cfg.getonboard.categories
        ],
    )
)
