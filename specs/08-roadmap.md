# 08 — Roadmap and tasks

Each phase ends with something runnable and verifiable. We don't move to the next phase without approval. No phase requires personal data before the one indicated.

## Phase 0 — Skeleton
- Repo, `pyproject.toml` (uv), ruff, pytest, `.gitignore` (profile, data, out).
- `models.py`, `config.py`, `db.py` + initial migration.
- `jobhunter doctor` with LaTeX toolchain check (tectonic/latexmk) compiling a minimal document.
- **Done when:** `pytest` and `ruff` pass; `jobhunter --help` and `jobhunter doctor` work.
- **Personal data:** none.

## Phase 1 — Sources ✅ done
- Breadth first: aggregators (Remotive, RemoteOK, We Work Remotely, Arbeitnow, Jobicy), then per-company ATS boards (Greenhouse, Lever, Ashby).
- `companies discover` grows `companies.yaml` from `company_candidates.txt`; `companies check` validates slugs. (Any-company coverage: see 03 §1.)
- Dedupe, `fetch_log`, closing absent postings, cross-source duplicates.
- **Done when:** `jobhunter run --stage fetch` fills the DB with real postings; fixture tests pass. ✅ (25,069 postings from 204 sources in ~35 s; re-run → 0 new / 0 updated; 76 tests passing.)
- **Personal data:** none needed (extra candidate company names optional).

## Phase 2 — Filter ✅ done
- `filters.py`, `refilter`, `explain`, `run --stage filter`.
- **Done when:** the acceptance criteria in 04 pass on real data. ✅ (25k postings evaluated in < 1 s; 132 tests passing.)
- **Personal data:** roles, seniority, work mode, location, salary range, keywords — *to be filled in `config/config.yaml`; the filter works with any values.*

## Phase 3 — Scoring ✅ done
- `latex.py` master parser/assembler (sections/entries/items, required entries, verbatim reassembly), `cv init`, `cv check`.
- `llm.py`: backends `claude_cli` (default, subscription) and `anthropic_api`, retries, call-count/USD budget, call log. `scoring.py`: batched scoring, caching, selection. `calibrate`. `doctor` checks the login.
- **Done when:** `master.tex` parses and compiles ✅; scoring runs on the real postings ✅ (≈ 11 s per batch of 8 after disabling extended thinking); calibration ≥ 80% hit rate *(needs the person to run `jobhunter calibrate`)*.
- **Personal data:** LaTeX CV (`master.tex`) ✅, `scoring.candidate_context` ✅, `claude auth login` ✅.

## Phase 4 — Tailoring ✅ done (pending the person's review of real packages)
- `cv translate` (one-time, reviewed translations per language), posting-language detection.
- `tailoring.py`: LLM selection of CV items (select mode), page-fit trimming, cover letter + recruiter message + notes in the posting's language, verification (ids, verbatim, letter facts, compile, pages), export to `out/`.
- LaTeX letter template (formal, one page) + generic example; `letter init`; `run --stage tailor`; `review`.
- **Done when:** the criteria in 06 pass; the person reviews 3 real packages (`.tex` + `.pdf`) and approves them.
- **Personal data:** letter template/tone ✅ (formal, warm, one page), languages ✅ (en/es), max CV pages ✅ (1).

## Phase 5 — Tracking, web UI and docs ✅ done
- `applications.py`: `mark`, `stats`, application stages and interviews; `review`.
- Local web UI (`jobhunter ui`, see 09): dashboard, postings, pipeline/interviews, packages, manual runs, settings.
- README in the style of the author's other projects (badges, diagrams, clear sections); a redesigned, friendlier UI (guided workflow, plain-language labels).
- **Done when:** the person can run the whole flow and track applications and interviews from the UI or the CLI, entirely by hand.
- **Out of scope by decision:** scheduling/automatic runs (see 00 principles).

## Phase 6 — Improvements (backlog, not committed)
- `rewrite` tailoring mode (LLM rewording with LaTeX escaper and command allow-list).
- Multiple CV variants (e.g. backend vs. platform) selectable per posting.
- More ATS (Workable, Recruitee, SmartRecruiters) and sources (Himalayas, GetOnBoard, Torre, HN). Keyed sources are in spec 14.
- Pre-ranking with local embeddings.
- Preference learning from `mark` and `calibrate`.

## Phase 7 — Planned features (specs written, nothing implemented yet)

Each feature has its own spec with a task list, so it can be built task by task. Suggested order (small and independent first, the ones that gain from more data last):

| # | Feature | Spec | Why this position |
|---|---|---|---|
| 1 | Favorites and company block list | [11](11-favorites-and-blocklist.md) | Small, no new dependencies, immediately useful; adds the multi-rule evaluation hook (`evaluate_all`) that insights need |
| 2 | Add a posting by hand | [10](10-manual-postings.md) | Closes the biggest coverage gap (referrals, LinkedIn, newsletters); needs the safe URL fetcher |
| 3 | New sources with API keys, **The Muse first** | [14](14-new-sources-api-keys.md) | More data for everything after; The Muse needs no key to start; defines the shared key/redaction rules for Adzuna and Jooble |
| 4 | Market insights (analytics) | [13](13-market-insights.md) | Most valuable with several sources and some weeks of history; deterministic, no LLM |
| 5 | Interview preparation kit | [12](12-interview-prep.md) | **Only on demand and only once a company answers** (`screening`/`interviewing`); built last because it is needed last |

Decisions recorded for this phase:

- The interview kit is never generated for postings that were merely applied to; the person asks for it per interview.
- The Muse is the first keyed/keyless extra source (works without a key, 500 requests/hour); Adzuna and Jooble wait until the person has keys and the design is proven.
- Insights are computed locally from the collected postings (skills vocabulary + cohorts); the LLM "market brief" is optional and off by default.
- The block list lives in `config.yaml` (`search.companies_exclude`), favorites in the database.
- Everything stays manual: none of these features adds a scheduler, background job or notification.

## Decisions (from review)

1. `tailoring.mode` default: **`select`**.
2. Package language: **the posting's** language for the CV, cover letter and recruiter message. The master CV is English-only, so the CV is translated **once per language** and reviewed by the person (see 06 §4.0). Allowed languages in `tailoring.languages`; unsupported languages fall back to English.
3. Score threshold **75**, **10 packages/day**.
4. Daily budget **USD 1**.
5. No automatic runs and no notifications: everything is triggered by hand from the CLI or the UI.
6. No sources added or excluded in v1.
