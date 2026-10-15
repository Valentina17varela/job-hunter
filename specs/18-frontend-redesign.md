# 18 — Frontend redesign from the design inputs

**Status:** DONE (tokens, font, logo set, all pages restyled, smoke tests, README). The contrast script and a component style page were dropped by the author.

## 1. Goal

Give the local web UI the visual identity and usability of the design inputs collected in `design/` (a Google Stitch design system, a project brief and a logo), without changing what the UI does, how it is served, or the project's principles.

## 2. Inputs received (reviewed)

| File | What it is |
|---|---|
| `design/brand/palette.md` | A Stitch design system named **Kinetic Horizon**: YAML tokens (Material-style color roles, typography scale, radii, spacing) followed by prose on style, colors, typography, elevation, shapes and components |
| `design/brand/logo/logo.png` | The mascot logo: an eagle head with dark sunglasses (navy, teal and white with an amber beak). 1024×1024 px, opaque white background (kept as the master/high-resolution source) |
| `design/brand/logo/logo_no_background.png` | The same mascot with a **transparent background**, 500×500 px with alpha. Checked on white, dark (`#0b1020`) and orange backgrounds: clean edges, no white halo |
| `design/project_brief.md` | A PRD-style brief for an idealized "JobHunter Copilot v0.4.2": vision, brand identity, and per-page feature wishes (Home, Job Matches, Applications, Documents, Actions, Settings) |

### 2.1 Palette "Kinetic Horizon" — what it says

- **Direction:** light, airy, "clean architectural white" with warm orange energy. Primary orange `#f97316` (hover `#ea580c`, tint `#fff7ed`), secondary deep slate `#0f172a`, tertiary sky blue `#0284c7`, neutral surfaces `#ffffff / #f8fafc / #f1f5f9`, hairline borders `#e2e8f0`, text `#111827` / `#475569`.
- **Tokens:** Material-3 style roles (`surface-container-*`, `on-surface`, `primary-container`, `error`, `*-fixed`) plus custom ones (`accent-orange-*`, `surface-base/subtle/muted`, `border-subtle`, `text-primary/secondary`).
- **Typography:** **Plus Jakarta Sans** for everything; scale from `label-sm` 11 px to `display-hero` 56 px, weights 400-800, tight tracking on headlines, **tabular numbers** for salaries and percentages.
- **Shape:** radii 4 / 8 / 12 / 16 / 24 px and pill; spacing scale 4 / 8 / 16 / 24 / 40 px, gutter 24, margin 32.
- **Elevation:** tonal layering and 1 px outlines instead of heavy shadows; hover lifts with a faint orange-tinted shadow and an orange-tinted border (`#fdba74`); an orange "halo" reserved for the main call to action and match scores.
- **Components described:** buttons (primary, secondary, ghost), chips and badges (match score, metadata, filter chip), inputs with an orange focus ring and glow, job cards (company logo, match pill, salary/location line, badges, save heart), checkboxes/radios, and a timeline with orange nodes.
- **Not covered:** a **dark theme** (the palette is explicitly light-only), success and warning colors (only `error` exists), and states for disabled/loading.

### 2.2 Problems found in the palette (to resolve in the redesign)

Contrast was computed from the given values (WCAG 2.x; normal text needs 4.5:1, large text and UI components 3:1):

