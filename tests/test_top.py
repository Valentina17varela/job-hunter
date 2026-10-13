import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from jobhunter import applications, latex, top
from jobhunter.cli import app
from jobhunter.config import Config
from jobhunter.db import connect
from jobhunter.llm import LlmClient, LlmResponse
from jobhunter.models import Job
from jobhunter.scoring import score_stage
from jobhunter.store import upsert_jobs
from jobhunter.web.app import create_app

CV = (Path(__file__).parent / "fixtures" / "master_marked.tex").read_text()
HOST = {"host": "testserver"}


def config(**scoring) -> Config:
    return Config.model_validate(
        {
            "scoring": {"batch_size": 2, "score_threshold": 75, "top_matches_count": 5, **scoring},
            "search": {"keywords_include": ["python"], "titles_include": ["engineer"],
                       "salary": {"min_usd": 80000}},
        }
    )  # fmt: skip


@pytest.fixture
def conn(tmp_path):
    return connect(tmp_path / "t.db")


def add(conn, n, *, start=1, status="passed", description="Python role", **extra):
    upsert_jobs(
        conn,
        [Job(source="s", external_id=str(i), company=f"Co{i}", title=f"Engineer {i}",
             description=description, url="https://x.test/1", remote="remote", **extra)
         for i in range(start, start + n)],
    )  # fmt: skip
    conn.execute("UPDATE jobs SET status = ? WHERE status = 'new'", (status,))
    conn.commit()


def score(conn, title_to_score, status="scored", verdict="apply"):
    for title, value in title_to_score.items():
        job_id = conn.execute("SELECT id FROM jobs WHERE title = ?", (title,)).fetchone()[0]
        conn.execute(
            "INSERT INTO scores(job_id, score, reasons, model, profile_hash, prompt_version, "
            "created_at) VALUES (?,?,?,?,?,?,?)",
            (job_id, value, json.dumps({"verdict": verdict, "reason": "r", "red_flags": []}),
             "m", "h", "v", "2026-10-01T00:00:00+00:00"),
        )  # fmt: skip
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()


def ids(rows):
    return [r["title"] for r in rows]


# --- ranking ------------------------------------------------------------------------------


def test_board_puts_above_threshold_first_then_the_best_of_the_rest_labelled(conn):
    add(conn, 7)
    score(conn, {"Engineer 1": 90, "Engineer 2": 80, "Engineer 3": 60, "Engineer 4": 70,
                 "Engineer 5": 95})  # fmt: skip
    board = top.top_matches(conn, config())
    assert ids(board) == ["Engineer 5", "Engineer 1", "Engineer 2", "Engineer 4", "Engineer 3"]
    assert [r["below_threshold"] for r in board] == [False, False, False, True, True]


def test_a_skip_verdict_is_never_presented_as_a_match_even_with_a_high_score(conn):
    add(conn, 2)
    score(conn, {"Engineer 1": 99}, verdict="skip")
    score(conn, {"Engineer 2": 80})
    board = top.top_matches(conn, config())
    assert ids(board) == ["Engineer 2", "Engineer 1"] and board[1]["below_threshold"]


def test_board_excludes_dismissed_applied_closed_duplicate_and_unscored(conn):
    add(conn, 8)
    score(conn, {f"Engineer {i}": 90 - i for i in range(1, 8)})
    conn.execute("UPDATE jobs SET status = 'ignored' WHERE title = 'Engineer 1'")
    conn.execute("UPDATE jobs SET status = 'closed' WHERE title = 'Engineer 2'")
    conn.execute("UPDATE jobs SET status = 'duplicate' WHERE title = 'Engineer 3'")
    conn.commit()
    applications.set_stage(conn, conn.execute("SELECT id FROM jobs WHERE title='Engineer 4'")
                           .fetchone()[0], "applied", None)  # fmt: skip
    assert ids(top.top_matches(conn, config())) == ["Engineer 5", "Engineer 6", "Engineer 7"]


def test_hiding_one_promotes_the_next_best_immediately(conn):
    add(conn, 7)
    score(conn, {f"Engineer {i}": 70 + i * 3 for i in range(1, 8)})
    before = top.top_matches(conn, config())
    assert len(before) == 5 and before[0]["title"] == "Engineer 7"
    applications.ignore(conn, before[0]["id"])
    after = top.top_matches(conn, config())
    assert len(after) == 5 and "Engineer 7" not in ids(after) and "Engineer 2" in ids(after)
    plan = top.plan(conn, config())
    assert plan["need"] == 0 and plan["fill_ids"] == []


