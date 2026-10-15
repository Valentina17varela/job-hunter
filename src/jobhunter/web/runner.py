"""Runs whitelisted jobhunter commands as subprocesses and keeps their output (specs/09 §3)."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunSpec:
    id: str
    label: str
    args: tuple[str, ...]
    description: str
    llm: bool = False  # uses the LLM backend (counts against your plan / budget)
    supports_dry_run: bool = False
    supports_jobs: bool = False  # accepts --job/--limit/--force (tailor)
    supports_job_ids: bool = False  # accepts --job only (score)


RUN_VERBS = {
    "search": "Search", "fetch": "Fetch", "filter": "Filter", "refilter": "Re-filter",
    "score": "Score", "tailor": "Build packages", "all": "Run everything",
    "companies-check": "Check boards", "companies-discover": "Find boards",
    "cv-check": "Check your CV", "doctor": "Check setup", "stats": "Show stats",
}  # fmt: skip

RUN_SPECS: tuple[RunSpec, ...] = (
    RunSpec("search", "Search for new jobs", ("run", "--stage", "search"),
            "Download new postings from all sources and keep the ones that match your criteria. "
            "Free and fast, no AI involved.", supports_dry_run=True),
    RunSpec("fetch", "Fetch postings", ("run", "--stage", "fetch"),
            "Download postings from every configured source and store new or changed ones. "
            "No cost.", supports_dry_run=True),
    RunSpec("filter", "Filter new postings", ("run", "--stage", "filter"),
            "Apply your search criteria to postings that are still new. No cost.",
            supports_dry_run=True),
    RunSpec("refilter", "Re-filter everything", ("refilter",),
            "Check every stored posting again after you change what you look for. No network."),
    RunSpec("score", "Score postings with AI", ("run", "--stage", "score"),
            "Rate postings that passed your criteria against your CV, in batches. Uses your Claude "
            "plan or API key, up to your per-run call limit.", llm=True, supports_dry_run=True,
            supports_job_ids=True),
    RunSpec("tailor", "Build application packages", ("run", "--stage", "tailor"),
            "For selected postings, pick CV bullets, write the cover letter and compile the PDFs. "
            "One AI call per posting.", llm=True, supports_dry_run=True, supports_jobs=True),
    RunSpec("all", "Run everything", ("run",),
            "Search, score and build packages in one go.", llm=True, supports_dry_run=True),
    RunSpec("companies-check", "Check company boards", ("companies", "check"),
            "Check that every company job board you follow still exists."),
    RunSpec("companies-discover", "Discover company boards", ("companies", "discover"),
            "Look for job boards of the companies on your list and add the ones found."),
    RunSpec("cv-check", "Check your LaTeX CV", ("cv", "check"),
            "Check your CV's structure markers and compile it."),
    RunSpec("doctor", "Check the environment", ("doctor",),
            "Python, your config, your AI login and the LaTeX engine."),
    RunSpec("stats", "Show stats", ("stats",), "Your funnel and AI usage as text."),
)  # fmt: skip
SPECS_BY_ID = {s.id: s for s in RUN_SPECS}


class RunError(ValueError):
    """Rejected run request (unknown command, bad option, another run active)."""


class Busy(RunError):
    """Another run is still in progress."""


@dataclass
class Run:
    id: str
    spec_id: str
    argv: list[str]
    started_at: float
    status: str = "running"  # running | ok | failed
    exit_code: int | None = None
    finished_at: float | None = None
    lines: list[str] = field(default_factory=list)

    def to_dict(self, since: int = 0) -> dict[str, Any]:
        return {
            "id": self.id, "command": self.spec_id, "argv": self.argv[3:], "status": self.status,
            "exit_code": self.exit_code, "started_at": self.started_at,
            "finished_at": self.finished_at, "next": len(self.lines),
            "log": "\n".join(self.lines[since:]),
        }  # fmt: skip


class RunManager:
    """One run at a time; output is kept in memory and mirrored to a log file."""

    def __init__(
        self, config_path: Path, cwd: Path, log_dir: Path | None = None,
        python: str | None = None, popen: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> None:  # fmt: skip
        self.config_path = config_path
        self.cwd = cwd
        self.log_dir = log_dir
        self.python = python or sys.executable
        self._popen = popen
        self._runs: dict[str, Run] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def build_argv(
        self, spec_id: str, *, dry_run: bool = False, jobs: list[int] | None = None,
        limit: int | None = None, force: bool = False,
    ) -> list[str]:  # fmt: skip
        spec = SPECS_BY_ID.get(spec_id)
        if spec is None:
            raise RunError(f"unknown command '{spec_id}'")
        argv = [self.python, "-m", "jobhunter", *spec.args]
        if dry_run:
            if not spec.supports_dry_run:
                raise RunError(f"'{spec_id}' has no dry-run mode")
            argv.append("--dry-run")
        if jobs or limit or force:
            if limit or force:
                if not spec.supports_jobs:
                    raise RunError(f"'{spec_id}' does not accept limit/force options")
            elif not (spec.supports_jobs or spec.supports_job_ids):
                raise RunError(f"'{spec_id}' does not accept job options")
            for job in jobs or []:
                argv += ["--job", str(int(job))]
            if limit:
                argv += ["--limit", str(int(limit))]
            if force:
                argv.append("--force")
        return [*argv, "--config", str(self.config_path)]

    def active(self) -> Run | None:
        return next((r for r in self._runs.values() if r.status == "running"), None)

    def start(self, spec_id: str, **options: Any) -> Run:
        argv = self.build_argv(spec_id, **options)
        with self._lock:
            if self.active():
                raise Busy("another run is still in progress")
            run = Run(uuid.uuid4().hex[:8], spec_id, argv, time.time())
            self._runs[run.id] = run
            self._order.append(run.id)
        threading.Thread(target=self._execute, args=(run,), daemon=True).start()
        return run

    def _execute(self, run: Run) -> None:
        log_file = None
        try:
            if self.log_dir:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                name = f"{int(run.started_at)}-{run.id}-{run.spec_id}.log"
                log_file = (self.log_dir / name).open("w")
            proc = self._popen(
                run.argv, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )  # fmt: skip
            assert proc.stdout is not None
            for line in proc.stdout:
                text = line.rstrip("\n")
                run.lines.append(text)
                if log_file:
                    log_file.write(text + "\n")
                    log_file.flush()
            run.exit_code = proc.wait()
            run.status = "ok" if run.exit_code == 0 else "failed"
        except Exception as exc:  # noqa: BLE001 - surface any launch problem in the log
            run.lines.append(f"could not run: {exc}")
            run.status = "failed"
        finally:
            run.finished_at = time.time()
            if log_file:
                log_file.close()

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def history(self, limit: int = 15) -> list[Run]:
        return [self._runs[i] for i in reversed(self._order[-limit:])]
