"""Persistence rules for postings: upsert/dedupe, closing stale ones (specs/02-data-model.md)."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jobhunter.models import ATS_SOURCES, Job, JobStatus

# Statuses set by a human decision; fetching never overrides them.
HUMAN_STATUSES = {
    JobStatus.APPLIED.value,
    JobStatus.REPLIED.value,
    JobStatus.REJECTED.value,
    JobStatus.IGNORED.value,
}
TERMINAL = HUMAN_STATUSES | {JobStatus.CLOSED.value}
# Direct ATS postings win over aggregator copies of the same job.
SOURCE_PRIORITY = dict.fromkeys(ATS_SOURCES, 0)


@dataclass
class UpsertResult:
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    reopened: int = 0


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _event(conn: sqlite3.Connection, job_id: int, old: str | None, new: str, note: str) -> None:
    conn.execute(
        "INSERT INTO events(job_id, from_status, to_status, note, created_at) VALUES (?,?,?,?,?)",
        (job_id, old, new, note, _now()),
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def upsert_jobs(
    conn: sqlite3.Connection, jobs: list[Job], now: datetime | None = None
) -> UpsertResult:
    """Insert new postings and refresh known ones, keyed by (source, external_id)."""
    seen = (now or datetime.now(UTC)).isoformat()
    result = UpsertResult()
    with conn:
        for job in jobs:
            row = conn.execute(
                "SELECT id, content_hash, status, filter_reason, filter_flags FROM jobs "
                "WHERE source = ? AND external_id = ?",
                (job.source, job.external_id),
            ).fetchone()
            fields = (
                job.company, job.title, job.location, job.remote, job.description, job.url,
                job.salary_min, job.salary_max, job.salary_currency, _iso(job.posted_at),
            )  # fmt: skip
            if row is None:
                cursor = conn.execute(
                    """INSERT INTO jobs(company, title, location, remote, description, url,
                           salary_min, salary_max, salary_currency, posted_at,
                           source, external_id, fetched_at, last_seen_at, content_hash, status)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (*fields, job.source, job.external_id, _iso(job.fetched_at), seen,
                     job.content_hash, JobStatus.NEW.value),
                )  # fmt: skip
                _event(conn, cursor.lastrowid, None, JobStatus.NEW.value, "fetched")
                result.new += 1
                continue

            job_id, old_hash, status = row["id"], row["content_hash"], row["status"]
            if old_hash == job.content_hash and status != JobStatus.CLOSED.value:
                conn.execute("UPDATE jobs SET last_seen_at = ? WHERE id = ?", (seen, job_id))
                result.unchanged += 1
                continue

            new_status = status
            if status == JobStatus.CLOSED.value:
                new_status, note = JobStatus.NEW.value, "reappeared"
                result.reopened += 1
            elif status not in HUMAN_STATUSES:
                # Content changed: the old filter result/score no longer applies.
                new_status, note = JobStatus.NEW.value, "content changed"
            else:
                note = "content changed (status kept)"
            conn.execute(
                """UPDATE jobs SET company=?, title=?, location=?, remote=?, description=?, url=?,
                       salary_min=?, salary_max=?, salary_currency=?, posted_at=?,
                       content_hash=?, last_seen_at=?, status=?, filter_reason=?, filter_flags=?
                   WHERE id=?""",
                (*fields, job.content_hash, seen, new_status,
                 None if new_status != status else row["filter_reason"],
                 None if new_status != status else row["filter_flags"], job_id),
            )  # fmt: skip
            if new_status != status:
                _event(conn, job_id, status, new_status, note)
            result.updated += 1
    return result


def close_stale(
    conn: sqlite3.Connection,
    sources_ok: set[str],
    stale_days: int = 7,
    now: datetime | None = None,
) -> int:
    """Close postings not seen for `stale_days`, only for sources fetched successfully."""
    if not sources_ok:
        return 0
    cutoff = ((now or datetime.now(UTC)) - timedelta(days=stale_days)).isoformat()
    marks = ",".join("?" for _ in sources_ok)
    skip = ",".join("?" for _ in TERMINAL)
    rows = conn.execute(
        f"SELECT id, status FROM jobs WHERE last_seen_at < ? AND source IN ({marks}) "
        f"AND status NOT IN ({skip})",
        (cutoff, *sources_ok, *TERMINAL),
    ).fetchall()
    with conn:
        for row in rows:
            conn.execute("UPDATE jobs SET status = 'closed' WHERE id = ?", (row["id"],))
            _event(conn, row["id"], row["status"], "closed", "not seen recently")
    return len(rows)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def mark_duplicates(conn: sqlite3.Connection) -> int:
    """Mark cross-source copies (same company + title) as duplicates, keeping the ATS one."""
    skip = ",".join("?" for _ in TERMINAL | {JobStatus.DUPLICATE.value})
    rows = conn.execute(
        f"SELECT id, source, company, title, status FROM jobs WHERE status NOT IN ({skip})",
        tuple(TERMINAL | {JobStatus.DUPLICATE.value}),
    ).fetchall()
    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        groups.setdefault((_norm(row["company"]), _norm(row["title"])), []).append(row)
    marked = 0
    with conn:
        for group in groups.values():
            if len({r["source"] for r in group}) < 2:
                continue
            group.sort(key=lambda r: (SOURCE_PRIORITY.get(r["source"], 1), r["id"]))
            keeper_source = group[0]["source"]
            for row in group[1:]:
                if row["source"] == keeper_source:
                    continue
                conn.execute("UPDATE jobs SET status = 'duplicate' WHERE id = ?", (row["id"],))
                _event(conn, row["id"], row["status"], "duplicate", f"copy of {keeper_source}")
                marked += 1
    return marked


def log_fetch(
    conn: sqlite3.Connection,
    source: str,
    target: str,
    status: str,
    jobs_found: int,
    error: str | None = None,
) -> None:
    with conn:
        conn.execute(
            "INSERT INTO fetch_log(source, target, status, jobs_found, error, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (source, target, status, jobs_found, error, _now()),
        )
