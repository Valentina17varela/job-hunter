# 22 — Always five best matches: replace what you hide or dislike

**Status:** DONE

## 1. Problem

*Best matches* (Job matches tab, and Home's "Matches worth a look") shows postings with status `selected` or `packaged`: scored at or above `scoring.score_threshold` (75) and within `tailoring.max_packages_per_day`. When the person hides one (*Hide*, status `ignored`) or applies to it, the list simply gets shorter; with 3 left, nothing brings it back to 5 until a new search and scoring run happens to produce more. The author wants **at least five good postings in front of them at all times**: hide or reject one, and the next-best candidate takes its place, evaluating more postings if there are not enough already scored.

## 2. Constraints from the project principles

- **Manual only** (roadmap decision 4): nothing runs in the background. Scoring costs LLM calls, so "re-evaluate" cannot silently start by itself after a click.
- **Bounded cost:** every LLM call counts against `budget.max_llm_calls_per_run` / `daily_budget_usd`.
- **Honest scores:** a posting below the threshold is not "a match"; if the only candidates left are weaker, the UI says so instead of padding the list silently.

## 3. Proposed design

### 3.1 A "Top 5" board
- A fixed-size section at the top of *Best matches* and on Home: **the five highest-scored open postings** the person has not dismissed, by score, **above the threshold first, then (clearly labelled "below your threshold") the best of the rest** when fewer than five reach it. Status filter: scored postings that are not `ignored`, `rejected`, `closed`, `duplicate` and have no application.
- Hiding, disliking or applying to one removes it and **the next-best scored posting moves up immediately** (same page, no run needed); the hide notice offers *Score replacements* when fewer than five scored candidates are left. This part is pure ranking over data already scored: free and instant.
- `top_matches_count` in config (default 5, editable in Settings → AI & documents).

### 3.2 "Not for me" (dislike) next to *Hide*
- *Hide* = I'm not interested right now; *Not for me* = a signal, with an optional one-click reason: *wrong role*, *location/visa*, *pay*, *company*, *seniority*, *other*. Stored in the existing `events` (or a small `feedback` table), status becomes `ignored` as with Hide.
- *Company* offers *Block this company* (spec 11) in the same dialog.
- The reasons are only **recorded and counted** in this spec. Using them to adjust filters or the scoring prompt is a separate, later task (it changes scores, so it needs its own spec); the Settings page can show "You marked 6 postings as *location*: tighten `locations_allowed`?" as a suggestion only.

### 3.3 Filling the board when there are not enough scored postings
When fewer than five scored candidates remain, the board shows a card: **"Only 3 of 5 matches. Score 8 more postings?"** with a button that runs the existing score stage for exactly the next batch (no new LLM logic):
- Candidates = postings in status `passed` (they met the hard criteria but have no score yet) and `score_failed`, ordered by a **free, deterministic pre-rank** so the LLM budget goes to the likeliest: number of `keywords_include` hits, title match strength, salary published and above the minimum, posted most recently, favorite or manual first.
- The button asks for **at most `needed × 2`** postings (so that, after scoring, enough clear the threshold), capped by the per-run call limit; the dry-run shows how many calls it will use, as every LLM stage does.
- It is a **person-started** run (or `jobhunter top --fill`), never automatic. The result is reported: "Scored 8, 2 reached your threshold, Top 5 is complete" or "Still 4 of 5: no more unscored postings; run Search for new jobs".
- If there are no `passed` postings left either, the card offers *Search for new jobs* (and notes that The Muse/other sources may add more) and *Loosen a rule* (links to the rule that rejected the most postings, from the Home "why postings were left out" data).

### 3.4 CLI
`jobhunter top [--count N] [--fill]`: prints the board; `--fill` scores the next candidates as above (`--dry-run` supported).

## 4. Data and code touched

- `applications.ignore` accepts a reason; an `events` row stores it (no migration if kept in `events.detail`; a `feedback` table only if the reasons feed later analysis).
- A `top_matches(conn, cfg, n)` query/ranking in `scoring.py` (or a new `top.py`), a `prerank(job)` function (pure, tested), and `score_stage(job_ids=...)` (already exists, spec 10) for the fill.
- UI: the Top 5 section, the dislike dialog, the fill card; Home's KPI "Matches worth a look" becomes "Top matches".
- `config.example.yaml`: `top_matches_count`.

## 5. Tests

- Ranking: above-threshold first, then labelled below-threshold ones; excludes ignored/closed/duplicate/applied; ties stable.
- Hide/dislike removes one and the next moves up; counts always `min(n, available)`.
- Pre-rank is deterministic and favors keyword hits, salary, recency; fill selects the right ids and never exceeds the call cap; dry-run makes no LLM call; a fake backend scores them and the board refills.
- Nothing runs without the person starting it (no code path calls score from a hide/dislike endpoint).
- UI: the card text for 3/5, 0 candidates left, below-threshold labelling; reasons are escaped.

## 6. Decisions (answered by the author)

1. **Below-threshold padding: yes.** When fewer than five reach the threshold, the board is completed with the best of the rest, clearly labelled *below your threshold*, with the "score more / loosen a rule" card on top.
2. **Re-evaluation trigger: a notice when hiding.** Hiding or rejecting a posting shows a notice ("Hidden. Score N replacements?") with a button that starts the fill run; the card on the board does the same. Still person-started, never automatic.
3. **Reasons only suggest.** *Not for me* reasons are recorded and counted; they never change filters or the scoring prompt on their own, they only show suggestions.
4. **Applying removes it from the Top 5** and the next-best takes its place.

## 7. Tasks

- [x] Author answers §6.
- [x] `top.py`: `top_matches` ranking, `prerank`, `fill_candidates`, `plan`, reasons and suggestions (`tests/test_top.py`).
- [x] Top section on Job matches and a compact card on Home; *Not for me* dialog with reasons (radio chips, optional note); `applications.dismiss`; `GET /api/top`; the notice after hide / not-for-me / applied (`sessionStorage` flag, read-only plan request).
- [x] Fill: card and notice start the existing `score` run with the chosen ids; `jobhunter top --fill [--dry-run]`.
- [x] Config `scoring.top_matches_count` (1-20), Settings field, `config.example.yaml`.
- [x] README (UI, CLI), spec 07 and this spec marked done; screenshots refreshed.

## 8. Acceptance criteria

- [x] Hiding or rejecting a posting from the Top 5 immediately shows the next-best one when any is already scored (`test_hiding_one_promotes_the_next_best_immediately`).
- [x] When there are not enough scored postings, one person-started action scores the best unscored candidates and refills the board, within the configured call cap (`test_filling_scores_only_the_chosen_postings_and_refills_the_board`, `test_fill_never_exceeds_what_the_call_cap_can_score`).
- [x] No LLM call happens without the person pressing a button or running a command (`test_hiding_updates_the_plan_and_never_starts_a_run_by_itself`).
- [x] The UI never presents a below-threshold posting as an above-threshold match (`test_a_skip_verdict_is_never_presented_as_a_match_even_with_a_high_score`, the *below your threshold* label).

## 9. Deviations

- The Top board counts every scored, undismissed posting without an application (statuses `scored`, `selected`, `packaged`, `below_threshold`), not only the `selected` ones, so the *Best matches* tab list below it can show fewer rows than the board.
- The *Hide* button keeps its confirmation; the notice with the replacement offer appears on the next page load (it needs the fresh plan from `GET /api/top`).
- Reason suggestions need 3 dismissals with the same reason (`SUGGESTION_MIN`).
