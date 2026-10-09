# 03 — Sources

Only sources with a **documented public API or feed**. No login, no browser.

## 1. Per-company ATS (`companies.yaml`)

```yaml
companies:
  - name: Stripe
    ats: greenhouse
    slug: stripe
  - name: Linear
    ats: ashby
    slug: linear
  - name: Netflix
    ats: lever
    slug: netflix
```

| ATS | Endpoint | Notes |
|---|---|---|
| Greenhouse | `GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | `content=true` returns the description |
| Lever | `GET https://api.lever.co/v0/postings/{slug}?mode=json` | |
| Ashby | `GET https://api.ashbyhq.com/posting-api/job-board/{slug}` | |

Later phase (not v1): Workable, Recruitee, SmartRecruiters.

## 2. Aggregators

| Source | Access |
|---|---|
| RemoteOK | `https://remoteok.com/api` (JSON; include attribution/UA per their terms) |
| We Work Remotely | RSS per category |
| Remotive | `https://remotive.com/api/remote-jobs` |

Later phase: Himalayas, GetOnBoard, Torre, HN "Who is hiring".

## 3. Good-citizen rules

- Identifiable `User-Agent` (`jobhunter/0.1 (personal use)`).
- 15 s timeout, max 3 retries with backoff.
- Limited concurrency (max 5 simultaneous requests, max 2 per host).
- One full run per day; no aggressive polling.
- Respect `robots.txt` and each aggregator's terms. If a source forbids automated use, it is removed.
- HTTP caching with `ETag`/`If-Modified-Since` where available.

## 4. Normalization

Each source implements `fetch()` → `list[Job]` and is responsible for:

- Cleaning HTML to plain text (`selectolax` or `html2text`).
- Inferring `remote` from location/title/description (simple rules, see 04).
- Extracting salary when structured (Ashby/Lever sometimes include it); otherwise try a regex over the description; otherwise `None` (the filter decides what to do, see 04).

## 5. Company discovery

`companies.yaml` starts with a seed (~50 tech companies). The helper command `jobhunter companies check` validates each slug (200 vs 404) and reports broken ones, without touching the pipeline.

## 6. Tests

- One real (trimmed) JSON fixture per source in `tests/fixtures/`.
- Tests with `respx`: correct parsing, missing fields, 404, invalid JSON, HTML with odd characters.
- No test makes real network requests.

## 7. Acceptance criteria

- [ ] Given one fixture per ATS, `fetch()` returns valid `Job`s.
- [ ] A 404 for one company does not interrupt the others and is recorded in `fetch_log`.
- [ ] Re-running `fetch` creates no duplicates.
- [ ] A posting that disappears for 7 days becomes `closed`.
