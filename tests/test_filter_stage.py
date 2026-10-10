from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from jobhunter.cli import app
from jobhunter.config import SearchConfig
from jobhunter.db import connect
from jobhunter.filters import JobFilter
from jobhunter.models import Job
from jobhunter.pipeline import REFILTER_STATUSES, filter_stage
from jobhunter.store import upsert_jobs

NOW = datetime(2026, 10, 9, tzinfo=UTC)


@pytest.fixture
def conn(tmp_path):
    return connect(tmp_path / "t.db")


def add(conn, ext, title, remote="remote"):
    upsert_jobs(
        conn,
        [Job(source="s", external_id=ext, company="Acme", title=title, remote=remote,
             description="Python", url="u")],
    )  # fmt: skip


def statuses(conn):
    return {r["external_id"]: (r["status"], r["filter_reason"]) for r in
            conn.execute("SELECT external_id, status, filter_reason FROM jobs")}  # fmt: skip


def test_filter_stage_marks_passed_and_filtered_with_reasons(conn):
    add(conn, "1", "Backend Engineer")
    add(conn, "2", "Sales Manager")
    filt = JobFilter(SearchConfig(titles_include=["engineer"]))
    summary = filter_stage(conn, filt, now=NOW)
    assert (summary.evaluated, summary.passed, summary.filtered) == (2, 1, 1)
    assert summary.reasons == {"titles_include": 1}
    got = statuses(conn)
    assert got["1"] == ("passed", None)
    assert got["2"][0] == "filtered" and got["2"][1].startswith("titles_include")
    events = conn.execute("SELECT to_status FROM events WHERE note LIKE 'titles%'").fetchall()
    assert len(events) == 1


def test_default_stage_only_touches_new_postings(conn):
    add(conn, "1", "Sales Manager")
    filter_stage(conn, JobFilter(SearchConfig(titles_include=["engineer"])), now=NOW)
    # criteria change, but the default stage ignores already-filtered postings
    summary = filter_stage(conn, JobFilter(SearchConfig(titles_include=["manager"])), now=NOW)
    assert summary.evaluated == 0
    assert statuses(conn)["1"][0] == "filtered"


def test_refilter_reevaluates_everything_after_criteria_change(conn):
    add(conn, "1", "Sales Manager")
    add(conn, "2", "Backend Engineer")
    filter_stage(conn, JobFilter(SearchConfig(titles_include=["engineer"])), now=NOW)
    summary = filter_stage(
        conn, JobFilter(SearchConfig(titles_include=["manager"])), REFILTER_STATUSES, now=NOW
    )
    got = statuses(conn)
    assert got["1"] == ("passed", None) and got["2"][0] == "filtered"
    assert summary.changed == 2


def test_refilter_keeps_later_stage_status_when_still_passing(conn):
    add(conn, "1", "Backend Engineer")
    conn.execute("UPDATE jobs SET status = 'scored'")
    filter_stage(conn, JobFilter(SearchConfig()), REFILTER_STATUSES, now=NOW)
    assert statuses(conn)["1"][0] == "scored"
    # ...but a posting that no longer passes is filtered
    filter_stage(
        conn, JobFilter(SearchConfig(titles_exclude=["backend"])), REFILTER_STATUSES, now=NOW
    )
    assert statuses(conn)["1"][0] == "filtered"


def test_refilter_never_touches_human_or_closed_statuses(conn):
    add(conn, "1", "Sales Manager")
    conn.execute("UPDATE jobs SET status = 'applied'")
    filter_stage(
        conn, JobFilter(SearchConfig(titles_include=["engineer"])), REFILTER_STATUSES, now=NOW
    )
    assert statuses(conn)["1"][0] == "applied"


def test_unknown_mode_flag_is_stored(conn):
    add(conn, "1", "Engineer", remote="unknown")
    filter_stage(conn, JobFilter(SearchConfig(work_mode=["remote"])), now=NOW)
    flags = conn.execute("SELECT filter_flags FROM jobs").fetchone()[0]
    assert flags == "unknown_mode"


def test_content_change_resets_verdict(conn):
    add(conn, "1", "Backend Engineer")
    filter_stage(conn, JobFilter(SearchConfig()), now=NOW)
    upsert_jobs(conn, [Job(source="s", external_id="1", company="Acme", title="Backend Engineer",
                           description="changed", url="u")])  # fmt: skip
    row = conn.execute("SELECT status, filter_reason, filter_flags FROM jobs").fetchone()
    assert tuple(row) == ("new", None, None)


# --- CLI ---------------------------------------------------------------------------------

runner = CliRunner()


@pytest.fixture
def cli_config(tmp_path):
    db = tmp_path / "t.db"
    conn = connect(db)
    add(conn, "1", "Backend Engineer")
    add(conn, "2", "Sales Manager")
    conn.close()
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"paths:\n  db: {db}\nsearch:\n  titles_include: [engineer]\n  work_mode: [remote]\n"
        f"sources:\n  companies_file: {tmp_path}/none.yaml\n"
    )
    return cfg


def test_cli_run_stage_filter_and_refilter(cli_config):
    result = runner.invoke(app, ["run", "--stage", "filter", "--config", str(cli_config)])
    assert result.exit_code == 0, result.output
    assert "passed 1" in result.stdout and "rejected by titles_include: 1" in result.stdout
    assert "1 postings currently pass" in result.stdout
    again = runner.invoke(app, ["refilter", "--config", str(cli_config)])
    assert again.exit_code == 0 and "filtered 2 postings" in again.stdout


def test_cli_explain(cli_config):
    runner.invoke(app, ["run", "--stage", "filter", "--config", str(cli_config)])
    result = runner.invoke(app, ["explain", "2", "--config", str(cli_config)])
    assert result.exit_code == 0
    assert "Sales Manager" in result.stdout
    assert "REJECTED — titles_include" in result.stdout
    ok = runner.invoke(app, ["explain", "1", "--config", str(cli_config)])
    assert "PASSES" in ok.stdout


def test_cli_explain_unknown_id(cli_config):
    result = runner.invoke(app, ["explain", "999", "--config", str(cli_config)])
    assert result.exit_code == 1
    assert "no posting with id 999" in result.output
