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
| **Dashboard** `/` | Funnel counts by status (fetched → filtered/passed → scored → selected → packaged → applied → interviewing → offer), rejections by filter rule, LLM calls/tokens today, last fetch per source, health (LaTeX, claude login, CV). Buttons to start the common runs |
| **Postings** `/jobs` | Table with search and filters (status, source, min score, remote mode, company), sortable by score/date. Click → detail |
| **Posting detail** `/jobs/<id>` | Title, company, location, mode, salary, link, description, filter verdict + flags (live `explain`), score, verdict, matches, gaps, red flags, package links. Actions: mark applied, ignore, create/rebuild a package (available for every posting, not only selected ones) |
| **Pipeline** `/pipeline` | Kanban of applications: Applied → Screening → Interviewing → Offer → Accepted / Rejected / Withdrawn / Ghosted. Move cards, add notes, schedule interviews (kind, date, notes, outcome) |
| **Packages** `/packages` | Generated packages (cv.pdf, cover_letter.pdf, recruiter message, notes, verification result) with preview links |
| **Run** `/run` | Every stage and option with a description: fetch, filter (`run`/`refilter`), score, tailor, companies check/discover, cv check, doctor; dry-run toggle; live log; history of recent runs. Shows a cost note for LLM stages |
| **Settings** `/settings` | Read-only view of the effective configuration (search criteria, scoring, tailoring, budgets) with explanations, the CV structure (sections, entries, ids) and the doctor checks. Editing stays in `config/config.yaml` |

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

- [ ] `jobhunter ui` starts on localhost and every page loads without console errors.
- [ ] A stage can be started from the Run page and its log streams until completion.
- [ ] An application can be moved through every stage and an interview scheduled, and the dashboard funnel reflects it.
- [ ] Requests with a foreign `Host`/`Origin` are rejected; files outside `out/` cannot be fetched.
