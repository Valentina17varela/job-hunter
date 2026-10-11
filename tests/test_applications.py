from datetime import UTC, datetime, timedelta

import pytest
from typer.testing import CliRunner

from jobhunter import applications as apps
from jobhunter.cli import app
from jobhunter.db import connect
from jobhunter.models import Job
from jobhunter.store import upsert_jobs


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "t.db")
    upsert_jobs(
        c,
        [Job(source="s", external_id=str(i), company=f"Co{i}", title=f"Eng {i}", url="u")
         for i in (1, 2, 3)],
    )  # fmt: skip
    return c


def status(conn, jid=1):
    return conn.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()["status"]


def test_set_stage_creates_application_updates_status_and_logs_events(conn):
    apps.set_stage(conn, 1, "applied", "sent via the careers page")
    assert status(conn) == "applied"
    row = conn.execute("SELECT * FROM applications").fetchone()
    assert (row["stage"], row["notes"]) == ("applied", "sent via the careers page")
    assert row["applied_at"] and row["updated_at"]
    apps.set_stage(conn, 1, "interviewing", "recruiter call booked")
    assert status(conn) == "replied"
    row = conn.execute("SELECT * FROM applications").fetchone()
    assert row["stage"] == "interviewing" and "recruiter call booked" in row["notes"]
    assert "sent via the careers page" in row["notes"]
    events = [
        r["note"] for r in conn.execute("SELECT note FROM events WHERE job_id=1 ORDER BY rowid")
    ]
    assert events[-1].startswith("stage: interviewing")


@pytest.mark.parametrize(
    ("stage", "expected"),
    [("applied", "applied"), ("screening", "replied"), ("offer", "replied"),
     ("accepted", "replied"), ("rejected", "rejected"), ("withdrawn", "rejected"),
     ("ghosted", "rejected")],
)  # fmt: skip
def test_stage_to_status_mapping(conn, stage, expected):
    apps.set_stage(conn, 1, stage)
    assert status(conn) == expected


def test_invalid_inputs(conn):
    with pytest.raises(apps.TrackingError, match="unknown stage"):
        apps.set_stage(conn, 1, "banana")
    with pytest.raises(apps.TrackingError, match="no posting"):
        apps.set_stage(conn, 99, "applied")
    with pytest.raises(apps.TrackingError, match="no application yet"):
        apps.set_notes(conn, 2, "x")


def test_human_status_survives_refetch_and_ignore_is_permanent(conn):
    apps.set_stage(conn, 1, "applied")
    apps.ignore(conn, 2, "not interesting")
    upsert_jobs(conn, [Job(source="s", external_id="1", company="Co1", title="Eng 1",
                           description="changed", url="u"),
                       Job(source="s", external_id="2", company="Co2", title="Eng 2",
                           description="changed", url="u")])  # fmt: skip
    assert status(conn, 1) == "applied" and status(conn, 2) == "ignored"


def test_interviews_crud_and_ordering(conn):
    apps.set_stage(conn, 1, "interviewing")
    later = apps.add_interview(conn, 1, "technical", "2026-10-20T15:00", "pair programming")
    sooner = apps.add_interview(conn, 1, "recruiter", "2026-10-15T10:00")
    unscheduled = apps.add_interview(conn, 1, "onsite")
    assert [i["id"] for i in apps.list_interviews(conn, 1)] == [sooner, later, unscheduled]
    apps.update_interview(conn, later, outcome="passed", notes="went well")
    updated = next(i for i in apps.list_interviews(conn, 1) if i["id"] == later)
    assert (updated["outcome"], updated["notes"]) == ("passed", "went well")
    apps.delete_interview(conn, unscheduled)
    assert len(apps.list_interviews(conn, 1)) == 2
    with pytest.raises(apps.TrackingError):
        apps.add_interview(conn, 1, "karaoke")
    with pytest.raises(apps.TrackingError):
        apps.update_interview(conn, later, outcome="maybe")
    with pytest.raises(apps.TrackingError):
        apps.update_interview(conn, later, job_id=5)
    with pytest.raises(apps.TrackingError, match="no interview"):
        apps.update_interview(conn, 999, notes="x")


