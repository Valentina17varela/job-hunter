"""Environment checks behind `jobhunter doctor` (see specs/07-cli-config.md)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from jobhunter.config import Config, ConfigError, load_config

MINIMAL_TEX = r"""\documentclass{article}
\begin{document}
jobhunter doctor
\end{document}
"""


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def compile_tex(tex_path: Path, engine: str, timeout: int) -> tuple[bool, str]:
    """Compile a .tex file in a temp copy of its directory; shell escape stays disabled."""
    binary = shutil.which(engine)
    if binary is None:
        return False, f"'{engine}' not found in PATH"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        src = work / "doc.tex"
        src.write_text(tex_path.read_text())
        if engine == "tectonic":
            cmd = [binary, "-X", "compile", "--untrusted", str(src)]
        else:
            cmd = [binary, "-pdf", "-no-shell-escape", "-interaction=nonstopmode", str(src)]
        try:
            proc = subprocess.run(
                cmd, cwd=work, capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired:
            return False, f"compilation timed out after {timeout}s"
        if proc.returncode != 0 or not (work / "doc.pdf").exists():
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
            return False, "compilation failed: " + " | ".join(tail)
    return True, "compiled OK"


def run_checks(config_path: Path) -> list[Check]:
    checks: list[Check] = []

    py_ok = sys.version_info >= (3, 12)
    checks.append(Check("python", py_ok, f"{sys.version.split()[0]} (need >= 3.12)"))

    config: Config | None = None
    try:
        config = load_config(config_path)
        checks.append(Check("config", True, f"{config_path} is valid"))
    except ConfigError as exc:
        checks.append(Check("config", False, str(exc)))

    checks.append(
        Check(
            "ANTHROPIC_API_KEY",
            bool(os.environ.get("ANTHROPIC_API_KEY")),
            "set" if os.environ.get("ANTHROPIC_API_KEY") else "not set (needed from Phase 3)",
            required=False,
        )
    )

    engine = config.latex.engine if config else "tectonic"
    timeout = config.latex.timeout_seconds if config else 60
    with tempfile.TemporaryDirectory() as tmp:
        minimal = Path(tmp) / "minimal.tex"
        minimal.write_text(MINIMAL_TEX)
        ok, detail = compile_tex(minimal, engine, timeout)
    checks.append(Check(f"latex ({engine})", ok, detail))

    if config is not None:
        master = config.paths.cv_master
        if master.exists():
            ok, detail = compile_tex(master, engine, timeout)
            checks.append(Check("master CV", ok, f"{master}: {detail}", required=False))
        else:
            checks.append(
                Check("master CV", False, f"{master} not found (needed from Phase 3)", False)
            )
    return checks
