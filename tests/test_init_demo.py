from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from jobhunter import latex, resources
from jobhunter.cli import app
from jobhunter.config import load_config
from jobhunter.demo import seed
from jobhunter.web.app import create_app

runner = CliRunner()


def test_bundled_files_are_all_found():
    for name in resources.NAMES:
        assert resources.read(name).strip()


def test_sample_cv_parses_and_has_markers():
    doc = latex.parse(resources.read("cv.example.tex"))
    assert len(doc.ids()) >= 8 and latex.sensitive_warnings(doc) == []


def test_init_creates_a_workspace_and_never_overwrites(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path / "ws"), "--sample-cv"])
    assert result.exit_code == 0, result.output
    ws = tmp_path / "ws"
    for name in (
        "config/config.yaml",
        "config/company_candidates.txt",
        "config/cv/letter_template.tex",
        "config/cv/master.tex",
    ):
        assert (ws / name).is_file(), name
    ignored = (ws / ".gitignore").read_text()
    assert "config/cv/" in ignored and "data/" in ignored and "out/" in ignored
    load_config(ws / "config/config.yaml")  # the generated config is valid

    (ws / "config/config.yaml").write_text("# mine\n")
    again = runner.invoke(app, ["init", str(ws)])
    assert again.exit_code == 0 and "kept" in again.output
    assert (ws / "config/config.yaml").read_text() == "# mine\n"
    assert (ws / ".gitignore").read_text().count("config/cv/") == 1


def test_init_without_sample_cv_tells_what_to_do(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert not (tmp_path / "config/cv/master.tex").exists()
    assert "master.tex" in result.output and "doctor" in result.output


def test_demo_workspace_is_valid_and_serves_the_ui(tmp_path):
    config = seed(tmp_path / "demo")
    cfg = load_config(config)
    assert cfg.paths.cv_master.is_file() and cfg.paths.letter_template.is_file()
    client = TestClient(create_app(config, allowed_hosts={"testserver"}))
    page = client.get("/jobs", headers={"host": "testserver"})
    assert page.status_code == 200 and "Northwind Labs" in page.text


def test_demo_command_without_serving_only_writes_files(tmp_path):
    result = runner.invoke(app, ["demo", str(tmp_path / "d"), "--no-serve"])
    assert result.exit_code == 0 and (tmp_path / "d" / "config.yaml").is_file()


def test_ui_bind_keeps_the_host_allowlist_local(tmp_path, monkeypatch):
    config = seed(tmp_path / "demo")
    seen = {}

    def fake_run(web_app, host, port, log_level):
        seen.update(host=host, port=port)
        client = TestClient(web_app)
        seen["foreign"] = client.get("/", headers={"host": "evil.example"}).status_code
        seen["local"] = client.get("/", headers={"host": f"127.0.0.1:{port}"}).status_code
        seen["extra"] = client.get("/", headers={"host": f"jobhunter:{port}"}).status_code

    monkeypatch.setattr("uvicorn.run", fake_run)
    out = runner.invoke(app, ["ui", "--config", str(config), "--bind", "0.0.0.0", "--port", "8123"])
    assert out.exit_code == 0, out.output
    assert "warning" in out.output  # listening beyond localhost is called out
    assert seen["host"] == "0.0.0.0"
    assert seen["foreign"] == 403 and seen["local"] == 200 and seen["extra"] == 403

    seen.clear()
    runner.invoke(
        app,
        ["ui", "--config", str(config), "--bind", "0.0.0.0", "--port", "8123",
         "--allow-host", "jobhunter"],
    )  # fmt: skip
    assert seen["extra"] == 200 and seen["foreign"] == 403


def test_default_ui_binds_to_loopback(tmp_path, monkeypatch):
    config = seed(tmp_path / "demo")
    seen = {}
    monkeypatch.setattr("uvicorn.run", lambda app_, host, port, log_level: seen.update(host=host))
    result = runner.invoke(app, ["ui", "--config", str(config)])
    assert result.exit_code == 0 and seen["host"] == "127.0.0.1"
    assert "warning" not in result.output


def test_wheel_force_include_matches_the_bundled_names():
    text = Path("pyproject.toml").read_text() if Path("pyproject.toml").exists() else ""
    root = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = root.read_text()
    for name in resources.NAMES:
        assert f"jobhunter/data/{name}" in text, f"{name} is not packaged in the wheel"
