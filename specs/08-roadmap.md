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

## Phase 3 — Scoring
- `latex.py` master parser (sections/entries/items with IDs), `cv init` and `cv check`.
- `llm.py` (client, caching, cost, budget), `scoring.py`, `profile_summary` built from the parsed items.
- `calibrate`.
- **Done when:** `master.tex` parses and compiles; cost/posting < USD 0.002 and calibration ≥ 80% hit rate.
- **Personal data:** LaTeX CV (`master.tex`), `ANTHROPIC_API_KEY`.

## Phase 4 — Tailoring
- `cv translate` (one-time, reviewed translations per language) and posting-language detection.
- `tailoring.py`, LaTeX assembly (select mode), letter template, PDF compilation, verification (IDs, verbatim, compile, page limit), export to `out/`.
- **Done when:** the criteria in 06 pass; the person reviews 3 real packages (`.tex` + `.pdf`) and approves them.
- **Personal data:** cover-letter template (or approval to derive one from the CV style), letter tone, languages, max CV pages.

## Phase 5 — Daily operation
- `review`, `mark`, `stats`, `launchd` scheduling, README.
- **Done when:** an automatic daily run for 1 week with no intervention and no budget overrun.

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
