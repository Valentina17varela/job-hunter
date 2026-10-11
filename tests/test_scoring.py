import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jobhunter import latex
from jobhunter.cli import app
from jobhunter.config import Config
from jobhunter.db import connect
from jobhunter.llm import LlmClient, LlmError, LlmResponse
from jobhunter.models import Job
from jobhunter.scoring import (
    build_system_prompt,
    posting_block,
    profile_hash,
    score_stage,
    truncate_description,
)
from jobhunter.store import upsert_jobs

CV = (Path(__file__).parent / "fixtures" / "master_marked.tex").read_text()


@pytest.fixture
def doc():
    return latex.parse(CV)


@pytest.fixture
def conn(tmp_path):
    return connect(tmp_path / "t.db")


def cfg(**scoring) -> Config:
    return Config.model_validate(
        {
            "scoring": {"batch_size": 2, "score_threshold": 75, **scoring},
            "tailoring": {"max_packages_per_day": 2},
        }
    )


def add_jobs(conn, n, status="passed"):
    upsert_jobs(
        conn,
        [Job(source="s", external_id=str(i), company=f"Co{i}", title=f"Engineer {i}",
             description=f"Python role {i}", url="u", remote="remote") for i in range(1, n + 1)],
    )  # fmt: skip
    conn.execute("UPDATE jobs SET status = ?", (status,))
    conn.commit()


class FakeScorer:
    """Scores postings from a {title: (score, verdict)} map; unknown ids are omitted on demand."""

    def __init__(self, scores, omit=(), fail=None):
        self.scores, self.omit, self.fail, self.calls, self.systems = scores, set(omit), fail, 0, []

    def complete(self, *, system, prompt, schema, model):
        self.calls += 1
        self.systems.append(system)
        if self.fail:
            raise self.fail
        blocks = json.loads(prompt.split("\n\n", 1)[1])
        results = []
        for b in blocks:
            if b["id"] in self.omit:
                continue
            score, verdict = self.scores.get(b["title"], (50, "maybe"))
            flags = ["needs US work authorization"] if score < 40 else []
            results.append(
                {
                    "id": b["id"],
                    "score": score,
                    "verdict": verdict,
                    "reason": "r",
                    "red_flags": flags,
                }
            )
        return LlmResponse(data={"results": results}, model=model, tokens_in=10, tokens_out=5)


def run(conn, backend, config, doc, max_calls=50):
    client = LlmClient(conn, backend, max_calls=max_calls, sleep=lambda s: None)
    return score_stage(conn, client, config, doc), client


def statuses(conn):
    return {r["title"]: r["status"] for r in conn.execute("SELECT title, status FROM jobs")}


def test_scores_in_batches_and_applies_threshold_and_top_n(conn, doc):
    add_jobs(conn, 5)
    backend = FakeScorer({
        "Engineer 1": (92, "apply"), "Engineer 2": (88, "apply"), "Engineer 3": (80, "apply"),
        "Engineer 4": (60, "maybe"), "Engineer 5": (95, "skip"),
    })  # fmt: skip
    summary, _ = run(conn, backend, cfg(), doc)
    assert backend.calls == 3  # 5 postings, batch size 2
    assert (summary.scored, summary.failed, summary.calls) == (5, 0, 3)
    got = statuses(conn)
    assert got["Engineer 1"] == "selected" and got["Engineer 2"] == "selected"  # top 2 (max 2/day)
    assert got["Engineer 3"] == "scored"  # above threshold but no slot left today
    assert got["Engineer 4"] == "below_threshold"
    assert got["Engineer 5"] == "below_threshold"  # verdict skip beats a high score
    row = conn.execute(
        "SELECT score, reasons, content_hash FROM scores WHERE score = 60"
    ).fetchone()
    assert json.loads(row["reasons"])["verdict"] == "maybe" and row["content_hash"]


