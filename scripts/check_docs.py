"""Checks that the written rules hold: docs, specs, example config and personal files.

    uv run python scripts/check_docs.py            # exit 1 and list what is wrong
    uv run python scripts/check_docs.py --write    # also regenerate docs/SUPPORTED_SOURCES.md

Run in CI (see .github/workflows/ci.yml). Each check maps to a rule in CLAUDE.md.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import typer.main  # noqa: E402

from jobhunter.cli import app  # noqa: E402
from jobhunter.config import Config  # noqa: E402
from jobhunter.sources import registry  # noqa: E402

STATUSES = ("LIVING", "PLANNED", "IN PROGRESS", "DONE")
PERSONAL = ("config/config.yaml", "config/companies.yaml", "config/cv/", "data/", "out/")
SOURCES_DOC = ROOT / "docs" / "SUPPORTED_SOURCES.md"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def cli_commands() -> list[tuple[str, Any]]:
    """(`name` or `group sub`, command) for every command of the CLI."""
    root = typer.main.get_command(app)
    found: list[tuple[str, Any]] = []

    def walk(command: Any, prefix: str) -> None:
        subcommands = getattr(command, "commands", None)
        if subcommands:
            for name, sub in subcommands.items():
                walk(sub, f"{prefix} {name}".strip())
        else:
            found.append((prefix, command))

    walk(root, "")
    return found


def check_cli_documented() -> list[str]:
    docs = read("README.md") + read("specs/07-cli-config.md")
    problems = []
    for name, command in cli_commands():
        if not name:
            continue  # the root command (--version, completion options)
        if f"jobhunter {name}" not in docs and f"`{name}`" not in docs:
            problems.append(f"CLI command `jobhunter {name}` is not in the README or specs/07")
        for param in command.params:
            for opt in getattr(param, "opts", []):
                if opt.startswith("--") and opt not in docs and opt != "--help":
                    problems.append(
                        f"CLI option `{opt}` (`{name}`) is not in the README or specs/07"
                    )
    return problems


def config_paths(model: type, prefix: str = "") -> list[str]:
    paths = []
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and hasattr(annotation, "model_fields"):
            paths += config_paths(annotation, f"{prefix}{name}.")
        else:
            paths.append(f"{prefix}{name}")
    return paths


def check_example_config() -> list[str]:
    example = read("config/config.example.yaml")
    problems = []
    for path in config_paths(Config):
        key = path.rsplit(".", 1)[-1]
        if not re.search(rf"^\s*#?\s*{re.escape(key)}\s*:", example, re.M):
            problems.append(f"config key `{path}` does not appear in config/config.example.yaml")
    return problems


def check_specs() -> list[str]:
    index = read("specs/README.md")
    roadmap = read("specs/08-roadmap.md")
    problems = []
    for path in sorted((ROOT / "specs").glob("[0-9][0-9]-*.md")):
        match = re.search(r"^\*\*Status:\*\*\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
        if not match or not match.group(1).strip().startswith(STATUSES):
            problems.append(f"{path.name}: missing or invalid `**Status:**` (use {STATUSES})")
        if path.name not in index:
            problems.append(f"{path.name} is not listed in specs/README.md")
    for target in re.findall(r"\]\(([0-9]{2}-[a-z0-9-]+\.md)", roadmap):
        if not (ROOT / "specs" / target).exists():
            problems.append(f"roadmap links to specs/{target}, which does not exist")
    return problems


def check_personal_files() -> list[str]:
    try:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return []  # not a git checkout (e.g. a source archive)
    allowed = {"config/config.example.yaml", "config/company_candidates.txt"}
    return [
        f"personal or generated file is tracked by git: {name}"
        for name in tracked
        if name not in allowed and any(name.startswith(p) for p in PERSONAL)
    ]


def sources_markdown() -> str:
    rows = ["| Source | Kind | What | Terms / API docs | Keys |", "|---|---|---|---|---|"]
    for name, info in registry.all_sources().items():
        kind = "company board (`ats:` in companies.yaml)" if info.kind == "ats" else "aggregator"
        keys = ", ".join(f"`{k}`" for k in info.env_keys) or "none"
        rows.append(
            f"| `{name}` | {kind} | {info.description} | [link]({info.terms_url}) | {keys} |"
        )
    return (
        "# Supported sources\n\n"
        "Generated from the source registry by `scripts/check_docs.py --write`; do not edit by "
        "hand. Only public APIs and feeds are used (see [specs/03-sources.md]"
        "(../specs/03-sources.md)). To add one, follow [ADDING_A_SOURCE.md](ADDING_A_SOURCE.md).\n\n"
        + "\n".join(rows)
        + "\n"
    )


def check_sources_doc(write: bool) -> list[str]:
    expected = sources_markdown()
    if write:
        SOURCES_DOC.write_text(expected, encoding="utf-8")
        return []
    if not SOURCES_DOC.exists() or SOURCES_DOC.read_text(encoding="utf-8") != expected:
        return ["docs/SUPPORTED_SOURCES.md is out of date: run `scripts/check_docs.py --write`"]
    return []


def main() -> int:
    write = "--write" in sys.argv
    problems = [
        *check_cli_documented(),
        *check_example_config(),
        *check_specs(),
        *check_personal_files(),
        *check_sources_doc(write),
    ]
    for problem in problems:
        print(f"- {problem}")
    print(f"{len(problems)} problem(s)" if problems else "docs OK")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
