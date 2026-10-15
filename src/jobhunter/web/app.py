"""FastAPI application for the local UI. Server-rendered pages + a small JSON API."""

from __future__ import annotations

import json
import math
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from jobhunter import applications, config_edit, favorites, fetch_url, latex, postings, tailoring
from jobhunter import top as top_board
from jobhunter.config import Config, ConfigError, load_config
from jobhunter.db import connect
from jobhunter.doctor import run_checks, source_keys
from jobhunter.filters import JobFilter, job_from_row, normalize_company
from jobhunter.sources import registry as sources_registry
from jobhunter.web.runner import RUN_SPECS, Busy, RunError, RunManager

HERE = Path(__file__).parent
PAGE_SIZE = 50
SERVED_SUFFIXES = {".pdf", ".tex", ".md", ".json", ".txt"}
ACTIVE_STATUSES = (
    "passed", "scored", "selected", "packaged", "below_threshold", "score_failed",
    "applied", "replied", "rejected",
)  # fmt: skip
STATUS_LABELS = {
    "new": "New", "filtered": "Filtered out", "passed": "Passed filter", "scored": "Scored",
    "selected": "Selected", "packaged": "Packaged", "below_threshold": "Below match score",
    "score_failed": "Score failed", "applied": "Applied", "replied": "In process",
    "rejected": "Rejected", "closed": "Closed", "duplicate": "Duplicate", "ignored": "Ignored",
}  # fmt: skip
STAGE_LABELS = {
    "applied": "Applied", "screening": "Screening", "interviewing": "Interviewing",
    "offer": "Offer", "accepted": "Accepted", "rejected": "Rejected",
    "withdrawn": "Withdrawn", "ghosted": "No response",
}  # fmt: skip


SOURCE_LABELS = {
    "getonboard": "Get on Board", "himalayas": "Himalayas", "themuse": "The Muse",
    "weworkremotely": "We Work Remotely", "remoteok": "RemoteOK", "remotive": "Remotive",
    "arbeitnow": "Arbeitnow", "jobicy": "Jobicy", "greenhouse": "Greenhouse", "lever": "Lever",
    "ashby": "Ashby", "manual": "Added by hand",
}  # fmt: skip


def score_options(current: int | None, threshold: int) -> list[dict[str, Any]]:
    values = sorted({*SCORE_FLOORS, threshold, *([current] if current is not None else [])})
    return [{"value": v, "label": f"{v}+" + (" (your threshold)" if v == threshold else "")}
            for v in values]  # fmt: skip


def active_filters(
    q: str, source: str, mode: str, fav: bool, days: int | None, score: int | None
) -> list[dict[str, str]]:
    """What the person has narrowed the list by, as removable chips (name = form control)."""
    chips = []
    if q:
        chips.append({"name": "q", "label": f"“{q}”"})
    if source:
        chips.append({"name": "source", "label": f"Source: {source_label(source)}"})
    if days is not None:
        chips.append(
            {"name": "fresh", "label": f"Posted: last {days} day{'s' if days != 1 else ''}"}
        )
    if score is not None:
        chips.append({"name": "min_score", "label": f"Score {score}+"})
    if mode:
        chips.append({"name": "mode", "label": f"Mode: {mode}"})
    if fav:
        chips.append({"name": "fav", "label": "★ Favorites only"})
    return chips


def asset_url(name: str) -> str:
    """`/static/<name>?v=<mtime>`: a changed file is never served from the browser cache."""
    try:
        version = int((HERE / "static" / name).stat().st_mtime)
    except OSError:
        version = 0
    return f"/static/{name}?v={version}"


FRESH_DAYS = (1, 3, 7, 14, 30, 60, 90)
SCORE_FLOORS = (50, 60, 70, 75, 80, 90)


def fresh_options(rule_days: int) -> list[dict[str, Any]]:
    """Choices for the *Posted* filter; the configured rule is included and marked."""
    days = sorted({*FRESH_DAYS, rule_days})
    return [
        {"days": d, "label": f"last {d} day{'s' if d != 1 else ''}"
         + (" (your rule)" if d == rule_days else "")}
        for d in days
    ]  # fmt: skip


