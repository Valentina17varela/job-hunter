# 15 — First-run setup wizard (in the UI)

**Status:** PLANNED (spec only, not implemented)

## 1. Problem

Getting started today means a terminal: install tools, copy a config file, edit YAML, mark a LaTeX CV, run commands in the right order. Competing tools sell a **one-time, easy setup**; ours is the biggest barrier for anyone who is not the author. The pieces already exist in the UI (Settings editor, CV editor, runs); what is missing is a guided path through them.

## 2. Goal

A person who has cloned the repository and installed the two tools (`uv`, `tectonic`) can reach **their first list of matching jobs without editing a file by hand**. Everything the wizard does goes through the existing safe editors and runs; it adds no new way to write files or execute programs.

## 3. When it appears

- `jobhunter ui` **creates `config/config.yaml` from `config.example.yaml` when it is missing** (and says so in the terminal) so the UI can always start. Today it exits with "Config file not found".
- The wizard opens automatically while the setup checklist (§6) is incomplete **and** the person has not dismissed it. It never blocks anything: a **Skip for now** link is on every step, and Home keeps a *Finish setup* card until the checklist is done.
- It can be reopened any time from Settings (*Run setup again*). Wizard progress is stored in a small `app_state(key, value)` table (`onboarding_dismissed`, `onboarding_done_at`); the checklist itself is always recomputed from the real state, never trusted from storage.

## 4. Steps

1. **Welcome.** One screen: what the tool does in three lines, that it runs only when the person presses a button, that nothing is sent anywhere except the text sent to the LLM (CV items and the posting; never the contact header).
2. **Check your computer.** Runs the doctor checks and shows each as ✓ / ⚠ / ✗ with a plain explanation and the exact command to fix it, with a copy button and a **Check again** button:
   - LaTeX engine missing → `brew install tectonic`.
   - Claude not logged in → `claude auth login` (run in *your own* terminal; the UI cannot and does not do it).
   - Or pick **API key mode**: the UI explains `export ANTHROPIC_API_KEY=…`; **keys are never typed into the UI** (same rule as spec 14).
   - LLM unavailable is **not blocking**: search and filtering work; scoring and packages stay disabled with an explanation.
3. **Your CV.** Three paths:
   - **Import my CV** → the importer of spec 16 (recommended; the default).
   - **I already have a marked LaTeX CV** → paste or upload it; it is validated with the same parser as `cv check` and compiled; errors point to the offending line.
   - **Skip for now** → the rest of the wizard works; scoring/packages show "add your CV" until it exists.
4. **What you are looking for.** A friendly form that writes the `search` and `scoring.candidate_context` config through `POST /api/config`:
   - **Start from a template** (chips): Backend engineer, Frontend, Full-stack, Mobile, Data engineer, DevOps / Platform, Data scientist, QA / SDET, or **Start empty**. A template fills titles to include, titles to exclude, technologies and seniority; everything stays editable tags. Templates are versioned data in `presets.py`, not config.
   - **Where do you live and where can you work?** A country picker plus two questions ("Can you work for companies abroad as a contractor?", "Only remote?"). The answers produce `locations_allowed` tokens (e.g. Colombia → `Colombia, LATAM, Latin America, Americas, Worldwide, Anywhere, Global`; contractor abroad → adds the chosen countries), `work_mode`, and a **drafted `candidate_context`** sentence the person can edit.
   - **Pay:** amount with a period selector (year / month / hour) and a currency; shown converted to the annual USD the filter uses, with the FX table values visible ("4,000 USD / month = 48,000 / year").
   - **Preview of what the filter will do:** while editing, a counter shows "about N of your downloaded postings would match" (uses the existing filter on stored postings; before the first search it shows "run a search to see this").
5. **Companies (optional).** Explains that company boards are a discovery mechanism, offers **Find company job boards** (runs `companies discover` with the built-in candidate list, with the dock log) and lets the person add company names.
6. **First search.** Runs the `search` stage with the live log, then shows: postings found, how many match, and — if few — the *why left out* breakdown with a one-click link to loosen the biggest rule. If CV and LLM are ready it offers **Score the best matches** (with the cost note and the call cap) as an optional last action.
7. **Done.** Links to Job matches, the workflow on Home, and the Settings page.

## 5. Interfaces

- `GET /api/setup/status` → `{checks: [...], checklist: [{id, label, done, hint}], dismissed, done}`.
- `GET /api/setup/presets` → templates and country/location mappings (read-only data).
- `POST /api/setup/dismiss {dismissed: bool}`.
- Everything else reuses `POST /api/config`, `POST /api/files/{name}`, `POST /api/runs`, the doctor endpoint and the importer endpoints; no new write path.
- Pages: `/setup` (single page with steps, progress bar, back/next, each step saves on *Next* and is idempotent).

## 6. Setup checklist (recomputed from real state)

| Item | Done when |
|---|---|
| Config file | `config/config.yaml` exists and validates |
| LaTeX | the engine compiles a minimal document |
| AI engine | `claude` is logged in (or the API key variable is set); optional |
| CV | `master.tex` parses and compiles with at least one section |
| Criteria | `search.titles_include` is not empty |
| Companies | `companies.yaml` has at least one board (optional) |
| First search | at least one fetch run exists in `fetch_log` |

## 7. Non-goals

- Installing software or logging in on the person's behalf; the wizard only explains and re-checks.
- Account creation, cloud sync, telemetry.
- Translating the wizard (the UI language option is a separate idea).

## 8. Changes to other specs when implemented

- 07 (`ui` command creates the config when missing), 09 (new `/setup` page and Home card), 02 (`app_state` table).

## 9. Tests

- `jobhunter ui` with no config creates it from the example and starts; the file is valid.
- Checklist computation for each combination (nothing / only config / CV broken / all done); dismissal does not change it.
- Presets and country answers produce configs that pass validation; salary conversion table (year/month/hour × USD/EUR/COP); drafted `candidate_context` contains the country and the contractor answer.
- The match counter equals running the filter on the stored postings.
- Every step page renders with and without data; skipping a step never raises; the wizard writes only through the existing endpoints (asserted by mocking them).

## 10. Tasks

- [ ] `jobhunter ui`: create the config when missing.
- [ ] `app_state` migration; `setup.py` (checklist, presets, location mapping, salary conversion).
- [ ] API endpoints and the `/setup` page with the 7 steps; *Finish setup* card on Home.
- [ ] Preview counter for criteria; first-search summary and loosening hint.
- [ ] README (Setup section rewritten around the wizard, commands/UI) and this spec marked done.

## 11. Acceptance criteria

- [ ] From a fresh clone with the tools installed, a person gets to their first matches using only the UI (plus `claude auth login` in a terminal).
- [ ] Every step can be skipped and the tool stays usable.
- [ ] No API key or secret is ever entered or shown in the UI.
