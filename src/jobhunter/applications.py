"""Application tracking: stages, interviews and the funnel stats (specs/02, specs/09)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

STAGES = (
    "applied", "screening", "interviewing", "offer", "accepted", "rejected", "withdrawn", "ghosted",
)  # fmt: skip
ACTIVE_STAGES = ("applied", "screening", "interviewing", "offer")
STATUS_FOR_STAGE = {
    "applied": "applied",
    "screening": "replied",
    "interviewing": "replied",
    "offer": "replied",
    "accepted": "replied",
    "rejected": "rejected",
    "withdrawn": "rejected",
    "ghosted": "rejected",
}
INTERVIEW_KINDS = (
    "recruiter", "technical", "system_design", "hiring_manager", "onsite", "other",
)  # fmt: skip
INTERVIEW_OUTCOMES = ("pending", "passed", "failed")


class TrackingError(ValueError):
    """Invalid stage/kind/outcome or unknown posting."""


def _now(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).isoformat()


def _job(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT id, status FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise TrackingError(f"no posting with id {job_id}")
    return row


def _event(
    conn: sqlite3.Connection, job_id: int, old: str | None, new: str, note: str, at: str
) -> None:
    conn.execute(
        "INSERT INTO events(job_id, from_status, to_status, note, created_at) VALUES (?,?,?,?,?)",
        (job_id, old, new, note, at),
    )


def set_stage(
    conn: sqlite3.Connection, job_id: int, stage: str, note: str | None = None,
    now: datetime | None = None,
) -> None:  # fmt: skip
    """Record that the person's application is now at `stage` (creating it if needed)."""
    if stage not in STAGES:
        raise TrackingError(f"unknown stage '{stage}'. Use one of: {', '.join(STAGES)}")
    job = _job(conn, job_id)
    at = _now(now)
    new_status = STATUS_FOR_STAGE[stage]
    with conn:
        existing = conn.execute(
            "SELECT stage, notes FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO applications(job_id, stage, applied_at, updated_at, notes) "
                "VALUES (?,?,?,?,?)",
                (job_id, stage, at, at, note),
            )
        else:
            merged = existing["notes"] or ""
            if note:
                merged = f"{merged}\n{note}".strip()
            conn.execute(
                "UPDATE applications SET stage = ?, updated_at = ?, notes = ? WHERE job_id = ?",
                (stage, at, merged or None, job_id),
            )
        if job["status"] != new_status:
            conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
        _event(
            conn,
            job_id,
            job["status"],
            new_status,
            f"stage: {stage}" + (f" — {note}" if note else ""),
            at,
        )


def set_notes(conn: sqlite3.Connection, job_id: int, notes: str) -> None:
    _job(conn, job_id)
    with conn:
        updated = conn.execute(
            "UPDATE applications SET notes = ?, updated_at = ? WHERE job_id = ?",
            (notes or None, _now(), job_id),
        ).rowcount
    if not updated:
        raise TrackingError(f"posting {job_id} has no application yet; mark it applied first")


def ignore(conn: sqlite3.Connection, job_id: int, note: str | None = None) -> None:
    """Hide a posting you are not interested in; fetching never brings it back."""
    job = _job(conn, job_id)
    if conn.execute("SELECT 1 FROM applications WHERE job_id = ?", (job_id,)).fetchone():
        raise TrackingError("this posting has an application; set a stage (e.g. withdrawn) instead")
    with conn:
        conn.execute("UPDATE jobs SET status = 'ignored' WHERE id = ?", (job_id,))
        _event(conn, job_id, job["status"], "ignored", note or "ignored by the person", _now())


def add_interview(
    conn: sqlite3.Connection, job_id: int, kind: str, scheduled_at: str | None = None,
    notes: str | None = None,
) -> int:  # fmt: skip
    if kind not in INTERVIEW_KINDS:
        raise TrackingError(f"unknown interview kind '{kind}'")
    _job(conn, job_id)
    with conn:
        cursor = conn.execute(
            "INSERT INTO interviews(job_id, kind, scheduled_at, notes) VALUES (?,?,?,?)",
            (job_id, kind, scheduled_at or None, notes or None),
        )
    return int(cursor.lastrowid)


def update_interview(conn: sqlite3.Connection, interview_id: int, **fields: Any) -> None:
    allowed = {"kind", "scheduled_at", "notes", "outcome"}
    unknown = set(fields) - allowed
    if unknown:
        raise TrackingError(f"cannot update {', '.join(sorted(unknown))}")
    if "kind" in fields and fields["kind"] not in INTERVIEW_KINDS:
        raise TrackingError(f"unknown interview kind '{fields['kind']}'")
    if "outcome" in fields and fields["outcome"] not in INTERVIEW_OUTCOMES:
        raise TrackingError(f"unknown outcome '{fields['outcome']}'")
    for key in ("scheduled_at", "notes"):
        if key in fields:
            value = fields[key]
            if value is not None and not isinstance(value, str):
                raise TrackingError(f"{key} must be text")
            fields[key] = value or None  # empty string means "not set"
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    with conn:
        updated = conn.execute(
            f"UPDATE interviews SET {sets} WHERE id = ?", (*fields.values(), interview_id)
        ).rowcount
    if not updated:
        raise TrackingError(f"no interview with id {interview_id}")


