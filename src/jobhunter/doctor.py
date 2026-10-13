"""Environment checks behind `jobhunter doctor` (see specs/07-cli-config.md)."""

from __future__ import annotations

import os
import platform
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from jobhunter.config import Config, ConfigError, load_config
from jobhunter.latex import compile_pdf
from jobhunter.llm import claude_login_status

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
    hint: str = ""  # how to fix it on this system; empty when everything is fine


def detect_system() -> str:
    """`macos`, `linux`, `wsl`, `docker`, `windows` or `other`: picks the right install hints."""
    if Path("/.dockerenv").exists():
        return "docker"
    name = platform.system()
    if name == "Darwin":
        return "macos"
    if name == "Windows":
        return "windows"
    if name == "Linux":
        try:
            if "microsoft" in Path("/proc/version").read_text().lower():
                return "wsl"
        except OSError:
            pass
        return "linux"
    return "other"


_SETUP = "More: docs/SETUP.md"
_APT_TEX = (
    "sudo apt install latexmk texlive-latex-recommended texlive-latex-extra "
    "texlive-fonts-recommended lmodern"
)
_LATEX_INSTALL = {
    "macos": "brew install tectonic",
    "linux": f"{_APT_TEX}   (or tectonic: https://tectonic-typesetting.github.io)",
    "wsl": f"{_APT_TEX}   (inside WSL, not Windows)",
    "docker": "use the provided image (it has TeX Live) or rebuild it: docker compose build",
    "windows": "native Windows is not supported: install WSL (Ubuntu), then the Linux steps",
}


def latex_hint(system: str, missing: bool) -> str:
    """How to get a LaTeX engine (missing=True) or why a compile may fail on this system."""
    if not missing:
        return (
            "Run `jobhunter cv check` for the compiler's message. tectonic downloads packages "
            "the first time it compiles (needs internet); with latexmk, install the missing "
            f"LaTeX package. {_SETUP}#troubleshooting"
        )
    how = _LATEX_INSTALL.get(system, "tectonic, or TeX Live with latexmk")
    return f"Install a LaTeX engine: {how}. {_SETUP}#1-install"


def python_hint() -> str:
    return f"Run `uv python install 3.12` (uv manages Python for you). {_SETUP}#1-install"


def claude_hint(not_found: bool) -> str:
    if not_found:
        return (
            "Install the Claude Code CLI (https://claude.com/claude-code) and run "
            "`claude auth login`, or use an API key: `llm.backend: anthropic_api` and "
            f"`export ANTHROPIC_API_KEY=...`. {_SETUP}#3-choose-the-ai-backend"
        )
    return f"Run `claude auth login` in your own terminal. {_SETUP}#3-choose-the-ai-backend"


def config_hint(missing: bool) -> str:
    if missing:
        return "Create one with `jobhunter init` (never overwrites), or pass --config FILE."
    return (
        "Fix the field named above; `config/config.example.yaml` lists every key. "
        f"{_SETUP}#4-tell-it-what-you-want"
    )


def source_keys(config: Config) -> list[tuple[str, str, bool, bool]]:
    """(source, ENV_VAR, is_set, optional) for the enabled sources that read a key.

    Only whether the variable is set is ever reported, never its value (spec 14 §3).
    """
    from jobhunter.sources import registry

    found = []
    for name in config.sources.aggregators:
        info = registry.aggregators().get(name)
        for env in info.env_keys if info else ():
            found.append((name, env, bool(os.environ.get(env)), info.key_optional))
    return found


def source_key_checks(config: Config) -> list[Check]:
    from jobhunter.sources import registry

    checks = []
    for name, env, is_set, optional in source_keys(config):
        if is_set:
            detail = "set"
        elif optional:
            detail = "not set (optional: a free key raises the rate limit)"
        else:
            detail = "not set (the source is skipped until you set it)"
        hint = (
            ""
            if is_set
            else (
                f"Optional: request a free key (see {registry.aggregators()[name].terms_url}) "
                f"and `export {env}=...` in your shell. Never put it in a file."
            )
        )
        checks.append(Check(f"{name} key", is_set, f"{env} {detail}", required=False, hint=hint))
    return checks


def compile_tex(tex_path: Path, engine: str, timeout: int) -> tuple[bool, str]:
    """Compile a .tex file; returns (ok, detail). Shell escape stays disabled."""
    result = compile_pdf(tex_path.read_text(), engine, timeout, resources=tex_path.parent)
    return result.ok, result.detail


def run_checks(config_path: Path) -> list[Check]:
    checks: list[Check] = []

    py_ok = sys.version_info >= (3, 12)
    system = detect_system()
    checks.append(
        Check(
            "python",
            py_ok,
            f"{sys.version.split()[0]} (need >= 3.12)",
            hint="" if py_ok else python_hint(),
        )
    )

    config: Config | None = None
    try:
        config = load_config(config_path)
        checks.append(Check("config", True, f"{config_path} is valid"))
    except ConfigError as exc:
        hint = config_hint(missing=not config_path.exists())
        checks.append(Check("config", False, str(exc), hint=hint))

    backend = config.llm.backend if config else "claude_cli"
    if backend == "claude_cli":
        ok, detail = claude_login_status(config.llm) if config else (False, "config invalid")
        hint = "" if ok else claude_hint(not_found="not found" in detail)
        checks.append(Check("llm (claude_cli)", ok, detail, required=False, hint=hint))
    else:
        has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
        detail = "ANTHROPIC_API_KEY set" if has_key else "ANTHROPIC_API_KEY not set"
        hint = (
            ""
            if has_key
            else "Set the key in your shell: `export ANTHROPIC_API_KEY=...` (never in a file)."
        )
        checks.append(Check("llm (anthropic_api)", has_key, detail, required=False, hint=hint))

    from jobhunter.latex import resolve_engine

    engine = resolve_engine(config.latex.engine if config else "auto")
    timeout = config.latex.timeout_seconds if config else 60
    with tempfile.TemporaryDirectory() as tmp:
        minimal = Path(tmp) / "minimal.tex"
        minimal.write_text(MINIMAL_TEX)
        ok, detail = compile_tex(minimal, engine, timeout)
    hint = "" if ok else latex_hint(system, missing="not found" in detail)
    checks.append(Check(f"latex ({engine})", ok, detail, hint=hint))

    if config is not None:
        checks.extend(source_key_checks(config))
        master = config.paths.cv_master
        if master.exists():
            ok, detail = compile_tex(master, engine, timeout)
            hint = (
                ""
                if ok
                else f"Run `jobhunter cv check` for details. {_SETUP}#4-tell-it-what-you-want"
            )
            checks.append(Check("master CV", ok, f"{master}: {detail}", required=False, hint=hint))
        else:
            checks.append(
                Check(
                    "master CV",
                    False,
                    f"{master} not found (needed for scoring)",
                    False,
                    hint="Put your LaTeX CV there and mark it (README: Your LaTeX CV), "
                    "or try `jobhunter init --sample-cv`.",
                )
            )
    return checks
