"""Edit config.yaml from the UI without losing the person's comments (specs/09 §2).

Updates are validated with the same pydantic model the CLI uses before anything is written, a
``.bak`` copy is kept, and the file is replaced atomically.
"""

from __future__ import annotations

import copy
import io
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from jobhunter.config import Config

# Sections the UI may change. `paths` is deliberately excluded: moving files by accident would
# break every command.
EDITABLE_SECTIONS = {
    "search", "scoring", "tailoring", "llm", "budget", "sources", "latex", "fx_rates_to_usd",
}  # fmt: skip
# Fields that choose which file is read/written or which program is executed. They stay
# editable only by hand in config.yaml: through the UI they would turn a settings save into an
# arbitrary file write (candidates_file) or code execution (claude_path).
LOCKED_FIELDS = {"llm.claude_path", "sources.companies_file", "sources.candidates_file"}
MAX_FILE_BYTES = 512 * 1024


class ConfigUpdateError(ValueError):
    """Updates were rejected; ``errors`` lists field-level problems for the UI."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__("; ".join(f"{e['field']}: {e['message']}" for e in errors))
        self.errors = errors


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _flatten(updates: dict[str, Any], prefix: str = "") -> list[str]:
    out: list[str] = []
    for key, value in updates.items():
        path = f"{prefix}{key}"
        out.append(path)
        if isinstance(value, dict):
            out += _flatten(value, f"{path}.")
    return out


def validate_updates(current: dict[str, Any], updates: dict[str, Any]) -> Config:
    """Return the validated Config that would result, or raise ConfigUpdateError."""
    locked = sorted(set(_flatten(updates)) & LOCKED_FIELDS)
    if locked:
        raise ConfigUpdateError(
            [{"field": f, "message": "edit this one by hand in config.yaml"} for f in locked]
        )
    forbidden = sorted(set(updates) - EDITABLE_SECTIONS)
    if forbidden:
        raise ConfigUpdateError(
            [
                {"field": k, "message": "this section cannot be edited from the UI"}
                for k in forbidden
            ]
        )
    try:
        return Config.model_validate(deep_merge(current, updates))
    except ValidationError as exc:
        raise ConfigUpdateError(
            [
                {"field": ".".join(str(p) for p in err["loc"]), "message": err["msg"]}
                for err in exc.errors()
            ]
        ) from exc


def _yaml11_safe(text: str) -> Any:
    """Quote strings that PyYAML (YAML 1.1, used by load_config) would read as another type,
    e.g. NO, yes, off, 1e3 or 2026-01-01."""
    try:
        if yaml.safe_load(text) == text:
            return text
    except yaml.YAMLError:
        pass
    return DoubleQuotedScalarString(text)


def _as_yaml_value(value: Any) -> Any:
    """Plain lists of scalars are written inline (`[a, b]`) like the example config."""
    if isinstance(value, str):
        return _yaml11_safe(value)
    if isinstance(value, list):
        seq = CommentedSeq(_as_yaml_value(v) for v in value)
        if all(not isinstance(v, (dict, list)) for v in value):
            seq.fa.set_flow_style()
        return seq
    if isinstance(value, dict):
        return CommentedMap((k, _as_yaml_value(v)) for k, v in value.items())
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _apply(node: CommentedMap, updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if key in node and not isinstance(value, dict) and _plain(node[key]) == value:
            continue  # unchanged: leave the person's formatting and comments exactly as written
        if isinstance(value, dict) and isinstance(node.get(key), CommentedMap):
            _apply(node[key], value)
        elif isinstance(node.get(key), CommentedSeq) and isinstance(value, list):
            old, new = node[key], _as_yaml_value(value)
            if isinstance(new, CommentedSeq) and not old.fa.flow_style():
                new.fa.set_block_style()  # keep a list the person wrote one item per line
            node[key] = new
        else:
            node[key] = _as_yaml_value(value)


def write_atomic(path: Path, text: str) -> None:
    """Replace ``path`` atomically, keeping backups.

    ``.bak`` is the version before this save; ``.orig`` is the very first version ever replaced,
    so two quick saves can never destroy the only good copy. A symlinked file is written
    through, and the original permissions are kept.
    """
    target = path.resolve() if path.is_symlink() else path
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = None
    if target.exists():
        mode = target.stat().st_mode & 0o777
        orig = target.with_name(target.name + ".orig")
        if not orig.exists():
            shutil.copy2(target, orig)
        shutil.copy2(target, target.with_name(target.name + ".bak"))
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def save_updates(path: Path, updates: dict[str, Any]) -> Config:
    """Validate and persist updates to ``path``, preserving comments and ordering."""
    try:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        current = yaml.safe_load(text) or {}
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ConfigUpdateError(
            [{"field": str(path.name), "message": f"cannot read the current file: {exc}"}]
        ) from exc
    config = validate_updates(current, updates)
    rt = YAML()
    rt.preserve_quotes = True
    rt.width = 100
    rt.indent(mapping=2, sequence=4, offset=2)  # same layout the example config uses
    try:
        data = rt.load(text) if text.strip() else CommentedMap()
    except Exception as exc:  # noqa: BLE001 - ruamel raises several error types
        raise ConfigUpdateError(
            [{"field": str(path.name), "message": f"cannot parse the current file: {exc}"}]
        ) from exc
    if data is None:
        data = CommentedMap()
    _apply(data, updates)
    buffer = io.StringIO()
    rt.dump(data, buffer)
    out = buffer.getvalue()
    # Never write something the rest of the tool cannot read back (YAML 1.1 vs 1.2 quirks).
    try:
        Config.model_validate(yaml.safe_load(out) or {})
    except (yaml.YAMLError, ValidationError) as exc:
        raise ConfigUpdateError(
            [{"field": str(path.name), "message": f"the result would not load back: {exc}"}]
        ) from exc
    write_atomic(path, out)
    return config


# --- plain text files (CV, letter template, company candidates) -----------------------------


def check_file_size(content: str) -> None:
    if len(content.encode()) > MAX_FILE_BYTES:
        raise ValueError(f"file is larger than {MAX_FILE_BYTES // 1024} KB")


LETTER_PLACEHOLDERS = (
    "%%DATE%%",
    "%%COMPANY%%",
    "%%SUBJECT%%",
    "%%GREETING%%",
    "%%BODY%%",
    "%%CLOSING%%",
)


def validate_letter_template(content: str) -> None:
    missing = [p for p in LETTER_PLACEHOLDERS if p not in content]
    if missing:
        raise ValueError(f"the template is missing placeholders: {', '.join(missing)}")
