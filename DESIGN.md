---
name: Job Hunter
description: A quiet, bright, local-first job-search cockpit: neutral surfaces, one orange next action, a sunglasses-eagle copilot.
colors:
  primary: "#c2410c"
  primary-hover: "#9d4300"
  on-primary: "#ffffff"
  orange: "#f97316"
  on-orange: "#582200"
  orange-border: "#fdba74"
  orange-soft: "#fff7ed"
  slate: "#0f172a"
  on-slate: "#ffffff"
  canvas: "#f8f9ff"
  panel: "#ffffff"
  soft: "#f8fafc"
  muted-surface: "#f1f5f9"
  surface-neutral: "#f1f5f9"
  ink-neutral: "#334155"
  border: "#e2e8f0"
  btn-border: "#cbd5e1"
  control-border: "#8391a7"
  ink: "#111827"
  muted: "#475569"
  placeholder: "#64748b"
  info: "#0369a1"
  info-soft: "#e0f2fe"
  good: "#047857"
  good-soft: "#d1fae5"
  good-fill: "#10b981"
  warn: "#92400e"
  warn-soft: "#fef3c7"
  warn-fill: "#f59e0b"
  bad: "#ba1a1a"
  bad-soft: "#ffdad6"
typography:
  display:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "2rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 700
    lineHeight: 1.55
    letterSpacing: "normal"
  body:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  label:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.06em"
rounded:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  full: "999px"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
    padding: "0.6rem 1.1rem"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0.6rem 1.1rem"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "{rounded.sm}"
    padding: "0.6rem 1.1rem"
  chip:
    backgroundColor: "{colors.soft}"
    textColor: "{colors.muted}"
    rounded: "{rounded.xs}"
    padding: "0.25rem 0.6rem"
  badge-status:
    backgroundColor: "{colors.good-soft}"
    textColor: "{colors.good}"
    rounded: "{rounded.xs}"
    padding: "0.14rem 0.6rem"
  card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "1.5rem 1.7rem"
  job-row:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "0"
    padding: "1rem 0.25rem"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 0.7rem"
  kanban-card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0.85rem"
---

# Design System: Job Hunter

## Overview

**Creative North Star: "The Quiet Cockpit"**

A calm instrument panel for one person's job search. Everything is neutral (slate on a faintly cool canvas) until something needs the person: then exactly one thing is orange. The sunglasses-eagle mascot is the copilot: 64px in the Home header, 38px in the sidebar, larger in empty states. Every stage of the pipeline (search, matches, package, apply, track) has a visible state and one clearly marked next action; orange fills mean *the next action*, orange rings mean *a match*, and nothing else is orange.

Surfaces are flat. Job lists are rows with dividers, not stacks of cards; sections are a heading and a divider; cards appear only for real groupings (a form section, a kanban column, a package). Shape follows role: only things you press or remove are pills (the primary button, filter chips, tags, tabs); status badges and metadata chips are small rectangles; controls are 8px; containers are 24px. Light is the default theme; dark is an opt-in toggle in the sidebar header that keeps the same roles with a lifted orange and tonal navy surfaces, applied before first paint.

The voice is plain and addressed to you ("Your application", "Mark as applied", "Score 12 postings"): buttons carry their verb and say how much they will do, nothing shows a raw token. The system rejects anything that suggests the tool acts on the person's behalf: no urgency theatre, no "apply now" framing, no dark patterns, no decorative motion. It is local: fonts are bundled, icons are inline SVG, nothing is fetched from outside.

**Key Characteristics:**
- White panels and flat rows on a cool canvas (`#f8f9ff`), hairline `#e2e8f0` borders, shadows only on state (hover, menus, floating layers).
- One orange voice: the filled primary button (at most one per area), match rings and the active-nav indicator bar. Avatars, tags, chips, counts and the active tab are neutral; the current pipeline step is marked with an ink number and a neutral "Next" badge, never a second orange button.
- Plus Jakarta Sans everywhere on a 1.2-ratio scale (`--text-xs…3xl`) and five weights; tabular figures for scores, salaries and counts.
- Status hues (green, amber, red, sky) never overlap the brand orange, so a warning cannot read as an action.
- WCAG AA contrast for text, 3:1 for control borders, focus and rings; `prefers-reduced-motion` honoured.
- All values live in `static/tokens.css`; `static/style.css` has no colour, shadow, font-size or z-index literals (enforced by `tests/test_css.py`).

