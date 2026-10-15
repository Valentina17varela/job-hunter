# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Job seekers, mostly software people, who clone the repo and run it on their own machine. The author is the first user; the project is built as an open-source product, so a stranger must be able to install it, try the fictional demo workspace, and then point it at their own CV and criteria. Typical situation: a repeated search over many companies, a handful of applications a week, where the grind is scanning boards and writing a tailored CV and letter for each posting. Their job in the UI: see what the pipeline found, decide what deserves their time, review a generated package, apply on the company site, and track the application until an offer.

## Product Purpose

Local Python job-search copilot with a web UI on 127.0.0.1. It finds postings on public job boards, filters them with deterministic rules (no LLM), scores the survivors against the person's LaTeX CV, builds a tailored CV and cover letter checked in code against invented facts, and tracks applications and interviews. Success in a UI session: search, matches, packages and tracking all live in one place, nothing slips, and the human stays in control. Targets from the specs: under USD 1 of LLM spend per run, at most 10 postings reviewed per day, under 5 minutes to review one package, zero false facts in generated documents.

## Positioning

Unlike all-in-one agents that burn tokens browsing and mass-send applications, this is code-first and LLM-last, runs fully local, and never sends anything: it prepares, the human reviews and applies. Generated CV and letter text is verified against the person's own master CV, and a failed check blocks the package.

## Operating Context

Started by hand from the CLI or the UI; every stage (fetch, filter, score, tailor) is triggered by a button press. No scheduler, daemon or notifications. Inputs are the person's LaTeX CV (`config/cv/master.tex`), a YAML config, and public job-board APIs. Outputs are LaTeX plus compiled PDF in `out/`, a SQLite database in `data/`. The UI is served locally (single user, no accounts) and also runs against a fictional demo workspace (`uv run jobhunter demo --open`). Viewed on a desktop or laptop browser; mobile web is secondary.

## Capabilities and Constraints

- Pipeline: fetch and dedupe, hard filter with stored rejection reasons, LLM scoring in batches with explicit blockers, tailoring (bullet selection, cover letter, recruiter message in the posting's language), verification, tracking.
- UI areas: Home (next action, pipeline with per-step state, applications, funnel), Matches (top five board, live filters, favorites, block list, postings added by hand), the posting page, Applications (ready strip and a four-column board), Documents, Actions, Settings (one tab at a time, one save bar).
- Terminology: posting, match, package (CV plus letter plus message plus notes), stage, blocker, "Not for me" (the one dismissal), "Mark as applied". Copy speaks to the person ("you/your"); buttons carry their verb and say how much they will do.
- Security rules the UI must keep: bind 127.0.0.1 only, escape all posting text, no external assets or CDN, JSON-only writes, files served only from `out/`, no secrets rendered, locked config fields.
- Everything is in English; the person's own profile data and postings may be in other languages.
- Stack is fixed: FastAPI, Jinja2, vanilla JS and CSS, no build step, fonts bundled locally.
- Decided: light is the default theme and dark is an opt-in toggle (applied before first paint). Still undecided: a true SVG logo.

## Brand Commitments

The mascot logo is binding: an eagle head with dark sunglasses in navy, teal and white with an amber beak (`design/brand/logo/logo.png`, 1024 px opaque master; `logo_no_background.png`, 500 px transparent). It is the only identity asset the author confirmed wanting. `design/brand/palette.md` (Kinetic Horizon) and `design/project_brief.md` are earlier design inputs (spec 18). The current look is "The Quiet Cockpit" (spec 24, `DESIGN.md`): neutral surfaces with one orange voice. Neither earlier input is binding.

## Evidence on Hand

- Logo files in `design/brand/logo/`.
- A fictional demo workspace (`uv run python scripts/seed_demo.py` or `jobhunter demo`) and screenshots in `docs/images/`.
- Specs in `specs/` including the frontend redesign (18), top matches (22), live filters (23) and the UI refinement (24), plus the design reviews in `docs/design-audit/`.
- No real user testimonials, usage data or other users' feedback yet. Do not fabricate any.

## Product Principles

1. The human reviews and applies; the UI never implies the system sends anything.
2. Code first, LLM last: show deterministic filter reasons and costs plainly; make every AI step visible, bounded and explainable.
3. No invented facts: surface verification results and blockers prominently; never present generated text as unchecked.
4. One place for the whole search: every stage and its state is reachable and legible from the same UI without hunting.
5. A stranger can try it safely in a minute: demo data first, real data only when the user chooses.

## Accessibility & Inclusion

Existing project rules: no external assets, labelled controls (`aria-label` on controls without a visible label), a single `h1` per page, and the smoke tests in `tests/test_web.py` must keep passing. No further standard stated; WCAG AA contrast is the working target, consistent with the contrast fixes recorded in spec 18.
