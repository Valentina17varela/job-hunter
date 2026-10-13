# 14 — New sources with free API keys (The Muse first)

**Status:** IN PROGRESS (The Muse, Get on Board, Himalayas and the key handling are done; Adzuna, Jooble and the other keyless sources of §7 are not)

## 1. Goal

Widen coverage beyond company boards and remote-only aggregators, especially for LATAM-friendly roles. **The Muse** is first because it is free, documented and needs no key to start; **Adzuna** and **Jooble** follow once the multi-key design is proven with The Muse.

## 2. The Muse (verified against the live API, 2026-10)

- Endpoint: `GET https://www.themuse.com/api/public/jobs?page=N&category=…&level=…&location=…` (pages start at 1, **20 results per page**, `page_count` in the response).
- **Works without an API key**: 500 requests/hour (headers `x-ratelimit-limit: 500`, `x-ratelimit-remaining`, `x-ratelimit-reset: 3600`). A free key (parameter `api_key`) raises the limit; it is optional.
- Useful filters: `category` (e.g. `Software Engineering`), `level` (`Mid Level`, `Senior Level`, repeatable), `location` (`Flexible / Remote` for remote roles). Measured: remote Software Engineering ≈ **850 postings = 43 pages** (mid+senior: 845), so a full fetch costs ~43 requests; adding `Data and Analytics` ≈ 35 more pages.
- Result item: `id`, `name` (title), `contents` (HTML description), `publication_date`, `locations[].name` (a remote role lists `Flexible / Remote`, sometimes plus real cities such as `Mexico City, Mexico`), `levels[].name/short_name`, `categories[].name`, `company{id,name,short_name}`, `refs.landing_page`, `tags`, `type`.
- Requests send an identifiable `User-Agent` (a request without one failed in testing).

### 2.1 Mapping to `Job`

| Muse | Job |
|---|---|
| `id` | `external_id` (string), `source = "themuse"` |
| `name` | `title` |
| `company.name` | `company` |
| `locations[].name` joined with `; ` | `location` |
| any location equal to `Flexible / Remote` | `remote = "remote"` (otherwise `infer_remote`) |
| `html_to_text(contents)` | `description` |
| `refs.landing_page` | `url` (kept for the link-back requirement) |
| `publication_date` | `posted_at` |
| salary | none published → existing regex over the description |

`levels` are kept as a **seniority hint** (`senior` ⇒ the filter may use it when the title has no marker; optional, specified in the task list).

### 2.2 Behaviour

- Config (all optional, defaults shown):
  ```yaml
  sources:
    aggregators: [remotive, remoteok, weworkremotely, arbeitnow, jobicy, themuse]
    themuse:
      categories: ["Software Engineering"]
      levels: ["Mid Level", "Senior Level"]
      locations: ["Flexible / Remote"]
      max_pages: 60            # per category, safety cap
  ```
- The fetch walks pages until `page_count` or `max_pages`, **stops early and cleanly** when `x-ratelimit-remaining` is low (< 20) and logs it in `fetch_log`; the next run continues normally (rows are upserted, nothing is lost).
- Remote roles with a restricted real location (`Flexible / Remote, Mexico City`) are not treated specially: the existing location rules and the scorer decide.
- Terms: the API asks for attribution/link back; every posting keeps `refs.landing_page` and the tool stays personal-use. To be re-checked against The Muse's current terms when implemented.

## 3. API keys: design that applies to every keyed source

