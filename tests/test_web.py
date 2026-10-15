import json
import re
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobhunter import applications as apps
from jobhunter.db import connect
from jobhunter.models import Job
from jobhunter.store import upsert_jobs
from jobhunter.web.app import create_app
from jobhunter.web.runner import RunManager

HOST = {"host": "testserver"}
STATIC_DIR = Path(__file__).resolve().parents[1] / "src" / "jobhunter" / "web" / "static"


class FakeProc:
    def __init__(self, lines, code=0, gate=None):
        self.stdout, self.code, self.gate = iter(lines), code, gate

    def wait(self):
        if self.gate:
            self.gate.wait(5)
        return self.code


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    folder = out / "2026-10-11" / "acme-eng-1"
    folder.mkdir(parents=True)
    (folder / "cv.pdf").write_bytes(b"%PDF-1.4 cv")
    (folder / "notes.md").write_text("# notes")
    (folder / "recruiter_message.md").write_text("Hello <b>there</b>")
    (folder / "meta.json").write_text(
        json.dumps({"language": "en", "cv_pages": 1, "problems": ["letter too long"]})
    )
    (tmp_path / "secret.txt").write_text("top secret")
    cv = tmp_path / "master.tex"
    cv.write_text("% jh:section skills\n% jh:item s-1\n\\item Python\n% jh:endsection\n")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"paths:\n  db: {tmp_path}/t.db\n  out: {out}\n  cv_master: {cv}\n"
        "search:\n  titles_include: [engineer]\n  work_mode: [remote]\n"
        "sources:\n  companies_file: /nonexistent.yaml\n"
    )
    conn = connect(tmp_path / "t.db")
    upsert_jobs(conn, [
        Job(source="greenhouse", external_id="1", company="Acme", title="Senior Engineer",
            description="Build APIs <script>alert(1)</script>", url="https://acme.test/1",
            remote="remote", location="Remote", salary_min=100000, salary_max=150000,
            salary_currency="USD"),
        Job(source="lever", external_id="2", company="Beta", title="Sales Manager",
            description="Sell", url="https://beta.test/2", remote="onsite"),
        Job(source="ashby", external_id="3", company="Gamma", title="Platform Engineer",
            description="Platform", url="https://gamma.test/3", remote="remote"),
    ])  # fmt: skip
    conn.execute("UPDATE jobs SET status='packaged' WHERE id=1")
    conn.execute("UPDATE jobs SET status='filtered', filter_reason='titles_include: x' WHERE id=2")
    conn.execute("UPDATE jobs SET status='selected' WHERE id=3")
    for jid, score in ((1, 91), (3, 78)):
        conn.execute(
            "INSERT INTO scores(job_id, score, reasons, model, profile_hash, prompt_version, "
            "created_at) VALUES (?,?,?,?,?,?,?)",
            (jid, score, json.dumps({"verdict": "apply", "reason": "great fit",
                                     "must_have_match": ["python"], "gaps": ["go"],
                                     "red_flags": ["check <i>residency</i>"]}),
             "haiku", "h", "v", "2026-10-11T10:00:00+00:00"),
        )  # fmt: skip
    conn.execute(
        "INSERT INTO packages(job_id, path, model, created_at, verified) VALUES (1,?,?,?,0)",
        (str(folder), "sonnet", "2026-10-11T11:00:00+00:00"),
    )
    conn.commit()
    started = []
    gate = threading.Event()

    def fake_popen(argv, **kwargs):
        started.append(argv)
        return FakeProc(["line one", "line two"], gate=gate if "--stage" in argv else None)

    manager = RunManager(cfg, tmp_path, popen=fake_popen, python="py")
    client = TestClient(create_app(cfg, allowed_hosts={"testserver"}, runner=manager))
    return client, conn, tmp_path, manager, started, gate


def test_every_page_renders_on_a_populated_database(env):
    client = env[0]
    for url in (
        "/",
        "/jobs",
        "/jobs?status=all",
        "/jobs/1",
        "/jobs/2",
        "/jobs/3",
        "/pipeline",
        "/packages",
        "/run",
        "/settings",
        "/jobs?q=acme&source=greenhouse&min_score=50",
        "/jobs?sort=company",
        "/jobs?sort=recent&mode=remote&page=2",
    ):
        res = client.get(url, headers=HOST)
        assert res.status_code == 200, url
        assert "Job Hunter" in res.text


def test_pages_render_on_an_empty_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"paths:\n  db: {tmp_path}/e.db\n  out: {tmp_path}/out\n")
    client = TestClient(create_app(cfg, allowed_hosts={"testserver"}))
    for url in ("/", "/jobs", "/pipeline", "/packages", "/run", "/settings"):
        assert client.get(url, headers=HOST).status_code == 200, url


def test_dashboard_shows_funnel_and_filter_reasons(env):
    html = env[0].get("/", headers=HOST).text
    assert "From postings to offers" in html and "Match your criteria" in html
    assert "Title is not one of your target roles" in html  # friendly rule names, not ids
    assert "Search for new jobs" in html and "Your pipeline" in html
    assert len(re.findall(r'btn primary" data-run', html)) == 1  # one primary action on Home
    assert re.search(r"(Score|Build) \d+ (posting|package)", html)  # buttons say how much


