# 08 — Roadmap

A flat list of tasks. Done tasks are checked; the rest are in the suggested order. Every task points to the spec that describes it and, where it matters, to what it depends on. Nothing here is a phase or a gate: each task is picked up, built, tested and documented on its own.

## Done

- [x] Project skeleton: config, SQLite with migrations, `doctor`, tests and lint
- [x] Sources: Greenhouse, Lever, Ashby and five remote aggregators, dedupe, company discovery — [03](03-sources.md)
- [x] Hard filter with `explain` and `refilter` — [04](04-filtering.md)
- [x] LaTeX CV parser and markers, `cv check`, `cv init` — [06](06-tailoring.md)
- [x] LLM scoring (subscription or API backend), batches, cache, selection, `calibrate` — [05](05-scoring.md)
- [x] Tailored CV and cover letter (LaTeX → PDF) with verification, `cv translate`, `letter init`, `review` — [06](06-tailoring.md)
- [x] Application tracking: stages, interviews, `mark`, `stats` — [02](02-data-model.md)
- [x] Local web UI: Home, Job matches, Applications, Documents, Actions, Settings — [09](09-web-ui.md)
- [x] Settings editor in the UI (criteria, AI, sources, CV, letter, company list) with safe writes — [09](09-web-ui.md)
- [x] Build a package by hand for any posting; delete generated documents — [09](09-web-ui.md)
- [x] Favorites and company block list — [11](11-favorites-and-blocklist.md)
- [x] Demo workspace (`scripts/seed_demo.py`) and README

## To do

Suggested order: small and independent first, those that gain from more data later, the ones needed late in a process last.

- [ ] **Add a posting by hand** (URL or pasted text) — [10](10-manual-postings.md)
- [ ] **The Muse as a new source** (works without a key) — [14](14-new-sources-api-keys.md)
- [ ] **CV importer**: any CV to a marked LaTeX master — [16](16-cv-importer.md)
- [ ] **First-run setup wizard** in the UI (uses the importer for its CV step) — [15](15-onboarding-wizard.md) · after the importer, or first with the "I have a marked CV / skip" paths
- [ ] **Market insights**: skills demand, gaps vs your CV, what a single rule discards, pay — [13](13-market-insights.md) · gains from The Muse and some weeks of data
- [ ] **Offer negotiation helper** — [17](17-offer-negotiation.md) · needs the pay percentiles of the insights task
- [ ] **Interview preparation kit**, on demand once a company answers — [12](12-interview-prep.md)
- [ ] **Frontend redesign** with the inputs in `design/` (Kinetic Horizon palette, mascot logo, project brief): tokens, fonts, components, then page by page — [18](18-frontend-redesign.md) · inputs and decisions are complete (transparent logo received, orange brand and derived dark theme confirmed); only the go-ahead to download the font files is pending; best done before the new pages (wizard, insights...) so they use the new components
- [ ] **Adzuna and Jooble sources**, once there are keys — [14](14-new-sources-api-keys.md)

## Not specified yet

From the design brief (see [18](18-frontend-redesign.md) §2.4): inline PDF preview with a "what changed vs. my master CV" view; application inspection drawer; extra instructions when building a package by hand; keyboard navigation and a command palette; a Stop run button; live preview while editing the CV or letter; company whitelist ("prefer"); local models (Ollama) as an AI backend.

Ideas reviewed and kept for later specs: match breakdown and keyword coverage of the generated CV; next actions, tasks and follow-up reminders with contacts and drafted outreach messages; answers bank and apply-assistant panel; trust and freshness badges; saved search profiles; learning from what you hide or apply to; a clip bookmarklet; weekly goals; UI in Spanish; `rewrite` tailoring mode; multiple CV variants; more boards (Workable, Recruitee, SmartRecruiters, Himalayas, GetOnBoard, Torre); CSV export and backup; `.ics` export of interviews.

Reviewed and deliberately **not** adopted: mass auto-apply, scraping recruiter emails, browser extensions that fill other sites' forms, an interactive terminal inside the web UI, API keys typed into the UI, an "autonomous daemon" framing.

## Decisions

1. Tailoring mode is `select`: the LLM reorders and picks the person's own bullets; code copies the original LaTeX.
2. Packages follow the posting's language; the master CV is translated once per language and reviewed by the person (06 §4.0).
3. Score threshold 75, up to 10 packages per run, a cap of AI calls per run instead of a price (subscription backend).
4. **Everything is manual**: no scheduler, background job or notification. Every stage is started from the CLI or the UI.
5. The README describes only what works today; planned work lives in the specs and in this list.
6. The interview kit and the negotiation helper are on demand and only available at the right stage of an application.
7. Keys for extra sources live only in environment variables and are redacted from every log (14).
8. The CV importer never sends contact details to the LLM and the LaTeX is produced by code (16).
9. The block list lives in `config.yaml` (`search.companies_exclude`); favorites live in the database (11).
10. Insights are computed locally from collected postings; any LLM summary is optional and off by default (13).
