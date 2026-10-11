# Job Hunter

Local Python pipeline that finds job postings on public job boards, filters and scores them against your criteria, and prepares LaTeX application packages (CV + cover letter) for **you** to review and send. It never sends anything on its own.

- Design (source of truth): [`specs/`](specs/) — start at [`00-overview.md`](specs/00-overview.md)
- Project conventions: [`CLAUDE.md`](CLAUDE.md)

> **Keep this file current.** Every phase that adds or changes behaviour must update the *Status*, *Commands* and *Configuration* sections below.

## Status

| Phase | What | State |
|---|---|---|
| 0 | Skeleton: config, SQLite, `doctor` (LaTeX toolchain check) | ✅ Done |
| 1 | Sources: aggregators + ATS boards, dedupe, company discovery | ✅ Done |
| 2 | Hard filter on your criteria (`refilter`, `explain`) | ✅ Done |
| 3 | LLM scoring (Haiku via your Claude subscription), LaTeX CV parser, `calibrate` | ✅ Done |
| 4 | Tailoring: LaTeX CV + cover letter packages (PDF), CV translation, verification | ✅ Done (pending review) |
| 5 | Application tracking (`mark`, `stats`, `review`) and the **local web UI** (`jobhunter ui`) | ✅ Done (pending review); scheduling with `launchd` still to do |

What works **today**, end to end: download postings from many sources, filter them against your criteria (no LLM), score the survivors with an LLM against your LaTeX CV, build a **tailored LaTeX CV + cover letter (PDF)** for the best matches, track your applications and interviews, and do all of it from a **local web UI** (`uv run jobhunter ui`) or the CLI. The tool never applies for you.

## How it works (the core loop)

```
   fetch ──▶ filter ──▶ score ──▶ tailor ──▶ YOU review and apply
   (done)    (done)     (done)    (done)
```

| Stage | What it does | Costs tokens? | Needs from you |
|---|---|---|---|
| **fetch** | Downloads postings from public job boards | No | Nothing |
| **filter** | Drops postings that don't match your criteria (title, seniority, remote, location, salary, keywords) | No | Your preferences in `config/config.yaml` |
| **score** | LLM rates the remaining postings 0–100 against your CV and flags explicit blockers (country restrictions, work authorization, required time zone) | Yes (your Claude plan usage, or API cents) | Your marked LaTeX CV + `claude auth login` (or an API key) |
| **tailor** | For the best ones: picks and orders your CV bullets, writes a one-page cover letter and a short recruiter message, compiles both PDFs, and checks them (ids, numbers, technologies, clichés, page limits) | Yes (one call per posting) | `config/cv/letter_template.tex` (see `letter init`) |
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

`doctor` output (warnings do not block the fetch and filter stages):

```
[ok  ] python: 3.12.x (need >= 3.12)
[ok  ] config: config/config.yaml is valid
[warn] llm (claude_cli): not logged in — run `claude auth login` in your terminal
[ok  ] latex (tectonic): compiled OK
[warn] master CV: config/cv/master.tex not found (needed for scoring)
```

The first LaTeX compilation is slow because `tectonic` downloads packages; later ones are fast. If `uv` or `tectonic` are not found, make sure `/opt/homebrew/bin` is in your `PATH`.

**2. Build your company list** *(optional but recommended; without it only the aggregators are fetched)*

```bash
uv run jobhunter companies discover   # probes config/company_candidates.txt, writes config/companies.yaml
```

Add any company you like to `config/company_candidates.txt` and re-run it any time.

