"""Postings added by hand: validation, ids and storage (see specs/10-manual-postings.md)."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from jobhunter.models import Job
from jobhunter.store import upsert_jobs

MANUAL_SOURCE = "manual"
MAX_TITLE = 200
MAX_COMPANY = 200
MAX_URL = 2000
MAX_LOCATION = 200
MAX_DESCRIPTION = 100 * 1024
REMOTE_MODES = ("remote", "hybrid", "onsite", "unknown")
_TRACKING_PARAMS = {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid", "ref", "ref_src", "source"}


class PostingError(ValueError):
    """The submitted posting is not valid (message is shown to the person)."""


def normalize_url(url: str) -> str:
    """Canonical form used to recognize the same posting: no fragment, tracking or default port."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    netloc = host
    default = {"http": 80, "https": 443}.get(parts.scheme.lower())
    if parts.port and parts.port != default:
        netloc = f"{host}:{parts.port}"
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query), ""))


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def manual_external_id(url: str | None, title: str, company: str, description: str) -> str:
    """Stable id: the normalized URL when there is one, else a hash of the content."""
    basis = (
        normalize_url(url) if url else f"{_squash(title)}|{_squash(company)}|{_squash(description)}"
    )
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def _text(data: dict[str, Any], key: str, limit: int, *, required: bool = False) -> str | None:
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise PostingError(f"{key} is required")
        return None
    if not isinstance(value, str):
        raise PostingError(f"{key} must be text")
    value = value.strip()
    if len(value.encode()) > limit:
        unit, size = ("KB", limit // 1024) if limit >= 1024 else ("characters", limit)
        raise PostingError(f"{key} is too long (limit {size} {unit})")
    return value


def _amount(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise PostingError(f"{key} must be a number")
    try:
        amount = int(float(value))
    except ValueError as exc:
        raise PostingError(f"{key} must be a number") from exc
    if amount < 0:
        raise PostingError(f"{key} cannot be negative")
    return amount


def validate_manual(data: dict[str, Any]) -> Job:
    """Turn submitted fields into a Job (source ``manual``) or raise PostingError."""
    title = _text(data, "title", MAX_TITLE, required=True)
    company = _text(data, "company", MAX_COMPANY, required=True)
    description = _text(data, "description", MAX_DESCRIPTION, required=True)
    location = _text(data, "location", MAX_LOCATION)
    url = _text(data, "url", MAX_URL)
    if url and urlsplit(url).scheme.lower() not in ("http", "https"):
        raise PostingError("the link must start with http:// or https://")
    remote = data.get("remote") or "unknown"
    if remote not in REMOTE_MODES:
        raise PostingError(f"work mode must be one of: {', '.join(REMOTE_MODES)}")
    low, high = _amount(data, "salary_min"), _amount(data, "salary_max")
    if low is not None and high is not None and low > high:
        raise PostingError("the minimum salary is above the maximum")
    currency = None
    if low is not None or high is not None:
        currency = str(data.get("salary_currency") or "USD").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            raise PostingError("currency must be a 3-letter code such as USD")
    assert title and company and description
    return Job(
        source=MANUAL_SOURCE,
        external_id=manual_external_id(url, title, company, description),
        company=company,
        title=title,
        location=location,
        remote=remote,
        description=description,
        url=url or "",
        salary_min=low if low is not None else high,
        salary_max=high if high is not None else low,
        salary_currency=currency,
    )


def add_manual(conn: sqlite3.Connection, data: dict[str, Any]) -> tuple[int, bool]:
    """Store a posting added by hand. Returns (id, created).

    It skips the hard filter on purpose (the person chose it): it starts as ``passed`` with the
    flag ``manual``, and editing its text later never sends it back through the filter.
    """
    job = validate_manual(data)
    result = upsert_jobs(conn, [job])
    row = conn.execute(
        "SELECT id, status FROM jobs WHERE source = ? AND external_id = ?",
        (job.source, job.external_id),
    ).fetchone()
    now = datetime.now(UTC).isoformat()
    with conn:
        if row["status"] in ("new", "filtered", "closed"):
            conn.execute("UPDATE jobs SET status = 'passed' WHERE id = ?", (row["id"],))
            conn.execute(
                "INSERT INTO events(job_id, from_status, to_status, note, created_at) "
                "VALUES (?,?,?,?,?)",
                (row["id"], row["status"], "passed", "added by hand", now),
            )
        conn.execute(
            "UPDATE jobs SET filter_flags = 'manual', filter_reason = NULL WHERE id = ?",
            (row["id"],),
        )
    return int(row["id"]), result.new == 1
