"""Every registered source must meet the contract in docs/ADDING_A_SOURCE.md."""

import importlib
import pkgutil
from pathlib import Path

import pytest

import jobhunter.sources as sources_pkg
from jobhunter.config import Config
from jobhunter.models import ATS_SOURCES
from jobhunter.sources import build_sources, registry
from jobhunter.sources.registry import SourceInfo

FIXTURES = Path(__file__).parent / "fixtures"
TESTS = Path(__file__).parent
ALL = registry.all_sources()


def test_every_source_module_registers_something():
    registered = {getattr(i.build or i.factory, "__module__", "") for i in ALL.values()}
    for module in pkgutil.iter_modules(sources_pkg.__path__):
        if module.name in {"base", "registry"}:
            continue
        name = f"jobhunter.sources.{module.name}"
        importlib.import_module(name)
        assert name in registered, f"{name} is in sources/ but registered no source"


@pytest.mark.parametrize("name", sorted(ALL))
def test_source_declares_what_it_needs(name):
    info: SourceInfo = ALL[name]
    assert info.description and not info.description.endswith(".")
    assert info.terms_url.startswith("https://"), "link the source's terms or API docs"
    assert info.fixtures, "every source needs a trimmed real response in tests/fixtures/"
    for env in info.env_keys:
        assert env.isupper(), "environment variable names are UPPER_CASE"


@pytest.mark.parametrize("name", sorted(ALL))
def test_fixtures_exist_and_are_used_by_a_test(name):
    corpus = "\n".join(
        p.read_text() for p in TESTS.glob("test_*.py") if p.name != Path(__file__).name
    )
    for fixture in ALL[name].fixtures:
        assert (FIXTURES / fixture).is_file(), f"missing tests/fixtures/{fixture}"
        assert fixture in corpus, f"no test parses tests/fixtures/{fixture}"


def test_company_boards_are_known_to_the_models():
    assert set(registry.company_boards()) <= set(ATS_SOURCES), (
        "add the new board type to models.ATS_SOURCES (postings on company boards never go stale)"
    )


def test_registered_sources_build_instances_with_the_source_interface():
    cfg = Config.model_validate({"sources": {"aggregators": sorted(registry.aggregators())}})
    for source in build_sources(cfg, []):
        assert source.name in ALL
        assert isinstance(source.target, str)
        assert callable(source.fetch)
    for name, info in registry.company_boards().items():
        instance = info.factory("Acme", "acme")
        assert instance.name == name and instance.target == "acme"
        assert "{slug}" in (info.probe_url or "")


def test_unknown_names_are_rejected_with_the_available_ones():
    with pytest.raises(Exception, match="unknown source"):
        Config.model_validate({"sources": {"aggregators": ["nope"]}})


def test_double_registration_is_an_error():
    info = next(iter(ALL.values()))
    with pytest.raises(ValueError, match="twice"):
        registry.register(info)
