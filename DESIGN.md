---
name: Job Hunter
description: A local-first job-search flight deck: a navy top bar, a four-stage pipeline that is the spine of every page, navy-tinted neutrals, one amber next action, a sunglasses-eagle copilot.
colors:
  primary: "#f5a524"
  primary-hover: "#e29210"
  on-primary: "#0f1b2d"
  orange: "#f5a524"
  on-orange: "#0f1b2d"
  orange-border: "#f0c274"
  accent-text: "#8f5400"
  badge-soft: "#fff3d9"
  slate: "#0f1b2d"
  on-slate: "#f4f7fb"
  canvas: "#f2f5f9"
  panel: "#ffffff"
  soft: "#f7f9fc"
  muted-surface: "#e9eef4"
  surface-neutral: "#e9eef4"
  ink-neutral: "#2d3f56"
  border: "#dbe2eb"
  btn-border: "#c3ccd8"
  control-border: "#6f7f95"
  ink: "#0f1b2d"
  muted: "#4a5a70"
  placeholder: "#5d6c82"
  focus-ring: "#0e7c86"
  info: "#0b6b75"
  info-soft: "#d6eff1"
  good: "#0a7347"
  good-soft: "#d6f2e3"
  good-fill: "#16a56a"
  warn: "#8a5200"
  warn-soft: "#fcefcb"
  warn-fill: "#d99100"
  bad: "#b3261e"
  bad-soft: "#fddcd8"
typography:
  display:
    fontFamily: "Bricolage Grotesque, Atkinson Hyperlegible Next, system-ui, sans-serif"
    fontSize: "2.6rem"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Bricolage Grotesque, Atkinson Hyperlegible Next, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Atkinson Hyperlegible Next, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 700
    lineHeight: 1.55
    letterSpacing: "normal"
  body:
    fontFamily: "Atkinson Hyperlegible Next, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  label:
    fontFamily: "Spline Sans Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "normal"
rounded:
  xs: "4px"
  sm: "6px"
  md: "10px"
  lg: "14px"
  xl: "18px"
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
    rounded: "{rounded.lg}"
    padding: "1.5rem 1.7rem"
  topbar:
    backgroundColor: "{colors.slate}"
    textColor: "{colors.on-slate}"
    padding: "0 1.5rem"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0.5rem 0.7rem"
---

# Design System: Job Hunter

## Overview

**Creative North Star: "The Flight Deck"**

Job hunting is a pipeline with four stages: Search, Score, Package, Apply. The interface shows it. A navy top bar carries the mascot, the wordmark and the six pages; under it, every page except Home shows a compact four-stage strip with the live count of each stage and one stage marked as the next step. Home owns the large version of the same pipeline, so a stranger sees what the product does in one glance. The palette is taken from the mascot: navy-tinted neutrals, teal for information and focus, and one amber accent (the beak) that always carries navy text.

Surfaces are flat. Job lists are rows with dividers; cards appear for real groupings (a form section, a package, a decision rail). Light is the default theme; dark is an opt-in toggle in the top bar with the same roles, applied before first paint. The voice is plain and addressed to you ("Your application", "Mark as applied", "Score 12 postings"): buttons carry their verb and the amount. Nothing suggests the tool acts for the person, and it is local: fonts are bundled, icons are inline SVG, nothing is fetched from outside.

**Key Characteristics:**
- Navy top bar, four-stage pipeline strip, white panels on a cool canvas (`#f2f5f9`), hairline `#dbe2eb` borders, shadows only on state.
- One amber voice: the filled primary button (at most one per area), match rings, the current-stage marker and the "Hunter" in the wordmark. Navy text on amber, never white. Avatars, tags, chips, counts and tabs are neutral.
- Status hues (green, amber-brown, red, teal) are separated from the accent by use: warnings are tinted chips and callouts, never filled buttons or stage markers.
- Three bundled variable fonts with distinct jobs: Bricolage Grotesque for display, Atkinson Hyperlegible Next for the interface, Spline Sans Mono for scores, counts and logs.
- WCAG AA contrast for text, 3:1 for control borders, focus and rings; `prefers-reduced-motion` honoured.
- All values live in `static/tokens.css`; `static/style.css` has no colour, shadow, font-size or z-index literals (enforced by `tests/test_css.py`).

