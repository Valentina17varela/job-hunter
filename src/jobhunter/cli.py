"""Command-line interface (see specs/07-cli-config.md)."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from jobhunter import __version__
from jobhunter.companies import (
    check_companies,
    discover,
    load_companies,
    read_candidates,
    save_companies,
)
from jobhunter.config import ConfigError, load_config
from jobhunter.db import connect
from jobhunter.doctor import run_checks
from jobhunter.filters import JobFilter, job_from_row
from jobhunter.http import HttpClient
from jobhunter.pipeline import REFILTER_STATUSES, FilterSummary, fetch_stage, filter_stage
from jobhunter.sources import build_sources

app = typer.Typer(help="Find job postings, score them and prepare application packages.")
companies_app = typer.Typer(help="Manage the list of companies with public ATS boards.")
app.add_typer(companies_app, name="companies")

ConfigOption = Annotated[Path, typer.Option("--config", "-c", help="Path to config.yaml.")]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"jobhunter {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version_callback, is_eager=True)
    ] = False,
) -> None:
    """jobhunter."""


@app.command()
def doctor(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Check the environment: Python, config, API key and the LaTeX toolchain."""
    failed_required = False
    for check in run_checks(config):
        mark = "ok  " if check.ok else ("FAIL" if check.required else "warn")
        typer.echo(f"[{mark}] {check.name}: {check.detail}")
        if not check.ok and check.required:
            failed_required = True
    if failed_required:
        raise typer.Exit(code=1)


class Stage(StrEnum):
    ALL = "all"
    FETCH = "fetch"
    FILTER = "filter"
    SCORE = "score"
    TAILOR = "tailor"


IMPLEMENTED_STAGES = {Stage.FETCH, Stage.FILTER}


def _load(config_path: Path):  # noqa: ANN202
    try:
        return load_config(config_path)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _http(config) -> HttpClient:  # noqa: ANN001
    return HttpClient(
        max_concurrency=config.sources.max_concurrency, max_per_host=config.sources.max_per_host
    )


@app.command()
def run(
    stage: Annotated[Stage, typer.Option(help="Run a single stage (default: all).")] = Stage.ALL,
    dry_run: Annotated[bool, typer.Option(help="Show the plan without fetching.")] = False,
    config: ConfigOption = Path("config/config.yaml"),
) -> None:
    """Run the pipeline: fetch, then filter (scoring and tailoring come in later phases)."""
    cfg = _load(config)
    if stage not in (Stage.ALL, *IMPLEMENTED_STAGES):
        typer.echo(f"error: stage '{stage}' is not implemented yet.", err=True)
        raise typer.Exit(code=1)
    companies = load_companies(cfg.sources.companies_file)
    sources = build_sources(cfg, companies)
    do_fetch = stage in (Stage.ALL, Stage.FETCH)
    do_filter = stage in (Stage.ALL, Stage.FILTER)
    if dry_run:
        planned = [n for n, on in (("fetch", do_fetch), ("filter", do_filter)) if on]
        typer.echo(f"Stages: {', '.join(planned)}")
        if do_fetch:
            typer.echo(f"Would fetch {len(sources)} sources ({len(companies)} company boards):")
            kinds: dict[str, int] = {}
            for source in sources:
                kinds[source.name] = kinds.get(source.name, 0) + 1
            for name, count in sorted(kinds.items()):
                typer.echo(f"  {name}: {count}")
        return

    conn = connect(cfg.paths.db)
    if do_fetch:
        asyncio.run(_fetch(cfg, conn, sources))
    if do_filter:
        summary = filter_stage(conn, JobFilter(cfg.search, cfg.fx_rates_to_usd))
        _print_filter_summary(summary, conn)


async def _fetch(cfg, conn, sources) -> None:  # noqa: ANN001
    async with _http(cfg) as http:
        summary = await fetch_stage(conn, sources, http, cfg.sources.stale_days)
    up = summary.upsert
    typer.echo(
        f"fetched {summary.jobs_found} postings from {summary.sources_ok} sources "
        f"({summary.sources_failed} failed) · new {up.new} · updated {up.updated} · "
        f"unchanged {up.unchanged} · closed {summary.closed} · duplicates {summary.duplicates}"
    )
    for failure in summary.failures[:10]:
        typer.echo(f"  failed: {failure}", err=True)


def _print_filter_summary(summary: FilterSummary, conn) -> None:  # noqa: ANN001
    typer.echo(
        f"filtered {summary.evaluated} postings · passed {summary.passed} · "
        f"rejected {summary.filtered} · status changes {summary.changed}"
    )
    for rule, count in summary.reasons.most_common():
        typer.echo(f"  rejected by {rule}: {count}")
    for flag, count in summary.flags.most_common():
        typer.echo(f"  flag {flag}: {count}")
    total = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'passed'").fetchone()[0]
    typer.echo(f"{total} postings currently pass your criteria")


@app.command()
def refilter(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Re-apply the filter to all stored postings after changing `search` in the config."""
    cfg = _load(config)
    conn = connect(cfg.paths.db)
    summary = filter_stage(conn, JobFilter(cfg.search, cfg.fx_rates_to_usd), REFILTER_STATUSES)
    _print_filter_summary(summary, conn)


@app.command()
def explain(
    job_id: Annotated[int, typer.Argument(help="Posting id (the `id` column of `jobs`).")],
    config: ConfigOption = Path("config/config.yaml"),
) -> None:
    """Show why a posting was filtered out (or passed), using the current criteria."""
    cfg = _load(config)
    conn = connect(cfg.paths.db)
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        typer.echo(f"error: no posting with id {job_id}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"#{row['id']} {row['title']} — {row['company']} ({row['source']})")
    typer.echo(f"  location: {row['location']} · mode: {row['remote']} · url: {row['url']}")
    pay = f"{row['salary_min']}–{row['salary_max']} {row['salary_currency']}"
    typer.echo(f"  salary: {pay if row['salary_max'] else 'not published'}")
    typer.echo(f"  stored status: {row['status']} · stored reason: {row['filter_reason'] or '-'}")
    result = JobFilter(cfg.search, cfg.fx_rates_to_usd).evaluate(job_from_row(row))
    verdict = "PASSES" if result.passed else f"REJECTED — {result.reason}"
    typer.echo(f"  with current criteria: {verdict}")
    if result.flags:
        typer.echo(f"  flags: {', '.join(result.flags)}")


@companies_app.command("check")
def companies_check(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Validate every slug in companies.yaml (200 vs 404) without touching the pipeline."""
    cfg = _load(config)
    companies = load_companies(cfg.sources.companies_file)

    async def _check() -> int:
        async with _http(cfg) as http:
            results = await check_companies(http, companies)
        broken = 0
        for company, result in results:
            if not result.ok:
                broken += 1
                typer.echo(f"[FAIL] {company.name} ({company.ats}/{company.slug}): {result.error}")
        typer.echo(f"{len(companies) - broken}/{len(companies)} boards OK")
        return broken

    if asyncio.run(_check()):
        raise typer.Exit(code=1)


@companies_app.command("discover")
def companies_discover(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Probe candidate company names for public boards and add the ones found."""
    cfg = _load(config)
    known = load_companies(cfg.sources.companies_file)
    names = read_candidates(cfg.sources.candidates_file)

    async def _discover() -> None:
        async with _http(cfg) as http:
            new, missing = await discover(http, names, known)
        save_companies(cfg.sources.companies_file, known + new)
        typer.echo(
            f"added {len(new)} boards from {len(names)} candidates "
            f"({len(missing)} names without a public board); total {len(known) + len(new)}"
        )

    asyncio.run(_discover())
