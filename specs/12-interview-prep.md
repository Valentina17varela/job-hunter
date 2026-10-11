# 12 — Interview preparation kit

**Status:** PLANNED (spec only, not implemented)

## 1. Problem

Preparing for an interview takes hours: what will they ask, which of my experiences answers it, what are my weak spots, what do I ask them. The tool already knows the posting, the CV and the AI's view of the gaps.

## 2. When it exists (decision)

The kit is **only available once an application reaches `screening` or `interviewing`** (the company answered), and it is generated **only when the person asks for it**. It is never produced for postings that were just applied to, because many applications are never answered and the LLM cost would be wasted. Home suggests it ("Interview in 3 days for X: prepare?") but does not run it.

## 3. What it contains

One Markdown document per **interview** (kind-specific) stored with the application:

1. **Role snapshot** — what the posting emphasizes (responsibilities, stack, level), only from the posting text.
2. **Likely questions** by interview kind (`recruiter`, `technical`, `system_design`, `hiring_manager`, `onsite`, `other`), tied to the posting's requirements; for `technical` and `system_design`, topics to review (not answers to memorize).
3. **Your stories (STAR)** — 4-6 stories built from CV bullets, each **citing the CV item ids** it comes from; every number must appear in the CV. No invented employers, results or technologies.
4. **Gaps and how to address them** — from the scoring gaps and red flags, with honest framing.
5. **Questions to ask them** — about the team, the problem, success in 6 months, hiring process, remote/time-zone and contractor eligibility when the posting is unclear.
6. **Practicalities** — salary expectation notes (the posting's range if any, the person's configured minimum), logistics checklist, things to verify (residency, contract type).

It does **not** browse the web, scrape the company, or claim facts about the company beyond the posting.

## 4. Flow and interfaces

- On an application page, each interview card has **Prepare** (or *Prepare again*). A run (docked log, like other actions) calls the LLM once for that interview kind.
- CLI: `jobhunter prep JOB_ID [--interview N] [--kind technical] [--force]`; refuses unless the application stage is `screening`/`interviewing`/`offer` (or `--force`).
- Storage: file `out/<date>/<company-role>-<id>/prep-<interview_id|kind>.md` plus table `interview_prep(id, job_id, interview_id, kind, path, model, created_at, verified)`.
- UI: a **Prep** card on the posting page renders the Markdown (escaped, no raw HTML), with a copy button and delete (same safe-deletion rules as packages).
- Model: Sonnet by default (`tailoring.model`); `claude_cli` or API like every LLM call, counted in `llm_calls` and `budget.max_llm_calls_per_run`.

## 5. Verification (deterministic)

- Every STAR story cites existing CV item ids; numbers/percentages and technologies mentioned appear in the cited items or the CV skills; otherwise `verified = 0` and the document starts with a **REVIEW** banner listing the failures (the file is still written).
- Length bounds per section so the output stays scannable.

## 6. Privacy

Same as tailoring: only the plain text of marked CV items, the posting and `candidate_context` are sent to the LLM; never the LaTeX header.

## 7. Tests

- Gate: refused for `applied`, allowed for `screening`/`interviewing`/`offer`, `--force` overrides.
- Fake LLM: valid kit → file + row; story citing an unknown id or an invented number → REVIEW banner; one call per interview kind; budget cap stops cleanly.
- UI: button visible only from `screening`; rendering escapes HTML in the generated text; delete removes only files inside `out/`.

## 8. Tasks

- [ ] Migration: `interview_prep`.
- [ ] `prep.py`: prompt, schema, verification, storage.
- [ ] CLI `prep`, API `POST /api/interviews/{id}/prep`, run-whitelist entry.
- [ ] UI: Prep card, buttons, Home suggestion.
- [ ] README and this spec marked done.

## 9. Acceptance criteria

- [ ] Nothing is generated before the company answers.
- [ ] Every story is traceable to CV items; invented facts are flagged.
- [ ] The kit is useful on its own: the person can prepare an interview from the page alone.
