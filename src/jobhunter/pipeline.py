"""Pipeline orchestration. Phase 1 implements the fetch stage only."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

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
