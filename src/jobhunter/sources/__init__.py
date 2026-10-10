"""Source registry: builds the list of Source instances to fetch from config."""

from __future__ import annotations

from jobhunter.companies import Company
from jobhunter.config import Config
from jobhunter.sources.aggregators import (
    ArbeitnowSource,
    JobicySource,
    RemoteOkSource,
    RemotiveSource,
    WeWorkRemotelySource,
)
from jobhunter.sources.ashby import AshbySource
from jobhunter.sources.base import Source
from jobhunter.sources.greenhouse import GreenhouseSource
from jobhunter.sources.lever import LeverSource

ATS_SOURCES = {"greenhouse": GreenhouseSource, "lever": LeverSource, "ashby": AshbySource}


def build_sources(config: Config, companies: list[Company]) -> list[Source]:
    cfg = config.sources
    sources: list[Source] = []
    for name in cfg.aggregators:
        if name == "remotive":
            sources.append(RemotiveSource())
        elif name == "remoteok":
            sources.append(RemoteOkSource())
        elif name == "weworkremotely":
            sources.extend(WeWorkRemotelySource(c) for c in cfg.wwr_categories)
        elif name == "arbeitnow":
            sources.append(ArbeitnowSource(cfg.arbeitnow_pages))
        elif name == "jobicy":
            sources.append(JobicySource())
    sources.extend(ATS_SOURCES[c.ats](c.name, c.slug) for c in companies)
    return sources
