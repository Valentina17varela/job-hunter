---
name: Job Hunter
description: A bright, warm, local-first job-search cockpit with a sunglasses-eagle copilot and one orange next action.
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
  border: "#e2e8f0"
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
    fontSize: "2.25rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "2rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "1.1rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  label:
    fontFamily: "Plus Jakarta Sans, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.06em"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  full: "999px"
spacing:
  xs: "0.35rem"
  sm: "0.6rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2.75rem"
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
    rounded: "10px"
    padding: "0.6rem 1.1rem"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "10px"
    padding: "0.6rem 1.1rem"
  chip:
    backgroundColor: "{colors.soft}"
    textColor: "{colors.muted}"
    rounded: "{rounded.full}"
    padding: "0.14rem 0.6rem"
  badge-match:
    backgroundColor: "{colors.orange-soft}"
    textColor: "{colors.primary}"
    rounded: "{rounded.full}"
    padding: "0.14rem 0.6rem"
  card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "1.5rem 1.7rem"
  job-card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xl}"
    padding: "1.15rem 1.4rem"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 0.7rem"
  hero:
    backgroundColor: "{colors.slate}"
    textColor: "{colors.on-slate}"
    rounded: "{rounded.xl}"
    padding: "2.4rem 2.6rem"
---

# Design System: Job Hunter

## Overview

**Creative North Star: "The Co-Pilot Cockpit"**

A bright, warm instrument panel for one person's job search. The sunglasses-eagle mascot is the copilot: it sits in the sidebar and on the Home hero, and the rest of the interface behaves like a well-labelled cockpit. Every stage of the pipeline (search, matches, package, apply, track) has a visible state and one clearly marked next action, and orange is reserved for that action and for match signals. White panels sit on a faintly cool canvas (`#f8f9ff`); dense data lives on hairline-bordered cards; deep slate is used once per page, for the hero.

The voice is friendly and precise. The mascot and the orange give warmth; exact numbers, plain labels and visible checks (blockers, verification, spend) give trust. Density is moderate: generous card padding and 24px corners keep the screen calm, while tabular figures, ring scores and compact chips let a person scan many postings quickly. Light is the default theme; dark is an opt-in toggle in the sidebar that keeps the same roles with lifted orange (`#f97316` primary) and tonal navy surfaces.

The system rejects anything that suggests the tool acts on the person's behalf: no urgency theatre, no pushy "apply now" framing, no dark patterns, no decorative motion. It is local, so nothing is fetched from outside: fonts are bundled, icons are inline SVG, there are no CDNs.

**Key Characteristics:**
- White cards on a cool canvas, hairline `#e2e8f0` borders, flat at rest, orange-tinted lift on hover.
- One orange voice: filled primary button, active nav, match rings and tags. Everything else is slate and neutral.
- Plus Jakarta Sans everywhere, tight tracking on headlines, tabular figures for scores, salaries and counts.
- Pill shapes for actions and chips; 24px containers; 8px form controls.
- Semantic status colors (good, warn, bad, info) are distinct from the brand orange so warnings never read as actions.
- WCAG AA contrast for text and 3:1 for control borders, focus and rings.

## Colors

A warm-orange and deep-slate palette over cool white, with separate semantic hues so status never competes with the brand.

### Primary
- **Cockpit Orange, deep** (`#c2410c`): the filled primary button, active tab and nav text, links, accent text and the focus ring. Chosen over the lighter brand orange because white text on `#f97316` fails contrast (2.8:1); `#c2410c` reaches 5.2:1.
- **Cockpit Orange, pressed** (`#9d4300`): primary hover.
- **Beacon Orange** (`#f97316`): brand fill that carries dark text (`#582200`), plus rings, bars, the halo, and the hero glow. Never behind white text.
- **Beacon Tint** (`#fff7ed`): soft fill for match badges, active nav, selected chips and tags; paired with the `#fdba74` orange border.

### Secondary
- **Deep Slate** (`#0f172a`): the Home hero panel and toasts; the one dark block per page. `#ffffff` text.

### Tertiary
- **Sky Info** (`#0369a1` on `#e0f2fe`): informational metrics, the "applied" progress node, links that must stay calm.

### Neutral
- **Cool Canvas** (`#f8f9ff`): page background, with a faint orange radial glow at the top-left (`rgba(249,115,22,.07)`).
- **Panel White** (`#ffffff`): cards, inputs, dialogs.
- **Mist** (`#f8fafc`) and **Fog** (`#f1f5f9`): wells, tab tracks, kanban columns, inactive panels.
- **Hairline** (`#e2e8f0`): decorative borders on cards and dividers.
- **Control Border** (`#8391a7`): input, select and button borders; 3:1 against white.
- **Ink** (`#111827`), **Slate Text** (`#475569`), **Placeholder** (`#64748b`).

