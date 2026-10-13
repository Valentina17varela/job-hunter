# job-hunter

Local Python "job-search copilot": finds postings on public job boards, filters them without an LLM, scores the survivors against the person's LaTeX CV, builds a tailored CV + cover letter (verified against invented facts) and tracks applications. **The human reviews and applies; the system never sends anything.** Full design in `specs/` (start at `specs/README.md`).

`AGENTS.md` is the short version of this file for other coding agents; if the two ever disagree, this file wins.

## Commands

```bash
uv sync                                   # install
uv run pytest -q                          # all tests (no network, no LLM; each runs in a temp dir)
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_docs.py       # docs/specs/example config/personal files in sync (also in CI)
uv run python scripts/seed_demo.py        # fictional workspace in data/demo/
uv run jobhunter ui --config data/demo/config.yaml --open   # UI on 127.0.0.1 with demo data
uv run jobhunter --help                   # CLI
```

Never run the real pipeline (`run`, `score`, `tailor`) or the UI against the person's own `config/config.yaml` and `data/` unless the task says so: it spends their LLM quota and touches their data. Use the demo workspace or temp dirs.

## How we work (spec-driven development)

1. **A spec exists before code.** Non-trivial work starts as a new spec or a change to one in `specs/` (template and status vocabulary in `specs/README.md`). Do not implement a spec that is not approved by the author; propose spec changes before diverging from it.
2. **One task at a time** from `specs/08-roadmap.md` (a flat list, no phases). Stop for the author's review after each task. Do not commit unless asked.
3. **Ship = definition of done.** A task is done only when all of these are true, in the same change:
   - [ ] code does what the spec says, with tests (see "Tests");
   - [ ] `uv run pytest -q` and `ruff check` + `ruff format --check` pass;
   - [ ] the spec's tasks and acceptance criteria are ticked **only for what is verified** (cite the test when there is one), its `Status` is updated, and deviations are written down in it;
   - [ ] `specs/08-roadmap.md`: task moved from *To do* to *Done*;
   - [ ] **`README.md` updated** for anything user-visible: commands and options, config keys, sources, statuses, UI pages and what they do, privacy/security behaviour, dependencies, file layout; screenshots refreshed when a page changed a lot. The README describes only what works today;
   - [ ] `config/config.example.yaml` in sync with the config model;
   - [ ] the code map below is still true (update it when modules are added or renamed).
4. **Specs say what and why; code says how.** If code and spec disagree, either fix the code or change the spec in the same change and say why. Never leave them silently apart.

## Conventions

- **English for everything:** code, identifiers, comments, docs, specs, commit and PR text, config keys, CLI output, tooling text of generated packages. The only non-English content is the person's own profile data and postings in other languages.
- **Manual only:** no cron/launchd, daemon, scheduler or notification. Every stage is started by the person from the CLI or the UI.
- **CV and cover letter are LaTeX** (input `config/cv/master.tex`, output `.tex` + compiled `.pdf`). Code copies the person's original LaTeX verbatim; the LLM never sees the preamble/header (contact details). See `specs/06-tailoring.md`.
- **Code first, LLM last:** discovery, dedupe and filtering are deterministic. The LLM only scores and writes, through `llm.py`, and every call is capped and logged.
- **No invented facts:** generated CV/letter text is verified in code against the master CV; a failed check blocks the package.
- **Security rules of the UI** (`specs/09-web-ui.md` §2.2, §5): bind 127.0.0.1 only; Host/Origin checks; JSON-only writes; escape all posting text; files served only from `out/`; locked config fields (`llm.claude_path`, `sources.companies_file`, `sources.candidates_file`, `paths`); no secrets rendered. Outbound requests only to job sources, the configured LLM backend and the single SSRF-safe page fetch of spec 10.
- **Keys** live only in environment variables, never in files, the database, logs or the UI.
- Request personal data only when the task needs it (`specs/00-overview.md` §7).
- Repo holds only code, specs, tests, docs, design inputs, `config/config.example.yaml` and `config/company_candidates.txt`. Never commit `config/config.yaml`, `config/companies.yaml`, `config/cv/`, `data/`, `out/` or any key.
- Stack: Python 3.12, uv, httpx, pydantic v2, SQLite (versioned migrations in `db.py`), typer, FastAPI + Jinja2 + vanilla JS/CSS (no build, no CDN), ruamel.yaml, pypdf, tectonic, pytest + respx, ruff (line length 100).

## Tests

- No test makes a real network or LLM call (respx / fake backends). An autouse fixture runs every test in an empty temp dir.
- Source adapters: one trimmed real fixture in `tests/fixtures/` per source.
- Anything security-relevant gets a negative test (foreign Host, path traversal, private IP, key in logs, XSS payload).
- UI changes: the smoke tests in `tests/test_web.py` (no external assets, one `h1`, labelled controls) must keep passing; add `aria-label` to controls without a visible label.
- Prefer asserting text and attributes (`data-run`, `data-cfg`, ids) over CSS classes.

## Code map (src/jobhunter/)

| Module | Responsibility | Spec |
|---|---|---|
| `models.py`, `db.py`, `store.py` | `Job` schema, SQLite + migrations, upsert/dedupe/close stale | 02 |
| `config.py`, `config_edit.py` | YAML config model; comment-preserving safe edits for the UI | 07, 09 |
| `http.py`, `sources/` | Polite async client; one self-registering module per source (`registry.py`: `greenhouse`, `lever`, `ashby`, `aggregators`) | 03, 19 |
| `companies.py`, `pipeline.py` | Company list/discovery; fetch + filter stages | 03, 04 |
| `filters.py`, `text.py`, `language.py` | Hard filter and `explain`; HTML cleaning, salary/remote inference; language detection | 04 |
| `llm.py` | The only place that calls an LLM: backends, budget, retries, call log | 05 |
| `scoring.py` | Batch scoring, cache, selection, `calibrate` | 05 |
| `latex.py`, `tailoring.py`, `translate.py` | Master-CV parser/assembler, compile; package building and verification; CV translation | 06 |
| `applications.py` | Stages, interviews, stats | 02, 09 |
| `favorites.py`, `postings.py`, `fetch_url.py` | Stars and notes; postings added by hand; SSRF-safe single-page fetcher | 11, 10 |
| `doctor.py`, `cli.py` | Environment checks; typer commands (`init`, `demo`, `ui --bind`…) | 07, 19 |
| `resources.py`, `demo.py` | Bundled examples (config, letter template, sample CV); the fictional demo workspace | 19 |
| `web/` | FastAPI app, run manager (whitelisted subprocess runs), templates, static (`tokens.css`, `style.css`, fonts, logo) | 09, 18 |

Tests mirror modules (`tests/test_<module>.py`); UI and API tests are in `tests/test_web.py`.
