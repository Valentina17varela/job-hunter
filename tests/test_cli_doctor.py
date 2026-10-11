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
