# 09 — Local web UI

Goal: one place, on `http://127.0.0.1:<port>`, to **see** the whole flow (funnel, postings, scores, packages), **run** stages manually with their options, and **follow applications** through the interview process. Everything the UI does is also possible from the CLI; the UI adds visibility, not new logic.

## 1. Principles

- **Local only.** Bound to `127.0.0.1`; refuses requests whose `Host`/`Origin` is not the local server (blocks DNS-rebinding and cross-site POSTs from other web pages). No accounts, no remote access. It shows personal data (CV items, applications), so it must never listen on another interface.
- **Same code path as the CLI.** Runs are launched as subprocesses of `python -m jobhunter ...` and their output is streamed to the page, so the UI cannot behave differently from the CLI. One run at a time.
- **Boring tech.** FastAPI + Jinja2 server-rendered pages, one CSS file, small vanilla JS for actions and log polling. No CDN, no npm, works offline.
- **Never sends anything.** Like the rest of the project, the UI only prepares: it opens PDFs and posting links, and records what the person did.

## 2. Pages

| Page | What it shows / does |
|---|---|
| **Home** `/` | Funnel counts by status (fetched → filtered/passed → scored → selected → packaged → applied → interviewing → offer), rejections by filter rule, LLM calls/tokens today, last fetch per source, health (LaTeX, claude login, CV). Buttons to start the common runs |
| **Job matches** `/jobs` | Table with search and filters (status, source, min score, remote mode, company), sortable by score/date. Click → detail |
| **Posting detail** `/jobs/<id>` | Title, company, location, mode, salary, link, description, filter verdict + flags (live `explain`), score, verdict, matches, gaps, red flags, package links. Actions: mark applied, ignore, create/rebuild a package (available for every posting, not only selected ones) |
| **Applications** `/pipeline` | Kanban of applications: Applied → Screening → Interviewing → Offer → Accepted / Rejected / Withdrawn / Ghosted. Move cards, add notes, schedule interviews (kind, date, notes, outcome) |
| **Documents** `/packages` | Generated packages (cv.pdf, cover_letter.pdf, recruiter message, notes, verification result) with preview links |
| **Actions** `/run` | Every stage and option with a description: fetch, filter (`run`/`refilter`), score, tailor, companies check/discover, cv check, doctor; dry-run toggle; live log; history of recent runs. Shows a cost note for LLM stages |
| **Settings** `/settings` | **Everything is editable**: search criteria (tag inputs, checkboxes), AI engine/model/threshold/tone/limits, sources, the company list, the LaTeX CV and the cover-letter template, with plain-language hints, "Save & re-filter", field-level validation errors and the doctor checks |

### 2.1 UX decisions (v2)

- **Platform identity:** a "personal job-search copilot", local-first. The sidebar and hero say so; the side card states that nothing runs by itself and nothing is sent for the person.
- **Guided workflow on Home:** three steps (Search → Review matches → Prepare & apply) with one button each, a plain-language "What to do next" list computed from the data, four KPIs, upcoming interviews, a log-scaled funnel and friendly names for filter rules.
- **Actions run in place:** every button (Home, Job matches, a posting, Documents, Actions) starts a whitelisted run and streams its log into a docked panel available on every page; the active run survives page navigation (`sessionStorage`) and the page refreshes itself when a run finishes.
- **Job matches** are cards (score ring, AI reason, "N things to verify", one-click Build package / I applied / Hide) with tabs (Best matches, All evaluated, Applied, Filtered out, Everything, ★ Favorites), a *Favorites only* toggle and a *Favorites first* sort. Every card and posting page has a ★ toggle (spec 11); a posting page also has a favorite note and *Block this company*.
- **`search` stage** = fetch + filter (everything that needs no AI) so the first button on Home is free.

### 2.2 Editing configuration (security and safety)

