# 08 — Roadmap and tasks

Each phase ends with something runnable and verifiable. We don't move to the next phase without approval. No phase requires personal data before the one indicated.

## Phase 0 — Skeleton
- Repo, `pyproject.toml` (uv), ruff, pytest, `.gitignore` (profile, data, out).
- `models.py`, `config.py`, `db.py` + initial migration.
- `jobhunter doctor` with LaTeX toolchain check (tectonic/latexmk) compiling a minimal document.
- **Done when:** `pytest` and `ruff` pass; `jobhunter --help` and `jobhunter doctor` work.
- **Personal data:** none.

## Phase 1 — Sources ✅ implemented, pending review
- Breadth first: aggregators (Remotive, RemoteOK, We Work Remotely, Arbeitnow, Jobicy), then per-company ATS boards (Greenhouse, Lever, Ashby).
- `companies discover` grows `companies.yaml` from `company_candidates.txt`; `companies check` validates slugs. (Any-company coverage: see 03 §1.)
- Dedupe, `fetch_log`, closing absent postings, cross-source duplicates.
- **Done when:** `jobhunter run --stage fetch` fills the DB with real postings; fixture tests pass. ✅ (25,069 postings from 204 sources in ~35 s; re-run → 0 new / 0 updated; 76 tests passing.)
- **Personal data:** none needed (extra candidate company names optional).

## Phase 2 — Filter ✅ implemented, pending review
- `filters.py`, `refilter`, `explain`, `run --stage filter`.
- **Done when:** the acceptance criteria in 04 pass on real data. ✅ (25k postings evaluated in < 1 s; 132 tests passing.)
- **Personal data:** roles, seniority, work mode, location, salary range, keywords — *to be filled in `config/config.yaml`; the filter works with any values.*

## Phase 3 — Scoring ✅ implemented, pending review
- `latex.py` master parser/assembler (sections/entries/items, required entries, verbatim reassembly), `cv init`, `cv check`.
- `llm.py`: backends `claude_cli` (default, subscription) and `anthropic_api`, retries, call-count/USD budget, call log. `scoring.py`: batched scoring, caching, selection. `calibrate`. `doctor` checks the login.
- **Done when:** `master.tex` parses and compiles ✅; scoring runs on the real postings ✅ (≈ 11 s per batch of 8 after disabling extended thinking); calibration ≥ 80% hit rate *(needs the person to run `jobhunter calibrate`)*.
- **Personal data:** LaTeX CV (`master.tex`) ✅, `scoring.candidate_context` ✅, `claude auth login` ✅.

## Phase 4 — Tailoring (in progress)
- `cv translate` (one-time, reviewed translations per language), posting-language detection.
- `tailoring.py`: LLM selection of CV items (select mode), page-fit trimming, cover letter + recruiter message + notes in the posting's language, verification (ids, verbatim, letter facts, compile, pages), export to `out/`.
- LaTeX letter template (formal, one page) + generic example; `letter init`; `run --stage tailor`; `review`.
- **Done when:** the criteria in 06 pass; the person reviews 3 real packages (`.tex` + `.pdf`) and approves them.
- **Personal data:** letter template/tone ✅ (formal, warm, one page), languages ✅ (en/es), max CV pages ✅ (1).

## Phase 5 — Operation and web UI (in progress)
- `applications.py`: `mark`, `stats`, application stages and interviews; `review`.
- Local web UI (`jobhunter ui`, see 09): dashboard, postings, pipeline/interviews, packages, manual runs, settings.
- Scheduling with `launchd`, README.
- **Done when:** the person can run the whole flow and track applications and interviews from the UI; a daily automatic run works for 1 week within budget.

## Phase 6 — Improvements (backlog, not committed)
- `rewrite` tailoring mode (LLM rewording with LaTeX escaper and command allow-list).
- Multiple CV variants (e.g. backend vs. platform) selectable per posting.
- More ATS (Workable, Recruitee, SmartRecruiters) and sources (Himalayas, GetOnBoard, Torre, HN).
- Pre-ranking with local embeddings.
- Daily notification (own email/Slack) with the summary.
- Preference learning from `mark` and `calibrate`.

## Decisions (from review)

1. `tailoring.mode` default: **`select`**.
2. Package language: **the posting's** language for the CV, cover letter and recruiter message. The master CV is English-only, so the CV is translated **once per language** and reviewed by the person (see 06 §4.0). Allowed languages in `tailoring.languages`; unsupported languages fall back to English.
3. Score threshold **75**, **10 packages/day**.
4. Daily budget **USD 1**.
5. No daily notification; the person runs `jobhunter review` manually.
6. No sources added or excluded in v1.