def source_label(name: str) -> str:
    return SOURCE_LABELS.get(name, name)


JOB_TABS = (
    ("best", "Best matches", ("selected", "packaged")),
    ("evaluated", "All evaluated",
     ("scored", "selected", "packaged", "below_threshold", "applied", "replied", "rejected")),
    ("applied", "Applied", ("applied", "replied", "rejected")),
    ("filtered", "Filtered out", ("filtered",)),
    ("all", "Everything", None),
)  # fmt: skip
RULE_LABELS = {
    "titles_include": "Title is not one of your target roles",
    "titles_exclude": "Title contains a word you excluded (frontend, mobile, QA...)",
    "work_mode": "Not a remote role",
    "seniority": "Seniority does not match (junior / staff / lead...)",
    "locations_allowed": "Not open to your location",
    "keywords_include": "None of your key technologies mentioned",
    "keywords_exclude": "Mentions something you cannot do (e.g. citizenship)",
    "salary": "Pay below your minimum",
    "max_age_days": "Posted too long ago",
    "companies_exclude": "Company is on your block list",
}


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def bar_width(n: int, total: int) -> float:
    """Funnel bar width in %, log-scaled so small stages stay visible next to huge ones."""
    if not n or not total:
        return 0.0
    return max(3.0, round(100 * math.log10(n + 1) / math.log10(total + 1), 1))


def kpis(conn: sqlite3.Connection, data: dict[str, Any]) -> dict[str, int]:
    """The four numbers shown at the top of the dashboard."""
    by = data["by_status"]
    ready = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('selected', 'packaged') AND id NOT IN "
        "(SELECT job_id FROM applications)"
    ).fetchone()[0]
    active = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE stage IN ('applied', 'screening', "
        "'interviewing', 'offer')"
    ).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM interviews WHERE outcome = 'pending'").fetchone()[
        0
    ]
    return {
        "matches": by.get("selected", 0) + by.get("packaged", 0) + by.get("scored", 0),
        "ready": ready, "active": active, "interviews": pending,
    }  # fmt: skip


def build_suggestions(
    conn: sqlite3.Connection, data: dict[str, Any], config: Config | None = None
) -> list[dict[str, Any]]:
    """Plain-language 'what to do next' list, most useful first."""
    by = data["by_status"]
    out: list[dict[str, Any]] = []
    if data["total"] == 0:
        out.append(
            {
                "text": "No postings yet. Run your first search to see what is out there.",
                "run": {"id": "search", "label": "Search for new jobs"},
            }
        )
        return out
    unscored = by.get("passed", 0) + by.get("score_failed", 0)
    if unscored:
        out.append(
            {
                "text": f"{plural(unscored, 'posting matches', 'postings match')} your criteria, "
                f"{'and is' if unscored == 1 else 'and are'} waiting for AI scoring.",
                "run": {"id": "score", "label": "Score them with AI", "llm": True},
            }
        )
    unpackaged = by.get("selected", 0)
    if unpackaged:
        out.append(
            {
                "text": f"{plural(unpackaged, 'top match has', 'top matches have')} no tailored CV "
                "and cover letter yet.",
                "run": {"id": "tailor", "label": "Build their packages", "llm": True},
                "link": {"href": "/jobs?status=best", "label": "Review them first"},
            }
        )
    ready = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status = 'packaged' AND id NOT IN "
        "(SELECT job_id FROM applications)"
    ).fetchone()[0]
    if ready:
        out.append(
            {
                "text": f"{plural(ready, 'package is', 'packages are')} ready. Open "
                f"{'it' if ready == 1 else 'them'}, check the notes and apply.",
                "link": {"href": "/packages", "label": "Open packages"},
            }
        )
    stale = conn.execute(
        "SELECT COUNT(*) FROM applications WHERE stage IN ('applied', 'screening') AND "
        "updated_at < ?",
        ((datetime.now(UTC) - timedelta(days=7)).isoformat(),),
    ).fetchone()[0]
    if stale:
        out.append(
            {
                "text": f"{plural(stale, 'application has', 'applications have')} had no update "
                "for a week. Time to follow up?",
                "link": {"href": "/pipeline", "label": "Open pipeline"},
            }
        )
    if config is not None:
        off = [n for n in sources_registry.aggregators() if n not in config.sources.aggregators]
        if off:
            names = ", ".join(source_label(n) for n in off)
            out.append(
                {
                    "text": f"{plural(len(off), 'source is', 'sources are')} available but not "
                    f"enabled: {names}. Turn them on to see their postings.",
                    "link": {"href": "/settings#sources", "label": "Open Settings → Sources"},
                }
            )
    last = conn.execute("SELECT MAX(created_at) FROM fetch_log").fetchone()[0]
    if last and datetime.fromisoformat(last) < datetime.now(UTC) - timedelta(days=2):
        out.append(
            {
                "text": "Your last search was more than two days ago.",
                "run": {"id": "search", "label": "Search again"},
            }
        )
    return out