## Colors

### Primary
- **Beak Amber** (`#f5a524`, dark `#f5b13a`): the filled primary button, rings, the current-stage number chip and the wordmark's "Hunter". It always carries **Navy Ink** (`#0f1b2d`) text.
- **Beak Amber, pressed** (`#e29210`): primary hover.
- **Amber Text** (`#8f5400`, dark `#f5b13a`): the accent as text on light surfaces.

### Secondary
- **Deep Navy** (`#0f1b2d`, dark `#16233a`): the top bar, toasts and the "not for me" notice.

### Tertiary
- **Teal** (`#0b6b75` on `#d6eff1`, focus ring `#0e7c86`): information, early application stages and keyboard focus.

### Neutral
- **Cool Canvas** (`#f2f5f9`), **Panel White** (`#ffffff`), **Mist** (`#f7f9fc`), **Fog** (`#e9eef4`): page, cards, wells, tab track and hover rows.
- **Ink Neutral** (`#2d3f56`), **Ink** (`#0f1b2d`), **Slate Text** (`#4a5a70`), **Placeholder** (`#5d6c82`).
- **Hairline** (`#dbe2eb`), **Button Border** (`#c3ccd8`), **Control Border** (`#6f7f95`, 3:1 on white).

### Status
- **Good** (`#0a7347` on `#d6f2e3`, fill `#16a56a`): packaged, selected, passing checks, high score.
- **Warn** (`#8a5200` on `#fcefcb`, fill `#d99100`): blockers, maybe verdicts, below-threshold. It sits in the same hue family as the accent, so it only appears as tinted text and chips, never as a filled control.
- **Bad** (`#b3261e` on `#fddcd8`): rejected, errors, danger actions.

### Named Rules
**The One Voice Rule.** Amber means "act here" or "this matches". Information is teal, status is green, amber-brown or red, everything else is neutral.
**The Navy-On-Amber Rule.** Text on the accent is navy. White text never sits on amber.

## Typography

**Fonts:** Bricolage Grotesque (display), Atkinson Hyperlegible Next (interface), Spline Sans Mono (scores, counts, logs, eyebrows). All bundled as variable woff2 (latin and latin-ext subsets, licences next to the files), with system fallbacks. Cyrillic and Greek fall back to the system font.

**Character:** Display type is large and tightly tracked (`text-wrap: balance`); the interface face is chosen for legibility at small sizes; numbers are monospaced so scores and counts never shift width. Paragraphs use `pretty`.

### Hierarchy (scale tokens)
- **Display** (800, `--text-2xl` 2.6rem, -0.04em): the page `h1`; the stage counts on Home use `--text-3xl`.
- **Headline** (700, `--text-md` 1.125rem): card and section titles.
- **Title / body** (700 / 400, `--text-base` 15px, 1.55): job-row titles and copy; secondary text is `--text-sm`.
- **Label / eyebrow** (500, mono, `--text-sm`): section labels and the pipeline eyebrow; **all caps only** for `.verdict` and filter names, enforced by a test.
- **Reading text** (400, `--text-base`, 1.65, 68ch): the posting text, prose in the body face.
- Weights are 400/500/600/700/800 only.

## Layout

A sticky 56px navy top bar (mascot, wordmark, six links, "100% local" note, theme toggle), then the pipeline strip, then one centred column (max 78rem). Home: a header with the value proposition and the one next action, the large four-column pipeline, notes when something needs attention, the top matches, "Your applications", then the funnel and the "left out" bars. Matches: tabs, a connected filter bar, the top board, then rows (avatar, title, chips, reason, ring, one button and a ⋯ menu). The posting page: the posting on the left (header, "Why it matches", posting text, criteria, history) and a sticky decision rail on the right (score ring, the one primary action, package, your application). The remaining pages (Applications, Documents, Actions, Settings) use the same shell and tokens.

