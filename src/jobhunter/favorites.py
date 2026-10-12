"""Favorites: bookmarks on postings of any status (specs/11-favorites-and-blocklist.md).

A favorite never changes ``jobs.status`` and lives in its own table, so refilter, dedupe and
stale-closing cannot remove it.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from jobhunter.applications import TrackingError

NOTE_MAX = 500


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _event(conn: sqlite3.Connection, job_id: int, kind: str, note: str | None) -> None:
    conn.execute(
        "INSERT INTO events(job_id, from_status, to_status, note, created_at) VALUES (?,?,?,?,?)",
        (job_id, None, kind, note, _now()),
    )


def set_favorite(conn: sqlite3.Connection, job_id: int, note: str | None = None) -> None:
    """Star a posting, or update the note of an already starred one."""
    if conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is None:
        raise TrackingError(f"no posting with id {job_id}")
    note = (note or "").strip() or None
    if note and len(note) > NOTE_MAX:
        raise TrackingError(f"the note is longer than {NOTE_MAX} characters")
    with conn:
        exists = conn.execute("SELECT 1 FROM favorites WHERE job_id = ?", (job_id,)).fetchone()
        if exists:
            if note is not None:  # a plain re-star keeps the existing note
                conn.execute("UPDATE favorites SET note = ? WHERE job_id = ?", (note, job_id))
            return
        conn.execute(
            "INSERT INTO favorites(job_id, created_at, note) VALUES (?,?,?)",
            (job_id, _now(), note),
        )
        _event(conn, job_id, "favorited", note)


def remove_favorite(conn: sqlite3.Connection, job_id: int) -> bool:
    """Unstar; returns False when the posting was not a favorite."""
    with conn:
        removed = conn.execute("DELETE FROM favorites WHERE job_id = ?", (job_id,)).rowcount
        if removed:
            _event(conn, job_id, "unfavorited", None)
    return bool(removed)


def list_favorites(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Favorites, newest first, with the posting fields needed to show them."""
    rows = conn.execute(
        "SELECT j.id, j.company, j.title, j.status, j.url, f.created_at, f.note, "
        "EXISTS(SELECT 1 FROM applications WHERE job_id = j.id) AS has_application "
        "FROM favorites f JOIN jobs j ON j.id = f.job_id ORDER BY f.created_at DESC, j.id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def count_without_application(conn: sqlite3.Connection) -> int:
    """Favorites the person has not applied to yet (shown on Home)."""
    return conn.execute(
        "SELECT COUNT(*) FROM favorites WHERE job_id NOT IN (SELECT job_id FROM applications)"
    ).fetchone()[0]