## Colors

A deep-orange accent and slate neutrals over cool white, with separate semantic hues so status never competes with the brand.

### Primary
- **Cockpit Orange, deep** (`#c2410c`): the filled primary button, accent text, the wordmark's "Hunter", links on hover and the focus ring. Chosen over the lighter brand orange because white text on `#f97316` fails contrast (2.8:1); `#c2410c` reaches 5.2:1.
- **Cockpit Orange, pressed** (`#9d4300`): primary hover.
- **Beacon Orange** (`#f97316`): the brand fill that carries dark text (`#582200`), plus rings, the halo and the faint canvas glow. Never behind white text and never as text on white.
- **Beacon Tint** (`#fff7ed`) with the `#fdba74` border: the Top-matches fill notice; no longer used for tags, chips or nav.

### Secondary
- **Deep Slate** (`#0f172a`): toasts and the "not for me" notice; the only dark blocks in light theme (the Home hero is gone).

### Tertiary
- **Sky Info** (`#0369a1` on `#e0f2fe`): early application stages (Applied, In process), informational chips.

### Neutral
- **Cool Canvas** (`#f8f9ff`): page background with a faint orange radial wash at the top-left.
- **Panel White** (`#ffffff`): cards, inputs, menus, dialogs.
- **Mist** (`#f8fafc`), **Fog** (`#f1f5f9`, also `--surface-neutral`): wells, the tab track, kanban columns, avatars, tags, hover rows.
- **Ink Neutral** (`#334155`): text and icons on neutral fills.
- **Hairline** (`#e2e8f0`): borders and dividers. **Button Border** (`#cbd5e1`) and **Control Border** (`#8391a7`, 3:1 on white): buttons and form controls.
- **Ink** (`#111827`), **Slate Text** (`#475569`), **Placeholder** (`#64748b`).

### Status
- **Good** (`#047857` on `#d1fae5`, fill `#10b981`): packaged, selected, passing checks, salary, high score.
- **Warn** (`#92400e` on `#fef3c7`, fill `#f59e0b`): blockers, maybe verdicts, below-threshold, upcoming interviews. Amber, never orange.
- **Bad** (`#ba1a1a` on `#ffdad6`): rejected, errors, danger actions.
Every posting status and application stage has an explicit rule; the neutral fill covers the rest (enforced by a test).

### Named Rules
**The One Voice Rule.** Orange means "act here" or "this matches". Status uses green, amber, red; information uses sky; everything else is neutral. A screen with orange on everything has no next action.
**The Dark-Text-On-Bright-Orange Rule.** Text on `#f97316` is `#582200`; white text only sits on `#c2410c` or darker.
**The Warning Is Amber Rule.** A warning never uses the brand orange.

## Typography

**Font:** Plus Jakarta Sans (bundled variable woff2, weights 200-800, preloaded), fallback system-ui. `ui-monospace, "SF Mono", Menlo, monospace` only for `code`, `pre` and logs. The family is a deliberate, author-confirmed keep, even though detectors list it among common faces.

**Character:** One rounded geometric family does everything. Weight and tracking carry hierarchy; headings are tightly tracked and balanced (`text-wrap: balance`), paragraphs use `pretty`, hints are capped near 68ch.

### Hierarchy (scale tokens)
- **Display** (800, `--text-2xl` 2rem, -0.035em): the page `h1`.
- **Headline** (700, `--text-md` 1.125rem): card and section titles (`h2`).
- **Title / body** (700 / 400, `--text-base` 15px, 1.55): job-row titles and copy; secondary text is `--text-sm` (14px).
- **Label** (700, `--text-xs` 12px): sentence-case section labels; **all caps only** for the micro-labels (`.verdict`, filter names), enforced by a test.
- **Metric** (800, `--text-xl` 1.6rem, -0.02em): reserved for a headline number; the ring score is 700 at 34% of the ring size.
- **Reading text** (400, `--text-base`, 1.65 leading, 68ch): the posting text on the posting page is prose in the body face, flat on the card, never monospace; `pre` stays for generated copy and logs.
- Weights are 400/500/600/700/800 only.

