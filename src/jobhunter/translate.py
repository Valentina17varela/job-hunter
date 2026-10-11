"""One-time, reviewable translation of the master CV (see specs/06-tailoring.md §4.0)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from jobhunter.config import Config
from jobhunter.latex import Document, translation_units
from jobhunter.llm import LlmClient

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\*?|\\\\|\\[%&$#_{}]")

LANGUAGE_NAMES = {
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "en": "English",
}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "units": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        }
    },
    "required": ["units"],
}


class TranslationBatch(BaseModel):
    units: dict[str, list[str]]


def translation_path(cv_dir: Path, lang: str) -> Path:
    return cv_dir / "translations" / f"{lang}.json"


def load_translation(
    cv_dir: Path, lang: str, doc: Document | None = None
) -> tuple[dict[str, list[str]] | None, str]:
    """Load a reviewed translation. Returns (units or None, note).

    Falls back to None (English CV) when the file is missing or unreadable, or when
    ``master.tex`` changed since it was made. Units whose numbers/LaTeX no longer match the
    original are dropped individually so one bad edit never breaks the whole CV.
    """
    path = translation_path(cv_dir, lang)
    if not path.exists():
        return None, "file not found; run `cv translate`"
    try:
        data = json.loads(path.read_text())
        units = data["units"]
        saved_hash = data.get("source_hash")
    except (ValueError, KeyError, TypeError) as exc:
        return None, f"unreadable file ({type(exc).__name__})"
    if doc is None:
        return units, ""
    if saved_hash and saved_hash != doc.source_hash:
        return None, "master.tex changed since the translation; run `cv translate --force`"
    originals = translation_units(doc)
    usable, dropped = {}, []
    for uid, lines in units.items():
        if uid in originals and isinstance(lines, list) and not check_unit(originals[uid], lines):
            usable[uid] = lines
        else:
            dropped.append(uid)
    note = (
        f"{len(dropped)} translated unit(s) fall back to English: {', '.join(dropped)}"
        if dropped
        else ""
    )
    return usable, note


def check_unit(original: list[str], translated: list[str]) -> list[str]:
    """Deterministic checks that a translation kept numbers, LaTeX commands and braces."""
    src, dst = "\n".join(original), "\n".join(translated)
    problems = []
    if sorted(_NUMBER_RE.findall(src)) != sorted(_NUMBER_RE.findall(dst)):
        problems.append("numbers changed")
    if sorted(_COMMAND_RE.findall(src)) != sorted(_COMMAND_RE.findall(dst)):
        problems.append("LaTeX commands changed")
    if dst.count("{") != dst.count("}") or src.count("{") - src.count("}") != (
        dst.count("{") - dst.count("}")
    ):
        problems.append("unbalanced braces")
    return problems


def translate_cv(
    client: LlmClient, cfg: Config, doc: Document, lang: str, batch_size: int = 12
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Translate every unit; returns (units, problems by unit id)."""
    name = LANGUAGE_NAMES.get(lang, lang)
    system = (
        f"You translate parts of a LaTeX CV from English to {name}. Return strict JSON only.\n"
        "Rules: keep every LaTeX command, brace, '\\\\' line break, '%' escape and the bullet "
        "character exactly as given; keep all numbers, percentages, product and technology "
        "names, company names, dates and URLs unchanged; translate only the human-readable words; "
        "keep each unit's number of lines. Use natural, professional CV wording."
    )
    units = translation_units(doc)
    items = list(units.items())
    result: dict[str, list[str]] = {}
    problems: dict[str, list[str]] = {}
    for start in range(0, len(items), batch_size):
        chunk = dict(items[start : start + batch_size])
        prompt = 'Translate these units. Return {"units": {id: [lines]}}.\n\n' + json.dumps(
            chunk, ensure_ascii=False
        )
        batch = client.call(
            stage="translate", system=system, prompt=prompt, schema=SCHEMA,
            model=cfg.tailoring.model, parse=TranslationBatch,
        )  # fmt: skip
        for uid, original in chunk.items():
            translated = batch.units.get(uid)
            if translated is None:
                result[uid], problems[uid] = original, ["missing from the response"]
                continue
            result[uid] = translated
            if found := check_unit(original, translated):
                problems[uid] = found
    return result, problems


def save_translation(
    cv_dir: Path, lang: str, units: dict[str, list[str]], problems: dict[str, list[str]],
    source_hash: str = "",
) -> Path:  # fmt: skip
    path = translation_path(cv_dir, lang)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "language": lang,
        "note": "Review and edit the lines; keep LaTeX commands and numbers unchanged.",
        "source_hash": source_hash,
        "problems": problems,
        "units": units,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path