def test_list_applications_includes_interviews_and_score(conn):
    apps.set_stage(conn, 1, "screening")
    apps.add_interview(conn, 1, "recruiter", "2026-10-15T10:00")
    conn.execute(
        "INSERT INTO scores(job_id, score, reasons, model, profile_hash, prompt_version, "
        "created_at) VALUES (1, 88, '{}', 'm', 'h', 'v', 'now')"
    )
    (row,) = apps.list_applications(conn)
    assert row["company"] == "Co1" and row["score"] == 88 and row["stage"] == "screening"
    assert row["interviews"][0]["kind"] == "recruiter"


def test_stats_funnel_rules_stages_and_llm_usage(conn):
    conn.execute("UPDATE jobs SET status='filtered', filter_reason='titles_include: x' WHERE id=1")
    conn.execute("UPDATE jobs SET status='selected' WHERE id=2")
    conn.execute("UPDATE jobs SET status='packaged' WHERE id=3")
    apps.set_stage(conn, 3, "interviewing")
    now = datetime.now(UTC)
    conn.execute(
        "INSERT INTO llm_calls(stage, model, tokens_in, tokens_out, cost_usd, created_at) "
        "VALUES ('score','m',100,50,0.5,?)",
        (now.isoformat(),),
    )
    conn.execute(
        "INSERT INTO fetch_log(source, target, status, jobs_found, created_at) VALUES "
        "('greenhouse','a','ok',10,?),('greenhouse','b','error',0,?),('lever','c','ok',5,?),"
        "('lever','old','ok',1,?)",
        (now.isoformat(), now.isoformat(), now.isoformat(), (now - timedelta(days=3)).isoformat()),
    )
    conn.commit()
    data = apps.stats(conn)
    assert data["total"] == 3 and data["rejected_by_rule"] == {"titles_include": 1}
    f = data["funnel"]
    assert (f["fetched"], f["passed_filter"], f["selected"], f["applied"]) == (3, 2, 2, 1)
    assert f["interviewing"] == 1 and f["offer"] == 0
    assert data["stages"] == {"interviewing": 1}
    assert data["llm_today"]["calls"] == 1 and data["llm_today"]["tin"] == 100
    last = {r["source"]: r for r in data["last_fetch"]}
    assert last["greenhouse"]["jobs"] == 10 and last["greenhouse"]["errors"] == 1
    assert last["lever"]["jobs"] == 5  # the 3-day-old row belongs to an earlier run


def test_stats_on_empty_database(tmp_path):
    data = apps.stats(connect(tmp_path / "e.db"))
    assert data["total"] == 0 and data["last_fetch"] == [] and data["funnel"]["applied"] == 0


runner = CliRunner()


def test_cli_mark_and_stats(tmp_path):
    db = tmp_path / "c.db"
    conn = connect(db)
    upsert_jobs(conn, [Job(source="s", external_id="1", company="Co", title="Eng", url="u")])
    conn.close()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"paths:\n  db: {db}\n")
    ok = runner.invoke(app, ["mark", "1", "applied", "--note", "hi", "--config", str(cfg)])
    assert ok.exit_code == 0 and "now 'applied'" in ok.stdout
    bad = runner.invoke(app, ["mark", "1", "banana", "--config", str(cfg)])
    assert bad.exit_code == 1 and "unknown stage" in bad.output
    out = runner.invoke(app, ["stats", "--config", str(cfg)])
    assert (
        out.exit_code == 0 and "applied 1" in out.stdout and "applications applied: 1" in out.stdout
    )


def test_funnel_counts_distinct_postings_and_interviews_after_a_rejection(conn):
    conn.execute("UPDATE jobs SET status='selected' WHERE id=1")
    conn.execute(
        "INSERT INTO packages(job_id, path, model, created_at, verified) VALUES (1,'p','m','now',1)"
    )
    apps.set_stage(conn, 1, "screening")
    apps.add_interview(conn, 1, "technical")
    apps.set_stage(conn, 1, "rejected")
    f = apps.stats(conn)["funnel"]
    assert f["selected"] == 1  # one posting, however many ways it qualifies
    assert f["interviewing"] == 1  # still counted after the rejection
    assert f["packaged"] == 1 and f["applied"] == 1


def test_ignore_is_refused_for_postings_with_an_application(conn):
    apps.set_stage(conn, 1, "applied")
    with pytest.raises(apps.TrackingError, match="has an application"):
        apps.ignore(conn, 1)
    apps.ignore(conn, 2)
    assert status(conn, 2) == "ignored"