def test_count_follows_the_setting_and_never_exceeds_whats_available(conn):
    add(conn, 3)
    score(conn, {"Engineer 1": 90, "Engineer 2": 80})
    assert len(top.top_matches(conn, config(top_matches_count=1))) == 1
    plan = top.plan(conn, config())
    assert len(plan["board"]) == 2 and plan["need"] == 3 and plan["unscored_left"] == 1


# --- pre-rank and the fill ---------------------------------------------------------------


def test_prerank_is_deterministic_and_prefers_keywords_salary_recency_and_chosen_ones(conn):
    add(conn, 1, description="Rust only")
    add(conn, 1, start=2, description="We use Python daily")
    add(conn, 1, start=3, description="Python", salary_min=100000, salary_max=120000,
        salary_currency="USD")  # fmt: skip
    rows = {r["external_id"]: r for r in conn.execute("SELECT * FROM jobs")}
    cfg = config()
    a, b, c = (top.prerank(rows[k], cfg) for k in ("1", "2", "3"))
    assert a < b < c
    assert top.prerank(rows["1"], cfg) == a  # same input, same output
    assert top.prerank(rows["1"], cfg, favorite=True) == a + 5


def test_fill_picks_the_most_promising_and_at_most_twice_the_gap(conn):
    add(conn, 2)
    score(conn, {"Engineer 1": 90, "Engineer 2": 85})
    add(conn, 10, start=3, description="no keywords here")
    add(conn, 1, start=13, description="Python everywhere")
    plan = top.plan(conn, config())
    assert plan["need"] == 3 and len(plan["fill_ids"]) == 6  # twice the gap
    best = conn.execute("SELECT id FROM jobs WHERE title = 'Engineer 13'").fetchone()[0]
    assert plan["fill_ids"][0] == best


def test_fill_never_exceeds_what_the_call_cap_can_score(conn):
    add(conn, 30)
    cfg = Config.model_validate(
        {"scoring": {"batch_size": 2}, "budget": {"max_llm_calls_per_run": 2}}
    )
    assert len(top.fill_candidates(conn, cfg, need=5)) == 4  # 2 calls x 2 per batch
    assert top.fill_candidates(conn, cfg, need=0) == []


class FakeScorer:
    def __init__(self, scores):
        self.scores, self.calls = scores, 0

    def complete(self, *, system, prompt, schema, model):
        self.calls += 1
        blocks = json.loads(prompt.split("\n\n", 1)[1])
        results = [
            {"id": b["id"], "score": self.scores.get(b["title"], 50), "verdict": "apply",
             "reason": "r", "red_flags": []}
            for b in blocks
        ]  # fmt: skip
        return LlmResponse(data={"results": results}, model=model, tokens_in=1, tokens_out=1)


def test_filling_scores_only_the_chosen_postings_and_refills_the_board(conn):
    cfg = config()
    add(conn, 3)
    score(conn, {"Engineer 1": 90, "Engineer 2": 85, "Engineer 3": 80})
    add(conn, 6, start=4)
    applications.ignore(conn, 1)
    plan = top.plan(conn, cfg)
    assert plan["need"] == 3 and plan["fill_ids"]
    backend = FakeScorer({f"Engineer {i}": 80 + i for i in range(4, 10)})
    client = LlmClient(conn, backend, max_calls=10, sleep=lambda s: None)
    summary = score_stage(conn, client, cfg, latex.parse(CV), plan["fill_ids"])
    assert summary.scored == len(plan["fill_ids"]) and backend.calls <= 3
    left = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'passed'").fetchone()[0]
    assert left == 6 - len(plan["fill_ids"])  # the rest were not touched
    assert top.plan(conn, cfg)["need"] == 0


# --- dismissals and suggestions --------------------------------------------------------------


