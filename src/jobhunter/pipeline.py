"""Pipeline orchestration: the fetch and filter stages."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from jobhunter.filters import JobFilter, job_from_row
from jobhunter.http import HttpClient
from jobhunter.models import Job
from jobhunter.sources.base import Source
from jobhunter.store import UpsertResult, close_stale, log_fetch, mark_duplicates, upsert_jobs

log = logging.getLogger(__name__)


@dataclass
class FetchSummary:
    sources_ok: int = 0
    sources_failed: int = 0
    jobs_found: int = 0
    upsert: UpsertResult = field(default_factory=UpsertResult)
    closed: int = 0
    duplicates: int = 0
    failures: list[str] = field(default_factory=list)


async def _fetch_one(source: Source, http: HttpClient) -> tuple[Source, list[Job] | None, str]:
    try:
        return source, await source.fetch(http), ""
    except Exception as exc:  # noqa: BLE001 - one failing source must never stop the others
        return source, None, f"{type(exc).__name__}: {exc}"


async def fetch_stage(
    conn: sqlite3.Connection,
    sources: list[Source],
    http: HttpClient,
    stale_days: int = 7,
) -> FetchSummary:
    """Fetch every source concurrently, store new/changed postings and tidy up."""
    summary = FetchSummary()
    results = await asyncio.gather(*(_fetch_one(s, http) for s in sources))

    ok_by_kind: defaultdict[str, int] = defaultdict(int)
    seen_keys: set[tuple[str, str]] = set()  # the same posting can appear in several feeds/pages
    for source, jobs, error in results:
        if jobs is None:
            summary.sources_failed += 1
            summary.failures.append(f"{source.name}/{source.target or '-'}: {error}")
            log_fetch(conn, source.name, source.target, "error", 0, error)
            log.warning("fetch failed for %s/%s: %s", source.name, source.target, error)
            continue
        summary.sources_ok += 1
        summary.jobs_found += len(jobs)
        ok_by_kind[source.name] += 1
        log_fetch(conn, source.name, source.target, "ok", len(jobs))
        fresh = []
        for job in jobs:
            key = (job.source, job.external_id)
            if key not in seen_keys:
                seen_keys.add(key)
                fresh.append(job)
        res = upsert_jobs(conn, fresh)
        summary.upsert.new += res.new
        summary.upsert.updated += res.updated
        summary.upsert.unchanged += res.unchanged
        summary.upsert.reopened += res.reopened

    summary.closed = close_stale(conn, set(ok_by_kind), stale_days)
    summary.duplicates = mark_duplicates(conn)
    return summary


# Statuses whose filter verdict can change when criteria change. Later stages keep their
# status when a posting still passes, so a package is never discarded by a re-filter.
REFILTER_STATUSES = (
    "new",
    "filtered",
    "passed",
    "score_failed",
    "below_threshold",
    "scored",
    "selected",
)


@dataclass
class FilterSummary:
    evaluated: int = 0
    passed: int = 0
    filtered: int = 0
    changed: int = 0
    reasons: Counter[str] = field(default_factory=Counter)  # rejections grouped by rule
    flags: Counter[str] = field(default_factory=Counter)


def filter_stage(
    conn: sqlite3.Connection,
    job_filter: JobFilter,
    statuses: tuple[str, ...] = ("new",),
    now: datetime | None = None,
) -> FilterSummary:
    """Evaluate postings with the hard filter and record the verdict (0 tokens)."""
    now = now or datetime.now(UTC)
    marks = ",".join("?" for _ in statuses)
    summary = FilterSummary()
    updates: list[tuple[str | None, str | None, str, int]] = []
    events: list[tuple[int, str, str, str]] = []
    for row in conn.execute(f"SELECT * FROM jobs WHERE status IN ({marks})", statuses):
        result = job_filter.evaluate(job_from_row(row), now)
        summary.evaluated += 1
        summary.flags.update(result.flags)
        current = row["status"]
        if result.passed:
            summary.passed += 1
            new_status = "passed" if current in ("new", "filtered") else current
        else:
            summary.filtered += 1
            summary.reasons[(result.reason or "").split(":")[0]] += 1
            new_status = "filtered"
        flags = ",".join(result.flags) or None
        updates.append((result.reason, flags, new_status, row["id"]))
        if new_status != current:
            summary.changed += 1
            events.append((row["id"], current, new_status, result.reason or "passed filter"))
    stamp = now.isoformat()
    with conn:
        conn.executemany(
            "UPDATE jobs SET filter_reason = ?, filter_flags = ?, status = ? WHERE id = ?", updates
        )
        conn.executemany(
            "INSERT INTO events(job_id, from_status, to_status, note, created_at) "
            "VALUES (?,?,?,?,?)",
            [(jid, old, new, note, stamp) for jid, old, new, note in events],
        )
    return summary