class LocalOnlyMiddleware(BaseHTTPMiddleware):
    """Reject foreign Host/Origin (DNS rebinding, cross-site posts) and non-JSON writes."""

    def __init__(self, app: Any, allowed_hosts: set[str]) -> None:
        super().__init__(app)
        self.allowed = allowed_hosts

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.headers.get("host", "") not in self.allowed:
            return JSONResponse({"error": "forbidden host"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc not in self.allowed:
            return JSONResponse({"error": "forbidden origin"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS") and not request.headers.get(
            "content-type", ""
        ).startswith("application/json"):
            return JSONResponse({"error": "JSON body required"}, status_code=415)
        return await call_next(request)


def create_app(
    config_path: Path, *, port: int = 8765, allowed_hosts: set[str] | None = None,
    runner: RunManager | None = None,
) -> FastAPI:  # fmt: skip
    config_path = config_path.resolve()
    hosts = allowed_hosts or {f"127.0.0.1:{port}", f"localhost:{port}"}
    app = FastAPI(title="Job Hunter", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(LocalOnlyMiddleware, allowed_hosts=hosts)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    manager = runner or RunManager(config_path, Path.cwd(), log_dir=None)
    templates.env.filters["dt"] = fmt_dt
    templates.env.filters["money"] = money
    templates.env.filters["bar_width"] = bar_width
    templates.env.filters["norm_company"] = normalize_company
    templates.env.globals.update(
        AGGREGATORS=list(sources_registry.aggregators()),
        NOT_FOR_ME_REASONS=top_board.REASONS,
        asset=asset_url,
        source_label=lambda n: SOURCE_LABELS.get(n, n),
        STATUS_LABELS=STATUS_LABELS, STAGE_LABELS=STAGE_LABELS,
        STAGES=applications.STAGES, KINDS=applications.INTERVIEW_KINDS,
        OUTCOMES=applications.INTERVIEW_OUTCOMES,
    )  # fmt: skip

    def cfg() -> Config:
        return load_config(config_path)

    def db(config: Config) -> sqlite3.Connection:
        return connect(config.paths.db)

    def blocked_set(config: Config) -> set[str]:
        return {n for n in map(normalize_company, config.search.companies_exclude) if n}

    def render(request: Request, name: str, **ctx: Any) -> Any:
        return templates.TemplateResponse(request, name, {"active": ctx.pop("active", ""), **ctx})

    @app.exception_handler(ConfigError)
    async def config_error(request: Request, exc: ConfigError) -> Any:
        return templates.TemplateResponse(request, "error.html", {"message": str(exc)}, 500)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Any:
        """Pages answer with the normal layout; the JSON API keeps JSON."""
        path = request.url.path
        if path.startswith(("/api/", "/static/", "/files/")) or request.method != "GET":
            return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)
        titles = {404: "Page not found", 405: "Not allowed"}
        message = (
            "That page does not exist. Check the address, or go back to where you were."
            if exc.status_code == 404
            else str(exc.detail)
        )
        return templates.TemplateResponse(
            request,
            "error.html",
            {"message": message, "title": titles.get(exc.status_code, "Something went wrong")},
            exc.status_code,
        )

    @app.exception_handler(applications.TrackingError)
    async def tracking_error(request: Request, exc: applications.TrackingError) -> Any:
        return JSONResponse({"error": str(exc)}, status_code=400)

    # -- pages -----------------------------------------------------------------------------

    @app.get("/")
    def dashboard(request: Request) -> Any:
        config = cfg()
        conn = db(config)
        data = applications.stats(conn)
        return render(
            request, "dashboard.html", active="dashboard", stats=data,
            suggestions=build_suggestions(conn, data, config),
            upcoming=applications.upcoming_interviews(conn),
            kpis=kpis(conn, data), rule_labels=RULE_LABELS,
            max_calls=config.budget.max_llm_calls_per_run, backend=config.llm.backend,
            running=manager.active(), favorites_open=favorites.count_without_application(conn),
            plan=top_board.plan(conn, config),
        )  # fmt: skip

    @app.get("/jobs")
    def jobs_page(
        request: Request, status: str = "best", source: str = "", q: str = "",
        min_score: str = "", mode: str = "", sort: str = "score", page: int = 1,
        fav: str = "", fresh: str = "",
    ) -> Any:  # fmt: skip
        config = cfg()
        conn = db(config)
        days = int(fresh) if fresh.strip().isdigit() and 0 < int(fresh) <= 3650 else None
        score_floor = int(min_score) if min_score.strip().lstrip("-").isdigit() else None
        where, params = ["1=1"], []
        tab_statuses = {key: sts for key, _, sts in JOB_TABS}
        if status == "favorites":
            where.append("f.job_id IS NOT NULL")
        elif status == "active":
            where.append(f"j.status IN ({','.join('?' for _ in ACTIVE_STATUSES)})")
            params += ACTIVE_STATUSES
        elif status in tab_statuses and tab_statuses[status]:
            where.append(f"j.status IN ({','.join('?' for _ in tab_statuses[status])})")
            params += tab_statuses[status]
        elif status not in ("all", *tab_statuses):
            where.append("j.status = ?")
            params.append(status)
        if fav == "1" and status != "favorites":
            where.append("f.job_id IS NOT NULL")
        if source:
            where.append("j.source = ?")
            params.append(source)
        if mode:
            where.append("j.remote = ?")
            params.append(mode)
        if q:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where.append("(j.title LIKE ? ESCAPE '\\' OR j.company LIKE ? ESCAPE '\\')")
            params += [f"%{escaped}%", f"%{escaped}%"]
        if days is not None:  # undated postings stay: a still-listed company posting is open
            cutoff = (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0)
            where.append("(j.posted_at IS NULL OR j.posted_at >= ?)")
            params.append(cutoff.isoformat())
        if score_floor is not None:
            where.append("s.score >= ?")
            params.append(score_floor)
        order = {
            "score": "s.score IS NULL, s.score DESC, j.id DESC",
            "recent": "j.posted_at IS NULL, j.posted_at DESC",
            "company": "j.company COLLATE NOCASE, j.title",
            "favorites": "f.job_id IS NULL, s.score IS NULL, s.score DESC, j.id DESC",
        }.get(sort, "s.score DESC")
        base = (
            "FROM jobs j LEFT JOIN scores s ON s.job_id = j.id AND s.created_at = "
            "(SELECT MAX(created_at) FROM scores WHERE job_id = j.id) "
            "LEFT JOIN favorites f ON f.job_id = j.id "
            f"WHERE {' AND '.join(where)}"
        )
        total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        page = min(max(1, page), 100_000)
        rows = conn.execute(
            "SELECT j.id, j.company, j.title, j.location, j.remote, j.source, j.status, "
            "j.salary_min, j.salary_max, j.salary_currency, j.posted_at, s.score, "
            "json_extract(s.reasons, '$.verdict') AS verdict, "
            "json_extract(s.reasons, '$.reason') AS reason, "
            "json_array_length(json_extract(s.reasons, '$.red_flags')) AS flags, "
            "EXISTS(SELECT 1 FROM packages WHERE job_id = j.id) AS has_package, "
            "(SELECT stage FROM applications WHERE job_id = j.id) AS stage, "
            "f.job_id IS NOT NULL AS is_favorite, f.note AS favorite_note "
            f"{base} ORDER BY {order} LIMIT ? OFFSET ?",
            [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
        ).fetchall()
        counts = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")}  # fmt: skip
        tabs = [
            {"key": key, "label": label,
             "n": sum(counts.values()) if sts is None else sum(counts.get(x, 0) for x in sts)}
            for key, label, sts in JOB_TABS
        ]  # fmt: skip
        fav_total = conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0]
        tabs.append({"key": "favorites", "label": "★ Favorites", "n": fav_total})
        per_source = {r[0]: r[1] for r in conn.execute(
            "SELECT source, COUNT(*) FROM jobs GROUP BY source")}  # fmt: skip
        enabled = [*config.sources.aggregators, *sources_registry.company_boards()]
        sources = [
            {"name": n, "label": source_label(n), "count": per_source.get(n, 0)}
            for n in dict.fromkeys([*enabled, *sorted(per_source)])
        ]
        plan = None
        board_ids: set[int] = set()
        if (
            status == "best"
            and page == 1
            and not (q or source or mode or fav or days or score_floor is not None)
        ):
            plan = top_board.plan(conn, config)
            board_ids = {r["id"] for r in plan["board"]}
            rows = [r for r in rows if r["id"] not in board_ids]
        return render(
            request, "jobs.html", active="jobs", rows=rows, total=total, page=page,
            plan=plan, board_suggestions=top_board.suggestions(conn) if plan else [],
            pages=max(1, -(-total // PAGE_SIZE)), counts=counts, sources=sources, tabs=tabs,
            qs=urlencode({k: v for k, v in {"status": status, "source": source, "q": q,
                          "mode": mode, "sort": sort, "min_score": score_floor,
                          "fresh": days, "fav": "1" if fav == "1" else ""}.items()
                          if v not in ("", None)}),
            f={"status": status, "source": source, "q": q, "min_score": score_floor,
               "mode": mode, "sort": sort, "fav": fav == "1", "fresh": days},
            fresh_options=fresh_options(config.search.max_age_days),
            score_options=score_options(score_floor, config.scoring.score_threshold),
            active_filters=active_filters(q, source, mode, fav == "1", days, score_floor),
            blocked=blocked_set(config),
        )  # fmt: skip

    @app.get("/jobs/{job_id}")
    def job_page(request: Request, job_id: int) -> Any:
        config = cfg()
        conn = db(config)
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return templates.TemplateResponse(
                request,
                "error.html",
                {"message": f"No posting with id {job_id}.", "title": "Posting not found"},
                404,
            )
        score = conn.execute(
            "SELECT * FROM scores WHERE job_id = ? ORDER BY created_at DESC LIMIT 1", (job_id,)
        ).fetchone()
        verdict = JobFilter(config.search, config.fx_rates_to_usd).evaluate(job_from_row(row))
        package = conn.execute(
            "SELECT * FROM packages WHERE job_id = ? ORDER BY created_at DESC LIMIT 1", (job_id,)
        ).fetchone()
        events = conn.execute(
            "SELECT * FROM events WHERE job_id = ? ORDER BY rowid DESC LIMIT 30", (job_id,)
        ).fetchall()
        application = conn.execute(
            "SELECT * FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
        return render(
            request, "job.html", active="jobs", job=row, verdict=verdict,
            threshold=config.scoring.score_threshold,
            score=score, info=json.loads(score["reasons"]) if score else None,
            package=package_view(config, package), application=application,
            interviews=applications.list_interviews(conn, job_id), events=events,
            favorite=conn.execute(
                "SELECT * FROM favorites WHERE job_id = ?", (job_id,)
            ).fetchone(),
            blocked=normalize_company(row["company"]) in blocked_set(config),
            config_blocked=config.search.companies_exclude,
        )  # fmt: skip

    @app.get("/pipeline")
    def pipeline_page(request: Request) -> Any:
        config = cfg()
        conn = db(config)
        cards = applications.list_applications(conn)
        ready = conn.execute(
            "SELECT j.id, j.company, j.title, j.status, "
            "(SELECT score FROM scores WHERE job_id = j.id ORDER BY created_at DESC LIMIT 1) "
            "AS score FROM jobs j WHERE j.status IN ('selected', 'packaged') AND j.id NOT IN "
            "(SELECT job_id FROM applications) ORDER BY score DESC"
        ).fetchall()
        return render(
            request, "pipeline.html", active="pipeline", cards=cards, ready=ready,
            columns=applications.STAGES,
        )  # fmt: skip

    @app.get("/packages")
    def packages_page(request: Request) -> Any:
        config = cfg()
        conn = db(config)
        rows = conn.execute(
            "SELECT j.id, j.company, j.title, j.status, p.path, p.verified, p.created_at, "
            "(SELECT score FROM scores WHERE job_id = j.id ORDER BY created_at DESC LIMIT 1) "
            "AS score FROM packages p JOIN jobs j ON j.id = p.job_id AND p.created_at = "
            "(SELECT MAX(created_at) FROM packages WHERE job_id = j.id) ORDER BY p.created_at DESC"
        ).fetchall()
        items = [{"row": r, "pkg": package_view(config, r)} for r in rows]
        return render(request, "packages.html", active="packages", items=items)

    @app.get("/run")
    def run_page(request: Request) -> Any:
        config = cfg()
        return render(
            request, "run.html", active="run", specs=RUN_SPECS, history=manager.history(),
            max_calls=config.budget.max_llm_calls_per_run, backend=config.llm.backend,
        )  # fmt: skip

    @app.get("/settings")
    def settings_page(request: Request) -> Any:
        config = cfg()
        cv = None
        if config.paths.cv_master.exists():
            try:
                cv = latex.parse(config.paths.cv_master.read_text())
            except latex.CvError as exc:
                cv = str(exc)
        return render(
            request, "settings.html", active="settings", config=config.model_dump(mode="json"),
            config_path=str(config_path), cv=cv, source_keys=source_keys(config),
        )  # fmt: skip

    # -- files -----------------------------------------------------------------------------

    @app.get("/files/{rel_path:path}")
    def serve_file(rel_path: str) -> Any:
        root = cfg().paths.out.resolve()
        target = (root / rel_path).resolve()
        if (
            root not in target.parents
            or target.suffix not in SERVED_SUFFIXES
            or not target.is_file()
        ):
            return JSONResponse({"error": "not found"}, status_code=404)
        media = "application/pdf" if target.suffix == ".pdf" else "text/plain; charset=utf-8"
        return FileResponse(target, media_type=media, headers={"Content-Disposition": "inline"})

    # -- JSON API --------------------------------------------------------------------------

    health_cache: dict[str, Any] = {"at": 0.0, "data": []}

    @app.get("/api/health")
    def health() -> Any:
        """Doctor checks, cached for a minute (they spawn `claude` and compile LaTeX)."""
        if time.monotonic() - health_cache["at"] > 60 or not health_cache["data"]:
            checks = run_checks(config_path)
            health_cache["data"] = [
                {"name": c.name, "ok": c.ok, "detail": c.detail, "required": c.required}
                for c in checks
            ]
            health_cache["at"] = time.monotonic()
        return health_cache["data"]

    async def read_json(request: Request) -> Any:
        try:
            return await request.json()
        except ValueError:
            return None

    @app.get("/api/config")
    def api_get_config() -> Any:
        return cfg().model_dump(mode="json")

    @app.post("/api/config")
    async def api_save_config(request: Request) -> Any:
        body = await read_json(request)
        updates = body.get("updates") if isinstance(body, dict) else None
        if not isinstance(updates, dict) or not updates:
            return JSONResponse({"error": "updates object required"}, status_code=400)
        try:
            config_edit.save_updates(config_path, updates)
        except config_edit.ConfigUpdateError as exc:
            return JSONResponse({"error": str(exc), "errors": exc.errors}, status_code=422)
        return {"ok": True}

    def editable_file(name: str) -> Path | None:
        config = cfg()
        return {
            "cv": config.paths.cv_master,
            "letter": config.paths.letter_template,
            "candidates": config.sources.candidates_file,
        }.get(name)

    @app.get("/api/files/{name}")
    def api_get_file(name: str) -> Any:
        path = editable_file(name)
        if path is None:
            return JSONResponse({"error": "unknown file"}, status_code=404)
        try:
            content = path.read_text(encoding="utf-8") if path.exists() else ""
        except UnicodeDecodeError:
            return JSONResponse({"error": "the file is not valid UTF-8 text"}, status_code=422)
        return {"path": str(path), "exists": path.exists(), "content": content}

    @app.post("/api/files/{name}")
    async def api_save_file(request: Request, name: str) -> Any:
        path = editable_file(name)
        body = await read_json(request)
        content = body.get("content") if isinstance(body, dict) else None
        if path is None or not isinstance(content, str):
            return JSONResponse({"error": "unknown file or missing content"}, status_code=400)
        try:
            config_edit.check_file_size(content)
            if name in ("cv", "letter") and not content.strip():
                raise ValueError("refusing to save an empty file")
            if name == "cv":
                latex.parse(content)
            elif name == "letter":
                config_edit.validate_letter_template(content)
        except (ValueError, latex.CvError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        config_edit.write_atomic(path, content if content.endswith("\n") else content + "\n")
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/favorite")
    async def api_favorite(request: Request, job_id: int) -> Any:
        body = await read_json(request)
        if not isinstance(body, dict) or not isinstance(body.get("on"), bool):
            return JSONResponse({"error": "{on: bool} required"}, status_code=400)
        note = body.get("note")
        if note is not None and not isinstance(note, str):
            return JSONResponse({"error": "note must be text"}, status_code=400)
        conn = db(cfg())
        if body["on"]:
            favorites.set_favorite(conn, job_id, note)
        else:
            favorites.remove_favorite(conn, job_id)
        return {"ok": True}

    @app.get("/api/favorites")
    def api_favorites() -> Any:
        return favorites.list_favorites(db(cfg()))

    @app.post("/api/jobs/{job_id}/package/delete")
    async def api_delete_package(job_id: int) -> Any:
        config = cfg()
        removed = tailoring.delete_packages(db(config), config.paths.out, job_id)
        return {"ok": True, "deleted": removed}

    @app.post("/api/postings/fetch")
    async def api_fetch_posting(request: Request) -> Any:
        """Fetch ONE page and pre-fill the form; the person reviews before saving."""
        body = await read_json(request)
        url = body.get("url") if isinstance(body, dict) else None
        if not isinstance(url, str) or not url.strip() or len(url) > postings.MAX_URL:
            return JSONResponse({"error": "a link is required"}, status_code=400)
        try:
            page = fetch_url.fetch_page(url)
        except fetch_url.FetchPageError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        fields = fetch_url.extract_posting(page.html, page.url)
        company = fields.get("company") or ""
        fields["blocked"] = bool(company) and normalize_company(company) in blocked_set(cfg())
        return fields

    @app.post("/api/postings")
    async def api_add_posting(request: Request) -> Any:
        body = await read_json(request)
        if not isinstance(body, dict):
            return JSONResponse({"error": "posting fields required"}, status_code=400)
        config = cfg()
        try:
            job_id, created = postings.add_manual(db(config), body)
        except postings.PostingError as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        blocked = normalize_company(str(body.get("company", ""))) in blocked_set(config)
        return {"ok": True, "id": job_id, "created": created, "blocked": blocked,
                "url": f"/jobs/{job_id}"}  # fmt: skip

    @app.post("/api/jobs/{job_id}/stage")
    async def api_stage(request: Request, job_id: int) -> Any:
        body = await request.json()
        applications.set_stage(db(cfg()), job_id, str(body.get("stage", "")), body.get("note"))
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/ignore")
    async def api_ignore(request: Request, job_id: int) -> Any:
        body = await request.json()
        reason = body.get("reason")
        if reason:  # "Not for me": hide it and record why (only counted, spec 22)
            applications.dismiss(db(cfg()), job_id, str(reason), body.get("note"))
        else:
            applications.ignore(db(cfg()), job_id, body.get("note"))
        return {"ok": True}

    @app.get("/api/top")
    def api_top() -> Any:
        """The Top matches plan: how many places are empty and which postings could fill them.

        Read-only. Scoring them is a separate run the person starts (never automatic).
        """
        plan = top_board.plan(db(cfg()), cfg())
        keys = ("target", "need", "above", "below", "fill_ids", "unscored_left")
        return {k: plan[k] for k in keys} | {"board": [r["id"] for r in plan["board"]]}

    @app.post("/api/jobs/{job_id}/notes")
    async def api_notes(request: Request, job_id: int) -> Any:
        body = await request.json()
        applications.set_notes(db(cfg()), job_id, str(body.get("notes", "")))
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/interviews")
    async def api_add_interview(request: Request, job_id: int) -> Any:
        body = await request.json()
        new_id = applications.add_interview(
            db(cfg()),
            job_id,
            str(body.get("kind", "")),
            body.get("scheduled_at"),
            body.get("notes"),
        )
        return {"ok": True, "id": new_id}

    @app.post("/api/interviews/{interview_id}")
    async def api_update_interview(request: Request, interview_id: int) -> Any:
        body = await request.json()
        fields = {k: body[k] for k in ("kind", "scheduled_at", "notes", "outcome") if k in body}
        if not isinstance(body, dict):
            return JSONResponse({"error": "JSON object required"}, status_code=400)
        applications.update_interview(db(cfg()), interview_id, **fields)
        return {"ok": True}

    @app.post("/api/interviews/{interview_id}/delete")
    async def api_delete_interview(request: Request, interview_id: int) -> Any:
        applications.delete_interview(db(cfg()), interview_id)
        return {"ok": True}

    @app.post("/api/runs")
    async def api_start_run(request: Request) -> Any:
        body = await request.json()
        try:
            run = manager.start(
                str(body.get("id", "")), dry_run=bool(body.get("dry_run")),
                jobs=[int(j) for j in body.get("jobs") or []],
                limit=int(body["limit"]) if body.get("limit") else None,
                force=bool(body.get("force")),
            )  # fmt: skip
        except Busy as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)
        except (RunError, ValueError, TypeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return run.to_dict()

    @app.get("/api/runs/{run_id}")
    def api_get_run(run_id: str, since: int = 0) -> Any:
        run = manager.get(run_id)
        if run is None:
            return JSONResponse({"error": "unknown run"}, status_code=404)
        return run.to_dict(since)

    def package_view(config: Config, pkg: sqlite3.Row | None) -> dict[str, Any] | None:
        """Files of a package as links under /files, plus the verification result."""
        if pkg is None:
            return None
        root = config.paths.out.resolve()
        folder = Path(pkg["path"]).resolve()
        if root not in folder.parents or not folder.is_dir():
            return None
        meta: dict[str, Any] = {}
        meta_path = folder / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
            except ValueError:
                meta = {"problems": ["meta.json is unreadable"]}
        files = [
            {"name": f.name, "url": f"/files/{f.relative_to(root).as_posix()}"}
            for f in sorted(folder.iterdir())
            if f.suffix in SERVED_SUFFIXES
        ]
        message = folder / "recruiter_message.md"
        return {
            "files": files, "meta": meta, "verified": bool(pkg["verified"]),
            "recruiter_message": message.read_text() if message.exists() else "",
            "folder": str(folder),
        }  # fmt: skip

    return app


def fmt_dt(value: str | float | None) -> str:
    """ISO timestamp (or epoch seconds) → 'Oct 11, 2026 14:05' (UTC)."""
    if not value:
        return "—"
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC).strftime("%b %d, %Y %H:%M")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo:
        parsed = parsed.astimezone(UTC)
    return parsed.strftime("%b %d, %Y %H:%M")


def money(amount: int | None, currency: str | None = "USD") -> str:
    if not amount:
        return "—"
    return f"{currency or 'USD'} {amount / 1000:,.0f}k"
