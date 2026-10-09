# 05 — Scoring (cheap LLM)

Goal: of the postings that passed the filter, estimate how good a match each is, at the lowest possible cost.

## 1. Model and input

- Default model: `claude-haiku-5-5` (configurable).
- Input per posting: **profile summary** (cached) + title + company + description truncated to `max_description_tokens` (default 1,500).
- A `profile_summary` derived from the plain text of `config/cv/master.tex` items (never the preamble/header) is used (~300 tokens: role, years, stack, key achievements, preferences). It is generated once and regenerated only when `master.tex` changes (by hash). Preferences not present in the CV come from `search` in `config.yaml`.

## 2. Prompt structure

```
[system, cached]  rules + rubric + profile_summary
[user]            posting
```

Stable prefix → prompt caching. Only the posting varies.

## 3. Output (strict JSON, validated with pydantic)

```json
{
  "score": 0-100,
  "must_have_match": ["python", "aws"],
  "gaps": ["kubernetes"],
  "red_flags": ["24/7 on-call"],
  "verdict": "apply | maybe | skip",
  "reason": "max 40 words"
}
```

No free text outside the JSON. Low `max_tokens` (~200).

## 4. Rubric

| Range | Meaning |
|---|---|
| 85–100 | Meets almost all key requirements, level and stack aligned |
| 70–84 | Good match, 1–2 minor gaps |
| 50–69 | Partial; relevant gaps |
| < 50 | Not a fit |

The rubric lives in the prompt so scores are comparable across postings.

## 5. Selection

`selected` = postings with `score ≥ score_threshold` (default 75), sorted by score, limited to `max_packages_per_day` (default 10). The rest become `below_threshold` (kept in case the threshold is lowered).

## 6. Token savings

- Cache keyed by `(content_hash, profile_hash, prompt_version)`: already-scored postings are not re-scored.
- Description truncation: the requirements/responsibilities section is prioritized (header heuristic) before cutting.
- Optional Batch API (`scoring.use_batch: true`): −50% cost, asynchronous result. Useful for the nightly run.
- Optional pre-ranking with local embeddings if volume exceeds ~500 postings/day (not v1).

## 7. Calibration

`jobhunter calibrate`: takes 20 postings, shows the LLM score and asks the person for a 👍/👎. Saved as a dataset to tune the rubric and threshold. It does not change code automatically.

## 8. Tests

- Mocked LLM: valid responses, invalid JSON (retry), out-of-range score.
- Cache test: second run with the same inputs → 0 calls.
- Budget test: exceeding `daily_budget_usd` stops and leaves postings pending.

## 9. Acceptance criteria

- [ ] Average cost per scored posting < USD 0.002 (with caching).
- [ ] 100% of responses pass validation or end up `score_failed`.
- [ ] Re-running makes no calls for already-scored postings.
- [ ] In calibration, ≥ 80% of postings with `verdict=apply` receive a 👍 from the person.