### Status
- **Good** (`#047857` on `#d1fae5`, fill `#10b981`): packaged, apply verdict, passing checks, salary.
- **Warn** (`#92400e` on `#fef3c7`, fill `#f59e0b`): blockers, maybe verdicts, flags, calendar items. Amber, never orange.
- **Bad** (`#ba1a1a` on `#ffdad6`): rejected, errors, danger actions.

### Named Rules
**The One Voice Rule.** Orange means "act here" or "this matches". Status uses green, amber, red; information uses sky. A screen with orange on everything has no next action.
**The Dark-Text-On-Bright-Orange Rule.** Text on `#f97316` is `#582200`; white text only sits on `#c2410c` or darker.
**The Warning Is Amber Rule.** A warning never uses the brand orange, so it cannot be confused with a primary action.

## Typography

**Display Font:** Plus Jakarta Sans (bundled variable woff2, weights 200-800), fallback system-ui.
**Body Font:** Plus Jakarta Sans.
**Label/Mono Font:** same family for labels; `ui-monospace, "SF Mono", Menlo, monospace` only for `code`, `pre` and logs.

**Character:** One rounded geometric family does everything. Weight and tracking carry hierarchy: heavy, tightly tracked headlines for page and job titles; regular body; semi-bold uppercase labels.

### Hierarchy
- **Display** (800, 2.25rem hero / 2rem page h1, 1.2, -0.035em): page titles and the Home hero line.
- **Headline** (700, 1.1rem, -0.01em): card and section titles (`h2`).
- **Title** (700, 1.05rem): job titles, kanban card titles, step titles.
- **Body** (400, 15px, 1.55): everything else; descriptions capped near 60ch (`.page-head p`).
- **Label** (700, 0.72-0.78rem, +0.06em, uppercase): group headings, filter labels, table headers, eyebrow pills.
- **Metric** (800, 1.7-1.8rem, -0.02em): KPI numbers and hero stats; the ring score is 750 at 34% of ring size.

### Named Rules
**The Tabular Figures Rule.** `font-variant-numeric: tabular-nums` is on at the body level; scores, salaries and counts never shift width.

## Layout

A fixed 248px sticky sidebar plus a single scrolling main column (max 1320px, padding 2.1rem 2.75rem). Pages are stacks of cards; rows are CSS grids: KPIs `auto-fit minmax(210px, 1fr)`, steps `minmax(240px, 1fr)`, `grid-2` at 360px, `grid-3` at 290px, and the applications board as five equal columns. Spacing uses a 0.35 / 0.6 / 1 / 1.5 / 2.75rem rhythm, with card padding 1.5rem. A floating run dock sits bottom-right; the toast and the "not for me" undo notice float bottom-center.

Below 860px the sidebar becomes a top bar with a horizontally scrolling nav, grids collapse to one column, KPIs to two, the kanban board scrolls horizontally in fixed 230px columns, and the settings save bar stays sticky at the bottom.

## Elevation & Depth

Tonal layering, flat at rest. Depth comes from white panels on the cool canvas, 1px hairline borders, and the Fog wells behind them. Shadows are a response to state, not decoration.

### Shadow Vocabulary
- **Resting card** (`box-shadow: 0 1px 2px rgba(15,23,42,.04)`): barely there; sets the card off from the canvas.
- **Hover lift** (`0 8px 24px rgba(249,115,22,.12)` + border `#fdba74`): job cards, KPI tiles and kanban cards when pointed at.
- **Halo** (`0 8px 22px rgba(249,115,22,.28)`): reserved for the filled primary button and the numbered step badges.
- **Ring glow** (`0 0 0 4px panel, 0 0 18px -2px <ring color 35%>`): the circular match score.
- **Floating layers** (`0 18px 50px rgba(15,23,42,.28)`): run dock, notices; modals use `0 30px 80px rgba(15,23,42,.35)` over a blurred `rgba(15,23,42,.55)` scrim.
- **Focus** (`3px outline #c2410c, offset 2px` for buttons and links; `0 0 0 3px rgba(249,115,22,.22)` glow with an orange border for form fields).

### Named Rules
**The Flat-By-Default Rule.** Surfaces carry at most the resting hairline shadow. Orange-tinted lift appears only on hover, focus and floating layers.
**The Halo Is Earned Rule.** The orange halo belongs to the primary action and the step badges; nothing else glows.

## Shapes

Generous soft geometry: 24px containers (cards, hero, columns, empty states), 16px medium containers (panels, filter bar), 12px inner tiles (kanban cards, callouts, `pre`), 8px controls (inputs, selects), and full pills for every action button, chip, badge, tab and tag. The circular score ring and the 44px rounded-square logo tile are the two signature forms. Borders are 1px solid `#e2e8f0`; empty states use a dashed border. Company avatars are rounded squares (radius 30% of size) with initials, not logos, because nothing external is fetched.