| Pair | Ratio | Verdict | Fix proposed |
|---|---|---|---|
| White text on `#f97316` (primary button as described) | 2.80 | ✗ fails even large text | Primary buttons use the darker orange `#c2410c` (5.18) or the YAML `primary #9d4300` (6.49) with white text; keep `#f97316` for fills that carry **dark** text (`#582200`, 4.56 ✓), rings, highlights and the halo |
| White on `#ea580c` (hover) | 3.56 | ✗ for normal text | Same as above |
| `#ea580c` text on `#fff7ed` (match badge) | 3.35 | ✗ | Badge text `#c2410c` (4.88 ✓) |
| Placeholder `#94a3b8` on white | 2.56 | ✗ | `#64748b` or darker |
| Input border `#e2e8f0` on white | 1.23 | ✗ for form controls (need 3:1) | Decorative card borders can stay; **input and control borders** use a darker neutral (≥ 3:1) |
| `#10b981` (brief's success) as text on white | 2.54 | ✗ | Use it for fills/rings; text uses `#047857` (5.48 ✓) |
| `#ef4444` (brief's red) as text on white | 3.76 | ✗ for normal text | Use the palette's `error #ba1a1a` (6.46 ✓) for text |
| `#0284c7` sky blue on white | 4.10 | ✗ for small text, ✓ large | Darken for text links (`#0369a1`) |
| `#475569` on `#f8fafc`, `#111827` on white | 7.24 / 17.74 | ✓ | — |

Also: the **prose and the YAML disagree on the primary** (prose `#f97316`; YAML `primary #9d4300` with `primary-container #f97316`); the Material pairing (`primary-container` + `on-primary-container`) is the self-consistent reading and is what §5 proposes. And **orange is both the brand color and the natural "warning" color**: warnings need a distinct amber/yellow so they are not confused with primary actions.

### 2.3 The logo

- Strong, friendly identity that matches the "copilot" idea; navy, teal and amber harmonize with the sky blue and the orange of the palette.
- **Transparent version received** (`logo_no_background.png`, 500×500). Reviewed on light, dark and orange backgrounds and at 64 / 40 / 32 / 24 / 16 px: clean edges; on the dark theme the navy outline loses some definition but the white face and the amber beak keep the mascot readable; it is recognizable down to ~24 px and muddy at 16 px.
- **Use:** sidebar badge ~40 px (with a subtle rounded `surface-muted` tile in the dark theme), Home hero and empty states at 96-160 px, favicon built from 32/48 px renders (the 16 px size is derived and accepted as approximate). A 500 px source is enough for all of these at 1×; for retina hero sizes above ~250 px displayed, the 1024 px master is used.
- **Optional improvements (not blocking):** a true `logo.svg`, and a flatter icon-only head for 16-24 px. If they never arrive, the redesign ships with the PNG-derived set.
- **Derived files to generate:** `static/img/logo.png` (500, transparent), `logo@2x.png` (1000, from the master), `icon-32/48/180/192/512.png`, `favicon.ico`, and a "Job Hunter" wordmark lockup in Plus Jakarta Sans 800 (CSS text, not an image).

### 2.4 The brief — triage

The brief describes a larger, more automated product than the one that exists. It is used as a **source of UI ideas**, not as requirements. Each item is classified:

**Adopt in the redesign (visual/UX over features that already exist)**

- Guided 3-step Home, KPI strip (add *average match score*), priority queue ("what to do next"), yield funnel, interview milestones.
- Job card anatomy: match score pill top-right, bold title, salary/location line, badge row, quick-save heart (the heart ties to favorites, spec 11), hover lift.
- Tabs *Best matches / All evaluated / Applied / Filtered out*; the "best" threshold shown comes from the configured `score_threshold` (the brief's 88% is only an example).
- **Quality gates** panel on a package: fact integrity (ids/verbatim/numbers), page budget, compiler health, keyword coverage when available; today's checks are presented as named gates with pass/fail.
- Timeline with orange nodes for the application history (`events` already exist).
- Company **initials avatar** instead of company logos (logos would need external images; offline rule).

**Candidates for new roadmap tasks (not specified yet; listed in the roadmap)**

- Inline **PDF preview next to a "what changed vs. my master CV" view** (kept/reordered/dropped bullets; select mode makes this exact).
- **Application inspection drawer** (side panel) with interview feedback, meeting link, attached documents, salary band and auto-saved notes.
- **Extra instructions when building a package by hand** ("emphasize payments experience"), with guardrails: they never override the facts-only rules.
- **Keyboard navigation and a command palette** (`⌘K`, `J/K`, `B`/`A` shortcuts), UI-only and offline.
- **Stop run** button (SIGTERM, then SIGKILL after a grace period) for the run dock.
- **Live preview** while editing the CV or the letter template in Settings.
- **Company whitelist** ("prefer") next to the block list of spec 11; collapse *accepted/rejected/withdrawn/ghosted* into a "Closed" column on the kanban so the board reads as 5 columns.
- Local models (e.g. Ollama) as an additional AI backend.

**Conflicts with the project's principles (not adopted as written)**

| Brief | Why not | Instead |
|---|---|---|
| "Autonomous pipeline agent", "local daemon" | Everything is manual; nothing runs in the background | Copy and labels say "copilot you drive"; the UI only listens while `jobhunter ui` runs |
| Embedded **interactive PTY terminal** | A web page with a real shell is arbitrary code execution for anything that passes the Host/Origin checks | Read-only streaming log dock (exists) + Stop run |
| **API key keyrings** in Settings | Keys never enter the UI (specs 14, 15) | Environment variables; the UI shows "set / not set" |
| Model selectors for GPT-4o etc., vector/embedding similarity, "cosine affinity" | Not supported or planned | Deterministic keyword coverage may be added as a task |
| Fixed paths `~/.config/jobhunter`, port 8080, `xelatex` | Example values of an idealized product | Real paths/port/engine stay as they are |
| "Desktop-native 1440px+ only" | Spec constraint is usable from 360-390 px | Desktop-first design, graceful down to phones (§4) |

## 3. The frontend today (starting point)

- Server-rendered **Jinja2** templates, one stylesheet, one vanilla script, FastAPI; **no build step, no framework, no CDN**: it works offline.
- Light and dark themes via CSS variables and `prefers-color-scheme`; inline SVG icon sprite.
- Pages: Home, Job matches (+ detail), Applications (kanban), Documents, Actions, Settings (editable forms); shared sidebar, run dock, toast, tag inputs.
- ~300 tests look for **text and attributes** in the HTML (`data-run`, `data-cfg`, `data-file`, ids used by the script), not for CSS classes.

## 4. Constraints the redesign keeps

1. **Local-first and offline:** no external fonts, scripts, images or analytics. **Plus Jakarta Sans must be self-hosted** (one variable `woff2`, SIL Open Font License; files added under `static/fonts/` with the license text; downloading them needs the author's approval at implementation time). Fallback stack `system-ui` keeps the UI usable if the font fails to load.
2. **No required build pipeline.** Stitch tokens become plain CSS variables; no Tailwind runtime.
3. **Security rules of spec 09 stay:** JSON-only writes, Host/Origin checks, escaped output, no inline event handlers.
4. **Everything stays manual** and honest wording (no fake social proof, nothing sent for the person).
5. **Accessibility:** AA contrast (§2.2 fixes applied), visible focus (the orange ring is kept, with ≥ 3:1 against its surroundings), labels on fields, keyboard reachable, `prefers-reduced-motion`.
6. **Responsive:** designed desktop-first (primary target ≥ 1280 px as in the brief) and usable down to 390 px; the sidebar collapses.
7. **Existing contracts** between templates, script and tests are preserved, or changed together with their tests.

## 5. Decisions

The author confirmed D1 (orange brand) and D3 (derive the dark theme) and delegated the rest to the recommendation, so all are **accepted**.

| # | Topic | Decision | Status |
|---|---|---|---|
| D1 | Brand direction | **Kinetic Horizon**: orange primary, slate secondary, sky-blue tertiary/info. The brief's "electric blue primary" is superseded | Confirmed by the author |
| D2 | Primary button | Light theme: solid `#c2410c` + white text (hover `#9d4300`). Dark theme: `#f97316` + dark brown `#2b1200` text (hover `#fb923c`). `#f97316` is also used for rings, highlights and the match halo | Accepted |
| D3 | Dark theme | **Kept and derived** from the tokens (§5.1). **Light is always the default**; dark is opt-in through a toggle in the sidebar (`data-theme="dark"`, remembered in `localStorage`); it no longer follows `prefers-color-scheme` | Confirmed by the author; opt-in change requested after the first pass |
| D4 | Status colors | Success `#10b981` fill / `#047857` text (light) · `#34d399` (dark); warning amber `#f59e0b` fill / `#92400e` text (light) · `#fcd34d` (dark); error from the palette `#ba1a1a` (light) · `#ffb4ab` (dark) | Accepted |
| D5 | Typography | Plus Jakarta Sans self-hosted (variable `woff2` + OFL license text); `system-ui` fallback; tabular numbers on salaries, scores and counters | Accepted (the download needs the author's go-ahead at implementation time) |
| D6 | Logo usage | Sidebar badge, Home hero, empty states, favicon set (see §2.3); wordmark lockup as CSS text | Accepted |
| D7 | Radii / spacing / elevation | Stitch scales: 8 px controls, 16 px cards, 24 px modals/hero, pills; spacing 4/8/16/24/40; outline-first elevation, orange-tinted hover | Accepted |
| D8 | Kanban | Five visible columns (*Ready to apply, Applied, Screening, Interviewing, Offer*) plus a collapsible *Closed* group; stage names unchanged in the data | Accepted |
| D9 | Brief features | The candidates of §2.4 live in the roadmap's *not specified yet* list; none is part of this redesign | Accepted |

### 5.1 Token table (derived values verified with a contrast script)

Ratios are WCAG 2.x; text needs ≥ 4.5, UI components and focus indicators ≥ 3.0.

| Token | Light | Dark (derived) | Pair checked → ratio (light / dark) |
|---|---|---|---|
| `--bg` | `#f8f9ff` | `#0b1220` | text on bg → 16.88 / 15.66 |
| `--surface` (cards) | `#ffffff` | `#111a2e` | body text → 17.74 / 14.51 |
| `--surface-subtle` | `#f8fafc` | `#0f172a` | secondary text on it → 7.24 / — |
| `--surface-muted` | `#f1f5f9` | `#1a2438` | — |
| `--border` (decorative) | `#e2e8f0` | `#243049` | decorative only |
| `--control-border` (inputs) | `#8391a7` | `#5f6f88` | vs surface → 3.19 / 3.40 |
| `--text` | `#111827` | `#e6ebf5` | |
| `--text-secondary` | `#475569` | `#a3b1c6` | 7.24 / 7.98 |
| `--placeholder` | `#64748b` | `#8795ab` | 4.76 / 5.71 |
| `--primary` (button fill) | `#c2410c` | `#f97316` | on-primary white / `#2b1200` → 5.18 / 6.30 |
| `--primary-hover` | `#9d4300` | `#fb923c` | 6.49 / 7.80 |
| `--on-primary` | `#ffffff` | `#2b1200` | |
| `--orange` (highlights, ring glow) | `#f97316` | `#f97316` | with `#582200` text → 4.56 |
| `--accent-text` (links, orange text) | `#c2410c` | `#fb923c` | 5.18 / 7.66 |
| `--focus-ring` | `#c2410c` | `#fb923c` | vs surface → 5.18 / 7.66 (plus a soft orange glow) |
| `--badge-soft` bg / text | `#fff7ed` / `#c2410c` | `#31262b` / `#fdba74` | 4.88 / 8.63 |
| `--info` text / soft | `#0369a1` / `#e0f2fe` | `#7dd3fc` / `#0e3150` | 5.17 / 8.00 |
| `--success` text / soft | `#047857` / `#d1fae5` | `#34d399` / `#11333b` | 4.84 / 7.00 |
| `--warning` text / soft | `#92400e` / `#fef3c7` | `#fcd34d` / `#352f28` | 6.37 / 9.17 |
| `--error` text / soft | `#ba1a1a` / `#ffdad6` | `#ffb4ab` / `#4c1a27` | 5.00 / 8.33 |
| Shape, spacing, type | as Stitch (§2.1) | same | |

The dark soft fills are the accent colors blended over `--surface` (orange 14 %, blue 22 %, green 16 %, amber 16 %, red 35 %).

## 6. Process

1. **Assets:** the transparent logo is in `design/brand/logo/`; the SVG and the icon-only mark are optional.
2. **Tokens:** translate the Stitch YAML into CSS variables (color roles light + derived dark, type scale, radii, spacing, elevation, focus), apply the contrast fixes of §2.2 and record every derived value in a table here.
3. **Migrate the current look onto the tokens** before redrawing anything (safe, visible change; all tests keep passing).
4. **Components:** button, chip/badge, score ring/pill, card, tag input, tabs, table, form field, dock, toast, empty state, kanban card, funnel bar, timeline, gate row, avatar-initials, logo badge; a static style page (`design/` or a dev-only route) shows them all with the demo data.
5. **Pages one at a time**, most used first: Home → Job matches → Posting detail → Applications → Documents → Actions → Settings; later features (wizard, insights...) are built on the same components.
6. **Review** with the demo workspace: before/after screenshots per page, light and dark, desktop and 390 px.

## 7. Tests and checks

- Existing tests keep passing; markup changes update their tests in the same commit.
- Smoke test over every page, empty and populated: no external URL in any `src`/`href`/CSS `url()`, every form control labelled, exactly one `h1` per page, the font file referenced exists.
- A script checks the contrast of every foreground/background token pair used by the components (≥ 4.5 text, ≥ 3 UI) in both themes.
- Manual checklist per page: keyboard only, both themes, 390 px, long titles, empty and error states, the run dock while a run is active.

## 8. Tasks

- [x] (author) Provide a transparent logo; confirm direction and dark theme (D1, D3).
- [x] Record the derived dark theme and status colors in a token table here (§5.1, contrast-verified).
- [x] Self-host Plus Jakarta Sans (`static/fonts/PlusJakartaSans.woff2`, 60 KB variable font, plus `OFL.txt`), downloaded with the author's go-ahead from github.com/tokotype/PlusJakartaSans.
- [x] Generate the logo set from `logo_no_background.png`: `static/img/logo.png` (500), `icon-32/48/180.png`, `favicon.ico`; the wordmark is CSS text. (The 1024 px master stays in `design/` for large uses.)
- [x] Tokens file (`static/tokens.css`, light + derived dark, §5.1) and migration of the current look onto it: orange primary with the contrast-safe pairs, slate hero, tinted KPI icons, 8 px controls with darker borders, orange focus ring and hover.
- [ ] Component set and the style page; logo badge, favicon set and wordmark.
- [x] First styling pass on Home (mascot hero), Job matches (initials avatar, score ring, segmented tabs) and the shell (wordmark, active-nav bar, theme toggle).
- [x] Applications: five columns (Ready, Applied, Screening, Interviewing, Offer) with a collapsible *Closed* group (D8), initials avatars, stage-colored tops. Documents, Actions and Settings: tokens, font, checkbox/tag/check styling.
- [x] Polish pass: Actions option fields, Documents warnings and file chips, quiet tables, empty states, sticky save bar in Settings, 390 px layout (scrolling nav, stacked cards, horizontal kanban), dark theme checked on Home and Applications.
- [x] Smoke tests (`tests/test_web.py`): nothing loaded from outside, one `h1` per page, labelled controls (they found and fixed unlabelled filters, note and editor fields), font and logo files served, light as default theme.
- [x] README: new screenshots (Home, matches, detail, applications, actions, dark, mobile).
- Dropped by the author: the contrast script (the table in §5.1 is the record) and a separate component style page.
- [ ] Smoke tests (offline assets, labels, headings) and the contrast script; before/after screenshots.
- [x] README (UI section) updated to the shipped look, `design/` kept as the source.

## 9. Acceptance criteria

- [x] The UI visibly uses the Kinetic Horizon identity and the mascot, and §5 documents every deviation and derived value.
- [x] Text and control colors use the contrast-checked pairs of §5.1 in both themes (verified when the table was made; no automated script, by decision of the author).
- [x] No request (covered by a test) leaves the machine to render a page; the same security checks and all tests pass.
- [x] Pages checked at 390 px by screenshot; controls carry labels and a visible orange focus ring.

## 10. Addendum (spec 24)

The identity this spec introduced was refined by [24](24-ui-refinement.md): the Home hero, orange as the default tint, card-on-card surfaces, uppercase labels and text-glyph icons were replaced by neutral surfaces, one orange voice, flat rows, shape by role and a sprite icon set. The tokens, font, mascot, security rules and the dark theme from this spec are unchanged; `DESIGN.md` describes the result. Where this spec and spec 24 disagree about looks, spec 24 wins.
