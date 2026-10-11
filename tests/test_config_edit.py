import pytest
import yaml
from fastapi.testclient import TestClient

from jobhunter.config import load_config
from jobhunter.config_edit import ConfigUpdateError, save_updates
from jobhunter.db import connect
from jobhunter.models import Job
from jobhunter.store import upsert_jobs
from jobhunter.tailoring import delete_packages
from jobhunter.web.app import create_app

HOST = {"host": "testserver"}

SAMPLE = """\
# My settings — keep this comment
search:
  # roles I want
  titles_include: ["backend", "python"]   # inline comment
  titles_exclude:
    - intern
    - junior
  seniority: ["mid", "senior"]
  salary:
    min_usd: 80000   # annual
    on_missing: pass
scoring:
  score_threshold: 75
"""


@pytest.fixture
def cfg_path(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(SAMPLE)
    return path


def test_updates_are_applied_and_comments_survive(cfg_path):
    save_updates(
        cfg_path,
        {"search": {"titles_include": ["backend", "golang"], "salary": {"min_usd": 90000}}},
    )
    text = cfg_path.read_text()
    assert "# My settings — keep this comment" in text and "# roles I want" in text
    assert "# annual" in text  # comment next to an edited value is kept
    config = load_config(cfg_path)
    assert config.search.titles_include == ["backend", "golang"]
    assert config.search.salary.min_usd == 90000 and config.search.salary.on_missing == "pass"
    assert config.scoring.score_threshold == 75  # untouched sections stay as they were


def test_list_style_is_preserved_inline_vs_block(cfg_path):
    save_updates(cfg_path, {"search": {"titles_include": ["a", "b"], "titles_exclude": ["x", "y"]}})
    text = cfg_path.read_text()
    assert 'titles_include: ["a", "b"]' in text or "titles_include: [a, b]" in text
    assert "titles_exclude:\n    - x\n    - y" in text  # block list stays block


def test_a_backup_is_kept_and_the_write_is_atomic(cfg_path):
    save_updates(cfg_path, {"scoring": {"score_threshold": 80}})
    assert (cfg_path.parent / "config.yaml.bak").read_text() == SAMPLE
    assert not list(cfg_path.parent.glob(".config.yaml.*.tmp"))


def test_invalid_values_are_rejected_with_field_names_and_nothing_is_written(cfg_path):
    with pytest.raises(ConfigUpdateError) as exc:
        save_updates(
            cfg_path,
            {
                "search": {"salary": {"on_missing": "banana"}},
                "scoring": {"score_threshold": "high"},
            },
        )
    fields = {e["field"] for e in exc.value.errors}
    assert {"search.salary.on_missing", "scoring.score_threshold"} <= fields
    assert cfg_path.read_text() == SAMPLE and not (cfg_path.parent / "config.yaml.bak").exists()


def test_unknown_keys_and_forbidden_sections_are_rejected(cfg_path):
    with pytest.raises(ConfigUpdateError, match="cannot be edited"):
        save_updates(cfg_path, {"paths": {"db": "/etc/passwd"}})
    with pytest.raises(ConfigUpdateError):
        save_updates(cfg_path, {"search": {"nonsense": 1}})
    assert cfg_path.read_text() == SAMPLE


def test_saving_into_a_missing_or_empty_config_creates_it(tmp_path):
    path = tmp_path / "new.yaml"
    save_updates(path, {"search": {"titles_include": ["x"]}})
    assert yaml.safe_load(path.read_text())["search"]["titles_include"] == ["x"]
    empty = tmp_path / "empty.yaml"
    empty.write_text("")
    save_updates(empty, {"budget": {"max_llm_calls_per_run": 5}})
    assert load_config(empty).budget.max_llm_calls_per_run == 5


def test_null_values_roundtrip(cfg_path):
    save_updates(cfg_path, {"search": {"max_age_days_ats": 120}})
    assert load_config(cfg_path).search.max_age_days_ats == 120
    save_updates(cfg_path, {"search": {"max_age_days_ats": None}})
    assert load_config(cfg_path).search.max_age_days_ats is None


# --- API -----------------------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cv = tmp_path / "master.tex"
    cv.write_text("% jh:section s\n% jh:item a\n• one\n% jh:endsection\n")
    letter = tmp_path / "letter.tex"
    letter.write_text("%%DATE%% %%COMPANY%% %%SUBJECT%% %%GREETING%% %%BODY%% %%CLOSING%%")
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        SAMPLE + f"paths:\n  db: {tmp_path}/t.db\n  out: {tmp_path}/out\n  cv_master: {cv}\n"
        f"  letter_template: {letter}\nsources:\n  candidates_file: {tmp_path}/cands.txt\n"
    )
    return TestClient(create_app(cfg, allowed_hosts={"testserver"})), tmp_path, cfg


