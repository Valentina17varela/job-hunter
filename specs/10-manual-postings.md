# 10 — Add a posting by hand

**Status:** DONE

## 1. Problem

The sources only see public job boards. Many good opportunities come from elsewhere: a LinkedIn post, a referral, a newsletter, a company careers page that is not on Greenhouse/Lever/Ashby. Today those can only be tracked by hand, without scoring, a tailored CV or a cover letter.

## 2. Goal

The person pastes a **URL and/or the posting text**, reviews the extracted fields, and the posting enters the normal pipeline: score → package → application tracking. Nothing is fetched or sent behind the person's back.

## 3. User flow

1. **Add posting** button on *Job matches* (and Home). A dialog asks for:
   - **URL** (optional) with a *Fetch details* button,
   - **Title**, **Company** (required), **Location**, **Work mode** (remote/hybrid/onsite/unknown), **Salary** (optional, annual amount + currency),
   - **Description** (required, plain text; the text of the posting).
2. *Fetch details* makes **one** request to the URL (see §5) and pre-fills the fields. The person always reviews and edits before saving (human in the loop).
3. On save the posting is stored with `source = manual` and opens its detail page with two buttons: **Score with AI** (this posting only) and **Build package**.
4. The same posting can also be added from the CLI: `jobhunter add --title T --company C [--url U] [--location L] [--salary-min N --salary-max N --currency USD] (--text-file F | --text -)  [--score] [--package]`.

## 4. Data and pipeline rules

- `Job.source = "manual"`, `external_id = sha256(normalized url or title|company|description)[:16]`. Adding the same URL/text twice updates the existing row instead of duplicating it.
- **Manual postings skip the hard filter**: the person chose it on purpose. They get status `passed` with the filter flag `manual`. Changing their text later does **not** send them back through the filter (the upsert rule "content changed → `new`" is overridden for `manual`).
- Scoring and tailoring treat them like any other posting (batching, cache by content hash, verification). The scoring prompt receives the flag `manual` and must not penalize a missing salary or location.
- They appear in all lists with a *Manual* badge; `refilter` never touches them; `closed` is never set automatically (there is no source to disappear from).
- If the company is on the block list (spec 11), the dialog shows a warning but still allows saving.

## 5. Fetching a URL safely

The server makes the request, so it must not become a way to reach internal services (SSRF):

- Only `http`/`https`; host resolved before connecting; **reject loopback, private, link-local and multicast addresses** (also after redirects, max 3); no credentials in URLs.
- Timeout 10 s, response limit 2 MB, `User-Agent: jobhunter/0.1 (personal use)`, no cookies, no JavaScript rendering, no crawling (a single GET).
- Extraction order: (1) `<script type="application/ld+json">` with `@type: JobPosting` (title, hiringOrganization, jobLocation, jobLocationType `TELECOMMUTE`, baseSalary, datePosted, description), (2) Open Graph/`<title>`, (3) readable text via the existing `html_to_text`.
- Sites that need a login or block bots (e.g. LinkedIn) will fail or return little: the dialog says so and the person pastes the text. No attempt to bypass blocks or captchas.
- The fetched text is untrusted data: it is stored and shown escaped, and it is never interpreted as instructions.

## 6. Interfaces

- `POST /api/postings/fetch {url}` → `{title, company, location, remote, description, salary_min, salary_max, currency, source_url}` or `{error}`.
- `POST /api/postings {fields}` → `{id}` (validates required fields, length limits: description ≤ 100 KB).
- CLI `jobhunter add ...` as in §3 (`--score` / `--package` run the stages for this id only).

## 7. Tests

- URL normalization and dedupe; same text twice → one row.
- Extraction fixtures: a page with JobPosting JSON-LD, a page with only `<title>`, a page with nothing useful.
- SSRF: `http://127.0.0.1`, `http://[::1]`, `http://10.x`, `http://169.254.169.254`, a public URL that redirects to a private one, `file://`, oversized and slow responses are all rejected (network mocked).
- A manual posting survives `refilter` and content edits as `passed`.
- UI: dialog validation and the two follow-up buttons.

## 8. Tasks

- [x] `postings.py`: normalization, id, upsert for `manual`; filter exemption.
- [x] `fetch_url.py`: safe fetcher + extractors + tests (network mocked).
- [x] API endpoints and CLI `add`.
- [x] UI dialog, *Manual* badge, follow-up buttons.
- [x] Scoring prompt: `manual` flag.
- [x] README (commands, UI, privacy note about the single fetch) and this spec marked done.

## 9. Acceptance criteria

- [x] A posting pasted as text can be scored and packaged without touching the filter.
- [x] A URL with JobPosting JSON-LD pre-fills title, company, location and salary.
- [x] No request is ever made to a private/loopback address.

## 10. Deviations from the plan

- The fetcher connects to the **resolved public IP** (pinned, with the original `Host` header and SNI), so a DNS answer cannot change between the check and the request. Only ports 80, 443, 8080 and 8443 are allowed; every redirect (max 3) is re-validated.
- Sites that need a login (LinkedIn) cannot be fetched; the dialog says so and the person pastes the text.
