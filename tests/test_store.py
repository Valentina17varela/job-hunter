from datetime import UTC, datetime, timedelta

import pytest

from jobhunter.db import connect
from jobhunter.models import Job
from jobhunter.store import close_stale, mark_duplicates, upsert_jobs


@pytest.fixture
def conn(tmp_path):
    return connect(tmp_path / "t.db")


def job(ext="1", source="greenhouse", company="Acme", title="Engineer", description="d"):
    return Job(
        source=source, external_id=ext, company=company, title=title,
        description=description, url="https://x/" + ext,
    )  # fmt: skip


def status(conn, ext="1", source="greenhouse"):
    row = conn.execute(
        "SELECT status FROM jobs WHERE source=? AND external_id=?", (source, ext)
    ).fetchone()
    return row["status"]


def test_insert_then_unchanged(conn):
    assert upsert_jobs(conn, [job()]).new == 1
    again = upsert_jobs(conn, [job()])
    assert (again.new, again.unchanged, again.updated) == (0, 1, 0)
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_changed_content_resets_status_and_clears_filter_reason(conn):
    upsert_jobs(conn, [job()])
    conn.execute("UPDATE jobs SET status='scored', filter_reason='x'")
    result = upsert_jobs(conn, [job(description="changed")])
    assert result.updated == 1
    row = conn.execute("SELECT status, filter_reason, description FROM jobs").fetchone()
    assert (row["status"], row["filter_reason"], row["description"]) == ("new", None, "changed")
    events = conn.execute("SELECT to_status, note FROM events ORDER BY rowid").fetchall()
    assert [tuple(e) for e in events] == [("new", "fetched"), ("new", "content changed")]


def test_human_status_survives_content_change(conn):
    upsert_jobs(conn, [job()])
    conn.execute("UPDATE jobs SET status='applied'")
    upsert_jobs(conn, [job(description="changed")])
    assert status(conn) == "applied"
    assert conn.execute("SELECT description FROM jobs").fetchone()[0] == "changed"


def test_closed_posting_reopens_when_it_reappears(conn):
    upsert_jobs(conn, [job()])
    conn.execute("UPDATE jobs SET status='closed'")
    result = upsert_jobs(conn, [job()])
    assert result.reopened == 1
    assert status(conn) == "new"


def test_close_stale_only_for_ok_sources_and_not_human_statuses(conn):
    long_ago = datetime.now(UTC) - timedelta(days=10)
    upsert_jobs(conn, [job("1"), job("2"), job("3")], now=long_ago)
    upsert_jobs(conn, [job("4", source="lever")], now=long_ago)
    conn.execute("UPDATE jobs SET status='applied' WHERE external_id='2'")
    assert close_stale(conn, {"greenhouse"}, stale_days=7) == 2
    assert status(conn, "1") == "closed"
    assert status(conn, "2") == "applied"
    assert status(conn, "4", "lever") == "new"  # lever was not fetched OK


def test_recently_seen_is_not_closed(conn):
    upsert_jobs(conn, [job()])
    assert close_stale(conn, {"greenhouse"}, stale_days=7) == 0


def test_close_stale_with_no_ok_sources_is_noop(conn):
    upsert_jobs(conn, [job()], now=datetime.now(UTC) - timedelta(days=30))
    assert close_stale(conn, set()) == 0


def test_duplicates_keep_direct_ats_posting(conn):
    upsert_jobs(conn, [job("1", "remoteok", "Acme, Inc.", "Senior Engineer")])
    upsert_jobs(conn, [job("a", "greenhouse", "Acme Inc", "Senior  Engineer!")])
    upsert_jobs(conn, [job("9", "greenhouse", "Other", "Senior Engineer")])
    assert mark_duplicates(conn) == 1
    assert status(conn, "1", "remoteok") == "duplicate"
    assert status(conn, "a") == "new"
    assert status(conn, "9") == "new"
    assert mark_duplicates(conn) == 0  # idempotent


def test_same_title_within_one_source_is_not_duplicate(conn):
    upsert_jobs(conn, [job("1"), job("2")])  # two openings of the same role
    assert mark_duplicates(conn) == 0
