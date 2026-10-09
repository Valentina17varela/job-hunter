# 08 — Roadmap and tasks

Each phase ends with something runnable and verifiable. We don't move to the next phase without approval. No phase requires personal data before the one indicated.

## Phase 0 — Skeleton
- Repo, `pyproject.toml` (uv), ruff, pytest, `.gitignore` (profile, data, out).
- `models.py`, `config.py`, `db.py` + initial migration.
- `jobhunter doctor` with LaTeX toolchain check (tectonic/latexmk) compiling a minimal document.
- **Done when:** `pytest` and `ruff` pass; `jobhunter --help` and `jobhunter doctor` work.
- **Personal data:** none.

## Phase 1 — Sources
- Base `Source`, Greenhouse, Lever, Ashby, RemoteOK, WWR, Remotive.
- `companies.yaml` with a ~50-company seed + `companies check`.
- Dedupe, `fetch_log`, closing absent postings.
- **Done when:** `jobhunter run --stage fetch` fills the DB with real postings; fixture tests pass.
- **Personal data:** optional, target company list.

## Phase 2 — Filter
- `filters.py`, `refilter`, `explain`.
- **Done when:** the acceptance criteria in 04 pass on real data.
- **Personal data:** roles, seniority, work mode, location, salary range, keywords.

## Phase 3 — Scoring
- `latex.py` master parser (sections/entries/items with IDs), `cv init` and `cv check`.
- `llm.py` (client, caching, cost, budget), `scoring.py`, `profile_summary` built from the parsed items.
- `calibrate`.
- **Done when:** `master.tex` parses and compiles; cost/posting < USD 0.002 and calibration ≥ 80% hit rate.
- **Personal data:** LaTeX CV (`master.tex`), `ANTHROPIC_API_KEY`.

## Phase 4 — Tailoring
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

## Open questions for the review

1. Default `tailoring.mode`: `select` (cheaper and safer) or `rewrite`?
2. Package language: the posting's or fixed?
3. Do an initial threshold of 75 and 10 packages/day seem reasonable?
4. Is a USD 1 daily budget adequate?
5. Do you want a daily notification (phase 6) or prefer running `review` manually?
6. Is there any source you want to add or exclude in v1?