def test_config_api_roundtrip_and_validation_errors(client):
    c, _, cfg = client
    assert c.get("/api/config", headers=HOST).json()["search"]["salary"]["min_usd"] == 80000
    ok = c.post(
        "/api/config", json={"updates": {"search": {"salary": {"min_usd": 95000}}}}, headers=HOST
    )
    assert ok.status_code == 200 and load_config(cfg).search.salary.min_usd == 95000
    bad = c.post(
        "/api/config", json={"updates": {"scoring": {"score_threshold": "x"}}}, headers=HOST
    )
    assert bad.status_code == 422 and bad.json()["errors"][0]["field"] == "scoring.score_threshold"
    assert (
        c.post("/api/config", json={"updates": {"paths": {"db": "x"}}}, headers=HOST).status_code
        == 422
    )
    assert c.post("/api/config", json={}, headers=HOST).status_code == 400
    assert c.post("/api/config", json=[1], headers=HOST).status_code == 400


def test_config_api_requires_json_and_local_origin(client):
    c = client[0]
    assert (
        c.post(
            "/api/config", content="x", headers={**HOST, "content-type": "text/plain"}
        ).status_code
        == 415
    )
    foreign = c.post(
        "/api/config",
        json={"updates": {"budget": {"max_llm_calls_per_run": 1}}},
        headers={**HOST, "origin": "https://evil.example"},
    )
    assert foreign.status_code == 403


def test_file_editors_validate_back_up_and_limit_size(client):
    c, tmp, _ = client
    got = c.get("/api/files/cv", headers=HOST).json()
    assert got["exists"] and "jh:section" in got["content"]
    new_cv = "% jh:section s\n% jh:item a\n• changed\n% jh:endsection"
    assert c.post("/api/files/cv", json={"content": new_cv}, headers=HOST).status_code == 200
    assert "changed" in (tmp / "master.tex").read_text() and (tmp / "master.tex.bak").exists()
    broken = c.post("/api/files/cv", json={"content": "% jh:item x\n"}, headers=HOST)
    assert broken.status_code == 422 and "outside a section" in broken.json()["error"]
    assert "changed" in (tmp / "master.tex").read_text()  # the invalid save changed nothing
    assert (
        c.post("/api/files/letter", json={"content": "no placeholders"}, headers=HOST).status_code
        == 422
    )
    assert (
        c.post(
            "/api/files/letter",
            json={
                "content": "%%DATE%% %%COMPANY%% %%SUBJECT%% %%GREETING%% %%BODY%% %%CLOSING%% x"
            },
            headers=HOST,
        ).status_code
        == 200
    )
    assert (
        c.post(
            "/api/files/candidates", json={"content": "Stripe\nLinear"}, headers=HOST
        ).status_code
        == 200
    )
    assert (tmp / "cands.txt").read_text() == "Stripe\nLinear\n"
    huge = c.post("/api/files/candidates", json={"content": "x" * (600 * 1024)}, headers=HOST)
    assert huge.status_code == 422
    assert c.get("/api/files/passwd", headers=HOST).status_code == 404
    assert c.post("/api/files/../../etc", json={"content": "x"}, headers=HOST).status_code in (
        404,
        400,
    )


def test_settings_page_renders_every_editor(client):
    html = client[0].get("/settings", headers=HOST).text
    for needle in (
        'data-cfg="search.titles_include"',
        'data-cfg="search.salary.min_usd"',
        'data-cfg="scoring.candidate_context"',
        'data-cfg="llm.backend"',
        'data-cfg="sources.aggregators"',
        'data-file="cv"',
        'data-file="letter"',
        'data-file="candidates"',
        "Save &amp; re-filter",
    ):
        assert needle in html, needle


# --- deleting generated documents ----------------------------------------------------------------


