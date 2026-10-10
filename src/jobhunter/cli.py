"""Command-line interface (see specs/07-cli-config.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from jobhunter import __version__
from jobhunter.doctor import run_checks

app = typer.Typer(help="Find job postings, score them and prepare application packages.")

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
