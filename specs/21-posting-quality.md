# 21 — Posting quality: ghost-job and scam signals, "still open?" check

**Status:** PLANNED (spec only, not implemented)

## 1. Problem

Some postings are never filled (evergreen or "ghost" jobs), some are reposted every few weeks, some are scams, and some closed days ago but still sit in an aggregator feed. The person spends a tailored package on them. *career-ops* (legitimacy check, `detect-reposts`, `--verify`) and *freehire* (ghost-job signal) both treat this as core; today we only close postings **not seen for 7 days** (03 §7).

Principle: **signals inform, they never delete.** Everything here is deterministic (no LLM), local, and shown as badges the person can ignore.

## 2. Quality signals (computed locally, stored as flags)

Each signal is a short code + a human sentence; none is a verdict on its own.

| Signal | Rule (starting point, tunable in code constants) |
|---|---|
| `old` | Listed for more than 45 days (from `posted_at`, else `fetched_at`, the first time we stored it; there is no `first_seen_at` column, only `fetched_at` and `last_seen_at`) and still open |
| `reposted` | Same normalized company + title (and similar description) seen under a **different external id** in the last 90 days, or the same posting re-appearing after being closed |
| `no_pay` | No salary and the company/board usually publishes one (only used as a soft hint, never alone) |
| `vague` | Description shorter than ~400 characters, or no responsibilities/requirements wording |
| `scam_wording` | Phrases such as paying for equipment/training, buying gift cards, crypto or wire payments, "WhatsApp/Telegram only" contact, "no experience, very high pay", a free-mail recruiter address |
| `mismatch_domain` | The apply link host has nothing to do with the company and is not a known ATS or aggregator (a cheap typo-squat hint) |
| `no_sponsorship` | Explicit "no visa sponsorship / must be authorized to work in …" wording; shown because it can contradict the person's `candidate_context` (also surfaced to the scorer's note) |

- Stored in a new column `jobs.quality_flags` (JSON list of codes) refreshed by the filter stage and `refilter`; never changes `status`.
- Manual postings (10) get the flags too (the person may paste a scam), but never `old`/`reposted`.
- UI: small amber/red badges on the card and a **"Before you apply"** box on the posting page listing the signals in plain language; Job matches gets a *Hide suspicious* toggle (off by default). Optional config `search.hide_flags: [scam_wording]` turns chosen signals into a hard-filter reason (`quality: …`), off by default.
- The scorer receives the flags in the per-posting block (not the system prompt, so cached scores stay valid for postings without flags).

## 3. "Is it still open?" check

- Button **Check it's still open** on the posting page, and an automatic check **right before building a package** (skippable with `--no-verify`), for postings that are not company-board API results seen in the last 24 h.
- One request to the posting URL through the **same SSRF-safe single-page fetcher** as spec 10 (public hosts only, size and time limits, no JavaScript). Closed when: HTTP 404/410, a redirect to a generic careers/home page, or known "no longer accepting applications / position has been filled / job expired" wording (list per language: en, es, pt, de, fr).
- Outcomes: *open*, *closed* (status → `closed`, event logged, favorites keep their star), *could not tell* (login wall, bot protection, JavaScript-only page: reported honestly, nothing changes).
- Never run in bulk and never in the background: it is per posting, by the person (principle 4 of the roadmap). A `jobhunter verify ID...` CLI command does the same for the ids given.
- Rate: at most one request per host every 2 seconds if several ids are given.

## 4. Tests

- Each signal on crafted postings, including the false-positive cases ("equipment is provided", a salary written in the text, a short but complete description).
- Repost detection across different external ids and after close/reopen; not triggered for the same posting refreshed.
- Flags never alter `status`; `refilter` recomputes them; manual postings skip `old`/`reposted`.
- Liveness: 404, 410, redirect to home, "position filled" wording, login wall → *could not tell*, SSRF rejections reused from spec 10's tests; package build skips the check with `--no-verify`.
- UI: badges, the "Before you apply" box, the toggle, escaping of any quoted text.

## 5. Tasks

- [ ] Migration `jobs.quality_flags`; `quality.py` with the signals and their wording.
- [ ] Wire into the filter stage, `refilter`, scoring note, manual postings.
- [ ] UI badges, "Before you apply" box, *Hide suspicious* toggle, optional `search.hide_flags`.
- [ ] Liveness check (button, pre-package step, `jobhunter verify`), reusing `fetch_url`.
- [ ] Measure the signals on the real database (how many postings each flags) and tune the thresholds; record the numbers here.
- [ ] README and this spec marked done.

## 6. Acceptance criteria

- [ ] A posting with scam wording or a repost pattern shows the matching badge and an explanation; nothing is hidden or deleted unless the person configured it.
- [ ] A closed posting whose page says so is marked closed after one press of the button.
- [ ] No check runs by itself in the background or in bulk.
