# 04 — Filtering (hard filter, 0 tokens)

Goal: drop the obvious with deterministic rules before spending a single token.

## 1. Criteria in `config.yaml`

```yaml
search:
  titles_include: ["backend", "software engineer", "platform"]   # at least one (title match)
  titles_exclude: ["intern", "junior", "manager", "director"]
  keywords_include: ["python", "typescript"]                      # optional; at least one in description
  keywords_exclude: ["security clearance", "us citizen only"]
  seniority: ["mid", "senior"]
  work_mode: ["remote"]                  # remote | hybrid | onsite
  locations_allowed: ["Colombia", "LATAM", "Worldwide", "Anywhere"]
  salary:
    min_usd: 0                           # ← filled in with the person
    on_missing: "pass"                   # pass | reject
  max_age_days: 30
```

## 2. Evaluation order

Evaluated in order, stopping at the first failure and storing `filter_reason`:

1. `max_age_days`
2. `titles_exclude`
3. `titles_include`
4. `seniority` (inferred from the title: `senior`, `staff`, `lead`, `jr`, etc.)
5. `work_mode`
6. `locations_allowed` (for remote: looks for restrictions like "US only", "EU only" in location and description)
7. `keywords_exclude`
8. `keywords_include`
9. `salary.min_usd` (if no salary, apply `on_missing`)

## 3. Inference

- **Remote:** the words `remote`, `anywhere`, `distributed` in location/title → `remote`; `hybrid` → `hybrid`; a city with no marker → `onsite`; empty → `unknown` (treated per `work_mode`: passes with an `unknown_mode` flag so the LLM can judge it).
- **Geographic restriction:** regex over common patterns (`US only`, `must be located in`, `EU timezone`) → `reject` if it doesn't match `locations_allowed`.
- **Currency:** conversion to USD with a fixed rate table in `config.yaml` (manual updates), enough for filtering.

## 4. Explainability

`jobhunter explain <job_id>` prints which rule dropped a posting and what text it matched. This lets the filter be tuned without guessing.

## 5. Tests

- Parametrized pytest table of cases `(job, config) → (passed|filtered, reason)`.
- Edge cases: missing salary, location "Remote - US", title "Senior Engineering Manager" (excluded by manager), different currency.

## 6. Acceptance criteria

- [ ] 100% deterministic: same input → same result.
- [ ] Every `filtered` posting has a non-empty `filter_reason`.
- [ ] Changing criteria and running `jobhunter refilter` re-evaluates without re-downloading.
- [ ] The filter processes 5,000 postings in < 2 s.
