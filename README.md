# Job Hunter

Local Python pipeline that finds job postings on public job boards, filters and scores them against your criteria, and prepares LaTeX application packages (CV + cover letter) for **you** to review and send. It never sends anything on its own.

- Design (source of truth): [`specs/`](specs/) — start at [`00-overview.md`](specs/00-overview.md)
- Project conventions: [`CLAUDE.md`](CLAUDE.md)

> **Keep this file current.** Every phase that adds or changes behaviour must update the *Status*, *Commands* and *Configuration* sections below.

## Status

| Phase | What | State |
|---|---|---|
| 0 | Skeleton: config, SQLite, `doctor` (LaTeX toolchain check) | ✅ Done |
| 1 | Sources: aggregators + ATS boards, dedupe, company discovery | ✅ Done (pending review) |
| 2 | Hard filter on your criteria (`refilter`, `explain`) | ⏳ Next |
| 3 | LLM scoring (Haiku), LaTeX CV parser, `calibrate` | ⏳ Planned |
| 4 | Tailoring: LaTeX CV/letter packages + PDF, translations, verification | ⏳ Planned |
| 5 | Daily operation: `review`, `mark`, `stats`, scheduling | ⏳ Planned |

What works **today**: downloading postings from many sources into a local database, growing the list of company boards, and checking your environment. Filtering, scoring and package generation are not implemented yet, so right now the tool collects postings but does not yet pick the best ones for you.

## How it works (the core loop)

```
   fetch ──▶ filter ──▶ score ──▶ tailor ──▶ YOU review and apply
   (done)    (Phase 2)  (Phase 3) (Phase 4)
```

| Stage | What it does | Costs tokens? | Needs from you |
|---|---|---|---|
| **fetch** | Downloads postings from public job boards | No | Nothing |
| **filter** | Drops postings that don't match your criteria (title, seniority, remote, location, salary, keywords) | No | Your preferences in `config/config.yaml` |
| **score** | LLM rates the remaining postings 0–100 against your CV | Yes (cents) | Your CV + `ANTHROPIC_API_KEY` |
| **tailor** | For the best ones, builds a LaTeX CV + cover letter (PDF) | Yes | Your cover-letter template |
| **you** | Read the package, apply, mark the result | — | — |

## Step by step

### A. One-time setup