def test_second_run_makes_no_calls_and_leftover_gets_a_slot_after_packaging(conn, doc):
    add_jobs(conn, 3)
    backend = FakeScorer({"Engineer 1": (92, "apply"), "Engineer 2": (88, "apply"),
                          "Engineer 3": (80, "apply")})  # fmt: skip
    run(conn, backend, cfg(), doc)
    calls = backend.calls
    summary, _ = run(conn, backend, cfg(), doc)
    assert backend.calls == calls and summary.candidates == 0
    conn.execute("UPDATE jobs SET status = 'packaged' WHERE title = 'Engineer 1'")
    conn.commit()
    run(conn, backend, cfg(), doc)  # next day: a slot is free
    assert statuses(conn)["Engineer 3"] == "selected"


def test_changed_candidate_context_invalidates_the_cache(conn, doc):
    add_jobs(conn, 1)
    backend = FakeScorer({"Engineer 1": (90, "apply")})
    run(conn, backend, cfg(), doc)
    run(conn, backend, cfg(), doc)
    assert backend.calls == 1  # unchanged inputs: cached
    run(conn, backend, cfg(candidate_context="Contractor in Colombia"), doc)  # stale → re-scored
    assert backend.calls == 2
    assert "Contractor in Colombia" in backend.systems[1]


def test_missing_ids_become_score_failed_and_are_retried(conn, doc):
    add_jobs(conn, 2)
    first = FakeScorer({}, omit={1})
    summary, _ = run(conn, first, cfg(batch_size=2), doc)
    assert summary.scored == 1 and summary.failed == 1
    assert statuses(conn)["Engineer 1"] == "score_failed"
    summary, _ = run(conn, FakeScorer({"Engineer 1": (90, "apply")}), cfg(batch_size=2), doc)
    assert summary.scored == 1 and statuses(conn)["Engineer 1"] == "selected"


def test_failed_call_marks_batch_score_failed_without_stopping(conn, doc):
    add_jobs(conn, 3)
    summary, _ = run(conn, FakeScorer({}, fail=LlmError("boom")), cfg(), doc)
    assert summary.failed == 3
    assert set(statuses(conn).values()) == {"score_failed"}


def test_call_cap_stops_cleanly_and_leaves_the_rest_pending(conn, doc):
    add_jobs(conn, 6)
    summary, _ = run(conn, FakeScorer({}), cfg(), doc, max_calls=1)
    assert summary.scored == 2 and summary.stopped and "cap of 1" in summary.stopped
    assert list(statuses(conn).values()).count("passed") == 4


def test_oversized_profile_is_rejected_with_a_clear_message(conn, doc):
    add_jobs(conn, 1)
    with pytest.raises(LlmError, match="max_profile_tokens"):
        run(conn, FakeScorer({}), cfg(max_profile_tokens=10), doc)


def test_system_prompt_has_cv_context_and_no_contact_details(doc):
    system = build_system_prompt(doc, cfg(candidate_context="Lives in Colombia"))
    assert "Lives in Colombia" in system and "[exp-acme-1]" in system
    assert "jane@example.com" not in system and "Jane Doe" not in system
    assert profile_hash(system) != profile_hash(system + " ")


def test_truncate_keeps_start_and_requirements_section():
    body = "Intro. " * 400 + "\nRequirements\n" + "Must know Python. " * 50 + "Blah. " * 2000
    out = truncate_description(body, 300)
    assert len(out) <= 300 * 4 + 20
    assert out.startswith("Intro.") and "Requirements" in out and "[...]" in out
    assert truncate_description("short", 300) == "short"


def test_posting_block_includes_flags_and_salary(conn):
    job = Job(source="s", external_id="1", company="C", title="T", url="u")
    job.salary_min, job.salary_max, job.salary_currency = 90000, 120000, "USD"
    upsert_jobs(conn, [job])
    conn.execute("UPDATE jobs SET filter_flags = 'no_salary,unknown_mode'")
    block = posting_block(conn.execute("SELECT * FROM jobs").fetchone(), 100)
    assert block["salary"] == "90000-120000 USD per year"
    assert block["filter_flags"] == ["no_salary", "unknown_mode"]