**3. Set your preferences** — edit the `search:` section of `config/config.yaml` (titles, seniority, remote/location, **annual USD** salary, keywords). See [Setting your preferences](#setting-your-preferences-search). Apply changes with `uv run jobhunter refilter`.

**4. Enable the LLM stages** *(scoring; tailoring later)*

- **Log in once, in your own terminal** (default backend, uses your Claude subscription, no API key): `claude auth login`. Then `uv run jobhunter doctor` should show `[ok] llm (claude_cli): logged in`.
  Prefer an API key instead? Set `llm.backend: anthropic_api` in `config/config.yaml` and `export ANTHROPIC_API_KEY=...`.
- **Put your LaTeX CV at `config/cv/master.tex`** and mark which parts can be selected (see [Your LaTeX CV](#your-latex-cv)).
- **Tell the scorer how you can work**: fill `scoring.candidate_context` in `config/config.yaml` (e.g. "Based in Colombia. Can work for companies in English-speaking countries only as an independent contractor, no work visa."). Postings that explicitly require something you cannot meet are flagged and scored down.

### B. Your routine (the core use)

**Today (Phases 1–2):** collect postings and keep the ones that match your criteria.

```bash
uv run jobhunter run --dry-run   # optional: see which sources would be fetched
uv run jobhunter run             # fetch postings, then filter them (writes data/jobhunter.db)
```

Run it at most once a day. The summary tells you how many postings pass and which rule rejected the rest:

```
filtered 24956 postings · passed 50 · rejected 24906 · status changes 24956
  rejected by titles_include: 14426
  rejected by titles_exclude: 6756
  rejected by work_mode: 2017
  ...
50 postings currently pass your criteria
```

Look at the matches, and understand any decision:

```bash
sqlite3 data/jobhunter.db "select id, company, title, location, url from jobs where status='passed' order by company;"
uv run jobhunter explain 123     # why posting #123 passed or was rejected, with the matching text
```

**Tuning your criteria:** edit `search:` in `config/config.yaml`, then `uv run jobhunter refilter` (re-evaluates everything already downloaded, no network). Too few matches? Look at which rule rejects the most in the summary and loosen it. Too many? Add `keywords_include` or tighten `titles_include`.

**Score the postings that pass** (needs the LLM setup from step A4):

```bash
uv run jobhunter run --stage score   # ~8 postings per LLM call, ~10 s per call
sqlite3 -separator ' | ' data/jobhunter.db "select j.id, j.company, j.title, s.score, json_extract(s.reasons,'$.verdict'), json_extract(s.reasons,'$.reason'), j.url from jobs j join scores s on s.job_id=j.id and s.created_at=(select max(created_at) from scores where job_id=j.id) where j.status='selected' order by s.score desc;"
uv run jobhunter explain 123         # criteria view of a posting
uv run jobhunter calibrate           # tell the tool where you disagree with it
```

Postings end as `selected` (best matches, up to 10 a day), `scored` (good but no slot today), or `below_threshold`. `red_flags` in the score shows explicit blockers it found.

**Build the application packages** (for the `selected` postings):

```bash
uv run jobhunter run --stage tailor              # one LLM call per posting, ~15 s each
uv run jobhunter run --stage tailor --job 1163   # build it by hand for ANY posting, whatever its score or filter verdict (--force rebuilds)
uv run jobhunter review                          # list packages waiting for you
```

Each package is a folder `out/<date>/<company>-<role>-<id>/` with `cv.pdf`/`cv.tex`, `cover_letter.pdf`/`.tex`, `recruiter_message.md`, `notes.md` (why it fits, gaps, what to verify) and `meta.json`. If an automatic check fails, `notes.md` starts with a **REVIEW** banner listing what to fix; the files are still written. Open the PDFs, check the "verify before applying" notes, and apply yourself.

**Keep track of what happened** (or use the web UI below):

```bash
uv run jobhunter mark 1163 applied --note "via careers page"
uv run jobhunter mark 1163 interviewing          # screening | interviewing | offer | accepted | rejected | withdrawn | ghosted
uv run jobhunter stats                           # funnel, filter reasons, LLM usage
```

**Or do everything in one command:** `uv run jobhunter run` (fetch → filter → score → tailor).

## Web UI (local dashboard)

```bash
uv run jobhunter ui --open      # http://127.0.0.1:8765  (--port to change)
```

| Page | What you can do |
|---|---|
| **Dashboard** | Funnel from fetched postings to offers, why postings were filtered out, applications per stage, LLM usage, last fetch per source, live health checks |
| **Postings** | Browse and filter (status, source, mode, min score, text search, sort); open any posting for its score, matches, gaps, red flags, the live filter verdict, history, the package and your application. **Any posting has a "Build package for this posting" button**, so you can package ones you like that the score left out |
| **Pipeline** | Kanban of your applications: *Ready to apply → Applied → Screening → Interviewing → Offer → Accepted / Rejected / Withdrawn / No response*. Move cards, keep notes, schedule interviews (type, date, outcome) |
| **Packages** | Every generated package with its PDFs, checks result and the recruiter message (copy button) |
| **Run** | Start any stage by hand (fetch, filter, re-filter, score, tailor with `--job/--limit/--force`, company discovery, CV check, doctor), with dry-run, a live log and run history |
| **Settings** | The effective configuration, your CV structure (ids), and the health checks. Editing stays in `config/config.yaml` |

The UI listens only on `127.0.0.1`, rejects requests from other hosts/origins, only accepts JSON for changes, runs a whitelist of commands as subprocesses of the CLI, and serves files only from `out/`. It shows personal data, so do not expose it through a tunnel or proxy.

Each phase updates this section when it ships, so what is written under "today" always works.

## Your LaTeX CV

`config/cv/master.tex` is your own LaTeX CV plus `% jh:` marker comments (comments only; compiling it still gives your original CV). Markers say what the tool may select or reorder; everything else, including your header with name, email and links, is copied untouched and **never sent to the LLM**.

```latex
% jh:section experience
\section*{WORK EXPERIENCE}
% jh:entry exp-acme required          % a job/project block; "required" = never dropped
\noindent \textbf{Software Engineer, Acme} \\
% jh:item exp-acme-1 tags=python,aws  % one bullet (ends at the next marker or a blank line)
• Cut latency by 40\% \\
% jh:item exp-acme-2
• Built an API \\
% jh:endentry
% jh:endsection
```

Rules: sections contain entries and/or items; entries contain items; every id is unique; every block is closed (`endentry`, `endsection`). `jobhunter cv check` validates this and compiles the file. `jobhunter cv init plain.tex` proposes markers for a CV with `\item` bullets. A copy of your unmarked original is kept as `config/cv/master.original.tex`.

## Commands

All commands accept `--config/-c PATH` (default `config/config.yaml`) except where noted.

### Implemented

| Command | What it does |
|---|---|
| `jobhunter --help` / `--version` | Usage and version |
| `jobhunter doctor` | Checks Python ≥ 3.12, config validity, the LLM backend (`claude` logged in, or `ANTHROPIC_API_KEY`), the LaTeX engine (compiles a minimal document) and `master.tex` if present. Exits non-zero only on **required** failures (warnings do not fail) |
| `jobhunter run --stage fetch` | Fetches every configured source concurrently, stores new/changed postings, closes postings that disappeared, marks cross-source duplicates. Prints a one-line summary |
| `jobhunter run --stage filter` | Applies your `search` criteria to postings with status `new` (no network, no tokens). Prints passed/rejected counts and how many each rule rejected |
| `jobhunter run` (no `--stage`) | Runs all implemented stages (currently `fetch` then `filter`) |
| `jobhunter run --dry-run` | Prints the stages and how many sources of each kind would be fetched, without any network call |
| `jobhunter run --stage score` | Scores `passed` postings with the LLM in batches of `scoring.batch_size`, stores score, verdict, matches, gaps and red flags, then marks postings `selected` (top `max_packages_per_day` at or above `score_threshold`), `scored` (above threshold, no slot left) or `below_threshold`. Already-scored postings are never re-scored unless your CV, `candidate_context`, criteria or the prompt change. Stops cleanly at `budget.max_llm_calls_per_run` and resumes next run |
| `jobhunter run --stage tailor [--job ID]... [--limit N] [--force]` | For `selected` postings, or **exactly the given ids whatever their status** (use it for postings you like that the score or filter left out; it never overrides a status you recorded, such as applied): one LLM call returns which CV entries/bullets to keep and in what order, a 190–260 word cover letter and a recruiter message in the **posting's language**; code assembles `cv.tex` by copying your original LaTeX, trims it deterministically to `tailoring.max_cv_pages`, fills the letter template, compiles both PDFs and verifies them. Postings become `packaged` |
| `jobhunter review` | Lists packages waiting for you with their score, check result and folder |
| `jobhunter mark <id> <stage> [--note]` | Records your application stage: `applied`, `screening`, `interviewing`, `offer`, `accepted`, `rejected`, `withdrawn`, `ghosted` (updates the posting status and its history) |
| `jobhunter stats` | Funnel (fetched → … → applied → interviewing → offers), filter rejections by rule, applications by stage, LLM usage |
| `jobhunter ui [--port N] [--open]` | Starts the local web UI on `127.0.0.1` |
| `jobhunter cv translate --lang es` | Translates every marked part of your English CV **once** into `config/cv/translations/es.json` (numbers, LaTeX and technology names are checked); you review the file. Spanish postings then get the reviewed Spanish CV |
| `jobhunter letter init` | Copies `config/letter_template.example.tex` to `config/cv/letter_template.tex`; edit its three header lines |
| `jobhunter cv check` | Validates the `% jh:` markers of `master.tex` (unique ids, balanced blocks, contact details inside marked text) and compiles it |
| `jobhunter cv init <plain.tex>` | Proposes markers for an unmarked LaTeX CV (sections and `\item` bullets) into `<plain>.marked.tex`; you review and finish it by hand |
| `jobhunter calibrate` | Shows scored postings and asks y/n whether you agree, to measure how well the verdicts match your judgement |
| `jobhunter refilter` | Re-applies the filter to **all** stored postings (except ones you applied to, closed or duplicates) after you change `search`. Postings that still pass keep their later-stage status |
| `jobhunter explain <id>` | Shows a posting (title, company, location, mode, salary, URL), its stored status/reason, and whether it passes the **current** criteria, with the rule and matching text if rejected |
| `jobhunter companies check` | Probes every board in `companies.yaml` (200 vs 404). Lists broken ones and exits 1 if any |
| `jobhunter companies discover` | Reads `config/company_candidates.txt`, probes each unknown name against Greenhouse, Lever and Ashby (slug variants like `huggingface` / `hugging-face`), and adds boards that exist **and** have at least one posting to `config/companies.yaml` |

Example fetch output:

```
fetched 25109 postings from 204 sources (0 failed) · new 25069 · updated 0 · unchanged 0 · closed 0 · duplicates 113
```

A second run immediately after reports `new 0 · updated 0` (idempotent).

### Planned (see [`specs/07-cli-config.md`](specs/07-cli-config.md))

`show <id>`, a `launchd` scheduler for the daily run, and the `rewrite` tailoring mode.

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
| `llm` | `backend` (`claude_cli` = your subscription, default; `anthropic_api`), `claude_path`, `timeout_seconds`, `max_attempts`, `effort`, `max_thinking_tokens` | Phase 3 |
| `scoring` | `model` (alias `haiku`), `score_threshold` (75), `batch_size` (8), description/profile limits, `candidate_context` | Phase 3 |
| `tailoring` | `model` (alias `sonnet`), `mode: select`, `max_packages_per_day` (10), `languages` (`en`, `es`: the letter and CV follow the posting's language, else English), `tone`, `max_cv_pages` (1) | Phase 4 |
| `latex` | `engine` (`tectonic` or `latexmk`), `timeout_seconds` | Phase 0 |
| `budget` | `max_llm_calls_per_run` (60, subscription backend) and `daily_budget_usd` (API backend) | Phase 3 |
| `fx_rates_to_usd` | Manual FX table used to compare salaries | Phase 2 |
| `paths` | CV master, letter template, database, output folder | — |

### Setting your preferences (`search`)

```yaml
search:
  titles_include: ["backend", "software engineer"]   # at least one must match the title
  titles_exclude: ["intern", "junior", "manager"]    # any match rejects (whole words: "intern" ≠ "Internal")
  keywords_include: ["python"]                        # at least one in title/description (optional)
  keywords_exclude: ["security clearance"]            # any match rejects
  seniority: ["mid", "senior"]                        # junior | mid | senior | lead (from the title)
  work_mode: ["remote"]                               # remote | hybrid | onsite
  locations_allowed: ["Colombia", "LATAM", "Americas", "Worldwide", "Anywhere", "Global"]
  salary:
    min_usd: 48000          # ANNUAL, in USD. Monthly × 12 (e.g. USD 4,000/month = 48000). 0 = off
    on_missing: pass        # pass = keep postings without a salary; reject = drop them
  max_age_days: 30          # aggregator postings only (they publish fresh dates)
  max_age_days_ats: null    # company-board postings; null = no limit (listed = open)
```

How each rule behaves (empty list = rule off; full details in [`specs/04-filtering.md`](specs/04-filtering.md)):

| Rule | Behaviour |
|---|---|
| Titles / keywords | Case-insensitive **whole-word** match. `titles_*` look at the title only; `keywords_*` at title + description |
| `seniority` | Inferred from the title: `staff/principal/lead/head of/architect` → lead, `senior/sr` → senior, `junior/jr/graduate/intern/trainee` → junior, no marker → mid |
| `work_mode` | Mode unknown → kept, flagged `unknown_mode` |
| `locations_allowed` | A named place ("Remote - US", "Seattle") must contain an allowed term (`LATAM` also matches "Latin America"; `US`/`UK` also match "U.S."/"United Kingdom"; short all-caps tokens like `US` are case-sensitive, so "contact us" never counts as a country). Generic ones ("Remote", "Worldwide") pass unless the description restricts it ("US only", "must be located in the United States", "EU time zones") |
| `salary` | Compared on the **top of the range**, in annual USD. Hourly/monthly pay is annualized; other currencies use `fx_rates_to_usd`; unknown currency → kept, flagged |
| Age | Unknown posting date → kept |

Postings kept with a doubt are flagged (`unknown_mode`, `unknown_location`, `no_salary`, `unknown_currency`); the flags are stored in the database for the scoring stage.

Salary: `min_usd` is **annual USD**. After editing, run `uv run jobhunter refilter`.

### Company lists

- `config/companies.yaml` — boards to fetch (`name`, `ats`, `slug`). Generated by `discover`; safe to edit by hand. If it is missing, only the aggregators are fetched.
- [`config/company_candidates.txt`](config/company_candidates.txt) — names to probe, one per line (`#` comments allowed). Add any company you like, then run `jobhunter companies discover`.

### Environment

| Variable | Use |
|---|---|
| `ANTHROPIC_API_KEY` | Only for `llm.backend: anthropic_api`. Never put it in files. The default `claude_cli` backend ignores it (and strips it from the subprocess) and uses your `claude auth login` session |

## Data and privacy

| Path | Content | Committed? |
|---|---|---|
| `data/jobhunter.db` | SQLite: postings, scores, packages, LLM calls, fetch log, status events | No |
| `out/` | Generated packages: CV and cover letter (`.tex` + `.pdf`), recruiter message, notes | No |
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
specs/                  design specs (00–09), source of truth
src/jobhunter/
  cli.py                typer CLI (doctor, run, refilter, explain, review, mark, stats, ui, cv, letter, companies)
  config.py             YAML config loading + validation (pydantic)
  models.py             Job model and JobStatus
  db.py                 SQLite connection + versioned migrations
  http.py               polite async HTTP client (UA, retries, concurrency limits)
  text.py               HTML→text, remote-mode and salary inference
  llm.py                LLM backends (claude -p / Anthropic API), budget, retries, call log
  latex.py              master CV parser/assembler, plain-text digest, `cv init` markers
  tailoring.py          CV item selection, page-fit trimming, cover letter, verification, packages
  translate.py          one-time reviewed CV translation
  language.py           posting language detection (stopword voting)
  applications.py      application stages, interviews, funnel stats
  web/                  local UI: app.py (FastAPI), runner.py (whitelisted CLI runs), templates/, static/
  scoring.py            batch scoring, truncation, selection (selected/scored/below_threshold)
  filters.py            hard filter (JobFilter): titles, seniority, mode, location, keywords, salary, age
  store.py              upsert/dedupe, close stale, duplicate marking, fetch log
  companies.py          companies.yaml, check, discover
  pipeline.py           fetch and filter stage orchestration
  doctor.py             environment checks
  sources/              greenhouse, lever, ashby, aggregators (+ base, registry)
tests/                  pytest suite with real (trimmed) fixtures; no network
```

## Development

```bash
uv run pytest                 # 265 tests, no network, no LLM, ~3 s (tests run in an empty temp dir and never touch your data)
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
| Too few postings pass the filter | Read the "rejected by <rule>: N" lines after `run`/`refilter`; loosen the rule with the highest count (often `titles_include` or `work_mode`) |
| Want to start over | Delete `data/jobhunter.db`; it is recreated on the next run |
