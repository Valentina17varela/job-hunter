from pathlib import Path

import pytest

from jobhunter.config import ConfigError, load_config

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "config" / "config.example.yaml"


def test_default_config_is_valid():
    config = load_config(EXAMPLE)
    assert config.scoring.score_threshold == 75
    assert config.tailoring.mode == "select"
    assert config.budget.daily_budget_usd == 1.0


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_missing_default_config_suggests_copying_the_example(tmp_path):
    with pytest.raises(ConfigError, match="cp .*config.example.yaml"):
        load_config(tmp_path / "config.yaml")


def test_invalid_field_reports_path(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("tailoring:\n  mode: banana\n")
    with pytest.raises(ConfigError, match="tailoring.mode"):
        load_config(path)


def test_unknown_key_rejected(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("bogus: 1\n")
    with pytest.raises(ConfigError, match="bogus"):
        load_config(path)


def test_invalid_yaml(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("a: [unclosed\n")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(path)
