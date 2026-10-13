# 01 — Architecture

**Status:** LIVING (describes the system as it works today)

## 1. Stack

| Area | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Strong ecosystem for APIs/data |
| Dependency manager | `uv` | Fast, lockfile |
| HTTP | `httpx` (async) | Concurrency in fetchers |
| Models | `pydantic` v2 | Validation and common schema |
| Storage | SQLite (`sqlite3` stdlib) | Local, no server |
| CLI | `typer` | Simple, typed |
| Config | YAML (`PyYAML`) + pydantic | Readable and validated |
| LLM | `claude -p` (subscription, default) or `anthropic` SDK (API key) behind one interface in `llm.py` | No API key required; see 05 §1 |
| Tests | `pytest`, `respx` (HTTP mocking) | Fetchers without network |
| Lint/format | `ruff` | Single tool |
| LaTeX | `tectonic` (preferred) or `latexmk` | Compile CV/letter to PDF; external binary, checked by `jobhunter doctor` |
| PDF inspection | `pypdf` | Page count check |
| Web UI | `fastapi` + `uvicorn` + `jinja2`, vanilla JS (no CDN, no build step) | Local dashboard; server-rendered pages, bound to 127.0.0.1 (see 09) |

## 2. Repo layout

```
job-hunter/
├── CLAUDE.md, AGENTS.md    # conventions for agents; definition of done
├── README.md, LICENSE      # what works today; MIT
├── specs/                  # source of truth (index + template in specs/README.md)
├── design/                 # visual identity inputs: palette, logo, brief (spec 18)
├── docs/images/            # README screenshots
├── scripts/seed_demo.py    # fictional workspace for the UI / screenshots
├── config/
│   ├── config.example.yaml, company_candidates.txt, letter_template.example.tex  # committed
│   ├── config.yaml, companies.yaml                                              # NOT committed
│   └── cv/                 # NOT committed: master.tex (+ jh: markers), letter_template.tex, translations
├── src/jobhunter/
│   ├── models.py           # Job, statuses (pydantic)
│   ├── config.py           # loads and validates YAML; config_edit.py = safe comment-preserving edits
│   ├── db.py               # SQLite, versioned migrations
│   ├── store.py            # upsert/dedupe, close stale, duplicates
│   ├── http.py             # polite async client (UA, retries, concurrency limits)
│   ├── text.py, language.py  # HTML cleaning, remote/salary inference; language detection
│   ├── sources/            # one module per source: base.py (interface), greenhouse, lever, ashby, aggregators
│   ├── companies.py        # companies.yaml, check, discover
│   ├── pipeline.py         # fetch + filter stages
│   ├── filters.py          # hard filter (+ explain)
│   ├── llm.py              # the only LLM caller: backends, budget, retries, call log
│   ├── scoring.py          # batch scoring, cache, selection, calibrate
│   ├── latex.py            # master.tex parser/assembler, escaper, compile
│   ├── tailoring.py        # package building and verification; translate.py = CV translation
│   ├── applications.py     # stages, interviews, stats
│   ├── favorites.py        # stars and notes
│   ├── postings.py         # postings added by hand; fetch_url.py = SSRF-safe single-page fetcher
│   ├── doctor.py           # environment checks
│   ├── cli.py              # typer commands
│   └── web/                # app.py, runner.py, templates/, static/ (tokens.css, style.css, app.js, fonts, img)
├── tests/                  # mirrors modules; fixtures/ holds trimmed real source responses
├── out/                    # generated packages (gitignored)
├── data/                   # SQLite db, run logs, demo workspace (gitignored)
└── pyproject.toml
```

## 3. Data flow

```
config + companies.yaml
        │
   [1 FETCH]   each Source → list[Job], normalized          (0 tokens)
        │
   [2 DEDUPE]  hash(source, external_id) → insert new only   (0 tokens)
        │
   [3 FILTER]  hard rules → status=filtered|passed + reason  (0 tokens)
        │
   [4 SCORE]   Haiku: score 0-100 + reasons, JSON            (low cost)
        │
   [5 SELECT]  top-N with score ≥ threshold
        │
   [6 TAILOR]  Sonnet: item selection + letter + notes       (medium cost)
        │
   [7 EXPORT]  assemble cv.tex, compile PDFs, verify
               out/YYYY-MM-DD/{company}-{role}/  → human review
```

Each stage reads/writes SQLite and is **resumable**: if stage 4 fails, stage 5 resumes from `passed` postings without a score.

## 4. Source interface

```python
class Source(Protocol):
    name: str  # source kind, e.g. "greenhouse"
    target: str  # instance, e.g. a company slug ("" for single-feed sources)

    async def fetch(self, http: HttpClient) -> list[Job]: ...  # raises on failure
```

Adding a source = one new file + registration in `sources/__init__.py` (`build_sources`, which reads the registry). The rest of the pipeline is unchanged. Each module registers itself in `sources/registry.py`; a contract test (`tests/test_source_contract.py`) checks every source ([19](19-open-source-ready.md) §5).

## 5. Error handling

- A failing fetcher (network, 404, invalid JSON) **does not stop** the pipeline: it is recorded in `fetch_log` and the others continue.
- LLM calls: exponential-backoff retries (max 3). If they fail, the posting stays `passed` without a score and is retried on the next run.
- LLM responses are validated with pydantic; on invalid JSON, one retry with the error as feedback; then the posting is marked `score_failed`.

## 6. Cost control

- `llm.py` is the only place that calls the LLM (backend `claude_cli` or `anthropic_api`). Per call it records: model, tokens in/out/cache and cost when the backend reports them → `llm_calls` table.
- Before each call, the budget is checked: `max_llm_calls_per_run` (subscription backend) or `daily_budget_usd` (API backend). If exceeded, the pipeline ends cleanly and reports how many postings remain pending.
- Prompt caching on the stable prefix (instructions + plain-text CV items).
- Result cache keyed by `(job.content_hash, profile_hash, prompt_version)`.

## 7. Security and privacy

- `ANTHROPIC_API_KEY` (API backend only) via environment variable, never in files. The subscription backend uses the person's own `claude` login and strips inherited credentials from the subprocess environment.
- `config/cv/`, `data/`, `out/` in `.gitignore`.
- Only the plain text of marked CV items and the posting text are sent to the LLM. The LaTeX preamble and header (name, phone, address, links) are never sent (see 06, 07).
- LaTeX compilation runs with shell escape disabled, in a temp directory, with a timeout.
- Fetchers use an identifiable `User-Agent`, timeouts and per-host rate limits (see 03).
