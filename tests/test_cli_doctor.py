import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jobhunter.cli import app
from jobhunter.doctor import MINIMAL_TEX, compile_tex

EXAMPLE_CONFIG = str(Path(__file__).resolve().parent.parent / "config" / "config.example.yaml")

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "jobhunter" in result.stdout


def test_doctor_fails_on_bad_config(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text("bogus: 1\n")
    result = runner.invoke(app, ["doctor", "--config", str(bad)])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout


def test_compile_tex_missing_engine(tmp_path):
    tex = tmp_path / "a.tex"
    tex.write_text(MINIMAL_TEX)
    ok, detail = compile_tex(tex, "definitely-not-an-engine", 5)
    assert not ok
    assert "not found" in detail


@pytest.mark.skipif(shutil.which("tectonic") is None, reason="tectonic not installed")
def test_compile_minimal_with_tectonic(tmp_path):
    tex = tmp_path / "a.tex"
    tex.write_text(MINIMAL_TEX)
    ok, detail = compile_tex(tex, "tectonic", 120)
    assert ok, detail


def test_run_dry_run_lists_sources(tmp_path):
    result = runner.invoke(app, ["run", "--dry-run", "--config", EXAMPLE_CONFIG])
    assert result.exit_code == 0
    assert "Would fetch" in result.stdout
    assert "remotive: 1" in result.stdout


def test_run_score_stage_without_a_cv_explains_what_is_missing():
    result = runner.invoke(app, ["run", "--stage", "score", "--config", EXAMPLE_CONFIG])
    assert result.exit_code == 1
    assert "master.tex not found" in result.output


def test_run_tailor_stage_without_cv_or_template_explains_what_is_missing():
    result = runner.invoke(app, ["run", "--stage", "tailor", "--config", EXAMPLE_CONFIG])
    assert result.exit_code == 1
    assert "not found" in result.output and "letter init" in result.output


def test_search_stage_is_fetch_plus_filter_and_needs_no_ai():
    result = runner.invoke(
        app, ["run", "--stage", "search", "--dry-run", "--config", EXAMPLE_CONFIG]
    )
    assert result.exit_code == 0
    assert "Stages: fetch, filter" in result.stdout and "score" not in result.stdout


# --- fix hints per system (spec 19) ------------------------------------------------------------


def test_system_detection(monkeypatch):
    import platform
    from pathlib import Path

    from jobhunter import doctor

    monkeypatch.setattr(Path, "exists", lambda self: False)
    for name, expected in (("Darwin", "macos"), ("Windows", "windows"), ("Plan9", "other")):
        monkeypatch.setattr(platform, "system", lambda n=name: n)
        assert doctor.detect_system() == expected
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: "Linux version 5 (Microsoft)")
    assert doctor.detect_system() == "wsl"
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: "Linux version 6.1 (debian)")
    assert doctor.detect_system() == "linux"
    monkeypatch.setattr(Path, "exists", lambda self: str(self) == "/.dockerenv")
    assert doctor.detect_system() == "docker"


def test_latex_hints_name_the_right_command_per_system():
    from jobhunter import doctor

    assert "brew install tectonic" in doctor.latex_hint("macos", missing=True)
    assert "apt install latexmk" in doctor.latex_hint("linux", missing=True)
    assert "WSL" in doctor.latex_hint("wsl", missing=True)
    assert "WSL" in doctor.latex_hint("windows", missing=True)
    assert "docker compose build" in doctor.latex_hint("docker", missing=True)
    assert "cv check" in doctor.latex_hint("macos", missing=False)
    assert all("docs/SETUP.md" in doctor.latex_hint(s, True) for s in ("macos", "linux", "other"))


def test_claude_and_config_hints():
    from jobhunter import doctor

    assert "claude auth login" in doctor.claude_hint(not_found=False)
    assert "ANTHROPIC_API_KEY" in doctor.claude_hint(not_found=True)
    assert "jobhunter init" in doctor.config_hint(missing=True)
    assert "config.example.yaml" in doctor.config_hint(missing=False)


def test_doctor_prints_a_fix_under_each_problem_and_nothing_when_ok(tmp_path, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)  # no claude, no LaTeX engine
    monkeypatch.setattr("jobhunter.doctor.detect_system", lambda: "macos")
    result = runner.invoke(app, ["doctor", "--config", str(tmp_path / "missing.yaml")])
    assert result.exit_code == 1
    assert "fix: Create one with `jobhunter init`" in result.stdout

    config = tmp_path / "config.yaml"
    config.write_text("{}\n")
    result = runner.invoke(app, ["doctor", "--config", str(config)])
    assert "brew install tectonic" in result.stdout  # LaTeX engine missing on macOS
    assert "claude auth login" in result.stdout or "Claude Code CLI" in result.stdout
    for line in result.stdout.splitlines():
        if line.startswith("[ok"):
            assert "fix:" not in line


def test_doctor_checks_carry_hints_only_when_failing(tmp_path):
    from jobhunter import doctor

    checks = doctor.run_checks(tmp_path / "missing.yaml")
    for check in checks:
        assert (check.hint != "") == (not check.ok), check.name
