# Specs

The specs are the source of truth for what the project does and why. Code follows them; when they diverge, one of the two changes in the same commit (see `CLAUDE.md`). Read them in order the first time; later, jump to the one you need.

## Status vocabulary

| Status | Meaning |
|---|---|
| `LIVING` | Describes how the system works **today**; kept in sync with the code (overview, architecture, data model, sources, filtering, scoring, tailoring, CLI, UI, roadmap) |
| `PLANNED` | Spec only. Written and reviewed, **not implemented**. Nothing in the README about it |
| `IN PROGRESS` | Approved and being built; the task list shows what is left |
| `DONE` | Implemented, tested, in the README; kept as the record of decisions and deviations |

A spec is **approved** when the author says so in the conversation or the PR; agents do not self-approve.

## Index

| # | Spec | Status | Code | Main tests |
|---|---|---|---|---|
| 00 | [Overview](00-overview.md): problem, principles, scope, risks | LIVING | — | — |
| 01 | [Architecture](01-architecture.md): stack, layout, data flow, errors, cost, security | LIVING | all | — |
| 02 | [Data model](02-data-model.md): `Job`, statuses, SQLite tables, dedupe | LIVING | `models.py`, `db.py`, `store.py` | `test_models`, `test_db`, `test_store` |
| 03 | [Sources](03-sources.md): public APIs/feeds, company discovery | LIVING | `sources/`, `http.py`, `companies.py`, `pipeline.py` | `test_sources`, `test_http`, `test_companies`, `test_pipeline` |
| 04 | [Filtering](04-filtering.md): the hard filter | LIVING | `filters.py`, `text.py` | `test_filters`, `test_filter_stage`, `test_text` |
| 05 | [Scoring](05-scoring.md): LLM backends, batches, selection | LIVING | `llm.py`, `scoring.py` | `test_llm`, `test_scoring` |
| 06 | [Tailoring](06-tailoring.md): CV and letter, verification | LIVING | `latex.py`, `tailoring.py`, `translate.py` | `test_latex`, `test_tailoring` |
| 07 | [CLI and config](07-cli-config.md) | LIVING | `cli.py`, `config.py`, `doctor.py` | `test_cli_doctor`, `test_config` |
| 08 | [Roadmap](08-roadmap.md): flat task list and decisions | LIVING | — | — |
| 09 | [Web UI](09-web-ui.md): pages, safe config editing, runs, security | LIVING | `web/`, `config_edit.py`, `applications.py` | `test_web`, `test_config_edit`, `test_applications` |
| 10 | [Add a posting by hand](10-manual-postings.md) | DONE | `postings.py`, `fetch_url.py` | `test_postings`, `test_web` |
| 11 | [Favorites and block list](11-favorites-and-blocklist.md) | DONE | `favorites.py`, `filters.py` | `test_favorites` |
| 12 | [Interview prep kit](12-interview-prep.md) | PLANNED | — | — |
| 13 | [Market insights](13-market-insights.md) | PLANNED | — | — |
| 14 | [New sources and API keys](14-new-sources-api-keys.md) | PLANNED | — | — |
| 15 | [First-run setup wizard](15-onboarding-wizard.md) | PLANNED | — | — |
| 16 | [CV importer](16-cv-importer.md) | PLANNED | — | — |
| 17 | [Offer negotiation helper](17-offer-negotiation.md) | PLANNED | — | — |
| 18 | [Frontend redesign](18-frontend-redesign.md) | DONE | `web/static`, `web/templates` | `test_web` (smoke tests) |
| 19 | [Open source ready](19-open-source-ready.md) | IN PROGRESS | `sources/registry.py`, `resources.py`, `demo.py`, `cli.py` (`init`, `demo`, `ui --bind`), `scripts/check_docs.py` | `test_source_contract`, `test_init_demo` |
| 20 | [OpenAI-compatible backend](20-openai-compatible-backend.md) | PLANNED | — | — |
| 21 | [Posting quality signals](21-posting-quality.md) | PLANNED | — | — |

Keep this table current when a spec is added or changes status.

## Template for a new spec

Copy this, keep the section names so every spec reads the same way:

```markdown
# NN — Title

**Status:** PLANNED (spec only, not implemented)

## 1. Problem
Who hurts and why, in two or three sentences. Reference what exists today.

## 2. Goal / Design
What it does, user-visible behaviour first, then the data, config keys, commands,
endpoints and UI it touches. Say what is deliberately NOT done and why.

## 3. Principles and safety
Which project principles apply (manual only, no invented facts, local-first, security rules).

## 4. Tests
The cases that prove it, including the negative ones (what must not happen).

## 5. Tasks
- [ ] Small, checkable steps, in order. The last one is always "README and this spec marked done".

## 6. Acceptance criteria
- [ ] Observable statements. When verified, tick them and cite the test: `(tests/test_x.py::test_name)`.
```

Rules of thumb: one problem per spec; a spec fits in a few screens; open questions go at the end under `## Open questions` and are answered by the author before work starts; decisions are numbered where several are made (see 18 §5); anything that changes a principle goes to the roadmap's *Decisions* list.

## How an agent should pick up work

1. Read `CLAUDE.md`, then this index, then the roadmap's first unchecked task and its spec.
2. If the spec is `PLANNED` and not approved, **ask the author** before building; if it is approved, set it to `IN PROGRESS`.
3. Build in small steps following the spec's task list; write the tests with the code.
4. Run the definition of done in `CLAUDE.md`; report what was verified and what was not; stop.
