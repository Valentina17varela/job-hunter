import sqlite3

import pytest

from jobhunter.db import MIGRATIONS, connect, migrate


def test_connect_creates_schema(tmp_path):
    conn = connect(tmp_path / "sub" / "t.db")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"jobs", "scores", "packages", "llm_calls", "fetch_log", "events"} <= tables
    assert conn.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)


def test_migrate_is_idempotent(tmp_path):
    conn = connect(tmp_path / "t.db")
    assert migrate(conn) == len(MIGRATIONS)


def test_unique_source_external_id(tmp_path):
    conn = connect(tmp_path / "t.db")
    row = ("s", "1", "c", "t", "u", "2026-01-01", "h")
    sql = (
        "INSERT INTO jobs(source, external_id, company, title, url, fetched_at, content_hash) "
        "VALUES (?,?,?,?,?,?,?)"
    )
    conn.execute(sql, row)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, row)
