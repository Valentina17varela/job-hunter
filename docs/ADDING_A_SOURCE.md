# Adding a source

A source turns one public API or feed into `Job` objects. You add **one module, one fixture and one test**; nothing else needs editing (the registry, the config validation, the Settings page and `docs/SUPPORTED_SOURCES.md` read it from there).

## 0. Is it allowed?

Only **public APIs and feeds** that permit automated use. Read the site's terms and `robots.txt`.

- Not accepted: anything behind a login, anything that needs bot-protection evasion, proxies or spoofing, scraping that the terms forbid.
- Keep the **link back**: every `Job.url` points to the original posting (aggregators require it).
- Needs a key? It goes in an environment variable, never in the config (declare it in `env_keys`); a missing key skips the source with a warning (spec 14 §3).

## 1. Find and record a real response

Call the endpoint once and save a **trimmed** real response (3–5 postings, include one with missing fields) as `tests/fixtures/<name>.json` (or `.rss`/`.xml`). No personal data, no secrets.

## 2. Write the module

Create `src/jobhunter/sources/<name>.py`. Look at `aggregators.py` (feeds) or `greenhouse.py` (company boards) for the style.

```python
"""Example Jobs: https://example.com/api/jobs (public JSON feed)."""

from __future__ import annotations

from typing import Any

from jobhunter.http import HttpClient
from jobhunter.models import Job
from jobhunter.sources.base import collect, parse_iso
from jobhunter.sources.registry import SourceInfo, register
from jobhunter.text import extract_salary, html_to_text, infer_remote


def _parse_one(raw: dict[str, Any]) -> Job | None:
    return Job(
        source="examplejobs",
        external_id=str(raw["id"]),
        company=raw["company"],
        title=raw["title"],
        location=raw.get("location") or None,
        remote=infer_remote(raw.get("location"), raw["title"]),
        description=html_to_text(raw.get("description")),
        url=raw["url"],  # the original posting: keep the link back
        posted_at=parse_iso(raw.get("published")),
    )


def parse(data: dict[str, Any]) -> list[Job]:
    return collect(data.get("jobs", []), _parse_one)  # a malformed item is skipped, never fatal


class ExampleJobsSource:
    name = "examplejobs"
    target = ""  # "" for a single feed; a slug or category for per-target sources

    async def fetch(self, http: HttpClient) -> list[Job]:
        return parse(await http.get_json("https://example.com/api/jobs"))


register(
    SourceInfo(
        name="examplejobs",
        kind="aggregator",
        description="Remote jobs from Example (link back required)",
        terms_url="https://example.com/api-terms",
        fixtures=("examplejobs.json",),
        build=lambda cfg: [ExampleJobsSource()],
    )
)
```

Rules (from spec 03 §6, they keep the pipeline honest):

- **Robust parsing:** use `collect(...)`; one bad item never discards the feed.
- **Clean text:** `html_to_text` for descriptions.
- **Remote:** infer from short fields only (location, title, a structured field), never from the description.
- **Salary:** use structured fields when the source has them (annualize hourly/monthly with `annualize`); otherwise `extract_salary` over the text; else leave `None`. Never invent.
- **Dates:** `posted_at` when the source gives one, as UTC.
- **No state, no side effects, no files:** `fetch` only returns `Job`s. Use the given `HttpClient` (it adds the User-Agent, timeouts, retries and per-host limits).

### Company boards (one instance per company)

For an ATS where each company has its own board, register with `kind="ats"`, a `factory=(company_name, slug) -> Source` and a `probe_url` with `{slug}` (used by `companies check` and `discover`), and add the type name to `ATS_SOURCES` in `models.py` (postings on company boards never go stale by date). People then write `ats: <name>` in `companies.yaml`.

### Several categories or pages

`build` receives the sources config (`SourcesConfig`) and may return several instances (see We Work Remotely). A new config key needs a field in `SourcesConfig`, an entry in `config/config.example.yaml` and a line in the README; `scripts/check_docs.py` will tell you if one is missing.

## 3. Test it

In `tests/test_sources.py`, parse the fixture and assert what matters:

```python
def test_examplejobs_parse(fixture_json):
    jobs = examplejobs.parse(fixture_json("examplejobs.json"))
    assert jobs and all(j.url.startswith("https://") for j in jobs)
    assert jobs[0].remote == "remote"
```

Add a case for a missing field and for a malformed item (skipped, not fatal). **No test touches the network** (`respx` if you need to test `fetch`). The contract test `tests/test_source_contract.py` then checks automatically that the source is registered, documented (description, terms link), has an existing fixture that some test uses, builds, and has a valid name.

## 4. Docs and checks

```bash
uv run python scripts/check_docs.py --write   # regenerates docs/SUPPORTED_SOURCES.md
uv run pytest -q && uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_docs.py
```

Add the source to the README's sources table, and to `specs/03-sources.md` if it changes behaviour. Then open the PR (the template has the checklist).