## Components

### Buttons
- **Shape:** pill (`999px`) for primary and small primary; 10px for secondary and ghost.
- **Primary:** `#c2410c` fill, white text, weight 600, `0.6rem 1.1rem`, orange halo. Hover goes to `#9d4300` with a 1px lift.
- **Secondary:** white fill, 1px `#cbd5e1` border (darker in dark theme), ink text; hover turns the border orange.
- **Ghost:** transparent, slate text, Fog wash on hover. Danger text is `#ba1a1a`.
- **Focus / disabled:** 3px orange outline with 2px offset; disabled is 50% opacity with no lift.

### Chips and Badges
- **Chip:** Mist fill, hairline border, slate text, weight 600, pill. Variants: good (salary), warn, link.
- **Badge:** Beacon Tint fill with deep-orange text; status variants (good, warn, bad) switch to their soft fills.
- **Tag** (editable list items): Beacon Tint with an orange-border, an inline remove button.
- **Active filter chip:** Beacon Tint, orange border, bold, with an "x" button.

### Cards / Containers
- **Card:** white, 1px hairline, 24px radius, padding 1.5rem 1.7rem, resting shadow.
- **Job card:** same card language laid out as a row: company avatar, title and sub-line, chips, then the score ring and actions on the right.
- **Hero:** Deep Slate, 24px radius, orange radial glow in the top-right corner, eyebrow pill, 2.25rem white headline, the mascot at 150px with an orange drop-shadow.

### Inputs / Fields
- **Style:** white, 1px `#8391a7` border, 8px radius, `0.5rem 0.7rem`; placeholder `#64748b`.
- **Focus:** border turns `#c2410c` with a 3px `rgba(249,115,22,.22)` glow.
- **Error:** border `#ba1a1a` and bold red helper text. Checkbox and radio use `accent-color: #c2410c`.
- **Filter bar:** one connected white row with a Mist search field and labelled select pills that tint orange when active.

### Navigation
- **Sidebar:** logo tile plus wordmark ("Job" ink, "Hunter" orange, 800) with a one-line tagline; nav items are 12px-radius rows with an 18px icon, slate text, weight 600.
- **Active:** Beacon Tint fill, deep-orange text, and a 4px orange bar on the sidebar's edge.
- **Tabs:** a Fog pill track with white pill selection and a faint shadow; scrolls horizontally on small screens.
- **Side card:** dashed border "100% local" note plus the theme toggle.

### Match score ring (signature)
A 56px conic-gradient circle on a Fog track with an inner white disc and a bold tabular number. Color encodes quality: red (0-1), amber (2), green (3-4); un-scored postings show a muted dash. It carries the glow of its own color, never orange by default except as fallback.

### Pipeline steps and kanban
- **Steps:** white 24px cards with a numbered orange badge and an orange arrow connecting them.
- **Board:** five Fog columns with uppercase labels and a 4px colored top rule per stage; cards are 12px-radius white tiles with a stage select.

### Run dock and toasts
A bottom-right panel with a pulsing amber dot while running (green when done, red on failure), a monospaced log, and a primary "Refresh page" footer. Toasts are ink pills at the bottom center; the "not for me" undo notice is a slate pill with an orange border.

## Do's and Don'ts

### Do:
- **Do** keep one primary orange action per area; make the next stage of the pipeline the filled button.
- **Do** put text on `#f97316` in `#582200`, and white text only on `#c2410c` or darker.
- **Do** use amber (`#92400e` / `#fef3c7`) for warnings and blockers, red for errors, green for success, sky for information.
- **Do** bundle every asset (fonts, inline SVG icons); the UI makes no outbound requests.
- **Do** keep controls at 3:1 contrast (`#8391a7` borders) while decorative card borders stay `#e2e8f0`.
- **Do** use tabular figures for scores, salaries, dates and counts; show company avatars as initials.
- **Do** show the mascot at the Home hero (150px), the sidebar tile (38px), empty states and the favicon set, always on a light or slate surface where the navy reads.
- **Do** keep light as the default theme and keep dark opt-in via the sidebar toggle.

### Don't:
- **Don't** use `#f97316` as a background behind white text, or `#ea580c` as text on `#fff7ed`; both fail contrast.
- **Don't** use orange for warnings or success; it is the action color.
- **Don't** add drop shadows to cards at rest, gradients on text, glass blur on content cards, or decorative motion; shadows follow state.
- **Don't** frame the product as acting for the person (no auto-apply language, no urgency counters); a person reviews and applies.
- **Don't** load fonts, icons, images or scripts from a CDN or any external host.
- **Don't** replace the mascot with an invented logo or redraw it; use the supplied PNGs.
- **Don't** nest cards inside cards or stack more than one slate hero per page.
