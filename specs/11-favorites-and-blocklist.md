# 11 — Favorites and company block list

**Status:** DONE

## 1. Problem

Two opposite needs the scoring cannot express: "this one is interesting, keep it close even if the AI scored it low" and "I never want to see anything from this company again" (bad experience, wrong industry, known layoffs).

## 2. Favorites

- A **star** on every posting card and on the posting page, for any status (also filtered-out or closed ones). Starring does **not** change the posting's status or push it through the pipeline; it is a bookmark.
- New tab **Favorites** in *Job matches* (count shown), plus a *Favorites first* sort option and a `★` filter chip combinable with the others. Home shows the number of favorites without an application.
- Table `favorites(job_id INTEGER PRIMARY KEY REFERENCES jobs(id), created_at TEXT NOT NULL, note TEXT)`; optional short note ("ask about the visa").
- A favorite whose posting later disappears from its source is shown with a **Closed** badge; the row is kept.
- A favorite is never removed by `refilter`, dedupe or stale-closing logic (those only change `jobs.status`).
- Events: starring/unstarring writes an `events` row (`favorited` / `unfavorited`) for the history.
- CLI: `jobhunter favorite ID [--note TEXT]` and `jobhunter favorite ID --remove`; `jobhunter favorites` lists them.

## 3. Company block list

- Config key `search.companies_exclude: [names]` (editable in **Settings → What I'm looking for** with the same tag input as the other lists).
- New hard-filter rule `companies_exclude` evaluated **right after the age rule**. Matching uses a **normalized company name**: lowercase, accents and punctuation removed, common legal suffixes dropped (`inc`, `llc`, `ltd`, `gmbh`, `s.a.`, `sas`, `corp`, `co`), whitespace collapsed; match is **whole-name equality** after normalization (so blocking "Meta" never blocks "Metamask").
- Rejection reason: `companies_exclude: company "<name>" is on your block list`; the Home "why postings were left out" card shows it as *Company is on your block list*.
- **Block this company** button on every posting page (asks for confirmation; a reason is not stored, the list holds names only), which adds the company to the config list through the existing safe config editor and offers *Re-filter now*.
- Settings lists the blocked companies with a remove (×) each.
- Existing postings: `refilter` moves matching postings to `filtered` like any other rule, except statuses the person decided (`applied`, `replied`, `rejected`, `ignored`) and `packaged` (consistent with today's rules).
- Manual postings (spec 10) from a blocked company are allowed with a warning; favorites from a blocked company keep their star but show a *Blocked company* badge.
- Block list matches are applied at ingestion time as well: postings from blocked companies are stored (for statistics) but start as `filtered`.

## 4. Interfaces

- `POST /api/jobs/{id}/favorite {on: bool, note?}`; `GET /api/favorites`.
- Block list goes through `POST /api/config` (`search.companies_exclude`), no new endpoint.
- Filter: `JobFilter` gains the rule and `evaluate_all` (spec 13) must include it.

## 5. Tests

- Normalization table (suffixes, accents, `Meta` vs `Metamask`, `Acme, Inc.` vs `ACME Inc`).
- Rule order and reason text; `explain` shows it; refilter moves postings and spares human statuses.
- Favorites: star/unstar, note, filtered/closed postings can be starred, tab counts, sort, events, survives refilter/closing.
- UI: star toggles without page reload errors; block button writes the config (comments kept).

## 6. Tasks

- [x] Migration: `favorites` table.
- [x] `JobFilter`: `companies_exclude` + name normalization + config field + validation.
- [x] Favorites API/CLI and queries (`favorites` tab, sort, chip).
- [x] UI: star, *Block this company*, Settings list, Home label for the new rule.
- [x] README (commands, UI, config key) and this spec marked done.

## 7. Acceptance criteria

- [x] A starred posting stays reachable under *Favorites* whatever the filters or the AI say.
- [x] Blocking a company removes its postings from the matches after a re-filter and keeps them out of future fetches.
- [x] "Meta" never blocks "Metamask".
