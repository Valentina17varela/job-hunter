import json
import threading

import pytest
from fastapi.testclient import TestClient

from jobhunter import applications as apps
from jobhunter.db import connect
from jobhunter.models import Job
from jobhunter.store import upsert_jobs
from jobhunter.web.app import create_app
from jobhunter.web.runner import RunManager

HOST = {"host": "testserver"}


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
    assert "Funnel" in html and "titles_include" in html and "Passed filter" in html


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
    assert "titles_include" in html and "engineer" in html and "s-1" in html


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
    assert 'data-build-job="2"' in below and "Build package for this posting" in below
    assert "/run?tailor" not in below  # runs in place, no navigation to the Run page
    assert 'id="build-log"' in below
    assert "Rebuild package" in client.get("/jobs/1", headers=HOST).text  # already packaged


def test_building_one_posting_runs_only_that_posting(env):
    client, _, _, _, started, gate = env
    gate.set()
    res = client.post("/api/runs", json={"id": "tailor", "jobs": [2]}, headers=HOST)
    wait_done(client, res.json()["id"])
    argv = started[-1]
    assert argv[3:6] == ["run", "--stage", "tailor"] and argv.count("--job") == 1
    assert argv[argv.index("--job") + 1] == "2"
