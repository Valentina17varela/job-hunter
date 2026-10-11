"""FastAPI application for the local UI. Server-rendered pages + a small JSON API."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from jobhunter import applications, latex
from jobhunter.config import Config, ConfigError, load_config
from jobhunter.db import connect
from jobhunter.doctor import run_checks
from jobhunter.filters import JobFilter, job_from_row
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
    "selected": "Selected", "packaged": "Packaged", "below_threshold": "Below threshold",
    "score_failed": "Score failed", "applied": "Applied", "replied": "In process",
    "rejected": "Rejected", "closed": "Closed", "duplicate": "Duplicate", "ignored": "Ignored",
}  # fmt: skip
STAGE_LABELS = {
    "applied": "Applied", "screening": "Screening", "interviewing": "Interviewing",
    "offer": "Offer", "accepted": "Accepted", "rejected": "Rejected",
    "withdrawn": "Withdrawn", "ghosted": "No response",
}  # fmt: skip


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
    templates.env.globals.update(
        STATUS_LABELS=STATUS_LABELS, STAGE_LABELS=STAGE_LABELS,
        STAGES=applications.STAGES, KINDS=applications.INTERVIEW_KINDS,
        OUTCOMES=applications.INTERVIEW_OUTCOMES,
    )  # fmt: skip

    def cfg() -> Config:
        return load_config(config_path)

    def db(config: Config) -> sqlite3.Connection:
        return connect(config.paths.db)

    def render(request: Request, name: str, **ctx: Any) -> Any:
        return templates.TemplateResponse(request, name, {"active": ctx.pop("active", ""), **ctx})

    @app.exception_handler(ConfigError)
    async def config_error(request: Request, exc: ConfigError) -> Any:
        return templates.TemplateResponse(request, "error.html", {"message": str(exc)}, 500)

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
            max_calls=config.budget.max_llm_calls_per_run, backend=config.llm.backend,
            running=manager.active(),
        )  # fmt: skip

    @app.get("/jobs")
    def jobs_page(
        request: Request, status: str = "active", source: str = "", q: str = "",
        min_score: str = "", mode: str = "", sort: str = "score", page: int = 1,
    ) -> Any:  # fmt: skip
        config = cfg()
        conn = db(config)
        score_floor = int(min_score) if min_score.strip().lstrip("-").isdigit() else None
        where, params = ["1=1"], []
        if status == "active":
            where.append(f"j.status IN ({','.join('?' for _ in ACTIVE_STATUSES)})")
            params += ACTIVE_STATUSES
        elif status != "all":
            where.append("j.status = ?")
            params.append(status)
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
        if score_floor is not None:
            where.append("s.score >= ?")
            params.append(score_floor)
        order = {
            "score": "s.score IS NULL, s.score DESC, j.id DESC",
            "recent": "j.posted_at IS NULL, j.posted_at DESC",
            "company": "j.company COLLATE NOCASE, j.title",
        }.get(sort, "s.score DESC")
        base = (
            "FROM jobs j LEFT JOIN scores s ON s.job_id = j.id AND s.created_at = "
            "(SELECT MAX(created_at) FROM scores WHERE job_id = j.id) "
            f"WHERE {' AND '.join(where)}"
        )
        total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        page = min(max(1, page), 100_000)
        rows = conn.execute(
            "SELECT j.id, j.company, j.title, j.location, j.remote, j.source, j.status, "
            "j.salary_max, j.salary_currency, j.posted_at, s.score, "
            "json_extract(s.reasons, '$.verdict') AS verdict "
            f"{base} ORDER BY {order} LIMIT ? OFFSET ?",
            [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
        ).fetchall()
        counts = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")}  # fmt: skip
        sources = [r[0] for r in conn.execute("SELECT DISTINCT source FROM jobs ORDER BY source")]
        return render(
            request, "jobs.html", active="jobs", rows=rows, total=total, page=page,
            pages=max(1, -(-total // PAGE_SIZE)), counts=counts, sources=sources,
            qs=urlencode({k: v for k, v in {"status": status, "source": source, "q": q,
                          "mode": mode, "sort": sort, "min_score": score_floor}.items()
                          if v not in ("", None)}),
            f={"status": status, "source": source, "q": q, "min_score": score_floor,
               "mode": mode, "sort": sort},
        )  # fmt: skip

    @app.get("/jobs/{job_id}")
    def job_page(request: Request, job_id: int) -> Any:
        config = cfg()
        conn = db(config)
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return templates.TemplateResponse(
                request, "error.html", {"message": f"No posting with id {job_id}"}, 404
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
            score=score, info=json.loads(score["reasons"]) if score else None,
            package=package_view(config, package), application=application,
            interviews=applications.list_interviews(conn, job_id), events=events,
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
            config_path=str(config_path), cv=cv,
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

    @app.post("/api/jobs/{job_id}/stage")
    async def api_stage(request: Request, job_id: int) -> Any:
        body = await request.json()
        applications.set_stage(db(cfg()), job_id, str(body.get("stage", "")), body.get("note"))
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/ignore")
    async def api_ignore(request: Request, job_id: int) -> Any:
        body = await request.json()
        applications.ignore(db(cfg()), job_id, body.get("note"))
        return {"ok": True}

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


def fmt_dt(value: str | None) -> str:
    """ISO timestamp → 'Oct 11, 2026 14:05' (UTC)."""
    if not value:
        return "—"
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
