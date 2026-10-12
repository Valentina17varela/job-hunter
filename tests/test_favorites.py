import pytest
from typer.testing import CliRunner

from jobhunter import favorites
from jobhunter.applications import TrackingError
from jobhunter.cli import app
from jobhunter.config import SearchConfig
from jobhunter.db import connect
from jobhunter.filters import JobFilter
from jobhunter.models import Job
from jobhunter.pipeline import REFILTER_STATUSES, filter_stage
from jobhunter.store import close_stale, upsert_jobs


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "t.db")
    upsert_jobs(c, [
        Job(source="greenhouse", external_id="1", company="Acme", title="Engineer",
            description="d", url="u1", remote="remote"),
        Job(source="lever", external_id="2", company="Metamask", title="Engineer",
            description="d", url="u2", remote="remote"),
    ])  # fmt: skip
    return c


def events(conn, job_id):
    return [r["to_status"] for r in conn.execute("SELECT * FROM events WHERE job_id=?", (job_id,))]


def test_star_unstar_note_and_events(conn):
    favorites.set_favorite(conn, 1, "ask about the visa")
    favorites.set_favorite(conn, 1)  # re-star keeps the note and logs nothing new
    assert favorites.list_favorites(conn)[0]["note"] == "ask about the visa"
    favorites.set_favorite(conn, 1, "new note")
    assert favorites.list_favorites(conn)[0]["note"] == "new note"
    assert events(conn, 1).count("favorited") == 1
    assert favorites.remove_favorite(conn, 1) is True
    assert favorites.remove_favorite(conn, 1) is False
    assert favorites.list_favorites(conn) == []
    assert events(conn, 1)[-1] == "unfavorited"
    assert conn.execute("SELECT status FROM jobs WHERE id=1").fetchone()[0] == "new"


def test_unknown_posting_and_long_note_are_rejected(conn):
    with pytest.raises(TrackingError):
        favorites.set_favorite(conn, 99)
    with pytest.raises(TrackingError):
        favorites.set_favorite(conn, 1, "x" * 501)


def test_any_status_can_be_starred_and_favorites_survive_refilter_and_closing(conn):
    conn.execute("UPDATE jobs SET status='filtered' WHERE id=1")
    favorites.set_favorite(conn, 1)
    block = JobFilter(SearchConfig(companies_exclude=["Acme"]))
    filter_stage(conn, block, REFILTER_STATUSES)
    conn.execute("UPDATE jobs SET last_seen_at='2000-01-01T00:00:00+00:00'")
    close_stale(conn, {"greenhouse", "lever"})
    # Only status changes (here: closed by the stale rule); the favorite row is untouched.
    assert [(f["id"], f["status"]) for f in favorites.list_favorites(conn)] == [(1, "closed")]
    favorites.set_favorite(conn, 2)  # closed postings can be starred too
    assert {f["id"] for f in favorites.list_favorites(conn)} == {1, 2}


def test_blocking_filters_existing_postings_and_spares_human_statuses(conn):
    upsert_jobs(conn, [Job(source="lever", external_id="3", company="Acme Inc", title="Dev",
                           description="d", url="u3", remote="remote")])  # fmt: skip
    conn.execute("UPDATE jobs SET status='applied' WHERE id=3")
    conn.execute("UPDATE jobs SET status='packaged' WHERE id=1")
    upsert_jobs(conn, [Job(source="lever", external_id="4", company="ACME", title="Dev",
                           description="d", url="u4", remote="remote")])  # fmt: skip
    block = JobFilter(SearchConfig(companies_exclude=["Acme"], work_mode=[]))
    summary = filter_stage(conn, block, REFILTER_STATUSES)
    status = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM jobs")}
    assert status[4] == "filtered" and status[3] == "applied" and status[1] == "packaged"
    assert status[2] == "passed"  # Metamask is not Meta/Acme
    assert summary.reasons["companies_exclude"] == 1


def test_new_postings_from_blocked_companies_start_filtered(conn):
    block = JobFilter(SearchConfig(companies_exclude=["Metamask"], work_mode=[]))
    filter_stage(conn, block)
    row = conn.execute("SELECT status, filter_reason FROM jobs WHERE id=2").fetchone()
    assert row["status"] == "filtered" and "block list" in row["filter_reason"]


def test_cli_favorite_and_favorites(tmp_path):
    runner = CliRunner()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"paths:\n  db: {tmp_path}/c.db\n")
    c = connect(tmp_path / "c.db")
    upsert_jobs(c, [Job(source="lever", external_id="1", company="Acme", title="Engineer",
                        description="d", url="u", remote="remote")])  # fmt: skip
    args = ["--config", str(cfg)]
    assert "no favorites" in runner.invoke(app, ["favorites", *args]).output
    assert runner.invoke(app, ["favorite", "1", "--note", "visa?", *args]).exit_code == 0
    listing = runner.invoke(app, ["favorites", *args]).output
    assert "Engineer" in listing and "visa?" in listing
    assert "unstarred" in runner.invoke(app, ["favorite", "1", "--remove", *args]).output
    assert runner.invoke(app, ["favorite", "9", *args]).exit_code == 1