- **Keys live only in environment variables**, never in `config.yaml`, the database, logs or the UI: `THEMUSE_API_KEY` (optional), `ADZUNA_APP_ID` + `ADZUNA_APP_KEY`, `JOOBLE_API_KEY`.
- A keyed source with a missing key is **skipped with a warning** (not an error); an optional key (The Muse) simply uses the keyless limit.
- `jobhunter doctor` and Settings → Sources show only **"set / not set"** per key (never the value) and a link to where the free key is requested.
- `HttpClient` **redacts credentials** (`api_key`, `app_id`, `app_key`, `key`, and keys embedded in paths such as Jooble's `/api/{key}`) from `FetchError` messages, `fetch_log` rows, logs and the run log shown in the UI. Tests assert a key never appears in any of them.
- The run subprocess inherits the environment (the keys are read there); the web UI never reads or displays them.

## 4. Adzuna and Jooble (to validate when the person has keys)

Not verifiable here (both answer 400/403 without credentials); the facts below come from their public documentation as remembered and **must be checked when implementing**:

- **Adzuna** — `GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}?app_id=…&app_key=…&results_per_page=50&what=…&where=…`. Supported countries include `br` and `mx` but **not Colombia**, so LATAM coverage would come through Brazil/Mexico and global remote postings. Free tier with request limits.
- **Jooble** — `POST https://jooble.org/api/{api_key}` with JSON `{keywords, location, page}`; documented as covering many countries, which would include Colombia. Returns snippets, so descriptions may be short and need a follow-up fetch (not planned) or a lower weight in scoring.
- Both follow the same adapter, key and rate-limit rules as The Muse; each gets its own fixture-based tests and config block.

## 5. Tests

- Fixtures with a trimmed real Muse response: parsing, `Flexible / Remote` mapping, missing fields, malformed item skipped.
- Pagination until `page_count`; `max_pages` cap; early stop on low `x-ratelimit-remaining`; 429 handling with the shared retry policy.
- Key handling: skipped-with-warning when missing, optional for The Muse, redaction in errors/logs/`fetch_log`/run log, `doctor` output.
- Integration with dedupe: the same job on The Muse and on a company board is marked duplicate (company board wins).

## 6. Tasks

- [x] `sources/themuse.py` adapter, `sources.themuse` config model (default on), registry entry, trimmed real fixture + tests (`tests/test_sources.py`, `tests/test_source_contract.py`).
- [x] Rate-limit awareness: the adapter reads `x-ratelimit-remaining` from the response headers and stops cleanly below 20 left, saying so in `fetch_log` (the `error` column of an `ok` row carries the note; nothing is lost, the next run continues); `max_pages` stop is noted the same way.
- [x] Credential redaction (`http.redact`, applied to every `FetchError`, the pipeline's error text and `fetch_log`); sources register the env names they read; `doctor` and Settings → Sources show "set / not set" only; a source with a required key is skipped with a warning (`tests/test_cli_doctor.py`, `tests/test_web.py`, `tests/test_sources.py`).
- [ ] Optional seniority hint from `levels`.
- [x] Real run (2026-10-12, temp workspace with the author's `search` criteria, no keys): 43 requests, ~15 s, **813 postings** (the live API had ~833 for remote Software Engineering, mid+senior). Findings below.
- [ ] Adzuna and Jooble adapters (after keys exist), then update this spec with the verified facts.
- [x] README (Sources section, env var, config) and generated `docs/SUPPORTED_SOURCES.md`.

### 6.1 Findings from the real run (The Muse, author's criteria)

- **0 of 813 pass the author's filter.** Rejected by: age 497 (`max_age_days: 30`), title not matching `titles_include` 183, `titles_exclude` 75, `locations_allowed` 34, seniority 24. Re-running the filter with **no age limit** still passes **0**: 479 titles do not match the wanted roles (the *Software Engineering* category includes hardware, security, systems and solutions roles), 185 hit `titles_exclude`, 103 name locations outside the allowed list, 46 fail seniority.
- **Dates are unreliable**: the median `publication_date` is 42 days old, 135 postings are over a year old (evergreen listings), so the age rule discards 61 % of the feed. They are not necessarily closed; whether to treat The Muse like a company board (open while listed, no age limit) is an open question.
- **Overlap**: about 10 % (78) of the postings also exist in the other sources (same normalized company and title) and are marked duplicate by the existing rule.
- Conclusion: The Muse is correct and cheap, but **adds little for this criteria set** (US-centred, many non-backend roles). It stays on by default because it costs one request per 20 postings and costs nothing otherwise; the person can switch it off in Settings → Sources. A narrower `categories` list (e.g. add *Data and Analytics*, drop none) or other sources (Get on Board, Himalayas) are likelier to help.

## Open question

- Should The Muse postings skip `max_age_days` (like company boards)? Left as is until the author decides.

## 7. More keyless sources (from reviewing career-ops)

*career-ops* lists about 55 provider modules; these are public, no-key feeds that fit our rules and our LATAM-friendly remote focus. **Endpoints and shapes are as reported by that project and must be verified live (trimmed fixture, terms, rate limits) when each adapter is written**, exactly as was done for The Muse in §2.

| Source | Type | Why it is interesting | Endpoint as reported |
|---|---|---|---|
| Get on Board | JSON:API | LATAM-heavy tech roles, salaries often published | **Built** (§7.1) |
| Himalayas | JSON | Remote-first, worldwide | **Built** (§7.1) |
| Landing.jobs | JSON | Tech, Europe, relocation | `https://landing.jobs/api/v1/jobs` |
| JustJoin.it | JSON | Polish/EU tech with salary ranges | `https://justjoin.it/api/candidate-api/offers` |
| 4 Day Week | JSON | Reduced-hours roles | `https://4dayweek.io/api/jobs` |
| Jobspresso | RSS | Curated remote | `https://jobspresso.co/?feed=job_feed` |
| CryptocurrencyJobs | RSS | Remote Web3 roles | `https://cryptocurrencyjobs.co/index.xml` |
| Hacker News "Who is hiring?" | Algolia API | Monthly thread, parsed comments | HN Algolia search for the current thread |

More **company-board ATS** (they register as `ats` values for `companies.yaml`, spec 19 §5): Workable, Recruitee, SmartRecruiters, BambooHR, Breezy HR, Jobvite. Each is a small adapter over a public per-company endpoint; same fixture-and-contract-test rules.

Order: The Muse (§2), Get on Board, Himalayas, then the rest by value after reading the real data. Each source is its own small task; none is added without checking its terms. Boards that answered with bot protection or were retired in the reviewed project are not attempted.

Task list additions: one task per adapter above; `docs/SUPPORTED_SOURCES.md` row and README sources table updated with each.

### 7.1 Get on Board and Himalayas (built, verified live 2026-10-13)

**Get on Board** — `GET https://www.getonbrd.com/api/v0/categories/{category}/jobs?per_page=100&page=N&expand=["company"]` (JSON:API; `meta.total_pages`; `per_page` up to 100 works; no rate-limit headers seen). Item: `id` (slug), `attributes{title, description/functions/desirable/benefits (+ *_headline), remote, remote_modality (`fully_remote`, `remote_local`, `hybrid`, `no_remote`), countries, min_salary, max_salary, published_at (epoch), lang, company.data.attributes.name}`, `links.public_url`.
- Mapping: `fully_remote`/`remote_local` → `remote`, `hybrid` → `hybrid`, `no_remote` → `onsite`; location is the country list, `Remote` for fully remote, `Remote, <countries>` or *Remote (specific countries)* for `remote_local`; description joins the headline and section texts; salary is **monthly USD** and is annualized (×12); `posted_at` from `published_at`.
- Config: `sources.getonboard.categories` (default `programming`, `sysadmin-devops-qa`), `max_pages` (10, 100 postings per page). Postings are often in Spanish.

**Himalayas** — the general feed `https://himalayas.app/jobs/api` has **125,000+** postings (cursor pagination), too many to fetch, so the adapter uses `GET https://himalayas.app/jobs/api/search?q=…&seniority=…&sort=recent&page=N` (20 per page, `limit` is ignored, `totalCount` capped at 5,000). **Only one `seniority` value is honoured per request** (a second one replaces the first), so each level is its own request set. No rate-limit headers seen.
- Item: `title, companyName, minSalary, maxSalary, salaryPeriod (annual|hourly), currency, seniority[], locationRestrictions[] (empty = worldwide), description, pubDate, expiryDate, applicationLink, guid`.
- Mapping: always `remote`; location is the restriction list or *Worldwide*; salary annualized by period and **dropped when no currency is given**; expired postings (`expiryDate` in the past) are skipped.
- Config: `sources.himalayas.queries` (default `software engineer`, `backend engineer`), `seniority` (`Mid-level`, `Senior`), `max_pages` (5 per query and level).

**Real run** (author's criteria, temp workspace, no keys): 4 source instances, ~30 requests, **732 postings in 8 s** (671 new after dedupe): Get on Board 416 (5 pass), Himalayas 255 (3 pass), **8 pass the filter in total** (The Muse: 0). Salary published in 36 % of Get on Board and 38 % of Himalayas postings. Overlap with the other sources: 1 posting. Rejections: age 259, title 236 + 59, location 86, work mode 14, seniority 6.