### Named Rules
**The Tabular Figures Rule.** `font-variant-numeric: tabular-nums` is on at the body level; scores, salaries and counts never shift width.

## Layout

A fixed 248px sticky sidebar plus one scrolling main column (max 1320px, padding about 2.1rem 2.75rem). Pages are a header and flat sections. Home: a slim header band (mascot, `h1`, one line of context, the one next action), a vertical three-step pipeline whose steps each show their own state, slim side notes when something needs attention, the top matches, "Your applications" (stage chips and upcoming interviews), then the funnel and the "left out" bars. Cards with nothing to show are not rendered. Matches: tabs, a connected filter bar (search, score and sort, with source, posted and mode folded into "More filters"), the top board, then rows (avatar, title, chips, reason, ring, one button and a ⋯ menu). The posting page: a header (score, one primary, star and ⋯ menu), "Why it matches" beside the shorter criteria card (3:2), a workspace of posting text beside the package (3:2, the package card stays in view while you read), then your application and history. Applications: a Ready-to-apply strip above a four-column board (Applied, Screening, Interviewing, Offer) that fits 1280px with no horizontal scroll; closed stages in a collapsed group. Settings: one tab at a time with a sticky save bar.

Spacing uses the `--space-1…8` scale (0.25 / 0.5 / 0.75 / 1 / 1.5 / 2 / 3 / 4rem). Below 1100px the board is two columns; below 860px the sidebar becomes a top bar with a horizontally scrolling nav and everything collapses to one column. A floating run dock sits bottom-right; the toast (with Undo after a stage change) and the notice float bottom-center. Targets are at least 24px; there is a skip link, landmarks, and `aria-current` on the active nav item and tab.

## Elevation & Depth

Flat by default. Depth comes from white panels on the cool canvas, 1px hairlines and Fog wells; shadows respond to state.

### Shadow Vocabulary (all tokens)
- **Resting card** (`0 1px 2px rgba(15,23,42,.04)`): barely there.
- **Hover** (`0 8px 24px rgba(15,23,42,.08)`, a neutral slate shadow): kanban cards and menus. Rows tint instead of lifting, so click targets never move.
- **Halo** (`0 8px 22px rgba(249,115,22,.28)`): reserved for the filled primary button.
- **Floating layers** (`0 18px 50px`, modal `0 30px 80px` over a `rgba(15,23,42,.55)` scrim): run dock, notices, dialogs.
- **Focus** (`3px outline --focus-ring, offset 2px` for buttons and links; a 3px glow with a ring-coloured border for form fields). Score rings have no neon glow.

### Named Rules
**The Flat-By-Default Rule.** Surfaces carry at most the resting hairline shadow; the rest appears on hover, focus and floating layers.
**The Halo Is Earned Rule.** Only the filled primary button glows.

## Shapes

Shape follows role. Containers are 24px (cards, empty states) and 16px (kanban columns, panels); inner tiles are 12px (kanban cards, menus, filter selects); controls are 8px; badges, metadata chips and code are 6px rectangles. Full pills (`999px`) are reserved for what you press or remove: the primary button, filter chips, tags and the tab track. The circular score ring and the 44px rounded-square logo tile are the two signature forms. Company avatars are neutral rounded squares with initials, not logos, because nothing external is fetched. Borders are 1px solid hairline; empty states use a dashed border; board columns mark their stage with an 8px colour dot before the title (no side stripes).

## Components

### Buttons
- **Primary** (at most one filled per area): `#c2410c` fill, white text, weight 600, `0.6rem 1.1rem`, pill, orange halo; hover `#9d4300`; the pressed state scales to 98%.
- **Secondary:** white fill, 1px `#cbd5e1` border, 8px radius, ink text; hover darkens the border neutrally. The default for everything that is not the next step, including "Build package" on a row and every Actions button.
- **Ghost:** transparent, slate text, Fog wash on hover. **Danger** text is `#ba1a1a`.
- **Icon button / ⋯ menu:** 24px+ target; `details.more` with a white 12px-radius menu that closes on outside click, item click and Esc.
- **Focus / disabled:** 3px outline with 2px offset; disabled is 50% opacity.

