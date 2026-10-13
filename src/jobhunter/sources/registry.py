"""Source registry: every source describes itself once and registers here.

Adding a source means adding one module under `sources/` that calls `register(...)` at the
bottom (see docs/ADDING_A_SOURCE.md). Nothing else needs editing: `build_sources`, the config
validation, the Settings page and the generated docs table all read this registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from jobhunter.config import SourcesConfig
    from jobhunter.sources.base import Source


@dataclass(frozen=True)
class SourceInfo:
    name: str  # config value (aggregators) or `ats:` value in companies.yaml
    kind: Literal["aggregator", "ats"]
    description: str  # one line, shown in the docs table
    terms_url: str  # where the source's terms / API docs live (https)
    fixtures: tuple[str, ...]  # trimmed real responses in tests/fixtures/
    # aggregators: builds its instances from the sources config
    build: Callable[[SourcesConfig], list[Source]] | None = None
    # company boards: builds one instance for a company name and board slug
    factory: Callable[[str, str], Source] | None = None
    probe_url: str | None = None  # company boards: URL template with {slug}, used by check/discover
    env_keys: tuple[str, ...] = ()  # environment variables the source needs (spec 14)


_REGISTRY: dict[str, SourceInfo] = {}


def register(info: SourceInfo) -> SourceInfo:
    if info.name in _REGISTRY:
        raise ValueError(f"source '{info.name}' is registered twice")
    if info.kind == "aggregator" and info.build is None:
        raise ValueError(f"aggregator '{info.name}' needs a build function")
    if info.kind == "ats" and (info.factory is None or not info.probe_url):
        raise ValueError(f"company board '{info.name}' needs a factory and a probe_url")
    _REGISTRY[info.name] = info
    return info


def all_sources() -> dict[str, SourceInfo]:
    return dict(_REGISTRY)


def aggregators() -> dict[str, SourceInfo]:
    return {n: i for n, i in _REGISTRY.items() if i.kind == "aggregator"}


def company_boards() -> dict[str, SourceInfo]:
    return {n: i for n, i in _REGISTRY.items() if i.kind == "ats"}
