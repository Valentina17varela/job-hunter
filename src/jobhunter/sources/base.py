"""Source interface and parsing helpers (see specs/03-sources.md)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any, Protocol

from jobhunter.http import HttpClient
from jobhunter.models import Job


class Source(Protocol):
    """A place jobs are fetched from. One instance per fetchable target.

    `name` is the source kind (e.g. "greenhouse"); `target` identifies the instance
    (e.g. a company slug) and is empty for single-feed sources. `fetch` raises
    FetchError on failure; the pipeline records it and moves on.
    """

    name: str
    target: str

    async def fetch(self, http: HttpClient) -> list[Job]: ...


def parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp; naive values are treated as UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def from_epoch(value: float | int | None, *, millis: bool = False) -> datetime | None:
    """Convert a unix timestamp (seconds, or milliseconds when `millis`) to UTC datetime."""
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000 if millis else value, tz=UTC)


def collect(items: Iterable[Any], parse_one: Callable[[Any], Job | None]) -> list[Job]:
    """Parse each raw item, skipping ones that are malformed or intentionally dropped.

    A single bad posting must never discard the rest of a feed.
    """
    jobs: list[Job] = []
    for raw in items:
        try:
            job = parse_one(raw)
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        if job is not None:
            jobs.append(job)
    return jobs