def make_package(tmp_path, conn, job_id=1, status="packaged"):
    folder = tmp_path / "out" / "2026-10-11" / f"acme-eng-{job_id}"
    folder.mkdir(parents=True)
    (folder / "cv.pdf").write_bytes(b"%PDF")
    conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.execute(
        "INSERT INTO packages(job_id, path, model, created_at, verified) VALUES (?,?,?,?,1)",
        (job_id, str(folder), "m", "2026-10-11T00:00:00+00:00"),
    )
    conn.commit()
    return folder


@pytest.fixture
def pkg_env(tmp_path):
    conn = connect(tmp_path / "t.db")
    upsert_jobs(
        conn,
        [
            Job(source="s", external_id=str(i), company="Acme", title=f"Eng {i}", url="u")
            for i in (1, 2)
        ],
    )
    return conn, tmp_path


def test_delete_package_removes_files_rows_and_reverts_status(pkg_env):
    conn, tmp = pkg_env
    folder = make_package(tmp, conn)
    assert delete_packages(conn, tmp / "out", 1) == 1
    assert not folder.exists() and not folder.parent.exists()  # empty date folder is removed too
    assert conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 0
    assert conn.execute("SELECT status FROM jobs WHERE id = 1").fetchone()[0] == "selected"
    assert delete_packages(conn, tmp / "out", 1) == 0  # idempotent


def test_delete_package_keeps_the_status_you_recorded(pkg_env):
    conn, tmp = pkg_env
    make_package(tmp, conn, status="applied")
    delete_packages(conn, tmp / "out", 1)
    assert conn.execute("SELECT status FROM jobs WHERE id = 1").fetchone()[0] == "applied"


def test_delete_package_never_touches_folders_outside_out(pkg_env):
    conn, tmp = pkg_env
    outside = tmp / "precious"
    outside.mkdir()
    (outside / "keep.txt").write_text("x")
    conn.execute(
        "INSERT INTO packages(job_id, path, model, created_at, verified) VALUES (1,?,?,?,1)",
        (str(outside), "m", "now"),
    )
    conn.commit()
    delete_packages(conn, tmp / "out", 1)
    assert (outside / "keep.txt").exists()
    assert conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 0  # the row is forgotten


def test_delete_package_endpoint_and_buttons(client):
    c, tmp, cfg = client
    conn = connect(tmp / "t.db")
    upsert_jobs(conn, [Job(source="s", external_id="1", company="Acme", title="Eng", url="u")])
    folder = make_package(tmp, conn)
    assert "package/delete" in c.get("/packages", headers=HOST).text
    assert "Delete package" in c.get("/jobs/1", headers=HOST).text
    res = c.post("/api/jobs/1/package/delete", json={}, headers=HOST)
    assert res.json() == {"ok": True, "deleted": 1} and not folder.exists()
    assert "Delete package" not in c.get("/jobs/1", headers=HOST).text


def test_fields_that_pick_files_or_programs_cannot_be_changed_from_the_ui(cfg_path):
    for update in (
        {"llm": {"claude_path": "/tmp/evil"}},
        {"sources": {"candidates_file": "/Users/me/.zshrc"}},
        {"sources": {"companies_file": "/etc/hosts"}},
    ):
        with pytest.raises(ConfigUpdateError, match="by hand"):
            save_updates(cfg_path, update)
    assert cfg_path.read_text() == SAMPLE
    save_updates(cfg_path, {"llm": {"timeout_seconds": 90}})  # the rest of the section is fine


def test_the_file_editor_cannot_be_redirected_through_the_config_api(client):
    c = client[0]
    res = c.post(
        "/api/config",
        json={"updates": {"sources": {"candidates_file": "/tmp/x"}}},
        headers=HOST,
    )
    assert res.status_code == 422


# --- reviewer findings ------------------------------------------------------------------------


def test_yaml11_ambiguous_strings_are_quoted_so_the_file_still_loads(cfg_path):
    save_updates(cfg_path, {"search": {"locations_allowed": ["NO", "yes", "off", "Remote", "1e3"]}})
    assert load_config(cfg_path).search.locations_allowed == ["NO", "yes", "off", "Remote", "1e3"]
    assert yaml.safe_load(cfg_path.read_text())["search"]["locations_allowed"][0] == "NO"