def test_jobs_filters(env):
    client = env[0]
    active = client.get("/jobs", headers=HOST).text
    assert "Senior Engineer" in active and "Platform Engineer" in active
    assert "Sales Manager" not in active  # filtered out is not "active"
    assert "Sales Manager" in client.get("/jobs?status=filtered", headers=HOST).text
    assert "Platform Engineer" not in client.get("/jobs?min_score=85", headers=HOST).text
    assert "Platform Engineer" in client.get("/jobs?q=gamma", headers=HOST).text
    assert "Senior Engineer" not in client.get("/jobs?source=ashby", headers=HOST).text


def test_job_detail_escapes_untrusted_text_and_shows_explain_and_package(env):
    html = env[0].get("/jobs/1", headers=HOST).text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert "check &lt;i&gt;residency&lt;/i&gt;" in html
    assert "Passes your criteria" in html and "great fit" in html
    assert "/files/2026-10-11/acme-eng-1/cv.pdf" in html and "letter too long" in html
    assert "Hello &lt;b&gt;there&lt;/b&gt;" in html and "Needs review" in html
    assert "Rejected" in env[0].get("/jobs/2", headers=HOST).text
    assert env[0].get("/jobs/999", headers=HOST).status_code == 404


def test_files_are_served_only_from_the_out_directory(env):
    client = env[0]
    ok = client.get("/files/2026-10-11/acme-eng-1/cv.pdf", headers=HOST)
    assert ok.status_code == 200 and ok.headers["content-type"] == "application/pdf"
    assert ok.content.startswith(b"%PDF")
    for bad in (
        "../../secret.txt",
        "..%2F..%2Fsecret.txt",
        "2026-10-11/acme-eng-1/nope.pdf",
        "2026-10-11/acme-eng-1",
    ):
        assert client.get(f"/files/{bad}", headers=HOST).status_code == 404, bad


def test_foreign_host_and_origin_are_rejected(env):
    client = env[0]
    assert client.get("/", headers={"host": "evil.example"}).status_code == 403
    assert (
        client.get(
            "/", headers={"host": "testserver", "origin": "https://evil.example"}
        ).status_code
        == 403
    )
    cross = client.post(
        "/api/jobs/1/stage",
        json={"stage": "applied"},
        headers={"host": "testserver", "origin": "https://evil.example"},
    )
    assert cross.status_code == 403
    assert (
        client.get("/", headers={"host": "testserver", "origin": "http://testserver"}).status_code
        == 200
    )


def test_writes_require_json(env):
    res = env[0].post(
        "/api/jobs/1/stage", content="stage=applied", headers={**HOST, "content-type": "text/plain"}
    )
    assert res.status_code == 415


def test_stage_changes_flow_through_to_the_pipeline_and_dashboard(env):
    client, conn = env[0], env[1]
    assert (
        client.post(
            "/api/jobs/1/stage", json={"stage": "applied", "note": "sent"}, headers=HOST
        ).status_code
        == 200
    )
    assert (
        client.post("/api/jobs/1/stage", json={"stage": "interviewing"}, headers=HOST).status_code
        == 200
    )
    assert conn.execute("SELECT status FROM jobs WHERE id=1").fetchone()[0] == "replied"
    pipeline = client.get("/pipeline", headers=HOST).text
    assert "Interviewing" in pipeline and "Senior Engineer" in pipeline
    assert "Platform Engineer" in pipeline  # still in "Ready to apply"
    assert apps.stats(conn)["funnel"]["interviewing"] == 1
    bad = client.post("/api/jobs/1/stage", json={"stage": "banana"}, headers=HOST)
    assert bad.status_code == 400 and "unknown stage" in bad.json()["error"]


def test_interview_crud_and_notes_and_ignore(env):
    client, conn = env[0], env[1]
    client.post("/api/jobs/1/stage", json={"stage": "screening"}, headers=HOST)
    added = client.post(
        "/api/jobs/1/interviews",
        headers=HOST,
        json={"kind": "technical", "scheduled_at": "2026-10-20T15:00", "notes": "pairing"},
    )
    iid = added.json()["id"]
    assert "pairing" in client.get("/jobs/1", headers=HOST).text
    client.post(f"/api/interviews/{iid}", json={"outcome": "passed"}, headers=HOST)
    assert conn.execute("SELECT outcome FROM interviews").fetchone()[0] == "passed"
    assert "Next:" not in client.get("/pipeline", headers=HOST).text  # no pending interview left
    client.post(f"/api/interviews/{iid}/delete", json={}, headers=HOST)
    assert conn.execute("SELECT COUNT(*) FROM interviews").fetchone()[0] == 0
    assert (
        client.post("/api/jobs/1/notes", json={"notes": "call Tuesday"}, headers=HOST).status_code
        == 200
    )
    assert "call Tuesday" in client.get("/jobs/1", headers=HOST).text
    assert client.post("/api/jobs/3/notes", json={"notes": "x"}, headers=HOST).status_code == 400
    client.post("/api/jobs/3/ignore", json={}, headers=HOST)
    assert conn.execute("SELECT status FROM jobs WHERE id=3").fetchone()[0] == "ignored"


def wait_done(client, run_id):
    for _ in range(200):
        data = client.get(f"/api/runs/{run_id}", headers=HOST).json()
        if data["status"] != "running":
            return data
        threading.Event().wait(0.02)
    raise AssertionError("run did not finish")