def delete_interview(conn: sqlite3.Connection, interview_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))


def list_interviews(conn: sqlite3.Connection, job_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM interviews WHERE job_id = ? ORDER BY COALESCE(scheduled_at, '9999'), id",
        (job_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_applications(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every application with its posting, latest score and upcoming interview."""
    rows = conn.execute(
        "SELECT a.job_id, a.stage, a.applied_at, a.updated_at, a.notes, j.company, j.title, "
        "j.url, j.location, (SELECT score FROM scores WHERE job_id = j.id "
        "ORDER BY created_at DESC LIMIT 1) AS score, "
        "(SELECT path FROM packages WHERE job_id = j.id ORDER BY created_at DESC LIMIT 1) "
        "AS package FROM applications a JOIN jobs j ON j.id = a.job_id ORDER BY a.updated_at DESC"
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["interviews"] = list_interviews(conn, row["job_id"])
        result.append(item)
    return result


NOT_PASSED = ("new", "filtered", "duplicate", "closed", "ignored")
SCORED = ("scored", "selected", "packaged", "below_threshold", "applied", "replied", "rejected")


def upcoming_interviews(conn: sqlite3.Connection, limit: int = 6) -> list[dict[str, Any]]:
    """Pending interviews, soonest first (unscheduled ones last)."""
    rows = conn.execute(
        "SELECT i.id, i.job_id, i.kind, i.scheduled_at, i.notes, j.company, j.title "
        "FROM interviews i JOIN jobs j ON j.id = i.job_id WHERE i.outcome = 'pending' "
        "ORDER BY COALESCE(i.scheduled_at, '9999'), i.id LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Counts for the dashboard and `jobhunter stats`."""
    by_status = {
        r["status"]: r["n"]
        for r in conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")
    }
    total = sum(by_status.values())
    rejected_by_rule: dict[str, int] = {}
    for r in conn.execute(
        "SELECT filter_reason FROM jobs WHERE status = 'filtered' AND filter_reason IS NOT NULL"
    ):
        rule = r["filter_reason"].split(":")[0]
        rejected_by_rule[rule] = rejected_by_rule.get(rule, 0) + 1
    stages = {
        r["stage"]: r["n"]
        for r in conn.execute("SELECT stage, COUNT(*) AS n FROM applications GROUP BY stage")
    }
    today = datetime.now(UTC).date().isoformat()
    usage = conn.execute(
        "SELECT COUNT(*) AS calls, COALESCE(SUM(tokens_in),0) AS tin, COALESCE(SUM(tokens_out),0) "
        "AS tout, COALESCE(SUM(cost_usd),0) AS cost FROM llm_calls WHERE created_at >= ?",
        (today,),
    ).fetchone()
    total_usage = conn.execute(
        "SELECT COUNT(*) AS calls, COALESCE(SUM(cost_usd),0) AS cost FROM llm_calls"
    ).fetchone()
    last_fetch: list[dict[str, Any]] = []
    latest = conn.execute("SELECT MAX(created_at) FROM fetch_log").fetchone()[0]
    if latest:  # the last run = log rows within ten minutes of the most recent one
        cutoff = (datetime.fromisoformat(latest) - timedelta(minutes=10)).isoformat()
        last_fetch = [
            dict(r)
            for r in conn.execute(
                "SELECT source, MAX(created_at) AS at, SUM(jobs_found) AS jobs, "
                "SUM(status = 'error') AS errors FROM fetch_log WHERE created_at >= ? "
                "GROUP BY source ORDER BY source",
                (cutoff,),
            )
        ]
    packaged_total = conn.execute("SELECT COUNT(DISTINCT job_id) FROM packages").fetchone()[0]
    reached_selection = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status = 'selected' OR id IN "
        "(SELECT job_id FROM packages UNION SELECT job_id FROM applications)"
    ).fetchone()[0]
    reached_interviews = conn.execute(
        "SELECT COUNT(*) FROM (SELECT job_id FROM interviews UNION SELECT job_id FROM "
        "applications WHERE stage IN ('interviewing', 'offer', 'accepted'))"
    ).fetchone()[0]
    passed_filter = total - sum(by_status.get(s, 0) for s in NOT_PASSED)
    scored = sum(by_status.get(s, 0) for s in SCORED)
    return {
        "by_status": by_status,
        "total": total,
        "funnel": {
            "fetched": total,
            "passed_filter": passed_filter,
            "scored": scored,
            "selected": reached_selection,
            "packaged": packaged_total,
            "applied": sum(stages.values()),
            "interviewing": reached_interviews,
            "offer": stages.get("offer", 0) + stages.get("accepted", 0),
        },
        "rejected_by_rule": dict(sorted(rejected_by_rule.items(), key=lambda kv: -kv[1])),
        "stages": stages,
        "llm_today": dict(usage),
        "llm_total": dict(total_usage),
        "last_fetch": last_fetch,
    }