Spacing uses the `--space-1…8` scale. Below 1100px the grids narrow; below 860px the top bar wraps with the nav as a scrolling second row, the strip becomes 2x2, the rail drops under the posting, and everything is one column. Targets are at least 24px; there is a skip link, landmarks, and `aria-current` on the active nav item and tab.

## Elevation & Depth

Flat by default: panels on the canvas, 1px hairlines and Fog wells. Shadows respond to state: hover, menus and floating layers (run dock, notices, dialogs). The halo is reserved for the filled primary button. Focus is a 3px teal outline with a 2px offset (a glow plus ring border on form fields).

## Shapes

Shape follows role: containers are 14px, inner tiles 10px, controls 6px, badges and metadata chips 4 to 6px rectangles. Full pills are reserved for what you press or remove: the primary button, filter chips and tags. The circular score ring is the signature form. Company avatars are neutral rounded squares with initials; nothing external is fetched. The mascot sits on the top bar with no tile behind it.

## Components

### Buttons
- **Primary** (at most one filled per area): amber fill, navy text, weight 600, pill, halo; the pressed state scales to 98%.
- **Secondary:** white fill, 1px Button Border, 6px radius, ink text. **Ghost** and **Danger** (red text) for the rest.
- **Icon button / ⋯ menu:** 24px+ target; `details.more` menu closes on outside click, item click and Esc.

### Pipeline strip and Home flight deck
- **Strip:** an ordered list of four links (number chip, stage title, mono count). The current stage has a faint amber wash and an amber number chip; the others have neutral chips.
- **Flight deck (Home):** the same four stages as large columns with a display-size count, one state line and count-aware buttons ("Score 12 postings"). The current stage has the wash and a "Next" badge and no extra primary button. The columns rise in once on load (reduced-motion safe).

### Chips, Badges and Tags
Chips: Mist fill, hairline border, 6px (variants good, warn, link, stage colours). Badges: status rectangles with soft fills, neutral by default. Tags and active filters: neutral pills with a remove button; no amber.

### Match score ring (signature)
A conic-gradient circle on a Fog track with an inner disc and a bold mono number (`role="img"` with a text alternative). Colour encodes quality: red, amber, green; un-scored postings show a muted dash. It appears at 56px in rows and 96px in the posting rail.

### Run dock and toasts
A bottom-right panel with a pulsing dot while running, a mono log and a "Refresh page" footer. Toasts are ink pills (`role="status"`).

## Do's and Don'ts

### Do:
- **Do** keep at most one filled amber action per area; make the next step of the pipeline the filled button and the rest secondary.
- **Do** put navy text on amber fills.
- **Do** add colours, shadows, radii, type sizes and z-indexes as tokens in `tokens.css` (light and dark together), never as literals in `style.css`.
- **Do** write labels in the second person, give buttons their verb and show the amount ("Build 4 packages").
- **Do** bundle every asset (fonts, inline SVG); the UI makes no outbound requests.
- **Do** keep controls at 3:1 contrast and at least 24px targets; announce results in live regions.
- **Do** keep light as the default theme, with dark opt-in, applied before first paint.

### Don't:
- **Don't** put white text on amber, or use amber text on white below `#8f5400`.
- **Don't** use amber for tags, avatars, chips or the active tab, and don't use the warn colour for fills or the current-stage marker.
- **Don't** add resting shadows, text gradients, glass blur, neon glows or decorative motion beyond the single entrance of the Home pipeline.
- **Don't** use glyph characters as icons; use the SVG sprite.
- **Don't** use side-stripe borders as status marks; use a chip, a badge or a label.
- **Don't** frame the product as acting for the person (no auto-apply language, no urgency counters).
- **Don't** load fonts, icons, images or scripts from a CDN or any external host.
- **Don't** replace or redraw the mascot, or put it on a background tile; use the supplied PNG.
- **Don't** nest cards inside cards (kanban cards in a column are the only exception).