# --- CLI ---------------------------------------------------------------------------------------

runner = CliRunner()


def write_cfg(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        f"paths:\n  db: {tmp_path}/t.db\n  cv_master: {tmp_path}/master.tex\n"
        f"sources:\n  companies_file: {tmp_path}/none.yaml\n"
    )
    return str(path)


def test_cv_check_reports_structure_and_errors(tmp_path):
    config = write_cfg(tmp_path)
    missing = runner.invoke(app, ["cv", "check", "--config", config])
    assert missing.exit_code == 1 and "not found" in missing.output
    (tmp_path / "master.tex").write_text("% jh:section s\n")
    broken = runner.invoke(app, ["cv", "check", "--config", config])
    assert broken.exit_code == 1 and "endsection" in broken.output


def test_cv_init_writes_a_marked_copy(tmp_path):
    src = tmp_path / "cv.tex"
    src.write_text("\\begin{document}\n\\section{Skills}\n\\begin{itemize}\n\\item Python\n"
                   "\\end{itemize}\n\\end{document}\n")  # fmt: skip
    result = runner.invoke(app, ["cv", "init", str(src)])
    assert result.exit_code == 0
    marked = (tmp_path / "cv.marked.tex").read_text()
    assert "% jh:section skills" in marked and "% jh:item skills-1" in marked
    assert latex.parse(marked).ids() == ["skills-1"]


def test_run_score_stage_with_a_broken_cv_fails_cleanly(tmp_path):
    config = write_cfg(tmp_path)
    (tmp_path / "master.tex").write_text("% jh:item x\n")
    result = runner.invoke(app, ["run", "--stage", "score", "--config", config])
    assert result.exit_code == 1 and "outside a section" in result.output


def test_full_run_skips_scoring_when_there_is_no_cv(tmp_path):
    config = write_cfg(tmp_path)
    result = runner.invoke(app, ["run", "--stage", "filter", "--config", config])
    assert result.exit_code == 0
    skipped = runner.invoke(app, ["run", "--dry-run", "--config", config])
    assert "score" in skipped.stdout


def test_calibrate_records_answers(tmp_path):
    config = write_cfg(tmp_path)
    conn = connect(tmp_path / "t.db")
    add_jobs(conn, 1)
    conn.execute(
        "INSERT INTO scores(job_id, score, reasons, model, profile_hash, prompt_version, "
        "created_at) VALUES (1, 90, ?, 'm', 'h', 'v', 'now')",
        (json.dumps({"verdict": "apply", "reason": "good", "red_flags": []}),),
    )
    conn.execute("UPDATE jobs SET status = 'selected'")
    conn.commit()
    conn.close()
    result = runner.invoke(app, ["calibrate", "--config", config], input="y\n")
    assert result.exit_code == 0, result.output
    assert "agreement on 'apply' verdicts so far: 1/1" in result.stdout
    again = runner.invoke(app, ["calibrate", "--config", config])
    assert "nothing to calibrate" in again.stdout


def test_rubric_only_flags_explicit_blockers():
    from jobhunter.scoring import RUBRIC

    assert "ONLY when the posting explicitly states" in RUBRIC
    assert "Do NOT infer a blocker from the location alone" in RUBRIC


def test_cv_translate_refuses_to_overwrite_reviewed_edits(tmp_path):
    cv_dir = tmp_path / "cv"
    cv_dir.mkdir()
    (cv_dir / "master.tex").write_text(CV)
    existing = cv_dir / "translations" / "es.json"
    existing.parent.mkdir()
    existing.write_text('{"units": {}}')
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"paths:\n  db: {tmp_path}/t.db\n  cv_master: {cv_dir / 'master.tex'}\n")
    result = runner.invoke(app, ["cv", "translate", "--lang", "es", "--config", str(cfg)])
    assert result.exit_code == 1 and "already exists" in result.output
    assert existing.read_text() == '{"units": {}}'
