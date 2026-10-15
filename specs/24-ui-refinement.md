# 24 — UI refinement: "The Quiet Cockpit"

**Status:** IN PROGRESS (decisions D1–D6 answered; slice 1 under way)

## 1. Problem

Spec 18 gave the UI an identity (orange, mascot, Plus Jakarta Sans, light by default). Three reviews of the shipped UI agree on what is wrong with it now, see [`docs/design-audit/`](../docs/design-audit/):

| Review | Verdict |
|---|---|
| `impeccable-critique.md` | 27/40. "Brand-specific skin on a template skeleton": the promise of *one orange next action* is broken on almost every screen |
| `impeccable-audit.md` | 11/20. Coherent system, uneven discipline: accessibility gaps, six stacked CSS passes, colours leaking out of `tokens.css` |
| `taste-audit.md` | "Calm and legible but undifferentiated": everything is a card and a pill, orange is the default tint, Home is the stock SaaS skeleton |

**Caveat:** all three were done by reading the source (the detector, a browser and the tests were blocked). Every `[P]` item must be confirmed in a real browser while implementing; nothing here is proven visually yet.

## 2. The new style (merged from the three reviews)

Name: **The Quiet Cockpit**. Same identity (orange, slate, mascot, Plus Jakarta Sans), different discipline: the interface goes neutral so that the one thing that matters on each screen can be orange.

