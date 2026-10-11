# 13 — Market insights (analytics)

**Status:** PLANNED (spec only, not implemented)

## 1. Problem

The tool collects tens of thousands of postings and throws most of them away. That pile is also a map of what the market asks for right now. Today the person cannot see which technologies keep showing up, which of them their CV lacks, or what they are missing because of a rule (for example location).

## 2. Goal

An **Insights** page (and `jobhunter insights`) that answers, from the person's own data and with no LLM required:

1. **What does the market ask for?** Top technologies/skills across the collected postings, by cohort.
2. **How do I compare?** Skills frequently requested in my matches that are **not in my CV** (learning priorities), and CV skills that almost nobody asks for.
3. **What is changing?** Which skills are rising or falling week over week.
4. **What am I leaving on the table?** How many strong-fit postings are discarded by a single rule (e.g. only because of location or a title word), so the person can decide whether to loosen it.
5. **Pay, companies and sources:** salary ranges where published, who hires the most, which source produces the best matches.

## 3. Skill extraction (deterministic)

- A versioned vocabulary `skills.py` (~300 terms) with aliases and categories: language, framework, database, cloud, devops, data/AI, practice (e.g. `golang`≡`go`≡`go (language)`, `postgres`≡`postgresql`, `k8s`≡`kubernetes`, `node.js`≡`nodejs`, `typescript`≡`ts`).
- Matching on word boundaries over title + description. **Ambiguous terms** (`go`, `r`, `c`, `rust` as a word, `swift`, `spark`, `express`, `react` as a verb) use case-sensitive and context rules (e.g. `Go` only next to a language cue such as "Golang", "Go,", "Go (", "in Go", or in the title) and are listed in the spec so false positives are testable.
- Result per posting stored in `job_skills(job_id, content_hash, skill)`; recomputed only when the content hash or the vocabulary version changes. Extraction of 25,000 postings must take under 5 s cold and be instant afterwards.
- The CV skills come from the same extraction over the plain text of the marked CV items (never the header).

## 4. Cohorts and filters

Every metric can be computed for a **cohort** and a **window**:

| Cohort | Meaning |
|---|---|
| `market` | Every posting collected (all sources, regardless of status) |
| `passed` | Passed the hard filter |
| `matches` | Best matches (`selected`, `packaged`, applied...) |
| `filtered` | Rejected by the hard filter (optionally by rule) |
| `favorites` / `applied` | Postings the person starred / applied to |

Window: last 30 / 90 days / all, by `posted_at` (falling back to `fetched_at`). Optional filter by source and by seniority.

## 5. Metrics

1. **Demand:** for each skill, `share = postings mentioning it / postings in the cohort` and count; top N with category chips.
2. **Gap table** (cohort `matches` by default): skill, demand %, *in my CV?*, *in my skills section?*, and an **opportunity score** = demand % when missing from the CV. Sorted by opportunity; a second list shows CV skills with demand < 2% ("rarely requested").
3. **Trend:** share per ISO week for the selected skills; shown as a sparkline and a ▲/▼ delta over the last 4 weeks vs the previous 4. Needs at least 4 weeks of history; otherwise the page says how much data exists ("1 week of data so far").
4. **Single-rule rejections:** `JobFilter.evaluate_all` (new) returns *every* failed rule instead of stopping at the first. A posting that fails **exactly one** rule while matching role and technologies is an "almost match"; the page shows counts per rule and examples ("1,240 postings would pass if locations also accepted US contractors"). This is the answer to *what am I discarding*.
5. **Salary:** median and 25/75th percentiles of published annual USD (using the configured FX table) per cohort and per top skill; hidden when fewer than 10 postings have a salary.
6. **Companies and sources:** companies with the most matches; per source: postings found, passed, matches, and match rate.
7. **Optional market brief:** a button asks the LLM (one call, off by default, counted in the budget) to write a short plain-language summary **from the computed tables only**; it must not add numbers that are not in the input (verification: every number in the summary appears in the tables).

## 6. UI and CLI

- Page `/insights` with a cohort selector, window selector and source filter; sections: *What the market asks for*, *Your gaps*, *What is rising*, *What you are discarding*, *Pay*, *Companies and sources*. Charts are inline SVG/CSS bars (no external library, works offline); every chart has a table fallback and states its sample size.
- CLI: `jobhunter insights [--cohort matches] [--days 90] [--top 20] [--json]`.
- Home gets one line linking to it ("Python appears in 71% of your matches; Kubernetes is in 38% and not in your CV").

## 7. Caveats shown to the person

Keyword counting is not understanding: counts reflect mentions, not importance; aggregator descriptions are short, so shares are lower there; the data only covers the postings this tool has collected with the filters in use, so it is a view of *your* market, not the whole market. The page says this once, briefly.

## 8. Tests

- Vocabulary: alias table, ambiguous-term cases (`Go` vs "go to market", `R` vs "R&D", `C` vs "C-level"), word boundaries.
- Cache: unchanged postings are not re-extracted; vocabulary version bump recomputes.
- Metrics on a fixture of ~50 postings: shares, gap list order, trend deltas with weekly buckets, percentile math, hidden-when-small rules.
- `evaluate_all` equals the first-failure result for the first rule and lists the others; single-rule rejection counts.
- Brief verification rejects invented numbers; UI renders with empty and populated data; performance test (generated 25k rows) stays within the bounds.

## 9. Tasks

- [ ] `skills.py` vocabulary + extractor + tests.
- [ ] Migration: `job_skills`; incremental extraction in the fetch/filter stages (or lazily on first visit).
- [ ] `JobFilter.evaluate_all` and single-rule counting.
- [ ] `insights.py` (cohorts, demand, gaps, trends, salary, companies/sources) + CLI.
- [ ] UI page with SVG bars and sample-size notes; Home line.
- [ ] Optional LLM market brief with number verification.
- [ ] README and this spec marked done.

## 10. Acceptance criteria

- [ ] The page lists the skills requested by the matches that are missing from the CV, with percentages and sample sizes.
- [ ] The page shows how many postings fail only one rule, per rule.
- [ ] Everything works offline and without any LLM call (the brief is optional).
