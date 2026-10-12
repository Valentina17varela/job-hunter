"""SQLite storage with simple versioned migrations (see specs/02-data-model.md)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS: list[str] = [
    # v1: initial schema
    """
    CREATE TABLE jobs (
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        external_id TEXT NOT NULL,
        company TEXT NOT NULL,
        title TEXT NOT NULL,
        location TEXT,
        remote TEXT NOT NULL DEFAULT 'unknown',
        description TEXT NOT NULL DEFAULT '',
        url TEXT NOT NULL,
        salary_min INTEGER,
        salary_max INTEGER,
        salary_currency TEXT,
        posted_at TEXT,
        fetched_at TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'new',
        filter_reason TEXT,
        UNIQUE(source, external_id)
    );
    CREATE INDEX idx_jobs_status ON jobs(status);

    CREATE TABLE scores (
        job_id INTEGER NOT NULL REFERENCES jobs(id),
        score INTEGER NOT NULL,
        reasons TEXT NOT NULL,
        model TEXT NOT NULL,
        profile_hash TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX idx_scores_job ON scores(job_id);

    CREATE TABLE packages (
        job_id INTEGER NOT NULL REFERENCES jobs(id),
        path TEXT NOT NULL,
        model TEXT NOT NULL,
        created_at TEXT NOT NULL,
        verified INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE llm_calls (
        id INTEGER PRIMARY KEY,
        stage TEXT NOT NULL,
        model TEXT NOT NULL,
        job_id INTEGER,
        tokens_in INTEGER NOT NULL,
        tokens_out INTEGER NOT NULL,
        tokens_cache_read INTEGER NOT NULL DEFAULT 0,
        cost_usd REAL NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE fetch_log (
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        target TEXT,
        status TEXT NOT NULL,
        jobs_found INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE events (
        job_id INTEGER NOT NULL REFERENCES jobs(id),
        from_status TEXT,
        to_status TEXT NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL
    );
    """,
    # v2: track when a posting was last seen, to close postings that disappear
    """
    ALTER TABLE jobs ADD COLUMN last_seen_at TEXT;
    UPDATE jobs SET last_seen_at = fetched_at;
    """,
    # v3: non-blocking observations from the filter (e.g. unknown_mode) for later stages
    """
    ALTER TABLE jobs ADD COLUMN filter_flags TEXT;
    """,
    # v4: scores remember which posting content they were computed for; human calibration
    """
    ALTER TABLE scores ADD COLUMN content_hash TEXT;
    CREATE INDEX idx_scores_cache ON scores(job_id, content_hash, profile_hash, prompt_version);
    CREATE TABLE calibration (
        job_id INTEGER NOT NULL REFERENCES jobs(id),
        llm_score INTEGER NOT NULL,
        verdict TEXT NOT NULL,
        agrees INTEGER NOT NULL,
        created_at TEXT NOT NULL
    );
    """,
    # v5: application tracking (stages) and interviews
    """
    CREATE TABLE applications (
        job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
        stage TEXT NOT NULL,
        applied_at TEXT,
        updated_at TEXT NOT NULL,
        notes TEXT
    );
    CREATE TABLE interviews (
        id INTEGER PRIMARY KEY,
        job_id INTEGER NOT NULL REFERENCES jobs(id),
        kind TEXT NOT NULL,
        scheduled_at TEXT,
        notes TEXT,
        outcome TEXT NOT NULL DEFAULT 'pending'
    );
    CREATE INDEX idx_interviews_job ON interviews(job_id);
    """,
    # v6: favorites (bookmarks independent of the posting status)
    """
    CREATE TABLE favorites (
        job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
        created_at TEXT NOT NULL,
        note TEXT
    );
    """,
]


def connect(path: Path) -> sqlite3.Connection:
    """Open (creating if needed) the database and apply pending migrations."""
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Apply migrations not yet applied; returns the resulting schema version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, script in enumerate(MIGRATIONS, start=1):
        if version > current:
            with conn:
                conn.executescript(script)
                conn.execute(f"PRAGMA user_version = {version}")
    return conn.execute("PRAGMA user_version").fetchone()[0]