def test_runs_are_whitelisted_streamed_and_exclusive(env):
    client, _, tmp, manager, started, gate = env
    assert client.post("/api/runs", json={"id": "rm -rf /"}, headers=HOST).status_code == 400
    assert (
        client.post("/api/runs", json={"id": "doctor", "dry_run": True}, headers=HOST).status_code
        == 400
    )
    assert (
        client.post("/api/runs", json={"id": "fetch", "jobs": [1]}, headers=HOST).status_code == 400
    )
    assert (
        client.post("/api/runs", json={"id": "tailor", "jobs": ["x"]}, headers=HOST).status_code
        == 400
    )
    first = client.post("/api/runs", json={"id": "fetch"}, headers=HOST)
    assert first.status_code == 200
    second = client.post("/api/runs", json={"id": "doctor"}, headers=HOST)
    assert second.status_code == 409  # the first is held open by the gate
    gate.set()
    done = wait_done(client, first.json()["id"])
    assert done["status"] == "ok" and done["log"] == "line one\nline two"
    assert started[0][:6] == ["py", "-m", "jobhunter", "run", "--stage", "fetch"]
    assert started[0][-2:] == ["--config", str(manager.config_path)]
    again = client.get(f"/api/runs/{first.json()['id']}?since=1", headers=HOST).json()
    assert again["log"] == "line two"
    assert client.get("/api/runs/nope", headers=HOST).status_code == 404


def test_tailor_run_options_are_passed_as_separate_arguments(env):
    client, _, _, _, started, gate = env
    gate.set()
    res = client.post(
        "/api/runs",
        headers=HOST,
        json={"id": "tailor", "jobs": [1163, 9478], "limit": 2, "force": True, "dry_run": True},
    )
    wait_done(client, res.json()["id"])
    argv = started[-1]
    assert argv[3:] == [
        "run",
        "--stage",
        "tailor",
        "--dry-run",
        "--job",
        "1163",
        "--job",
        "9478",
        "--limit",
        "2",
        "--force",
        "--config",
        argv[-1],
    ]


def test_run_history_and_log_files(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f"paths:\n  db: {tmp_path}/t.db\n")
    manager = RunManager(
        cfg,
        tmp_path,
        log_dir=tmp_path / "runs",
        popen=lambda argv, **kw: FakeProc(["hello"], code=1),
        python="py",
    )
    run = manager.start("doctor")
    for _ in range(200):
        if run.status != "running":
            break
        threading.Event().wait(0.02)
    assert run.status == "failed" and run.exit_code == 1
    logs = list((tmp_path / "runs").iterdir())
    assert len(logs) == 1 and logs[0].read_text() == "hello\n"
    assert manager.history()[0].id == run.id


def test_health_endpoint_reports_checks(env):
    data = env[0].get("/api/health", headers=HOST).json()
    assert {"python", "config"} <= {c["name"] for c in data}


def test_settings_shows_search_criteria_and_cv_tree(env):
    html = env[0].get("/settings", headers=HOST).text
    assert "What I&#39;m looking for" in html or "What I'm looking for" in html
    assert 'data-cfg="search.titles_include"' in html and "engineer" in html and "s-1" in html
    assert "titles_include" in html and "Roles I want" in html  # editable, with plain labels


# --- regressions found in review ---------------------------------------------------------------


def test_javascript_urls_are_never_rendered_as_links(env):
    client, conn = env[0], env[1]
    conn.execute("UPDATE jobs SET url = 'javascript:alert(1)' WHERE id = 1")
    conn.commit()
    html = client.get("/jobs/1", headers=HOST).text
    assert "javascript:alert" not in html and "Posting link unavailable" in html


def test_search_wildcards_are_literal_and_pagination_links_are_encoded(env):
    client = env[0]
    assert (
        "Senior Engineer" not in client.get("/jobs?q=%25", headers=HOST).text
    )  # '%' is not a wildcard
    assert client.get("/jobs?q=a%26b%23c&page=999999999999", headers=HOST).status_code == 200


def test_empty_interview_fields_become_null_and_bad_types_are_rejected(env):
    client, conn = env[0], env[1]
    client.post("/api/jobs/1/stage", json={"stage": "screening"}, headers=HOST)
    iid = client.post(
        "/api/jobs/1/interviews",
        json={"kind": "recruiter", "scheduled_at": "2026-10-20T10:00"},
        headers=HOST,
    ).json()["id"]
    client.post(f"/api/interviews/{iid}", json={"scheduled_at": "", "notes": ""}, headers=HOST)
    row = conn.execute("SELECT scheduled_at, notes FROM interviews").fetchone()
    assert (row["scheduled_at"], row["notes"]) == (None, None)
    bad = client.post(f"/api/interviews/{iid}", json={"notes": {"x": 1}}, headers=HOST)
    assert bad.status_code == 400


def test_postings_with_an_application_cannot_be_ignored(env):
    client = env[0]
    client.post("/api/jobs/1/stage", json={"stage": "applied"}, headers=HOST)
    res = client.post("/api/jobs/1/ignore", json={}, headers=HOST)
    assert res.status_code == 400 and "has an application" in res.json()["error"]


def test_health_checks_are_cached(env, monkeypatch):
    from jobhunter.web import app as web_app

    calls = []
    monkeypatch.setattr(web_app, "run_checks", lambda path: calls.append(1) or [])
    client = TestClient(web_app.create_app(env[3].config_path, allowed_hosts={"testserver"}))
    client.get("/api/health", headers=HOST)
    client.get("/api/health", headers=HOST)
    assert len(calls) <= 2  # an empty result is re-checked, but a non-empty one is cached


