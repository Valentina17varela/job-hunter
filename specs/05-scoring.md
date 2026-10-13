# 05 — Scoring (cheap LLM)

**Status:** LIVING (describes the system as it works today)

Goal: of the postings that passed the filter, estimate how good a match each is, at the lowest possible cost, and pick the daily top-N for tailoring.

## 1. LLM backends

All LLM calls go through `llm.py`, which hides the backend (`llm.backend` in config):

| Backend | How | Needs | Notes |
|---|---|---|---|
| `claude_cli` (default) | `claude -p` subprocess using the person's **Claude subscription** login | `claude auth login` once, in the person's own terminal | No API key or billing. Counts against the plan's usage limits. Slower per call, so postings are scored in **batches**. Cost is not exact |
| `anthropic_api` | Anthropic Python SDK | `ANTHROPIC_API_KEY` | Pay per use; exact tokens/cost; prompt caching with `cache_control` |

`claude_cli` details:
- Invocation: `claude -p --model <model> --tools "" --system-prompt <system> --setting-sources "" --disable-slash-commands --no-session-persistence --output-format json --json-schema <schema> --effort low`, with the user prompt on **stdin**, run in a temporary directory so no project `CLAUDE.md`, hooks, skills or tools are involved.
- Extended thinking is disabled (`MAX_THINKING_TOKENS=0`, config `llm.max_thinking_tokens`). Measured on real postings: a batch of 8 went from ~2 min / ~14k output tokens to ~11 s / ~1k output tokens with the same verdict quality.
- The subprocess environment **drops** every inherited `ANTHROPIC_*` / `CLAUDE_CODE_*` / `CLAUDE_AGENT_*` / `CLAUDECODE` variable (including `ANTHROPIC_API_KEY`), so it always uses the person's own login even when launched from inside another Claude session, and never silently switches to API billing.
- Result parsing is defensive: prefer the structured-output field, else parse the `result` text as JSON (code fences stripped); then validate with pydantic.
- Budget is a **cap on calls per run** (`budget.max_llm_calls_per_run`), since there is no exact price. `usage`/`total_cost_usd` from the CLI JSON are recorded when present.
- If the usage limit is reached mid-run, the stage stops cleanly and resumes next run.

`anthropic_api` budget is `budget.daily_budget_usd` as before.

## 2. Model and input

- Default model: `haiku` alias for `claude_cli` / `claude-haiku-5-5` for the API (`scoring.model`).
- **Batching:** `scoring.batch_size` postings (default 8) per call; the stable part (rubric + candidate profile) is sent once per batch. This cuts subprocess overhead and tokens.
- Per posting: id, title, company, location, mode, salary (if any), filter flags, and the description truncated to `scoring.max_description_tokens` (default 1,500 tokens ≈ 6,000 chars). Truncation keeps the start plus the requirements/responsibilities section (header heuristic) instead of a blind cut.
- **Candidate profile** = a deterministic plain-text digest of the `jh:` items of `config/cv/master.tex` (never the preamble/header), plus `scoring.candidate_context` (free text from the person, e.g. where they live and under what arrangement they can work) and the target roles/locations from `search`. No separate LLM summarization step; `scoring.max_profile_tokens` (default 3,000) is a guard that fails with a clear message if the CV digest is too large.
- `profile_hash` = hash of digest + candidate context + criteria; any change invalidates cached scores.

## 3. Output (strict JSON, validated with pydantic)

```json
{"results": [
  {
    "id": 123,
    "score": 0-100,
    "verdict": "apply | maybe | skip",
    "must_have_match": ["python", "aws"],
    "gaps": ["kubernetes"],
    "red_flags": ["requires US work authorization"],
    "reason": "max 40 words"
  }
]}
```

No free text outside the JSON. Every id in the batch must come back exactly once; missing ids stay `passed` for retry, malformed ones count as failures. Blockers go in `red_flags` **only when the posting explicitly states them** (citizenship/residency/work-authorization requirement, employee-only hiring in a country the candidate cannot work in, a required time zone, or an eligible-country list that excludes the candidate's country). The scorer must not infer a blocker from location or industry alone (first real trial: it marked every "USA" posting as a blocker; fixed in prompt `score-v2`). Output is kept terse (reason ≤ 30 words, ≤ 3 red flags).

## 4. Rubric

| Range | Meaning |
|---|---|
| 85–100 | Meets almost all key requirements, level and stack aligned, no blocker |
| 70–84 | Good match, 1–2 minor gaps |
| 50–69 | Partial; relevant gaps |
| < 50 | Not a fit, or a hard blocker (e.g. work authorization the candidate cannot meet) |

## 5. Selection

After scoring, per posting:
- `score < score_threshold` (default 75) → `below_threshold` (kept in case the threshold is lowered).
- `score ≥ threshold` → ranked by score; the top `tailoring.max_packages_per_day` (default 10) become `selected`, the rest stay `scored` for the next day.
- A posting whose `verdict` is `skip` is `below_threshold` regardless of score.

## 6. Token savings

- Cache keyed by `(content_hash, profile_hash, prompt_version)`: already-scored postings are never re-scored.
- Batching, description truncation, strict JSON output, small `max_tokens`.
- Only postings that passed the hard filter reach the LLM.
- Optional (API backend): Batch API (`scoring.use_batch`) for −50% cost.

## 7. Calibration

`jobhunter calibrate`: shows 20 scored postings (score, verdict, reason) and asks the person 👍/👎 (`y/n`). Answers are stored in a `calibration` table to tune the rubric and threshold. It never changes code or config automatically.

## 8. Tests

- Fake backend (no subprocess, no network): valid batch, missing id, invalid JSON (one retry with the error), out-of-range score.
- `ClaudeCliBackend` with a fake `claude` executable: command-line flags, environment sanitized, both output shapes parsed, non-zero exit and usage-limit handling.
- Cache test: second run with the same inputs → 0 calls.
- Budget test: exceeding `max_llm_calls_per_run` stops cleanly and leaves postings pending.
- Truncation test; selection test (threshold, top-N, `skip` verdict).

## 9. Acceptance criteria

- [x] Scoring 238 postings takes ≤ 40 LLM calls at the default batch size (≈ 30 calls, ~11 s each).
- [x] 100% of responses pass validation or leave the posting retryable (`score_failed`).
- [x] Re-running makes no calls for already-scored postings; stale scores (CV, context, criteria or prompt changed) are re-scored.
- [x] Postings that explicitly require local work authorization / residency / a time zone the candidate lacks are flagged in `red_flags`.
- [ ] (needs the author's `calibrate` answers; not measured yet) In calibration, ≥ 80% of postings with `verdict=apply` receive a 👍 from the person.