- `POST /api/config {updates}` validates with the same pydantic model the CLI uses (numeric bounds included), then rewrites `config.yaml` with `ruamel.yaml` so comments and layout survive (fields left unchanged are not touched at all; a list the person edits loses comments inside it). Writes are atomic (temp file, `fsync`, replace), follow symlinks, keep the file mode, keep `.bak` (previous version) and a one-time `.orig`, and are verified by re-reading the result with the loader the CLI uses (YAML 1.1 quirks such as `NO`/`yes` are quoted).
- Editable sections: `search`, `scoring`, `tailoring`, `llm`, `budget`, `sources`, `latex`, `fx_rates_to_usd`. **Not editable from the UI:** `paths`, and the fields that name a file or a program to run: `llm.claude_path`, `sources.companies_file`, `sources.candidates_file` (they would turn a save into an arbitrary file write or code execution).
- `GET/POST /api/files/{cv|letter|candidates}` read and write only the paths configured in `config.yaml`. The CV is parsed (`% jh:` markers) and the letter template checked for its placeholders before saving; empty CV/letter content, files over 512 KB and non-UTF-8 files are refused. The buttons stay disabled until the file has loaded, so a failed load cannot overwrite a file with nothing.
- `POST /api/jobs/{id}/package/delete` removes a posting's generated folder (only inside `out/`, never following links out of it), forgets its package rows and sends a still-`packaged` posting back to `selected`; a status you recorded (applied...) is kept. If a folder cannot be removed its row stays so the person can retry.

### 2.3 Planned UI additions (specs only)

A visual redesign from collected design ideas is specified in [18](18-frontend-redesign.md) (inputs in `design/`).


`/setup` first-run wizard ([15](15-onboarding-wizard.md)), the CV importer screens ([16](16-cv-importer.md)), the Offer card and analysis page on applications at stage `offer` ([17](17-offer-negotiation.md)), plus the pages of specs 10-14 (add posting dialog, favorites tab, Insights, Prep card).

## 3. Runs

- `POST /api/runs {command: [...], dry_run}` accepts only a **whitelist** of commands (`run --stage …`, `refilter`, `companies check|discover`, `cv check`, `doctor`); anything else is rejected. Arguments are never interpolated into a shell.
- State: in-memory registry + a log file per run in `data/runs/`. `GET /api/runs/<id>` returns status (`running|ok|failed`), exit code and the log so far; the page polls it. A second run while one is active gets `409`.
- LLM stages are labelled; the UI shows the configured `max_llm_calls_per_run`.

## 4. Applications and interviews

- `applications` and `interviews` tables (see 02). Stage changes update `jobs.status` and write an `events` row.
- CLI parity: `jobhunter mark <id> applied|screening|interviewing|offer|accepted|rejected|withdrawn|ghosted [--note]`, `jobhunter stats` (funnel and LLM usage).

## 5. Security checklist

- Bound to `127.0.0.1`; `Host` and `Origin` validation middleware on every request; state-changing endpoints are `POST` with JSON only (`Content-Type: application/json` cannot be sent cross-site without a CORS preflight, which is denied).
- PDF/files served only from the configured `out/` directory with path-traversal protection.
- Jinja autoescape on; posting text is untrusted and always escaped.
- No secrets are rendered (API keys are never read by the UI).

## 6. Tests

- `TestClient`: every page renders on an empty and a populated database; filters; actions (mark, move stage, interview CRUD); whitelist and `409`; bad `Host`/`Origin` rejected; path traversal rejected; XSS payload in a posting is escaped.
- Runner tested with a fake command (no real fetch/LLM).

## 7. Acceptance criteria

- [x] `jobhunter ui` starts on localhost and every page loads without console errors.
- [x] A stage can be started from the Run page and its log streams until completion.
- [x] An application can be moved through every stage and an interview scheduled, and the dashboard funnel reflects it.
- [x] Requests with a foreign `Host`/`Origin` are rejected; files outside `out/` cannot be fetched.