def test_unwritable_log_dir_fails_the_run_instead_of_hanging_the_manager(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    cfg = tmp_path / "c.yaml"
    cfg.write_text("")
    manager = RunManager(
        cfg, tmp_path, log_dir=blocker / "runs", popen=lambda *a, **k: None, python="py"
    )
    run = manager.start("doctor")
    for _ in range(200):
        if run.status != "running":
            break
        threading.Event().wait(0.02)
    assert run.status == "failed" and manager.active() is None


def test_empty_or_invalid_numeric_filters_do_not_break_the_page(env):
    client = env[0]
    for url in (
        "/jobs?min_score=",
        "/jobs?min_score=abc",
        "/jobs?min_score=%20",
        "/jobs?min_score=80",
    ):
        assert client.get(url, headers=HOST).status_code == 200, url
    assert "Platform Engineer" not in client.get("/jobs?min_score=80", headers=HOST).text


def test_any_posting_can_be_packaged_by_hand_from_its_page(env):
    client = env[0]
    below = client.get("/jobs/2", headers=HOST).text  # filtered-out posting
    assert "Build package</button>" in below and "No package yet" in below
    assert "&#34;jobs&#34;: [2]" in below or '"jobs": [2]' in below  # runs only this posting
    assert "/run?tailor" not in below  # runs in place, no navigation to the Actions page
    assert 'id="dock"' in below  # the live log panel exists on every page
    assert "Rebuild package" in client.get("/jobs/1", headers=HOST).text  # already packaged


def test_building_one_posting_runs_only_that_posting(env):
    client, _, _, _, started, gate = env
    gate.set()
    res = client.post("/api/runs", json={"id": "tailor", "jobs": [2]}, headers=HOST)
    wait_done(client, res.json()["id"])
    argv = started[-1]
    assert argv[3:6] == ["run", "--stage", "tailor"] and argv.count("--job") == 1
    assert argv[argv.index("--job") + 1] == "2"


def test_job_list_defaults_to_best_matches_and_shows_cards_with_reasons(env):
    client = env[0]
    html = client.get("/jobs", headers=HOST).text
    assert "Best matches" in html and "great fit" in html  # AI reason on the card
    assert "Sales Manager" not in html  # filtered out is not a best match
    assert "1 thing to verify" in html  # the red flag count is surfaced
    filtered = client.get("/jobs?status=filtered", headers=HOST).text
    assert "Sales Manager" in filtered and "Filtered out" in filtered
    assert "Sales Manager" in client.get("/jobs?status=all", headers=HOST).text
    # legacy raw status values keep working
    assert "Platform Engineer" in client.get("/jobs?status=selected", headers=HOST).text


def test_tabs_show_counts(env):
    html = env[0].get("/jobs", headers=HOST).text
    for label in ("Best matches", "All evaluated", "Applied", "Filtered out", "Everything"):
        assert label in html


def test_dashboard_suggests_next_steps_in_plain_language(env):
    client, conn = env[0], env[1]
    html = client.get("/", headers=HOST).text
    assert "What to do next" in html
    assert "top match has no tailored CV" in html  # job 3 is selected without a package
    assert "package is ready" in html  # job 1 is packaged and not applied yet
    conn.execute("UPDATE jobs SET status = 'passed' WHERE id = 3")
    conn.commit()
    assert "waiting for AI scoring" in client.get("/", headers=HOST).text


def test_dashboard_on_empty_db_invites_the_first_search(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(f"paths:\n  db: {tmp_path}/e.db\n  out: {tmp_path}/out\n")
    html = TestClient(create_app(cfg, allowed_hosts={"testserver"})).get("/", headers=HOST).text
    assert "Run your first search" in html


def test_upcoming_interviews_appear_on_the_dashboard(env):
    client = env[0]
    client.post("/api/jobs/1/stage", json={"stage": "interviewing"}, headers=HOST)
    client.post(
        "/api/jobs/1/interviews",
        headers=HOST,
        json={"kind": "system_design", "scheduled_at": "2026-10-22T09:30"},
    )
    html = client.get("/", headers=HOST).text
    assert "System design" in html and "2026-10-22 09:30" in html


def test_search_is_a_whitelisted_run_that_needs_no_ai(env):
    client, _, _, _, started, gate = env
    gate.set()
    res = client.post("/api/runs", json={"id": "search", "dry_run": True}, headers=HOST)
    assert res.status_code == 200
    wait_done(client, res.json()["id"])
    assert started[-1][3:7] == ["run", "--stage", "search", "--dry-run"]
    page = client.get("/run", headers=HOST).text
    card = page.split('data-spec="search"')[1].split("</section>")[0]
    assert "uses AI" not in card


def test_actions_page_groups_every_command(env):
    html = env[0].get("/run", headers=HOST).text
    for heading in ("Find jobs", "Evaluate with AI", "Apply", "Maintenance"):
        assert heading in html
    assert html.count("data-runcard=") >= 10


def test_suggestion_grammar_and_funnel_scale():
    from jobhunter.web.app import bar_width, plural

    assert plural(1, "package is", "packages are") == "1 package is"
    assert plural(3, "package is", "packages are") == "3 packages are"
    assert bar_width(0, 1000) == 0 and bar_width(5, 0) == 0
    assert bar_width(1000, 1000) == 100
    assert 3 <= bar_width(2, 25000) < bar_width(30, 25000) < bar_width(5000, 25000) < 100


def test_favorites_api_tab_chip_sort_and_badges(env):
    client, conn = env[0], env[1]
    assert client.post("/api/jobs/3/favorite", json={"on": True, "note": "visa?"},
                       headers=HOST).status_code == 200  # fmt: skip
    client.post("/api/jobs/2/favorite", json={"on": True}, headers=HOST)  # a filtered posting
    listing = client.get("/api/favorites", headers=HOST).json()
    assert {f["id"] for f in listing} == {2, 3}
    tab = client.get("/jobs?status=favorites", headers=HOST).text
    assert "Platform Engineer" in tab and "Sales Manager" in tab and "Senior Engineer" not in tab
    assert "visa?" in tab
    chip = client.get("/jobs?status=all&fav=1&sort=favorites", headers=HOST).text
    assert "Platform Engineer" in chip and "Senior Engineer" not in chip
    first = client.get("/jobs?status=all&sort=favorites", headers=HOST).text
    assert first.index("Platform Engineer") < first.index("Senior Engineer")
    assert 'href="/jobs?status=favorites"' in client.get("/jobs", headers=HOST).text
    assert "favorites without an application" in client.get("/", headers=HOST).text
    page = client.get("/jobs/3", headers=HOST).text
    assert 'aria-pressed="true"' in page and "Block this company" in page
    conn.execute("UPDATE jobs SET status='closed' WHERE id=3")
    conn.commit()
    assert "Closed" in client.get("/jobs/3", headers=HOST).text
    client.post("/api/jobs/3/favorite", json={"on": False}, headers=HOST)
    assert {f["id"] for f in client.get("/api/favorites", headers=HOST).json()} == {2}


def test_favorite_api_validates_input(env):
    client = env[0]
    assert client.post("/api/jobs/1/favorite", json={}, headers=HOST).status_code == 400
    assert client.post("/api/jobs/1/favorite", json={"on": True, "note": 5},
                       headers=HOST).status_code == 400  # fmt: skip
    assert client.post("/api/jobs/99/favorite", json={"on": True},
                       headers=HOST).status_code == 400  # fmt: skip


def test_block_company_writes_config_keeps_comments_and_shows_badges(env):
    client, tmp = env[0], env[2]
    cfg = tmp / "config.yaml"
    cfg.write_text(cfg.read_text() + "# keep me\n")
    res = client.post("/api/config", json={"updates": {"search": {"companies_exclude": ["Gamma"]}}},
                      headers=HOST)  # fmt: skip
    assert res.status_code == 200
    text = cfg.read_text()
    assert "Gamma" in text and "# keep me" in text
    client.post("/api/jobs/3/favorite", json={"on": True}, headers=HOST)
    assert "Blocked company" in client.get("/jobs/3", headers=HOST).text
    assert "Blocked company" in client.get("/jobs?status=favorites", headers=HOST).text
    assert "Block this company" not in client.get("/jobs/3", headers=HOST).text
    assert "Gamma" in client.get("/settings", headers=HOST).text


def test_below_threshold_is_explained_as_the_ai_match_score_not_salary(env):
    client, conn = env[0], env[1]
    conn.execute("UPDATE jobs SET status = 'below_threshold' WHERE id = 3")
    conn.execute("UPDATE scores SET score = 60 WHERE job_id = 3")
    conn.commit()
    html = client.get("/jobs/3", headers=HOST).text
    assert (
        "below your best-match threshold of 75" in html
        and "not your salary or location criteria" in html
    )
    assert "Below match score" in html
    assert "Below match score" in client.get("/jobs?status=below_threshold", headers=HOST).text


def test_add_posting_api_and_pages(env):
    client = env[0]
    body = {"title": "Go Engineer", "company": "Delta", "description": "Write Go."}
    res = client.post("/api/postings", json=body, headers=HOST)
    assert res.status_code == 200 and res.json()["created"]
    url = res.json()["url"]
    page = client.get(url, headers=HOST).text
    assert "Manual" in page and "Score this posting</button>" in page
    assert "Manual" in client.get("/jobs?status=all", headers=HOST).text
    again = client.post("/api/postings", json=body, headers=HOST).json()
    assert not again["created"]
    bad = client.post("/api/postings", json={**body, "title": ""}, headers=HOST)
    assert bad.status_code == 422 and "error" in bad.json()
    assert client.post("/api/postings", content="x", headers=HOST).status_code >= 400
    assert 'id="add-posting"' in client.get("/", headers=HOST).text


def test_fetch_posting_api_refuses_private_hosts(env):
    client = env[0]
    res = client.post("/api/postings/fetch", json={"url": "http://127.0.0.1/x"}, headers=HOST)
    assert res.status_code == 422
    assert client.post("/api/postings/fetch", json={}, headers=HOST).status_code == 400


# --- redesign smoke tests (spec 18 §7) ---------------------------------------------------------

PAGES = ("/", "/jobs", "/jobs?status=all", "/jobs/1", "/jobs/2", "/jobs/3", "/pipeline",
         "/packages", "/run", "/settings")  # fmt: skip


def _unlabelled_controls(html: str) -> list[str]:
    import re

    labels_for = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', html))
    bad = []
    for match in re.finditer(r"<(input|select|textarea)\b([^>]*)>", html):
        tag, attrs = match.groups()
        if re.search(r'type="(hidden|submit|button)"', attrs):
            continue
        if re.search(r'aria-label(ledby)?="', attrs):
            continue
        ident = re.search(r'\bid="([^"]+)"', attrs)
        if ident and ident.group(1) in labels_for:
            continue
        before = html[: match.start()]
        # wrapped by a <label> that is still open
        if before.rfind("<label") > before.rfind("</label>"):
            continue
        bad.append(f"<{tag}{attrs[:60]}")
    return bad


def test_no_page_loads_anything_from_outside(env):
    import re

    client = env[0]
    for url in PAGES:
        html = client.get(url, headers=HOST).text
        assert not re.search(r'<(script|img|iframe)[^>]+src="(https?:)?//', html), url
        assert not re.search(r'<link[^>]+href="(https?:)?//', html), url
        assert not re.search(r'url\(["\']?(https?:)?//', html), url
    for sheet in ("/static/style.css", "/static/tokens.css"):
        css = client.get(sheet, headers=HOST).text
        assert not re.search(r'url\(["\']?(https?:)?//', css), sheet
        assert "@import" not in css


def test_every_page_has_one_h1_and_labelled_controls(env):
    client = env[0]
    for url in PAGES:
        html = client.get(url, headers=HOST).text
        assert html.count("<h1") == 1, url
        bad = _unlabelled_controls(html)
        assert bad == [], (url, bad)


def test_font_and_logo_files_exist_and_are_served(env):
    import re

    client = env[0]
    css = client.get("/static/tokens.css", headers=HOST).text
    paths = re.findall(r'url\("(/static/[^"]+)"\)', css)
    assert paths and all(client.get(p, headers=HOST).status_code == 200 for p in paths)
    html = client.get("/", headers=HOST).text
    for path in re.findall(r'(?:src|href)="(/static/[^"]+)"', html):
        assert client.get(path, headers=HOST).status_code == 200, path


def test_light_is_the_default_theme(env):
    client = env[0]
    css = client.get("/static/tokens.css", headers=HOST).text
    assert "prefers-color-scheme" not in css and 'data-theme="dark"' in css
    assert 'data-theme="dark"' not in client.get("/", headers=HOST).text


def test_settings_shows_key_status_without_the_value(env, monkeypatch):
    monkeypatch.setenv("THEMUSE_API_KEY", "super-secret-value")
    html = env[0].get("/settings", headers=HOST).text
    assert "THEMUSE_API_KEY" in html and "<b>set</b>" in html
    assert "super-secret-value" not in html
    monkeypatch.delenv("THEMUSE_API_KEY")
    html = env[0].get("/settings", headers=HOST).text
    assert "not set" in html and "(optional)" in html


def test_an_applied_posting_shows_one_applied_label_not_two(env):
    client, conn, *_ = env
    apps.set_stage(conn, 3, "applied", None)
    card = client.get("/jobs?status=applied", headers=HOST).text
    assert card.count(">Applied<") == 1  # one badge on the card (it used to be two)
    page = client.get("/jobs/3", headers=HOST).text
    chips = page.split('<div class="chips">')[1].split("</div>")[0]
    assert chips.count("Applied") == 1
    apps.set_stage(conn, 3, "interviewing", None)  # a different stage still gets its own chip
    chips = (
        client.get("/jobs/3", headers=HOST).text.split('<div class="chips">')[1].split("</div>")[0]
    )
    assert "Interviewing" in chips


def test_source_filter_lists_every_enabled_source_even_before_anything_is_fetched(env):
    client = env[0]
    html = client.get("/jobs", headers=HOST).text
    select = html.split('name="source"')[1].split("</select>")[0]
    for label in ("Get on Board", "Himalayas", "The Muse", "Greenhouse", "Lever", "Ashby"):
        assert label in select
    assert "Get on Board (none fetched yet)" in select
    assert "Greenhouse (1)" in select  # sources with postings show their count
    filtered = client.get("/jobs?status=all&source=ashby", headers=HOST).text
    assert "Platform Engineer" in filtered and "Senior Engineer" not in filtered


def test_home_points_to_sources_that_exist_but_are_not_enabled(env, tmp_path):
    client = env[0]
    html = client.get("/", headers=HOST).text
    assert "available but not enabled" not in html  # the default config has them all on
    cfg_path = next(tmp_path.glob("config.yaml"))
    cfg_path.write_text(cfg_path.read_text() + "  aggregators: [remotive]\n")
    html = client.get("/", headers=HOST).text
    assert "available but not enabled" in html and "Get on Board" in html and "Himalayas" in html
    assert "/settings#sources" in html


# --- freshness filter and live filtering (spec 23) -------------------------------------------


def _date_postings(conn):
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    for job_id, days in ((1, 2), (3, 20)):  # Senior Engineer 2 days old, Platform Engineer 20
        conn.execute(
            "UPDATE jobs SET posted_at = ? WHERE id = ?",
            ((now - timedelta(days=days)).isoformat(), job_id),
        )
    conn.execute("UPDATE jobs SET posted_at = NULL WHERE id = 2")  # Sales Manager: undated
    conn.commit()


def test_fresh_filter_keeps_recent_and_undated_postings_and_drops_older_ones(env):
    client, conn, *_ = env
    _date_postings(conn)
    week = client.get("/jobs?status=all&fresh=7", headers=HOST).text
    assert "Senior Engineer" in week and "Sales Manager" in week  # recent + undated
    assert "Platform Engineer" not in week  # 20 days old
    month = client.get("/jobs?status=all&fresh=30", headers=HOST).text
    assert "Platform Engineer" in month
    for bad in ("0", "-3", "abc", "99999", ""):
        page = client.get(f"/jobs?status=all&fresh={bad}", headers=HOST).text
        assert "Platform Engineer" in page, bad  # an invalid value is ignored, not an error


def test_fresh_filter_combines_with_other_filters_and_turns_the_board_off(env):
    client, conn, *_ = env
    _date_postings(conn)
    page = client.get("/jobs?status=all&fresh=30&source=lever", headers=HOST).text
    assert "Sales Manager" in page and "Senior Engineer" not in page
    best = client.get("/jobs?status=best", headers=HOST).text
    filtered = client.get("/jobs?status=best&fresh=7", headers=HOST).text
    assert 'id="top-board"' in best and 'id="top-board"' not in filtered


def test_posted_control_lists_the_options_and_marks_the_configured_rule(env):
    client = env[0]
    html = client.get("/jobs?fresh=14", headers=HOST).text
    select = html.split('name="fresh"')[1].split("</select>")[0]
    assert "Any time" in select and "last 7 days" in select
    assert "last 30 days (your rule)" in select  # max_age_days defaults to 30
    assert select.count("last 30 days") == 1  # no duplicate when the rule is a standard option
    assert 'value="14" selected' in select


def test_filters_form_one_connected_bar_that_applies_live(env):
    client = env[0]
    html = client.get("/jobs", headers=HOST).text
    form = html.split('<form class="filterbar"')[1].split("</form>")[0]
    for label in ("Source", "Posted", "Score", "Mode", "Sort", "Favorites"):
        assert label in form, label
    assert "<noscript>" in form and "Filter</button>" not in form  # no Filter button any more
    assert 'id="jobs-results"' in html
    js = client.get("/static/app.js", headers=HOST).text
    assert "jobs-results" in js and "setTimeout(refresh, 300)" in js and "replaceState" in js
    assert "data-clear" in js
    assert "form.filterbar" in js  # the script must target the form the template renders


def test_static_files_are_versioned_so_a_cached_script_cannot_hide_the_new_behaviour(env):
    import re

    html = env[0].get("/jobs", headers=HOST).text
    for name in ("app.js", "style.css", "tokens.css"):
        assert re.search(rf"/static/{re.escape(name)}\?v=\d+", html), name


def test_active_filters_are_shown_as_removable_chips_and_score_is_a_choice(env):
    client = env[0]
    url = "/jobs?status=all&source=ashby&fresh=7&min_score=75&q=platform"
    page = client.get(url, headers=HOST).text
    chips = page.split('class="active-filters"')[1].split("</div>")[0]
    for text in ("Source: Ashby", "Posted: last 7 days", "Score 75+", "“platform”"):
        assert text in chips
    assert chips.count("data-clear=") == 4 and "data-clear-all" in chips
    assert "75+ (your threshold)" in page  # the threshold is one of the options
    assert 'class="active-filters"' not in client.get("/jobs?status=all", headers=HOST).text
    # the score control makes no sense on the filtered-out tab, which has no scores
    assert 'name="min_score"' not in client.get("/jobs?status=filtered", headers=HOST).text


def test_settings_points_to_the_posted_filter(env):
    html = env[0].get("/settings", headers=HOST).text
    assert "Posted</b> filter" in html


# --- accessibility and theming floor (spec 24, slice 2) -----------------------------------------


def test_settings_labels_are_associated_with_their_controls(env):
    import re

    html = env[0].get("/settings", headers=HOST).text
    labels = re.findall(r'<label class="flabel" for="(f-\d+)"', html)
    assert len(labels) >= 20
    for fid in labels:
        assert f'id="{fid}"' in html or f'data-input-id="{fid}"' in html, fid  # a target exists
    assert html.count("<legend") >= 3  # checkbox groups are fieldsets with a legend
    assert 'aria-label="Freshness for company boards, in days"' in html
    hinted = re.findall(r'aria-describedby="(f-\d+-hint)"', html) + re.findall(
        r'data-desc="(f-\d+-hint)"', html
    )
    assert hinted and all(f'id="{h}"' in html for h in hinted)  # hints are real elements
    js = env[0].get("/static/app.js", headers=HOST).text
    assert "box.dataset.inputId" in js and "box.dataset.label" in js  # the tag input is named


def test_interview_controls_have_names(env):
    client, conn, *_ = env
    apps.set_stage(conn, 3, "applied", None)
    apps.add_interview(conn, 3, "technical", "2026-10-20T10:00", "bring examples")
    html = client.get("/jobs/3", headers=HOST).text
    for text in ("Interview 1: kind", "Interview 1: date and time", "Interview 1: outcome",
                 "Interview 1: notes", "New interview: kind", "New interview: notes"):  # fmt: skip
        assert f'aria-label="{text}"' in html, text


def test_page_chrome_has_skip_link_landmarks_and_current_page(env):
    client = env[0]
    html = client.get("/jobs", headers=HOST).text
    assert 'class="skip-link" href="#main"' in html and '<main id="main"' in html
    assert '<nav aria-label="Main">' in html and 'aria-label="Job Hunter"' in html
    assert html.count('aria-current="page"') == 1
    assert ">Job matches" in html.split('aria-current="page"')[1][:300]
    assert 'id="theme-toggle"' in html and 'aria-pressed="false"' in html


def test_announcements_and_status_regions(env):
    client = env[0]
    html = client.get("/jobs", headers=HOST).text
    assert 'id="toast" class="toast" role="status" aria-live="polite"' in html
    assert 'id="jobs-live"' in html and 'aria-live="polite"' in html
    settings = client.get("/settings", headers=HOST).text
    assert 'class="save-state' in settings and 'role="status" aria-live="polite"' in settings
    js = client.get("/static/app.js", headers=HOST).text
    assert "jobs-live" in js  # the filter count is announced after each live refresh


def test_score_ring_star_and_icons_have_accessible_names(env):
    client = env[0]
    html = client.get("/jobs?status=all", headers=HOST).text
    assert 'role="img" aria-label="AI match score 91 of 100"' in html
    assert 'class="star' in html and 'aria-label="Favorite"' in html
    assert '<svg class="ic" aria-hidden="true" focusable="false">' in html
    assert 'rel="noopener"' in client.get("/packages", headers=HOST).text


def test_theme_is_applied_before_first_paint_and_the_toggle_keeps_the_key(env):
    client = env[0]
    html = client.get("/", headers=HOST).text
    head = html.split("</head>")[0]
    assert "/static/theme.js" in head  # blocking, in <head>, before the body paints
    theme = client.get("/static/theme.js", headers=HOST).text
    assert "jh_theme" in theme and "data-theme" in theme
    assert "jh_theme" in client.get("/static/app.js", headers=HOST).text


def test_css_honours_reduced_motion_and_minimum_target_sizes():
    css = (STATIC_DIR / "style.css").read_text()
    assert "prefers-reduced-motion: reduce" in css and "animation: none" in css
    for selector in (".star", ".icon-btn", ".afchip button", ".tag button"):
        block = css.split(f"{selector} {{")[1].split("}")[0]
        assert "1.5rem" in block, f"{selector} must be at least 24px (1.5rem)"
    assert ".skip-link:focus" in css and ".sr-only" in css


def test_unknown_pages_get_a_real_404_and_the_api_keeps_json(env):
    client = env[0]
    page = client.get("/nope", headers=HOST)
    assert page.status_code == 404 and "Page not found" in page.text
    assert page.text.count("<h1") == 1 and 'href="/"' in page.text
    api = client.get("/api/nope", headers=HOST)
    assert api.status_code == 404 and api.json()["error"]
    missing = client.get("/jobs/99999", headers=HOST)
    assert missing.status_code == 404 and "Posting not found" in missing.text


def test_static_cache_headers(env):
    client = env[0]
    html = client.get("/").text
    assert 'rel="preload" href="/static/fonts/PlusJakartaSans.woff2"' in html
    versioned = re.search(r'href="(/static/style\.css\?v=\d+)"', html).group(1)
    assert "immutable" in client.get(versioned).headers["cache-control"]
    assert client.get("/static/style.css").headers["cache-control"] == "no-cache"
    assert "max-age" in client.get("/static/fonts/PlusJakartaSans.woff2").headers["cache-control"]


def test_reload_keeps_place():
    js = (Path(__file__).parents[1] / "src/jobhunter/web/static/app.js").read_text()
    assert js.count("location.reload()") == 1  # only inside reloadHere
    assert "jh_place" in js


def test_job_cards_are_quiet_and_dismissal_is_one_action(env):
    html = env[0].get("/jobs?status=best", headers=HOST).text
    assert ">Hide<" not in html and "data-not-for-me" in html  # Hide merged into Not for me
    assert 'class="more"' in html  # secondary actions live in an overflow menu
    assert len(re.findall(r'btn small primary" (?:data-run|href)', html)) == 0  # none per card


def test_posting_page_has_one_primary_and_a_workspace(env):
    page = env[0].get("/jobs/3", headers=HOST).text
    assert len(re.findall(r'class="btn primary" (?:data-run|href)', page)) == 1
    assert 'class="more"' in page and "workspace" in page
    h1 = re.search(r"<h1>(.*?)</h1>", page, re.S).group(1)
    assert "star" not in h1  # the star left the title


def test_settings_has_one_save_bar_and_real_tabs(env):
    page = env[0].get("/settings", headers=HOST).text
    assert page.count("data-save-cfg") == 2  # Save and Save & re-filter, once for the whole page
    assert 'id="savebar"' in page and 'aria-label="Settings sections"' in page
    for panel in ("looking", "ai", "sources", "files", "system"):
        assert f'id="{panel}"' in page


def test_applications_board_has_four_stage_columns_and_a_ready_strip(env):
    apps.set_stage(env[1], 3, "applied", None)
    page = env[0].get("/pipeline", headers=HOST).text
    assert "ready-strip" in page or "Nothing waiting" in page and 'class="column ready"' not in page
    assert page.count('class="column stage-') >= 4
    assert re.search(r"applied (today|yesterday|\d+ days ago)", page)  # not a raw timestamp


def test_ago_filter():
    from jobhunter.web.app import ago

    now = datetime.now(UTC)
    assert ago(now.isoformat()) == "today"
    assert ago((now - timedelta(days=1)).isoformat()) == "yesterday"
    assert ago((now - timedelta(days=5)).isoformat()) == "5 days ago"
    assert ago(None) == "—"
