"""Configuration loading and validation (see specs/07-cli-config.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    ValidationError,
    field_validator,
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SalaryConfig(_Strict):
    min_usd: NonNegativeInt = 0
    on_missing: Literal["pass", "reject"] = "pass"


class SearchConfig(_Strict):
    titles_include: list[str] = []
    titles_exclude: list[str] = []
    keywords_include: list[str] = []
    keywords_exclude: list[str] = []
    companies_exclude: list[str] = []  # block list: whole company names, matched normalized
    seniority: list[Literal["junior", "mid", "senior", "lead"]] = []
    work_mode: list[Literal["remote", "hybrid", "onsite"]] = ["remote"]
    locations_allowed: list[str] = []
    salary: SalaryConfig = SalaryConfig()
    max_age_days: PositiveInt = 30  # aggregators (dated feeds)
    max_age_days_ats: PositiveInt | None = (
        None  # company boards; None = no limit (still listed = open)
    )


class LlmConfig(_Strict):
    backend: Literal["claude_cli", "anthropic_api"] = "claude_cli"
    claude_path: str = "claude"
    timeout_seconds: PositiveInt = 180
    max_attempts: PositiveInt = 3
    effort: str | None = "low"  # `claude --effort`; low keeps scoring fast and terse
    max_thinking_tokens: int | None = 0  # 0 disables extended thinking (fast, cheap)
    # Optional USD per million tokens (input, output) per model, for the API backend's budget.
    api_prices: dict[str, tuple[float, float]] = {}


class ScoringConfig(_Strict):
    model: str = "haiku"
    score_threshold: int = Field(75, ge=0, le=100)
    batch_size: PositiveInt = 8
    max_description_tokens: PositiveInt = 1500
    max_profile_tokens: PositiveInt = 3000
    candidate_context: str = ""
    use_batch: bool = False


class TailoringConfig(_Strict):
    model: str = "sonnet"
    mode: Literal["select", "rewrite"] = "select"
    max_packages_per_day: PositiveInt = 10
    languages: list[str] = ["en", "es"]
    tone: str = ""
    max_cv_pages: PositiveInt = 1


class LatexConfig(_Strict):
    engine: Literal["auto", "tectonic", "latexmk"] = "auto"  # auto: tectonic, else latexmk
    timeout_seconds: PositiveInt = 60


class BudgetConfig(_Strict):
    max_llm_calls_per_run: PositiveInt = 60  # claude_cli backend
    daily_budget_usd: NonNegativeFloat = 1.0  # anthropic_api backend


class PathsConfig(_Strict):
    cv_master: Path = Path("config/cv/master.tex")
    letter_template: Path = Path("config/cv/letter_template.tex")
    db: Path = Path("data/jobhunter.db")
    out: Path = Path("out")


class SourcesConfig(_Strict):
    aggregators: list[str] = [
        "remotive",
        "remoteok",
        "weworkremotely",
        "arbeitnow",
        "jobicy",
    ]
    wwr_categories: list[str] = [
        "remote-programming-jobs",
        "remote-back-end-programming-jobs",
        "remote-full-stack-programming-jobs",
        "remote-devops-sysadmin-jobs",
    ]
    arbeitnow_pages: PositiveInt = 3
    companies_file: Path = Path("config/companies.yaml")
    candidates_file: Path = Path("config/company_candidates.txt")
    max_concurrency: PositiveInt = 5
    max_per_host: PositiveInt = 2
    stale_days: PositiveInt = 7

    @field_validator("aggregators")
    @classmethod
    def _known_aggregators(cls, names: list[str]) -> list[str]:
        from jobhunter.sources import registry  # lazy: the sources import this module

        known = registry.aggregators()
        unknown = [n for n in names if n not in known]
        if unknown:
            raise ValueError(f"unknown source(s) {unknown}; available: {sorted(known)}")
        return names


class Config(_Strict):
    sources: SourcesConfig = SourcesConfig()
    search: SearchConfig = SearchConfig()
    llm: LlmConfig = LlmConfig()
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
        hint = ""
        if path.name == "config.yaml":
            hint = f". Create it with: cp {path.with_name('config.example.yaml')} {path}"
        raise ConfigError(f"Config file not found: {path}{hint}")
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
