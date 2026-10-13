# 22 — Always five best matches: replace what you hide or dislike

**Status:** PLANNED (spec only, not implemented; **needs the author's answers to the open questions before building**)

## 1. Problem

*Best matches* (Job matches tab, and Home's "Matches worth a look") shows postings with status `selected` or `packaged`: scored at or above `scoring.score_threshold` (75) and within `tailoring.max_packages_per_day`. When the person hides one (*Hide*, status `ignored`) or applies to it, the list simply gets shorter; with 3 left, nothing brings it back to 5 until a new search and scoring run happens to produce more. The author wants **at least five good postings in front of them at all times**: hide or reject one, and the next-best candidate takes its place, evaluating more postings if there are not enough already scored.

## 2. Constraints from the project principles

- **Manual only** (roadmap decision 4): nothing runs in the background. Scoring costs LLM calls, so "re-evaluate" cannot silently start by itself after a click.
- **Bounded cost:** every LLM call counts against `budget.max_llm_calls_per_run` / `daily_budget_usd`.
- **Honest scores:** a posting below the threshold is not "a match"; if the only candidates left are weaker, the UI says so instead of padding the list silently.

## 3. Proposed design

### 3.1 A "Top 5" board
- A fixed-size section at the top of *Best matches* and on Home: **the five highest-scored open postings** the person has not dismissed, by score, **above the threshold first, then (clearly labelled "below your threshold") the best of the rest** when fewer than five reach it. Status filter: scored postings that are not `ignored`, `rejected`, `closed`, `duplicate` and have no application.
- Hiding, disliking or applying to one removes it and **the next-best scored posting moves up immediately** (same page, no run needed). This part is pure ranking over data already scored: free and instant.
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

## 6. Open questions (author to answer)

1. **Below-threshold padding:** if only 3 postings reach 75, should the board show 2 weaker ones (labelled) to reach five, or show 3 and the "score more / loosen a rule" card? *Recommended: show them labelled, so you always have something to look at, with the card on top.*
2. **Automatic vs one click:** the fill needs LLM calls. Is *one click on the card* acceptable, or should hiding a posting offer "Score replacements?" right in the toast? (Both stay manual; the toast is just faster.) *Recommended: toast with a button, since you are already there.*
3. **Reasons for *Not for me*:** is the list in 3.2 right? Should a reason ever change the filters automatically (it would break "no silent changes"), or only suggest? *Recommended: suggest only.*
4. **Does *applied* count?** When you apply, should the posting leave the Top 5 (yes in this draft) and be replaced?

## 7. Tasks

- [ ] Author answers §6.
- [ ] `top_matches` ranking and `prerank`, with tests.
- [ ] Top 5 section (Job matches, Home) and the dislike dialog with reasons.
- [ ] Fill: card/toast, `jobhunter top --fill`, run-whitelist entry, tests with a fake backend.
- [ ] Config `top_matches_count` and the Settings field; `config.example.yaml`.
- [ ] README (UI, CLI, config) and this spec marked done.

## 8. Acceptance criteria

- [ ] Hiding or rejecting a posting from the Top 5 immediately shows the next-best one when any is already scored.
- [ ] When there are not enough scored postings, one person-started action scores the best unscored candidates and refills the board, within the configured call cap.
- [ ] No LLM call happens without the person pressing a button or running a command.
- [ ] The UI never presents a below-threshold posting as an above-threshold match.