### Chips, Badges and Tags
- **Chip:** Mist fill, hairline border, slate text, 6px. Variants: good (salary), warn, link, stage colours.
- **Badge:** small status rectangle with the status's soft fill; neutral by default.
- **Tag** (editable list items) and **active filter chip:** neutral pills with a remove button; no orange.

### Cards / Containers
- **Card:** white, 1px hairline, 24px radius, `1.5rem 1.7rem`, resting shadow. Used for real groups only; never a card inside a card except kanban cards in a column.
- **Job row:** transparent, divider below, `1rem .25rem`, Mist wash on hover; avatar, title with the star, company line, chips, one-line AI reason, ring, one button and the ⋯ menu.

### Inputs / Fields
- **Style:** white, 1px `#8391a7` border, 8px, `0.5rem 0.7rem`; every control has a programmatically associated label (`for`/`id`, `fieldset/legend`, `aria-describedby`).
- **Focus:** ring-coloured border and a 3px glow. **Error:** red border; helper text announced (`role="alert"`).
- **Filter bar:** one connected white row; selects and search apply as you choose, results announced in a live region.
- **Settings save bar:** sticky; "Save" (primary) and "Save & re-filter", enabled only when something changed.

### Navigation
- **Sidebar:** logo tile plus wordmark ("Job" ink, "Hunter" deep orange, 800) with a tagline, a theme toggle (moon/sun icon button), and six rows with an 18px icon: Home, Matches, Applications, Documents, Actions, Settings.
- **Active:** Fog fill and a 4px orange indicator bar on the sidebar's edge, `aria-current="page"`.
- **Tabs:** a Fog pill track with a white pill selection and a faint shadow; the active tab is neutral. Settings tabs show one panel at a time.

### Match score ring (signature)
A 56px conic-gradient circle on a Fog track with an inner white disc and a bold tabular number (`role="img"` with a text alternative). Colour encodes quality: red, amber, green; un-scored postings show a muted dash.

### Pipeline list and kanban
- **Pipeline (Home):** a vertical list: a number, a title, one state line, controls on the right. The step the header acts on has an ink number and a neutral "Next" badge and no button of its own; the other steps show count-aware secondary buttons ("Score 12 postings") only when there is work.
- **Board:** Fog columns with a stage dot, a plain count and 12px white cards (title, interview chip, "applied 5 days ago", stage select); changing a stage offers Undo in a toast.

### Run dock and toasts
A bottom-right panel with a pulsing amber dot while running (green done, red failed), a monospaced log and a "Refresh page" footer. Toasts are ink pills (`role="status"`); the "not for me" notice is a slate pill with an orange border.

## Do's and Don'ts

### Do:
- **Do** keep at most one filled orange action per area; make the next step of the pipeline the filled button and the rest secondary.
- **Do** put text on `#f97316` in `#582200`, and white text only on `#c2410c` or darker.
- **Do** use amber for warnings and blockers, red for errors, green for success, sky for information, neutral for everything else.
- **Do** add colours, shadows, radii, type sizes and z-indexes as tokens in `tokens.css` (light and dark together), never as literals in `style.css`.
- **Do** write labels in the second person, give buttons their verb and show the amount ("Build 4 packages"); show dates, work modes, sources and statuses as readable labels.
- **Do** bundle every asset (fonts, inline SVG); the UI makes no outbound requests.
- **Do** keep controls at 3:1 contrast and at least 24px targets; announce results and saves in live regions; restore focus after an action reloads the page.
- **Do** keep light as the default theme, with dark opt-in, applied before first paint.

### Don't:
- **Don't** use `#f97316` as a background behind white text or as text on white.
- **Don't** use orange for warnings, success, tags, avatars, chips or the active tab.
- **Don't** add resting shadows, text gradients, glass blur, neon glows or decorative motion; shadows follow state.
- **Don't** use glyph characters as icons (★ ✕ as decoration); use the SVG sprite.
- **Don't** use side-stripe borders as status marks; use a dot, a badge or a label.
- **Don't** frame the product as acting for the person (no auto-apply language, no urgency counters).
- **Don't** load fonts, icons, images or scripts from a CDN or any external host.
- **Don't** replace or redraw the mascot; use the supplied PNGs.
- **Don't** nest cards inside cards (kanban cards in a column are the only exception) or stack more than one dark block per page.
