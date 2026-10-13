"""Files that ship with the tool: the example config, letter template, sample CV, company list.

Installed as a package they live in `jobhunter/data/`; in a source checkout they are read from
`config/` (the same files, so there is one source of truth).
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE = Path(__file__).resolve().parent / "data"
_CHECKOUT = Path(__file__).resolve().parents[2] / "config"

NAMES = (
    "config.example.yaml",
    "company_candidates.txt",
    "letter_template.example.tex",
    "cv.example.tex",
)


def path(name: str) -> Path:
    """Location of a bundled file; raises FileNotFoundError with a clear message."""
    if name not in NAMES:
        raise FileNotFoundError(f"'{name}' is not a bundled file")
    for base in (_PACKAGE, _CHECKOUT):
        candidate = base / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"bundled file '{name}' not found (broken installation?)")


def read(name: str) -> str:
    return path(name).read_text(encoding="utf-8")
