# 03 — Sources

**Status:** LIVING (describes the system as it works today)

Only sources with a **documented public API or feed**. No login, no browser, no scraping of sites that forbid it.

> A new source is one module that registers itself in the source registry; see `docs/ADDING_A_SOURCE.md` and spec 19 §5.

## 1. Strategy: breadth first, depth second

The person wants **any posting that matches their criteria, regardless of company**. No free API lists every job on the web, so coverage comes from three layers. The hard filter (04) ignores the company entirely.

| Layer | What | Why |
|---|---|---|
| 1. Multi-company aggregators | Remotive, RemoteOK, We Work Remotely, Arbeitnow, Jobicy | One call returns postings from many companies; fastest to results |
| 2. Per-company ATS boards | Greenhouse, Lever, Ashby | Depth: thousands of companies publish here, often not mirrored on aggregators |
| 3. Self-growing company list | `jobhunter companies discover` | Replaces a hand-maintained company list |

Later: The Muse (works without a key), Adzuna and Jooble (need a personal free key) — see [14-new-sources-api-keys.md](14-new-sources-api-keys.md). Also later: Himalayas, GetOnBoard, Torre, HN "Who is hiring", Workable, Recruitee, SmartRecruiters.

## 2. Aggregators (`config.yaml → sources.aggregators`)

| Source | Endpoint | Notes |
|---|---|---|
| Remotive | `GET https://remotive.com/api/remote-jobs` | Terms: link back + attribution; do not republish to third-party job sites (personal use only) |
| RemoteOK | `GET https://remoteok.com/api` | First array element is a legal notice (skipped). Appends a per-request tracking tag to descriptions → stripped so content hashes stay stable. Some text is double-encoded (mojibake) → repaired. Terms: link back + attribution |
| We Work Remotely | RSS `https://weworkremotely.com/categories/{category}.rss` | Categories from `sources.wwr_categories`. Title format `Company: Role` |
| Arbeitnow | `GET https://www.arbeitnow.com/api/job-board-api?page=N` | `sources.arbeitnow_pages` pages (default 3), stops at an empty page |
| Jobicy | `GET https://jobicy.com/api/v2/remote-jobs?count=100` | Has structured salary. Asks for credit + link back; keep to ~once a day |

Every `Job.url` is the aggregator's own link, satisfying the link-back terms. The tool never republishes postings.

## 3. ATS boards (`companies.yaml`)

```yaml
companies:
  - name: Stripe
    ats: greenhouse
    slug: stripe
```

| ATS | Endpoint | Notes |
|---|---|---|
| Greenhouse | `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | Description is returned HTML-escaped (unescape, then clean). No structured salary → regex on text |
| Lever | `GET https://api.lever.co/v0/postings/{slug}?mode=json` | `workplaceType`, optional `salaryRange` (annualized from its interval) |
| Ashby | `GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` | `isRemote`/`workplaceType`, salary from compensation tiers; unlisted postings skipped |

## 4. Company discovery

- `config/company_candidates.txt` — plain list of company names (committed; public names only, any company the person likes can be added).
- `jobhunter companies discover` probes each unknown name against Greenhouse, Lever and Ashby using slug variants (`huggingface`, `hugging-face`) and adds boards that exist **and have at least one posting** to `companies.yaml`. Names without a public board are reported and ignored.
- `jobhunter companies check` re-validates every slug (200 vs 404) and exits non-zero if any is broken.
- A slug match is name-based, so a rare false match (a different company with the same slug) is possible; since filtering ignores the company, the cost is just some irrelevant postings.

## 5. Good-citizen rules

- Identifiable `User-Agent` (`jobhunter/0.1 (personal use)`).
- 15 s timeout, max 3 attempts with exponential backoff; retry only network errors, 429 and 5xx (404 fails immediately).
- Concurrency limits: max 5 simultaneous requests, max 2 per host (configurable).
- One full run per day; no aggressive polling.
- Respect each source's terms. If a source forbids automated use, it is removed.
- Deferred: conditional requests (`ETag`/`If-Modified-Since`); not needed at current volumes (~25k postings in ~35 s).

## 6. Normalization

A source implements `async fetch(http) -> list[Job]` and raises on failure. It is responsible for:

- Cleaning HTML to plain text with the stdlib `html.parser` (no extra dependency), keeping list bullets and paragraph breaks, and normalizing whitespace (no-break spaces, blank-line runs).
- Inferring `remote` from short fields only (location, title, structured workplace type) — never from the description, which mentions "remote" incidentally.
- Salary: structured fields when present (annualized from hour/month/year); otherwise a conservative regex over the description that needs a currency marker and a plausible annual value (so "2-5 years" is never a salary). Missing → `None` (the filter decides what to do, see 04). Currency is kept as found; USD conversion happens in the filter using the configured FX table.
- **Robust parsing:** a malformed item is skipped; it never discards the rest of a feed.

## 7. Pipeline behaviour (fetch stage)

- All sources run concurrently under the client's limits. A failing source (network, 404, invalid JSON/RSS) is recorded in `fetch_log` with its error and does **not** stop the others.
- The same posting appearing twice in one run (several feeds/pages) is stored once.
- Upsert by `(source, external_id)`: new → `new`; same content → only `last_seen_at` refreshed; changed content → description updated and status reset to `new` (filter/score re-evaluated), except human statuses (`applied`, `replied`, `rejected`), which are kept; a `closed` posting that reappears becomes `new`.
- Postings not seen for `sources.stale_days` (default 7) become `closed`, **only for source kinds fetched successfully in this run** (an outage never closes everything).
- Cross-source copies (same normalized company + title in different sources) are marked `duplicate`, keeping the direct-ATS posting.

## 8. Tests

- One real (trimmed) fixture per source in `tests/fixtures/`.
- `respx`-mocked tests: parsing, missing fields, malformed items, 404, 5xx retries, invalid JSON/RSS, pagination, endpoints/params.
- Store and pipeline tests with an in-memory/temp SQLite: dedupe, content change, closing, duplicates, failure isolation.
- No test makes real network requests.

## 9. Acceptance criteria

- [x] Given one fixture per source, `fetch()` returns valid `Job`s.
- [x] A 404 in one source does not interrupt the others and is recorded in `fetch_log`.
- [x] Re-running fetch creates no duplicates and reports 0 new / 0 updated for unchanged feeds (verified against the live APIs: 25,069 postings, second run 0 new / 0 updated).
- [x] A posting that disappears for 7 days becomes `closed`.
- [x] `companies discover` and `companies check` work against the live APIs (196 boards found from 332 candidate names).
