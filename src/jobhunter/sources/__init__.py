"""Sources: every module in this package registers itself in `registry` when imported."""

from __future__ import annotations

import importlib
import logging
import os
import pkgutil

from jobhunter.companies import Company
from jobhunter.config import Config
from jobhunter.sources import registry
from jobhunter.sources.base import Source

log = logging.getLogger(__name__)

for _module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_module.name}")


def build_sources(config: Config, companies: list[Company]) -> list[Source]:
    """Instances to fetch: the configured aggregators plus one per listed company board."""
    aggregators = registry.aggregators()
    boards = registry.company_boards()
    sources: list[Source] = []
    for name in config.sources.aggregators:
        info = aggregators.get(name)
        if info is None or info.build is None:
            continue
        missing = [k for k in info.env_keys if not os.environ.get(k)]
        if missing and not info.key_optional:
            log.warning("skipping source '%s': %s not set", name, ", ".join(missing))
            continue
        sources.extend(info.build(config.sources))
    for company in companies:
        info = boards.get(company.ats)
        if info is not None and info.factory is not None:
            sources.append(info.factory(company.name, company.slug))
    return sources
