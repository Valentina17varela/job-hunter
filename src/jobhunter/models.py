"""Common data models shared across the pipeline (see specs/02-data-model.md)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, computed_field

RemoteMode = Literal["remote", "hybrid", "onsite", "unknown"]

# Company job boards: a posting still listed there is open, however old its publish date.
ATS_SOURCES = frozenset({"greenhouse", "lever", "ashby"})


class JobStatus(StrEnum):
    NEW = "new"
    FILTERED = "filtered"
    PASSED = "passed"
    SCORED = "scored"
    SCORE_FAILED = "score_failed"
    BELOW_THRESHOLD = "below_threshold"
    SELECTED = "selected"
    PACKAGED = "packaged"
    APPLIED = "applied"
    REPLIED = "replied"
    REJECTED = "rejected"
    CLOSED = "closed"
    DUPLICATE = "duplicate"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Job(BaseModel):
    """A job posting normalized from any source."""

    source: str
    external_id: str
    company: str
    title: str
    location: str | None = None
    remote: RemoteMode = "unknown"
    description: str = ""
    url: str
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    posted_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=_utcnow)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_hash(self) -> str:
        """sha256 of title + description; changes when the posting content changes."""
        payload = f"{self.title}\n{self.description}".encode()
        return hashlib.sha256(payload).hexdigest()