1. **One orange voice.** Orange fills mean *the next action* and orange rings/badges mean *a match*; nothing else. Avatars, tags, generic badges, filter chips, the active tab and the KPI/step icons become neutral (new `--surface-neutral`/`--ink-neutral` tokens); links get an underline instead of a colour. Result: one filled primary per area (Home: the pipeline's next step; a job list: none per card, one at the head; a posting: the next stage action).
2. **Flat, with graded shapes.** No card inside a card (the top board, the workflow steps and the Closed group lose their outer surface; sections use a heading and dividers). Radii are graded (container 24 / row 12 / control 8). **Shape by role:** pill only for what can be pressed or removed (primary button, filter chip, tag); status badges are small rectangles; counts are plain tabular text.
3. **A real type scale.** Keep Plus Jakarta Sans. Add a 1.2-ratio scale, five weights (400/500/600/700/800), section titles one clear step above body, sentence-case labels (all caps only for the quietest cases), `text-wrap: balance`/`pretty`, 68ch measure on hints.
4. **Home is a cockpit, not a banner.** The slate hero becomes a slim header band (h1 "Home", one line of state, the next action, the mascot at 56–72 px); the three equal step cards become one vertical pipeline list with one control per row; the four KPI tiles become one inline strip; "What to do next" moves to the top; AI buttons say how much they will do ("Score 12 postings"); System check lives in Settings and appears on Home only when something fails.
5. **The posting page is a review workspace.** Posting text (not collapsed) beside the package; the verification shown as named checks with plain-sentence problems; CV and letter previewed inline; the header's primary is the next stage action, *Open posting* secondary, *Block* and *Hide* in a quiet *More* menu; the star leaves the `h1`.
6. **Slimmer job cards.** About eight elements instead of fourteen; *Build package* is secondary (the filled action sits at the board's head); *Hide* and *Not for me* merge into one dismiss with the reason and "never show again"; *I applied* moves to the detail page or an overflow menu.
7. **Interaction with feel.** One transition token, `:active` states, visible search focus, focus restored after live filtering and actions, view transitions between pages, `prefers-reduced-motion` respected, no hover lift that moves click targets, no neon glow on score rings.
8. **Accessibility as a floor.** Labels associated with every control (shared macro + a test that scans templates), names on interview controls, `role="status"`/`aria-live` for toasts, save state and the filter count, skip link, landmark labels, `aria-current`, 24 px minimum targets, accessible score ring, `aria-hidden` icons.
9. **Theming done properly.** `color-scheme`, theme set before first paint, shadows/scrims/glows as tokens with dark values, a dark hero/header that differs from cards, theme toggle reachable on small screens.
10. **Layout that fits a laptop.** Centered content, `dvh`, scrollable sidebar, the Applications board fitting 1280 px (tighter cards or a closed-stages strip, undo on stage change, "applied N days ago"), grids that stop stretching empty cards.
11. **Honest icons.** The "gear" is a sun today: redraw it (the sun moves to the theme toggle); retire the AI sparkle from decoration; replace text glyphs (★ ✕ → ←) with sprite icons.
12. **One voice in the copy.** "You/your" everywhere, nav labels *Home, Matches, Applications, Documents, Actions, Settings*, buttons carry their verb (not thirteen "Run"), no raw tokens (`onsite`, `apply/maybe/skip`, ISO dates, run ids).

**Inspirations to steer taste (not to copy):** Linear for a quiet, neutral surface with a single accent and dense lists; Stripe's dashboard detail pages for side-by-side review; Raycast for keyboard-first affordances. Operate mode (app UI): scanability and consistency outrank expression; the brand lives in details.

**Rejected from the reviews (with reason):** background photos and CDNs (offline rule), grain, glass, parallax and staggered entrance animations (a daily tool), swapping the font or the whole icon set, social/OG meta (the app is never shared), skeleton screens (requests are local and fast).

## 3. What does not change
Principles of `PRODUCT.md`, the security rules of spec 09, offline assets only, `tokens.css` as the single home of tokens (light and dark side by side), vanilla CSS/JS with no build step, the mascot, Plus Jakarta Sans, light by default. All 451 tests keep passing; text changes update their tests in the same slice.

## 4. Slices (each shippable, tested and documented on its own)

| # | Slice | Content | Needs a decision? |
|---|---|---|---|
| 1 | **Foundation** | Scale tokens (type, space, weight, z-index, shadows, scrims, `color-scheme`); consolidate `style.css` into one pass per component with **no visual change** (verified by computed-style diff and screenshots) | No |
| 2 | **Accessibility and theming floor** | Items 8 and 9, 404 page, skip link | No |
| 3 | **Surface language** | Items 1, 2, 3, 11: neutral tokens, shape by role, flattening, graded radii, type scale, icons | D1, D2 |
| 4 | **Interaction** | Item 7 and focus/scroll after actions (cheap path first: restore focus and position; in-place updates later) | D5 |
| 5 | **Home** | Item 4 | D1 |
| 6 | **Posting page and job cards** | Items 5 and 6 | D3, D4 |
| 7 | **Applications and Settings** | Item 10; Settings tabs that really work, one dirty-aware save, trimmed hints | D6 |
| 8 | **Voice** | Item 12 | No |
| 9 | **Close** | `DESIGN.md` refreshed (`/impeccable document`), `PRODUCT.md` corrections, a new `/impeccable audit` to compare scores, README/screenshots, spec 18 gets an addendum, this spec DONE | No |

## 5. Decisions (answered by the author: all as recommended)

- **D1 — Home hero:** replaced by the slim header band; the mascot at 56–72 px (kept in the sidebar, the header and empty states).
- **D2 — Orange scope:** the active nav item and tab become neutral with an orange indicator bar; avatars, tags and chips neutral.
- **D3 — Dismiss actions:** *Hide* merges into *Not for me* (the dialog offers "never show again").
- **D4 — Bulk and primary actions:** a single *Build packages for the top N* at the board's head (respecting `max_packages_per_day`); multi-select deferred.
- **D5 — Reload after actions:** cheap path first (restore focus and scroll, view transitions); in-place row updates later.
- **D6 — Sidebar:** keep the 248 px sidebar; revisit an icon rail after slice 7.

## 6. How it is applied
The Impeccable skill is the executor (Operate mode, *refinement preserves, redesign replaces*), one command per slice (`extract`, `harden`, `quieter` + `colorize`, `typeset`, `distill`, `shape` then `layout`, `adapt`, `clarify`, `polish`, `document`, `audit`). The taste skill (`redesign-existing-projects`) is a second reviewer after each visual slice, not an executor. Each slice: spec section → code → tests → before/after screenshots in a real browser (light, dark, 390 / 1280 / 1440 px) → README/spec updates → author review.

## 7. Tests
Existing smoke tests stay green. New ones per slice: no orphaned unlabelled control in any template; every status has a style rule; `color-scheme` and the early theme script present; skip link and `aria-current`; no raw tokens in rendered pages; the primary-action count per page; the board fits at 1280 px (browser check, recorded in the spec).

## 8. Tasks
- [x] Author answers §5.
- [x] Slice 1 — Foundation (see §10).
- [ ] Slices 2 to 9 of §4, each ticked here when shipped.
- [ ] README (UI section) and screenshots, `DESIGN.md`, `PRODUCT.md`, `design/README.md` and this spec marked done.

## 9. Acceptance criteria
- [ ] Every page shows at most one filled primary action per area, and it is the next step.
- [ ] A new `/impeccable audit` scores clearly above 11/20 and the critique above 27/40, with browser evidence this time.
- [ ] No control without an accessible name; toasts, saves and filter results are announced.
- [ ] The Applications board shows all five stages at 1280 px without horizontal scroll.
- [ ] Light and dark are both verified in a real browser; nothing loads from outside.

## 10. Slice 1 — Foundation (done)

**What changed (no visible change in the light theme).**
- `tokens.css` is now the single home of every color, shadow, glow, overlay, radius (`--r-full` added), weight, layer (`--z-*`), type-scale (`--text-xs…3xl`) and spacing (`--space-1…8`) value, light and dark side by side, with `color-scheme: light|dark`. The scale tokens are defined and adopted in slice 3.
- `style.css` went from six stacked passes (348 lines, 75 selectors declared more than once, four `@media (max-width: 860px)` blocks) to **one block per selector**, grouped by component, with a single responsive section at the end (961 lines, one declaration per line where a rule is long). **No color or shadow literal remains in it**; layers and shadows use tokens.
- Dead rules removed: `.chip-toggle`, `.filters*` (replaced by the filter bar), `dl.kv*`, `dl.profile*`. Their classes are not used by any template or script.
- The dark-only `.btn` border override (a specificity accident) became the `--btn-border` token.

**How it was verified.**
1. *Rule level:* every `(media context, selector)` pair has the same declarations after resolving tokens; the only differences are the removed dead rules and the dark `.btn` override (12 items).
2. *Whole-page computed styles:* 12 000 elements (about 60 properties each plus `::before`/`::after` and the layout rectangle) on 11 pages × 2 widths (1440 and 390 px) × 2 themes, before and after, in a real browser. **Light theme: 0 differences.** Dark theme: only the two items below.
3. *Cascade risks the check caught and fixed:* the merged `.badge` rule overrode the status colours (`.st-*`) and `.column h2` overrode the stage colours; both were reordered to keep the original winner.
4. New tests (`tests/test_css.py`): one rule per selector per context, no color/shadow/z-index literals in `style.css`, every `var(--x)` used is defined in `tokens.css`, dark overrides only existing tokens, scale tokens exist.

**Intended visual differences (dark theme only).**
- Primary and ghost buttons no longer draw a grey border: the old dark rule out-ranked `.btn.primary { border-color: transparent }` by accident.
- `color-scheme: dark` makes native controls (scrollbars, `<select>` popups, date pickers) follow the theme.
