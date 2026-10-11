# 14 — New sources with free API keys (The Muse first)

**Status:** PLANNED (spec only, not implemented)

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

- [ ] `sources/themuse.py` adapter, config model, registry entry, fixture + tests.
- [ ] Rate-limit awareness in `HttpClient` (expose response headers) and early-stop.
- [ ] Credential redaction in `HttpClient`/`fetch_log` + tests; `doctor` and Settings "key set / not set".
- [ ] Optional seniority hint from `levels`.
- [ ] Real run: compare matches from The Muse against existing sources and record the findings in this spec.
- [ ] Adzuna and Jooble adapters (after keys exist), then update this spec with the verified facts.
- [ ] README (sources table, env vars, config) and this spec marked done.

## 7. Acceptance criteria

- [ ] `jobhunter run --stage search` includes The Muse and finishes within its keyless hourly limit.
- [ ] Without any key the tool still works; with a key set the key never appears anywhere visible.
- [ ] A decision recorded here: does The Muse add enough new matches to keep it enabled?