Requirements: macOS with [Homebrew](https://brew.sh). Python 3.12 is installed by `uv`.

**1. Install and check the environment**

```bash
git clone <repo-url> job-hunter && cd job-hunter
brew install uv tectonic                          # uv = Python/deps manager, tectonic = LaTeX engine
uv sync                                           # creates .venv and installs dependencies
cp config/config.example.yaml config/config.yaml  # your local settings (gitignored)
uv run jobhunter doctor                           # verifies Python, config, LaTeX and API key
```

`doctor` output (the two warnings are expected until Phase 3):

```
[ok  ] python: 3.12.x (need >= 3.12)
[ok  ] config: config/config.yaml is valid
[warn] ANTHROPIC_API_KEY: not set (needed from Phase 3)
[ok  ] latex (tectonic): compiled OK
[warn] master CV: config/cv/master.tex not found (needed from Phase 3)
```

The first LaTeX compilation is slow because `tectonic` downloads packages; later ones are fast. If `uv` or `tectonic` are not found, make sure `/opt/homebrew/bin` is in your `PATH`.

**2. Build your company list** *(optional but recommended; without it only the aggregators are fetched)*

```bash
uv run jobhunter companies discover   # probes config/company_candidates.txt, writes config/companies.yaml
```

Add any company you like to `config/company_candidates.txt` and re-run it any time.

**3. Set your preferences** — edit the `search:` section of `config/config.yaml` (titles, seniority, remote/location, **annual USD** salary, keywords). See [Setting your preferences](#setting-your-preferences-search). Takes effect once the filter exists (Phase 2).

**4. Add your CV and API key** *(needed from Phase 3)* — put your LaTeX CV at `config/cv/master.tex` and `export ANTHROPIC_API_KEY=...` in your shell.

### B. Your routine (the core use)

**Today (Phase 1):** collect postings.

```bash
uv run jobhunter run --dry-run   # optional: see which sources would be fetched
uv run jobhunter run             # download postings into data/jobhunter.db
```

Run it at most once a day. Look at what was collected:

```bash
sqlite3 data/jobhunter.db "select company, title, location, url from jobs where status='new' limit 20;"
```

**When the phases land, the routine becomes:**

```bash
uv run jobhunter run          # fetch → filter → score → tailor, in one command
uv run jobhunter review       # list today's best matches and their packages   (Phase 5)
# open out/<date>/<company>-<role>/ : read cv.pdf and cover_letter.pdf, apply yourself
uv run jobhunter mark <id> applied   # keep track of what you did               (Phase 5)
uv run jobhunter stats               # funnel and LLM cost                      (Phase 5)
```

Each phase updates this section when it ships, so what is written under "today" always works.

## Commands

All commands accept `--config/-c PATH` (default `config/config.yaml`) except where noted.

### Implemented

| Command | What it does |
|---|---|
| `jobhunter --help` / `--version` | Usage and version |
| `jobhunter doctor` | Checks Python ≥ 3.12, config validity, `ANTHROPIC_API_KEY`, the LaTeX engine (compiles a minimal document) and `master.tex` if present. Exits non-zero only on **required** failures (warnings do not fail) |
| `jobhunter run --stage fetch` | Fetches every configured source concurrently, stores new/changed postings, closes postings that disappeared, marks cross-source duplicates. Prints a one-line summary |
| `jobhunter run --dry-run` | Prints how many sources of each kind would be fetched, without any network call |
| `jobhunter run` (no `--stage`) | Runs all implemented stages (currently just `fetch`) |
| `jobhunter run --stage filter\|score\|tailor` | Exits with "not implemented yet" |
| `jobhunter companies check` | Probes every board in `companies.yaml` (200 vs 404). Lists broken ones and exits 1 if any |
| `jobhunter companies discover` | Reads `config/company_candidates.txt`, probes each unknown name against Greenhouse, Lever and Ashby (slug variants like `huggingface` / `hugging-face`), and adds boards that exist **and** have at least one posting to `config/companies.yaml` |

Example fetch output:

```
fetched 25109 postings from 204 sources (0 failed) · new 25069 · updated 0 · unchanged 0 · closed 0 · duplicates 113
```

A second run immediately after reports `new 0 · updated 0` (idempotent).

### Planned (see [`specs/07-cli-config.md`](specs/07-cli-config.md))

`refilter`, `explain <id>`, `show <id>`, `review`, `mark <id> applied|replied|rejected|closed`, `stats`, `calibrate`, `cv init`, `cv check`, `cv translate --lang <code>`, and `run --stage filter|score|tailor`.

## What it fetches

Only sources with a documented public API or feed. No login, no browser, **no LinkedIn/Indeed**.

| Layer | Sources | Notes |
|---|---|---|
| Aggregators (many companies per call) | Remotive, RemoteOK, We Work Remotely (RSS), Arbeitnow, Jobicy | Mostly remote jobs. Each posting keeps the aggregator's own URL (their terms ask for a link back). Personal use only |
| Per-company boards | Greenhouse, Lever, Ashby | One API call per company; the list lives in `config/companies.yaml` |
| Company discovery | `jobhunter companies discover` | Grows `companies.yaml` from `config/company_candidates.txt`. The company list is only a discovery mechanism: your filters (Phase 2) ignore which company a posting comes from |

Not included yet (backlog): Adzuna / Jooble / The Muse (need a free personal API key), Himalayas, GetOnBoard, Torre, HN "Who is hiring", Workable, Recruitee, SmartRecruiters.

Details and rationale: [`specs/03-sources.md`](specs/03-sources.md).

### How postings are tracked

- Each posting is keyed by `(source, external_id)` and stored once, even if it appears in several feeds/pages.
- **Content changed** → description updated and the posting goes back to `new` so it is re-filtered/re-scored. Postings you marked `applied`, `replied` or `rejected` keep their status.
- **Not seen for `stale_days` (default 7)** → `closed`, but only for source kinds fetched successfully in that run (an outage never closes everything). A closed posting that reappears becomes `new` again.
- **Same company + title in different sources** → the direct-ATS posting is kept, the copy is marked `duplicate`.
- A failing source (network error, 404, invalid JSON/RSS) is recorded in `fetch_log` and never stops the other sources. A malformed single item is skipped, not the whole feed.

Statuses: `new → filtered | passed → scored | score_failed | below_threshold → selected → packaged → applied → replied | rejected`, plus `closed` and `duplicate`. See [`specs/02-data-model.md`](specs/02-data-model.md).

## Configuration

Your settings live in `config/config.yaml` (create it with `cp config/config.example.yaml config/config.yaml`; the example documents every default). It is validated at load (unknown keys and bad values give an error naming the field). Reference: [`specs/07-cli-config.md`](specs/07-cli-config.md).

| Section | Purpose | Used since |
|---|---|---|
| `sources` | Which aggregators, WWR categories, Arbeitnow pages, concurrency limits, `stale_days`, company/candidate file paths | Phase 1 |
| `search` | **Your criteria**: `titles_include/exclude`, `keywords_include/exclude`, `seniority`, `work_mode`, `locations_allowed`, `salary`, `max_age_days` | Phase 2 |
| `scoring` | Model (default `claude-haiku-5-5`), `score_threshold` (75), description truncation | Phase 3 |
| `tailoring` | Model (default `claude-sonnet-5-5`), `mode: select`, `max_packages_per_day` (10), `languages`, `tone`, `max_cv_pages` | Phase 4 |
| `latex` | `engine` (`tectonic` or `latexmk`), `timeout_seconds` | Phase 0 |
| `budget` | `daily_budget_usd` (1.00) cap on LLM spend | Phase 3 |
| `fx_rates_to_usd` | Manual FX table used to compare salaries | Phase 2 |
| `paths` | CV master, letter template, database, output folder | — |

### Setting your preferences (`search`)

```yaml
search:
  titles_include: ["backend", "software engineer"]   # at least one must match the title
  titles_exclude: ["intern", "junior", "manager"]
  keywords_include: ["python"]                        # at least one in the description (optional)
  keywords_exclude: ["security clearance"]
  seniority: ["mid", "senior"]
  work_mode: ["remote"]                               # remote | hybrid | onsite
  locations_allowed: ["Colombia", "LATAM", "Worldwide", "Anywhere"]
  salary:
    min_usd: 48000          # ANNUAL, in USD. Monthly × 12 (e.g. USD 4,000/month = 48000)
    on_missing: pass        # pass = keep postings without a salary; reject = drop them
  max_age_days: 30
```

Salary notes: `min_usd` is **annual USD**. Postings that publish hourly or monthly pay are annualized automatically; other currencies are converted with `fx_rates_to_usd`. These values take effect once the filter exists (Phase 2).

### Company lists

- `config/companies.yaml` — boards to fetch (`name`, `ats`, `slug`). Generated by `discover`; safe to edit by hand. If it is missing, only the aggregators are fetched.
- [`config/company_candidates.txt`](config/company_candidates.txt) — names to probe, one per line (`#` comments allowed). Add any company you like, then run `jobhunter companies discover`.

### Environment

| Variable | Use |
|---|---|
| `ANTHROPIC_API_KEY` | Only credential; needed from Phase 3. Never put it in files |

## Data and privacy

| Path | Content | Committed? |
|---|---|---|
| `data/jobhunter.db` | SQLite: postings, scores, packages, LLM calls, fetch log, status events | No |
| `out/` | Generated application packages (Phase 4) | No |
| `config/cv/` | Your LaTeX CV (`master.tex`) and letter template | No |
| `config/config.yaml` | Your local settings and search preferences (copy of `config.example.yaml`) | No |
| `config/companies.yaml` | Company boards, generated by `companies discover` | No |
| `config/config.example.yaml` | Documented defaults; the template for `config.yaml` | Yes |
| `config/company_candidates.txt` | Public company names to probe (shared seed list) | Yes |

Only code, specs, tests (with small public-API fixtures), the example config and the candidate list are committed. See [`.gitignore`](.gitignore).

Inspect the database directly:

```bash
sqlite3 data/jobhunter.db "select source, count(*) from jobs group by source order by 2 desc;"
sqlite3 data/jobhunter.db "select status, count(*) from jobs group by status;"
sqlite3 data/jobhunter.db "select source, target, status, error from fetch_log where status='error';"
```

Privacy design (Phase 3+): only the plain text of CV items you mark and the posting text are ever sent to the LLM. Your LaTeX preamble/header (name, phone, email, address) is copied by code and never leaves your machine. See [`specs/06-tailoring.md`](specs/06-tailoring.md) and [`specs/07-cli-config.md`](specs/07-cli-config.md).

## Project layout

```
config/                 config.example.yaml, company_candidates.txt (committed); config.yaml, companies.yaml, cv/ (yours, gitignored)
specs/                  design specs (00–08), source of truth
src/jobhunter/
  cli.py                typer CLI (doctor, run, companies check/discover)
  config.py             YAML config loading + validation (pydantic)
  models.py             Job model and JobStatus
  db.py                 SQLite connection + versioned migrations
  http.py               polite async HTTP client (UA, retries, concurrency limits)
  text.py               HTML→text, remote-mode and salary inference
  store.py              upsert/dedupe, close stale, duplicate marking, fetch log
  companies.py          companies.yaml, check, discover
  pipeline.py           fetch stage orchestration
  doctor.py             environment checks
  sources/              greenhouse, lever, ashby, aggregators (+ base, registry)
tests/                  pytest suite with real (trimmed) fixtures; no network
```

## Development

```bash
uv run pytest                 # 77 tests, no network, ~1 s
uv run ruff check .           # lint
uv run ruff format .          # format
```

Conventions (English everywhere, spec-driven, phase-by-phase) are in [`CLAUDE.md`](CLAUDE.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `uv: command not found` | `brew install uv`; ensure `/opt/homebrew/bin` is in `PATH` |
| `doctor` says LaTeX `not found` | `brew install tectonic` (or set `latex.engine: latexmk` and install a TeX distribution) |
| First LaTeX compile takes ~1 min | Normal: `tectonic` downloads packages once |
| `Config file not found: config/config.yaml` | `cp config/config.example.yaml config/config.yaml` |
| `error: Invalid config ...: search.work_mode...` | Fix the named field in `config/config.yaml` |
| A source shows as failed in the fetch summary | See `fetch_log` (query above); a dead company slug shows up in `companies check` |
| Want to start over | Delete `data/jobhunter.db`; it is recreated on the next run |
