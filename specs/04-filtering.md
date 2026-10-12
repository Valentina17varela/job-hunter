# 04 — Filtering (hard filter, 0 tokens)

Goal: drop the obvious with deterministic rules before spending a single token.

## 1. Criteria in `config.yaml`

```yaml
search:
  titles_include: ["backend", "software engineer", "platform"]   # at least one (title match)
  titles_exclude: ["intern", "junior", "manager", "director"]
  keywords_include: ["python", "typescript"]                      # optional; at least one in description
  keywords_exclude: ["security clearance", "us citizen only"]
  companies_exclude: []                  # block list, whole company names
  seniority: ["mid", "senior"]
  work_mode: ["remote"]                  # remote | hybrid | onsite
  locations_allowed: ["Colombia", "LATAM", "Worldwide", "Anywhere"]
  salary:
    min_usd: 0                           # ← filled in with the person
    on_missing: "pass"                   # pass | reject
  max_age_days: 30                       # aggregators only (dated feeds)
  max_age_days_ats: null                 # company boards; null = no limit
```

## 2. Evaluation order

Evaluated in order, stopping at the first failure and storing `filter_reason`:

1. Age: `max_age_days` for aggregator postings, `max_age_days_ats` for Greenhouse/Lever/Ashby ones (default: none — a posting still listed on a company board is open however old its first-publish date; on real data 65% of ATS postings were older than 30 days). Unknown posting date passes
2. `companies_exclude` — block list (normalized whole-name equality, spec 11)
3. `titles_exclude`
4. `titles_include`
5. `seniority` — one of `junior`, `mid`, `senior`, `lead`, inferred from the title: `staff|principal|lead|head of|architect` → lead (checked first), `senior|sr` → senior, `junior|jr|entry level|graduate|intern|trainee` → junior, no marker → mid
6. `work_mode`
7. `locations_allowed` (for remote: looks for restrictions like "US only", "EU only" in location and description)
8. `keywords_exclude`
9. `keywords_include`
10. `salary.min_usd` (if no salary, apply `on_missing`)

## 3. Inference

- **Remote:** the words `remote`, `anywhere`, `distributed` in location/title → `remote`; `hybrid` → `hybrid`; a city with no marker → `onsite`; empty → `unknown` (treated per `work_mode`: passes with an `unknown_mode` flag so the LLM can judge it).
- **Geographic restriction:** regex over common patterns (`US only`, `must be located in`, `EU timezone`) → `reject` if it doesn't match `locations_allowed`.
- **Currency:** conversion to USD with a fixed rate table in `config.yaml` (manual updates), enough for filtering.

### Implementation notes

- Terms match on **word boundaries**, case-insensitive: `intern` does not match "Internal".
- A non-generic location ("Remote - US", "Seattle") must contain an allowed term (`latam` also matches "latin america"). Generic ones ("Remote", "Worldwide", "Anywhere in the World") pass unless the description restricts the location ("US only", "must be located in the United States", "EU time zones") **and** no allowed place is mentioned next to the restriction. Acronyms (`US`, `EU`) are case-sensitive so "contact us only…" is not a restriction; "US-based startup" is not a restriction either.
- Place tokens: `latam`↔`latin america`, `us`→`u.s.`, `usa`→`united states`, `uk`→`united kingdom` are aliases. Short all-caps tokens (`US`, `UK`) match case-sensitively.
- Salary is compared on the **upper bound** of the range (`salary_max`, else `salary_min`) in USD. Unknown currency → pass with flag `unknown_currency`.
- Non-blocking observations are stored in `jobs.filter_flags` for the scoring stage: `unknown_mode`, `unknown_location`, `no_salary`, `unknown_currency`.
- Statuses: `new` → `filtered` | `passed`. `refilter` also re-evaluates `filtered`, `passed`, `score_failed`, `below_threshold`, `scored` and `selected`; a posting that still passes keeps its later-stage status (a package is never discarded by a re-filter). `applied`/`replied`/`rejected`/`closed`/`duplicate` are never touched. `run --stage filter` only evaluates `new` postings.
- Rejection reasons look like `rule: detail`, so a run summary can show how many postings each rule rejected — the quickest way to tune criteria.

## 4. Explainability

`jobhunter explain <job_id>` prints which rule dropped a posting and what text it matched. This lets the filter be tuned without guessing.

## 5. Tests

- Parametrized pytest table of cases `(job, config) → (passed|filtered, reason)`.
- Edge cases: missing salary, location "Remote - US", title "Senior Engineering Manager" (excluded by manager), different currency.

## 6. Acceptance criteria

- [x] 100% deterministic: same input → same result.
- [x] Every `filtered` posting has a non-empty `filter_reason`.
- [x] Changing criteria and running `jobhunter refilter` re-evaluates without re-downloading.
- [x] The filter processes 5,000 postings in < 2 s.