def test_backups_keep_the_original_even_after_several_saves(cfg_path):
    for n in (81, 82, 83):
        save_updates(cfg_path, {"scoring": {"score_threshold": n}})
    folder = cfg_path.parent
    assert (folder / "config.yaml.orig").read_text() == SAMPLE  # the very first version
    assert "82" in (folder / "config.yaml.bak").read_text()  # the one before the last save


def test_unchanged_fields_keep_their_comments_and_style_byte_for_byte(cfg_path):
    save_updates(
        cfg_path,
        {
            "search": {
                "titles_include": ["backend", "python"],
                "titles_exclude": ["intern", "junior"],
                "salary": {"min_usd": 80000},
            },
            "scoring": {"score_threshold": 90},
        },
    )
    text = cfg_path.read_text()
    assert '  titles_include: ["backend", "python"]   # inline comment' in text
    assert "min_usd: 80000   # annual" in text and "score_threshold: 90" in text


def test_write_through_a_symlink_keeps_the_link_and_the_file_mode(tmp_path):
    import os

    real = tmp_path / "dotfiles" / "config.yaml"
    real.parent.mkdir()
    real.write_text(SAMPLE)
    real.chmod(0o640)
    link = tmp_path / "config.yaml"
    link.symlink_to(real)
    save_updates(link, {"scoring": {"score_threshold": 70}})
    assert link.is_symlink() and "70" in real.read_text()
    assert os.stat(real).st_mode & 0o777 == 0o640


def test_unreadable_or_odd_files_give_a_readable_error_not_a_crash(tmp_path):
    multi = tmp_path / "multi.yaml"
    multi.write_text("a: 1\n---\nb: 2\n")
    with pytest.raises(ConfigUpdateError):
        save_updates(multi, {"scoring": {"score_threshold": 70}})
    binary = tmp_path / "bin.yaml"
    binary.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(ConfigUpdateError):
        save_updates(binary, {"scoring": {"score_threshold": 70}})


@pytest.mark.parametrize(
    ("update", "field"),
    [
        ({"search": {"max_age_days": 0}}, "search.max_age_days"),
        ({"scoring": {"batch_size": 0}}, "scoring.batch_size"),
        ({"scoring": {"score_threshold": 101}}, "scoring.score_threshold"),
        ({"llm": {"timeout_seconds": -1}}, "llm.timeout_seconds"),
        ({"budget": {"max_llm_calls_per_run": -5}}, "budget.max_llm_calls_per_run"),
    ],
)
def test_numeric_fields_have_sensible_bounds(cfg_path, update, field):
    with pytest.raises(ConfigUpdateError) as exc:
        save_updates(cfg_path, update)
    assert field in {e["field"] for e in exc.value.errors}


def test_api_survives_malformed_bodies_and_refuses_empty_cv_or_letter(client):
    c, tmp, _ = client
    for url in ("/api/config", "/api/files/cv"):
        res = c.post(url, content="{not json", headers={**HOST, "content-type": "application/json"})
        assert res.status_code == 400
    assert c.post("/api/files/cv", json={"content": "   \n"}, headers=HOST).status_code == 422
    assert c.post("/api/files/letter", json={"content": ""}, headers=HOST).status_code == 422
    assert "jh:section" in (tmp / "master.tex").read_text()  # untouched
    (tmp / "cands.txt").write_bytes(b"\xff\xfe\x00")
    assert c.get("/api/files/candidates", headers=HOST).status_code == 422


def test_delete_package_keeps_the_row_when_the_folder_cannot_be_removed(pkg_env, monkeypatch):
    import shutil

    from jobhunter import tailoring

    real_rmtree = shutil.rmtree  # `tailoring.shutil` is the same module object
    conn, tmp = pkg_env
    make_package(tmp, conn)
    monkeypatch.setattr(
        tailoring.shutil, "rmtree", lambda *a, **k: (_ for _ in ()).throw(OSError("busy"))
    )
    assert delete_packages(conn, tmp / "out", 1) == 0
    assert conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 1
    assert conn.execute("SELECT status FROM jobs WHERE id = 1").fetchone()[0] == "packaged"
    monkeypatch.setattr(tailoring.shutil, "rmtree", real_rmtree)
    assert delete_packages(conn, tmp / "out", 1) == 1
