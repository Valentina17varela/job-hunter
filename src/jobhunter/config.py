"""Configuration loading and validation (see specs/07-cli-config.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SalaryConfig(_Strict):
    min_usd: int = 0
    on_missing: Literal["pass", "reject"] = "pass"


class SearchConfig(_Strict):
    titles_include: list[str] = []
    titles_exclude: list[str] = []
    keywords_include: list[str] = []
    keywords_exclude: list[str] = []
    seniority: list[str] = []
    work_mode: list[Literal["remote", "hybrid", "onsite"]] = ["remote"]
    locations_allowed: list[str] = []
    salary: SalaryConfig = SalaryConfig()
    max_age_days: int = 30


class ScoringConfig(_Strict):
    model: str = "claude-haiku-5-5"
    score_threshold: int = 75
    max_description_tokens: int = 1500
    use_batch: bool = False


class TailoringConfig(_Strict):
    model: str = "claude-sonnet-5-5"
    mode: Literal["select", "rewrite"] = "select"
    max_packages_per_day: int = 10
    languages: list[str] = ["en", "es"]
    tone: str = ""
    max_cv_pages: int = 1


class LatexConfig(_Strict):
    engine: Literal["tectonic", "latexmk"] = "tectonic"
    timeout_seconds: int = 60


class BudgetConfig(_Strict):
    daily_budget_usd: float = 1.0


class PathsConfig(_Strict):
    cv_master: Path = Path("config/cv/master.tex")
    letter_template: Path = Path("config/cv/letter_template.tex")
    db: Path = Path("data/jobhunter.db")
    out: Path = Path("out")


class Config(_Strict):
    search: SearchConfig = SearchConfig()
    scoring: ScoringConfig = ScoringConfig()
    tailoring: TailoringConfig = TailoringConfig()
    latex: LatexConfig = LatexConfig()
    budget: BudgetConfig = BudgetConfig()
    fx_rates_to_usd: dict[str, float] = {}
    paths: PathsConfig = PathsConfig()


class ConfigError(Exception):
    """Raised when the config file is missing or invalid."""


def load_config(path: Path) -> Config:
    """Load and validate a YAML config file, raising ConfigError with the offending field."""
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    try:
        return Config.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigError(f"Invalid config {path}: {details}") from exc