def test_not_for_me_records_a_reason_hides_it_and_only_suggests(conn):
    add(conn, 4)
    for i in (1, 2, 3):
        applications.dismiss(conn, i, "location", "needs US residency" if i == 1 else None)
    applications.dismiss(conn, 4, "pay")
    assert conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'ignored'").fetchone()[0] == 4
    assert top.reason_counts(conn) == {"location": 3, "pay": 1}
    (hint,) = top.suggestions(conn)  # only the reason repeated 3 times
    assert "3 postings" in hint and "location" in hint and "Where I can work" in hint
    note = conn.execute("SELECT note FROM events WHERE note LIKE '%US residency%'").fetchone()
    assert note and note[0].startswith("not for me: location |")
    with pytest.raises(applications.TrackingError):
        applications.dismiss(conn, 1, "because", None)


# --- web and CLI -----------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"paths:\n  db: {tmp_path}/t.db\n  out: {tmp_path}/out\n"
        f"sources:\n  companies_file: {tmp_path}/none.yaml\n"
        "scoring:\n  top_matches_count: 3\nsearch:\n  keywords_include: [python]\n"
    )
    db = connect(tmp_path / "t.db")
    add(db, 2)
    score(db, {"Engineer 1": 90, "Engineer 2": 70})
    add(db, 4, start=3)
    return TestClient(create_app(cfg_path, allowed_hosts={"testserver"})), db


def test_board_is_shown_with_the_fill_card_and_below_threshold_label(client):
    http, _ = client
    page = http.get("/jobs", headers=HOST).text
    assert "Your top 3" in page and "Engineer 1" in page
    assert "below your threshold" in page  # Engineer 2 scored 70 < 75
    assert "Only 2 of 3 matches so far" in page and "Score 2 replacements" in page
    assert "&#34;score&#34;" in page and "&#34;jobs&#34;" in page  # the offered run
    assert "Top matches" in http.get("/", headers=HOST).text


def test_hiding_updates_the_plan_and_never_starts_a_run_by_itself(client):
    http, db = client
    before = http.get("/api/top", headers=HOST).json()
    assert before["need"] == 1 and before["board"] == [1, 2]
    res = http.post("/api/jobs/1/ignore", json={"reason": "role", "note": "meh"}, headers=HOST)
    assert res.status_code == 200
    after = http.get("/api/top", headers=HOST).json()
    assert after["board"] == [2] and after["need"] == 2 and after["fill_ids"]
    assert db.execute("SELECT COUNT(*) FROM llm_calls").fetchone()[0] == 0  # nothing was scored
    unscored = db.execute("SELECT COUNT(*) FROM jobs WHERE status = 'passed'").fetchone()[0]
    assert unscored == 4  # the postings waiting for a score were not touched
    bad = http.post("/api/jobs/2/ignore", json={"reason": "nope"}, headers=HOST)
    assert bad.status_code >= 400


def test_no_unscored_postings_left_offers_search_instead(client):
    http, db = client
    db.execute("UPDATE jobs SET status = 'filtered' WHERE status = 'passed'")
    db.commit()
    page = http.get("/jobs", headers=HOST).text
    assert "no unscored postings left" in page and "Search for new jobs" in page
    assert http.get("/api/top", headers=HOST).json()["fill_ids"] == []


def test_the_dialog_and_notice_exist_and_reasons_are_escaped(client):
    http, _ = client
    html = http.get("/jobs", headers=HOST).text
    assert 'id="not-for-me"' in html and 'id="top-notice"' in html
    for label in top.REASONS.values():
        assert label in html


runner = CliRunner()


def test_top_command_lists_the_board_and_fills_on_request(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"paths:\n  db: {tmp_path}/t.db\n  cv_master: {tmp_path}/master.tex\n"
        f"sources:\n  companies_file: {tmp_path}/none.yaml\nscoring:\n  top_matches_count: 3\n"
    )
    db = connect(tmp_path / "t.db")
    add(db, 1)
    score(db, {"Engineer 1": 90})
    add(db, 4, start=2)
    db.close()
    shown = runner.invoke(app, ["top", "--config", str(cfg_path)])
    assert "Engineer 1" in shown.output and "only 1 of 3" in shown.output
    assert "--fill" in shown.output
    dry = runner.invoke(app, ["top", "--fill", "--dry-run", "--config", str(cfg_path)])
    assert dry.exit_code == 0 and "would score 4 postings in about 1 AI call:" in dry.output
    nothing = (
        connect(tmp_path / "t.db")
        .execute("SELECT COUNT(*) FROM jobs WHERE status = 'passed'")
        .fetchone()[0]
    )
    assert nothing == 4  # a dry run scores nothing
