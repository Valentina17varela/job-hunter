"""Command-line interface (see specs/07-cli-config.md)."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from jobhunter import __version__, latex
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
from jobhunter.llm import LlmAuthError, LlmClient, LlmError, build_backend
from jobhunter.pipeline import REFILTER_STATUSES, FilterSummary, fetch_stage, filter_stage
from jobhunter.scoring import ScoreSummary, score_stage
from jobhunter.sources import build_sources
from jobhunter.tailoring import tailor_stage

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
    SEARCH = "search"  # fetch + filter: everything that needs no LLM
    FETCH = "fetch"
    FILTER = "filter"
    SCORE = "score"
    TAILOR = "tailor"


IMPLEMENTED_STAGES = {Stage.SEARCH, Stage.FETCH, Stage.FILTER, Stage.SCORE, Stage.TAILOR}


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
    job: Annotated[
        list[int] | None, typer.Option("--job", help="Tailor only these posting ids (repeatable).")
    ] = None,
    force: Annotated[bool, typer.Option(help="Tailor again postings already packaged.")] = False,
    limit: Annotated[int | None, typer.Option(help="Tailor at most this many postings.")] = None,
    config: ConfigOption = Path("config/config.yaml"),
) -> None:
    """Run the pipeline: fetch → filter → score → tailor (each stage can be run alone)."""
    cfg = _load(config)
    if stage not in (Stage.ALL, *IMPLEMENTED_STAGES):
        typer.echo(f"error: stage '{stage}' is not implemented yet.", err=True)
        raise typer.Exit(code=1)
    companies = load_companies(cfg.sources.companies_file)
    sources = build_sources(cfg, companies)
    do_fetch = stage in (Stage.ALL, Stage.SEARCH, Stage.FETCH)
    do_filter = stage in (Stage.ALL, Stage.SEARCH, Stage.FILTER)
    do_score = stage in (Stage.ALL, Stage.SCORE)
    do_tailor = stage in (Stage.ALL, Stage.TAILOR)
    if dry_run:
        planned = [
            n
            for n, on in (
                ("fetch", do_fetch),
                ("filter", do_filter),
                ("score", do_score),
                ("tailor", do_tailor),
            )
            if on
        ]
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
    if do_score:
        _score(cfg, conn, explicit=stage == Stage.SCORE)
    if do_tailor:
        _tailor(cfg, conn, explicit=stage == Stage.TAILOR, job_ids=job, force=force, limit=limit)


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


def _score(cfg, conn, *, explicit: bool) -> None:  # noqa: ANN001
    """Run the scoring stage. In a full run it is skipped (with a note) when no CV exists yet."""
    master = cfg.paths.cv_master
    if not master.exists():
        message = f"{master} not found; add your LaTeX CV to enable scoring."
        if explicit:
            typer.echo(f"error: {message}", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"score skipped: {message}")
        return
    try:
        doc = latex.parse(master.read_text())
    except latex.CvError as exc:
        typer.echo(f"error: {master}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    client = _make_client(cfg, conn)
    try:
        summary = score_stage(conn, client, cfg, doc)
    except LlmAuthError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except LlmError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _print_score_summary(summary)


def _make_client(cfg, conn) -> LlmClient:  # noqa: ANN001
    return LlmClient(
        conn,
        build_backend(cfg),
        max_calls=cfg.budget.max_llm_calls_per_run,
        daily_budget_usd=cfg.budget.daily_budget_usd
        if cfg.llm.backend == "anthropic_api"
        else None,
        max_attempts=cfg.llm.max_attempts,
    )


def _tailor(cfg, conn, *, explicit: bool, job_ids, force: bool, limit) -> None:  # noqa: ANN001
    """Build application packages for `selected` postings."""
    master, template_path = cfg.paths.cv_master, cfg.paths.letter_template
    missing = [str(p) for p in (master, template_path) if not p.exists()]
    if missing:
        message = f"{', '.join(missing)} not found (see `jobhunter letter init`)."
        if explicit:
            typer.echo(f"error: {message}", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"tailor skipped: {message}")
        return
    try:
        doc = latex.parse(master.read_text())
    except latex.CvError as exc:
        typer.echo(f"error: {master}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    try:
        summary = tailor_stage(
            conn, _make_client(cfg, conn), cfg, doc, cv_dir=master.parent,
            template=template_path.read_text(), out_root=cfg.paths.out,
            force=force, limit=limit, job_ids=job_ids,
        )  # fmt: skip
    except LlmError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"packaged {summary.packaged} of {summary.candidates} selected postings in "
        f"{summary.calls} LLM calls · needs review {summary.needs_review}"
    )
    for result in summary.results:
        flag = "ok " if result.verified else "REVIEW"
        typer.echo(f"  [{flag}] #{result.job_id} ({result.language}) {result.path}")
        for problem in result.problems:
            typer.echo(f"      - {problem}")
    for error in summary.errors:
        typer.echo(f"  failed: {error}", err=True)
    if summary.stopped:
        typer.echo(f"  stopped early: {summary.stopped} (re-run later to continue)")


def _print_score_summary(s: ScoreSummary) -> None:
    typer.echo(
        f"scored {s.scored} postings in {s.calls} LLM calls · reused {s.cached} cached · "
        f"failed {s.failed} · selected {s.selected} · below threshold {s.below_threshold}"
    )
    if s.stopped:
        typer.echo(f"  stopped early: {s.stopped} (re-run later to continue)")


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


cv_app = typer.Typer(help="Work with your LaTeX master CV.")
app.add_typer(cv_app, name="cv")


@cv_app.command("check")
def cv_check(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Validate the `% jh:` markers of master.tex (unique ids, balanced blocks) and compile it."""
    from jobhunter.doctor import compile_tex

    cfg = _load(config)
    path = cfg.paths.cv_master
    if not path.exists():
        typer.echo(f"error: {path} not found", err=True)
        raise typer.Exit(code=1)
    try:
        doc = latex.parse(path.read_text())
    except latex.CvError as exc:
        typer.echo(f"error: {path}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    entries = sum(isinstance(c, latex.Entry) for sec in doc.sections for c in sec.children)
    typer.echo(f"{len(doc.sections)} sections · {entries} entries · {len(doc.ids())} ids in total")
    if not doc.sections:
        typer.echo("warning: no `% jh:section` markers found; run `jobhunter cv init` first.")
    for warning in latex.sensitive_warnings(doc):
        typer.echo(f"warning: {warning} (marked text is sent to the LLM)")
    ok, detail = compile_tex(path, cfg.latex.engine, cfg.latex.timeout_seconds)
    typer.echo(f"compile: {detail}")
    if not ok:
        raise typer.Exit(code=1)


@cv_app.command("init")
def cv_init(
    source: Annotated[Path, typer.Argument(help="Your plain LaTeX CV.")],
    output: Annotated[
        Path | None, typer.Option(help="Where to write (default: <source>.marked.tex).")
    ] = None,
) -> None:
    """Propose `% jh:` markers for a plain LaTeX CV. Review the result before using it."""
    if not source.exists():
        typer.echo(f"error: {source} not found", err=True)
        raise typer.Exit(code=1)
    target = output or source.with_suffix(".marked.tex")
    target.write_text(latex.propose_markers(source.read_text()))
    typer.echo(
        f"wrote {target}. Review it: sections and bullets got ids; wrap job/project blocks in "
        "`% jh:entry <id> [required]` ... `% jh:endentry` by hand, "
        "then save it as config/cv/master.tex."
    )


@app.command()
def calibrate(
    count: Annotated[int, typer.Option(help="How many scored postings to review.")] = 20,
    config: ConfigOption = Path("config/config.yaml"),
) -> None:
    """Review the LLM's scores (y/n) so the rubric and threshold can be tuned."""
    import json

    cfg = _load(config)
    conn = connect(cfg.paths.db)
    rows = conn.execute(
        "SELECT j.id, j.title, j.company, j.location, j.url, s.score, s.reasons FROM jobs j "
        "JOIN scores s ON s.job_id = j.id WHERE j.id NOT IN (SELECT job_id FROM calibration) "
        "AND j.status IN ('selected', 'scored', 'below_threshold') "
        "GROUP BY j.id ORDER BY RANDOM() LIMIT ?",
        (count,),
    ).fetchall()
    if not rows:
        typer.echo("nothing to calibrate yet: score some postings first.")
        return
    from datetime import UTC, datetime

    for row in rows:
        info = json.loads(row["reasons"])
        typer.echo(f"\n#{row['id']} {row['title']} — {row['company']} ({row['location']})")
        typer.echo(f"  score {row['score']} · {info['verdict']} · {info['reason']}")
        if info.get("red_flags"):
            typer.echo(f"  red flags: {', '.join(info['red_flags'])}")
        typer.echo(f"  {row['url']}")
        agrees = typer.confirm("  Do you agree with this verdict?", default=True)
        with conn:
            conn.execute(
                "INSERT INTO calibration(job_id, llm_score, verdict, agrees, created_at) "
                "VALUES (?,?,?,?,?)",
                (
                    row["id"],
                    row["score"],
                    info["verdict"],
                    int(agrees),
                    datetime.now(UTC).isoformat(),
                ),
            )
    agree, total = conn.execute(
        "SELECT COALESCE(SUM(agrees), 0), COUNT(*) FROM calibration WHERE verdict = 'apply'"
    ).fetchone()
    if total:
        typer.echo(f"\nagreement on 'apply' verdicts so far: {agree}/{total} ({agree / total:.0%})")


@cv_app.command("translate")
def cv_translate(
    lang: Annotated[str, typer.Option("--lang", help="Target language code, e.g. es.")],
    force: Annotated[
        bool, typer.Option(help="Overwrite an existing reviewed translation.")
    ] = False,
    config: ConfigOption = Path("config/config.yaml"),
) -> None:
    """Translate the master CV once into another language, for you to review and edit."""
    from jobhunter.translate import save_translation, translate_cv

    cfg = _load(config)
    master = cfg.paths.cv_master
    if not master.exists():
        typer.echo(f"error: {master} not found", err=True)
        raise typer.Exit(code=1)
    doc = latex.parse(master.read_text())
    from jobhunter.translate import translation_path

    existing = translation_path(master.parent, lang)
    if existing.exists() and not force:
        typer.echo(
            f"error: {existing} already exists (it may hold your reviewed edits). "
            "Use --force to overwrite it.",
            err=True,
        )
        raise typer.Exit(code=1)
    conn = connect(cfg.paths.db)
    try:
        units, problems = translate_cv(_make_client(cfg, conn), cfg, doc, lang)
    except LlmError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    path = save_translation(master.parent, lang, units, problems, doc.source_hash)
    typer.echo(f"translated {len(units)} units into {path}")
    if problems:
        typer.echo(f"{len(problems)} units need attention (numbers or LaTeX changed); fix them:")
        for uid, found in problems.items():
            typer.echo(f"  {uid}: {', '.join(found)}")
    typer.echo("Review the file; the language must also be listed in tailoring.languages.")


letter_app = typer.Typer(help="Cover letter template.")
app.add_typer(letter_app, name="letter")


@letter_app.command("init")
def letter_init(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Create config/cv/letter_template.tex from the example; you edit the header lines."""
    import shutil

    cfg = _load(config)
    target = cfg.paths.letter_template
    example = Path(__file__).resolve().parents[2] / "config" / "letter_template.example.tex"
    if target.exists():
        typer.echo(f"{target} already exists; not overwriting.")
        return
    if not example.exists():
        typer.echo(f"error: example template not found at {example}", err=True)
        raise typer.Exit(code=1)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(example, target)
    typer.echo(
        f"wrote {target}. Edit the header (name, role, contact); keep the %%...%% placeholders."
    )


@app.command()
def review(config: ConfigOption = Path("config/config.yaml")) -> None:
    """List generated packages that are waiting for you to review and apply."""
    cfg = _load(config)
    conn = connect(cfg.paths.db)
    rows = conn.execute(
        "SELECT j.id, j.company, j.title, p.path, p.verified, "
        "(SELECT score FROM scores WHERE job_id = j.id ORDER BY created_at DESC LIMIT 1) AS score "
        "FROM jobs j JOIN packages p ON p.job_id = j.id "
        "AND p.created_at = (SELECT MAX(created_at) FROM packages WHERE job_id = j.id) "
        "WHERE j.status = 'packaged' ORDER BY score DESC"
    ).fetchall()
    if not rows:
        typer.echo("no packages waiting. Run `jobhunter run --stage tailor` first.")
        return
    for row in rows:
        flag = "ok" if row["verified"] else "REVIEW"
        typer.echo(
            f"#{row['id']} [{flag}] score {row['score']} · {row['title']} — {row['company']}"
        )
        typer.echo(f"    {row['path']}")


STAGE_HELP = (
    "applied | screening | interviewing | offer | accepted | rejected | withdrawn | ghosted"
)


@app.command()
def mark(
    job_id: Annotated[int, typer.Argument(help="Posting id.")],
    stage: Annotated[str, typer.Argument(help=STAGE_HELP)],
    note: Annotated[str | None, typer.Option(help="Optional note to keep with the change.")] = None,
    config: ConfigOption = Path("config/config.yaml"),
) -> None:
    """Record where an application stands (you apply yourself; this only keeps track)."""
    from jobhunter import applications

    cfg = _load(config)
    conn = connect(cfg.paths.db)
    try:
        applications.set_stage(conn, job_id, stage, note)
    except applications.TrackingError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"#{job_id} is now '{stage}'")


@app.command()
def favorite(
    job_id: Annotated[int, typer.Argument(help="Posting id.")],
    note: Annotated[str | None, typer.Option(help="Short note, e.g. 'ask about the visa'.")] = None,
    remove: Annotated[bool, typer.Option("--remove", help="Remove the star instead.")] = False,
    config: ConfigOption = Path("config/config.yaml"),
) -> None:
    """Star a posting (any status) so it stays easy to find, or remove its star."""
    from jobhunter import favorites
    from jobhunter.applications import TrackingError

    cfg = _load(config)
    conn = connect(cfg.paths.db)
    try:
        if remove:
            changed = favorites.remove_favorite(conn, job_id)
            typer.echo(f"#{job_id} unstarred" if changed else f"#{job_id} was not a favorite")
            return
        favorites.set_favorite(conn, job_id, note)
    except TrackingError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"#{job_id} starred")


@app.command("favorites")
def favorites_list(config: ConfigOption = Path("config/config.yaml")) -> None:
    """List starred postings, newest first."""
    from jobhunter import favorites

    cfg = _load(config)
    items = favorites.list_favorites(connect(cfg.paths.db))
    if not items:
        typer.echo("no favorites yet. Star one with: jobhunter favorite ID")
        return
    for item in items:
        note = f" — {item['note']}" if item["note"] else ""
        typer.echo(f"#{item['id']} {item['title']} · {item['company']} [{item['status']}]{note}")


@app.command()
def stats(config: ConfigOption = Path("config/config.yaml")) -> None:
    """Funnel from fetched postings to offers, rejections by rule and LLM usage."""
    from jobhunter import applications

    cfg = _load(config)
    data = applications.stats(connect(cfg.paths.db))
    f = data["funnel"]
    typer.echo(
        f"fetched {f['fetched']} → passed filter {f['passed_filter']} → scored {f['scored']} → "
        f"selected {f['selected']} → packaged {f['packaged']} → applied {f['applied']} → "
        f"interviewing {f['interviewing']} → offers {f['offer']}"
    )
    for rule, count in data["rejected_by_rule"].items():
        typer.echo(f"  filtered by {rule}: {count}")
    for stage, count in data["stages"].items():
        typer.echo(f"  applications {stage}: {count}")
    today, total = data["llm_today"], data["llm_total"]
    typer.echo(
        f"LLM today: {today['calls']} calls, {today['tin'] + today['tout']} tokens · "
        f"all time: {total['calls']} calls (API-equivalent ${total['cost']:.2f})"
    )


@app.command()
def ui(
    port: Annotated[int, typer.Option(help="Port on 127.0.0.1.")] = 8765,
    open_browser: Annotated[bool, typer.Option("--open", help="Open the browser.")] = False,
    config: ConfigOption = Path("config/config.yaml"),
) -> None:
    """Start the local web UI (dashboard, postings, pipeline, manual runs) on 127.0.0.1."""
    import threading
    import webbrowser

    import uvicorn

    from jobhunter.web.app import create_app
    from jobhunter.web.runner import RunManager

    cfg = _load(config)
    manager = RunManager(config.resolve(), Path.cwd(), log_dir=cfg.paths.db.parent / "runs")
    web_app = create_app(config, port=port, runner=manager)
    url = f"http://127.0.0.1:{port}"
    typer.echo(f"Job Hunter UI on {url}  (Ctrl+C to stop; only reachable from this machine)")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(web_app, host="127.0.0.1", port=port, log_level="warning")
