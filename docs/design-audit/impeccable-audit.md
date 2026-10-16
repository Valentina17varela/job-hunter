⚠️ DEGRADED: single-context (source review only). The detector (`impeccable detect`), `pytest`, `check_docs.py`, a browser and sub-agents did not run because Bash and Agent calls were blocked in this session. Every finding below was read in source. Items that need a browser or a screen reader are tagged **[P]** (plausible, unverified). Items read directly in code are tagged **[S]**. Values marked **[C]** were computed by hand from the tokens.

# Impeccable Audit: whole web UI

Target: `src/jobhunter/web/` (templates, `static/tokens.css`, `static/style.css`, `static/app.js`, `app.py` routes and headers).
Scope: accessibility, responsive, theming, performance, anti-patterns.
Standard: WCAG 2.2 AA (project working target, `PRODUCT.md`), `DESIGN.md` ("The Co-Pilot Cockpit"), CLAUDE.md UI rules.
Mode: audit only. No file was modified except this report.

Pages covered: Home, Job matches (list and Top 5 board), posting detail, Applications, Documents, Actions, Settings, the "Add posting" and "Not for me" dialogs, the run dock, toast and undo notice.

## Audit Health Score

| # | Dimension | Score | Key finding |
|---|---|---|---|
| 1 | Accessibility | 2 / 4 | Unassociated Settings labels, unnamed interview controls, silent status updates, focus reset by full reload |
| 2 | Performance | 3 / 4 | Cheap server work and no external requests; missing cache headers and font preload, fixed-attachment gradient, reload after every action |
| 3 | Theming | 2 / 4 | Good token set and dark variant; colours leak outside `tokens.css`, theme applied late (flash), no `color-scheme`, unstyled statuses |
| 4 | Responsive Design | 2 / 4 | Board switches to scrolling columns at 1280px, targets under 44px, fixed-width rows, sticky bars on every form |
| 5 | Implementation Integrity | 2 / 4 | Six layered CSS passes with overrides, orange used for too many roles, docs drift from code |
| | **Total** | **11 / 20** | **Acceptable** |

Band: 10-13 Acceptable (significant work needed).

## Implementation Integrity Verdict

**Verdict: coherent system, uneven discipline.** This is not template output. There is a documented token set, a real brand asset, a purposeful palette split (orange for act and match, amber/green/red/sky for status), bundled fonts and inline SVG, and a `<dialog>`-based modal layer. What weakens it is accumulation, not taste:

- `style.css` is six stacked passes (base, refinement, second, polish, spec 22, spec 23) with the same selectors redefined later. The cascade is the real source of truth, so the file cannot be read top to bottom. See finding 18.
- Orange does more jobs than `DESIGN.md`'s One Voice Rule allows (active nav, links, tags, badges, rings, filter chips, halos, hero glow). See finding 17 and the critique.
- Code and docs disagree in three places (board breakpoint, "no decorative motion", dark theme "undecided"). See finding 25.

## Executive Summary

- Findings: **26** (P0: 0, P1: 4, P2: 14, P3: 8).
- No blocker that stops use. The P1s are all accessibility defects with small, local fixes.
- Top issues:
  1. Settings form fields are not programmatically labelled (finding 1).
  2. Interview rows on the posting page have controls with no accessible name (finding 2).
  3. Toasts, save state and live-filter results are never announced (finding 3).
  4. Every row action ends in `location.reload()`, which resets scroll and focus (finding 4).
  5. Theme is applied after first paint and native controls ignore the dark theme (findings 9, 10).
- Next steps: fix the four P1s as one accessibility task, then move hard-coded colours into `tokens.css`, then tackle the responsive and cache items. Per CLAUDE.md, each needs an approved spec in `specs/` before code.

## Detailed Findings by Severity

### P1 Major

**[P1] 1. Settings labels are not associated with their fields** [S]
- Location: `templates/settings.html`, `field` macro (prints `<label class="flabel">` with no `for` and no wrapper around the control).
- Category: Accessibility
- Impact: A screen reader announces an unnamed edit field for every Settings input. Clicking the label does not focus the field. Voice-control users cannot say the field name. Settings is the highest-stakes form (budget, filters, LLM backend).
- WCAG: 1.3.1 Info and Relationships (A), 3.3.2 Labels or Instructions (A), 4.1.2 Name, Role, Value (A).
- Recommendation: In the macro, generate an `id` per field (from the config key) and emit `for`, or wrap the control in the `<label>`. Keep `data-cfg` attributes unchanged so the JS and tests still match. Add `aria-describedby` for hint text.
- Suggested command: `/impeccable harden`

**[P1] 2. Interview rows on the posting page have unnamed controls** [S]
- Location: `templates/job.html`, interview list (`data-field` selects for kind and outcome, a `datetime-local` input, a notes input).
- Category: Accessibility
- Impact: Four controls per interview are announced as bare "combo box" or "edit text". The repeated rows make it impossible to tell which interview a control edits.
- WCAG: 4.1.2 (A), 1.3.1 (A), 3.3.2 (A).
- Recommendation: Add `aria-label` such as "Interview 2 kind", "Interview 2 date and time", "Interview 2 notes". The project rule already requires `aria-label` on controls without a visible label (CLAUDE.md, Tests).
- Suggested command: `/impeccable harden`

**[P1] 3. Status changes are never announced** [S] (behaviour with a screen reader [P])
- Location: `templates/base.html` (`#toast` has no role; `#top-notice` has `role="status"`; `.save-state` in Settings is plain text), `static/app.js` (live filter replaces `#jobs-results.innerHTML`; save handlers write `.save-state`).
- Category: Accessibility
- Impact: "Saved", "Hidden", "Copied" and error toasts appear and vanish with no announcement. After typing in the filter, the result list changes with no "N postings" message, so a screen-reader user cannot tell the filter did anything. Failed saves are as silent as successful ones.
- WCAG: 4.1.3 Status Messages (AA).
- Recommendation: Give `#toast` `role="status"` (and `role="alert"` for errors), give `.save-state` `aria-live="polite"`, and add a visually hidden live region for the filter count ("12 postings"). The undo notice already shows the right pattern. Keep the toast visible long enough to read (a 5s minimum is common).
- Suggested command: `/impeccable harden`

**[P1] 4. Every action reloads the page and resets scroll and focus** [S]
- Location: `static/app.js`, `act()` (calls `location.reload()` after each `data-post` action and stage change); live filter falls back to `location.href` on error.
- Category: Accessibility and Performance
- Impact: Starring, dismissing, changing a stage or deleting a package re-requests the whole page, re-runs every SQL query, re-decodes the font and returns the user to the top with focus on `<body>`. A keyboard user loses their place in a 50-row list after each action. A screen reader re-reads the page. It also makes the (mild) theme flash in finding 9 happen on every click.
- WCAG: 2.4.3 Focus Order (A), 3.2.2 On Input (A) [P].
- Recommendation: Update the affected row or card in place (the response already returns JSON), or at minimum restore scroll position and refocus the same control after reload (store the element's `data-*` key in `sessionStorage`). Announce the result through the live region from finding 3.
- Suggested command: `/impeccable optimize`

### P2 Minor

**[P2] 5. Links are only distinguishable by colour inside muted text** [C]
- Location: `static/style.css` `a { color: var(--accent-text) }`, underline only on `:hover`.
- Category: Accessibility
- Impact: `#c2410c` links against ink (`#111827`) are about 3.2:1, but inside `--muted` (`#475569`) paragraphs the difference is roughly 1.4:1. Only hue marks them as links, which fails for colour-blind users and in the dark theme's lifted orange.
- WCAG: 1.4.1 Use of Color (A).
- Recommendation: Underline inline links in running text (`text-decoration: underline; text-underline-offset: .15em`), keep the no-underline style only for nav and buttons.
- Suggested command: `/impeccable polish`

**[P2] 6. Several targets are smaller than 24 by 24 CSS px** [S] (spacing exception [P])
- Location: `.star` (about 22 by 18px: font 1.15rem, padding `0 .25rem 0 0`), `.tag button` and `.afchip button` (1.4rem, about 22px), `.icon-btn`; `.btn.small` is about 32px high.
- Category: Accessibility and Responsive
- Impact: The star is the primary quick action on every posting row. Small, close targets cause mis-taps and are hard for tremor or touch use.
- WCAG: 2.5.8 Target Size (Minimum) (AA). Best practice 44px.
- Recommendation: Give interactive icons a 24px minimum box (`min-width/min-height`, padding instead of font size), and 44px on `(pointer: coarse)`. This stays inside tokens.css if a `--hit` token is added.
- Suggested command: `/impeccable adapt`

**[P2] 7. No skip link, unlabelled landmarks, no `aria-current`, tabs without state** [S]
- Location: `templates/base.html` (sidebar `<aside>` and `<nav>` have no labels; nav items use the `on` class only; no skip link); `static/app.js:257-260` (Settings tabs only toggle `.on`).
- Category: Accessibility
- Impact: Keyboard users tab through the whole sidebar (logo, 6 links, theme toggle, side card) on every page before reaching content. Screen readers cannot tell the current page or the selected Settings tab. The `<main>` landmark and single `h1` are correct.
- WCAG: 2.4.1 Bypass Blocks (A), 4.1.2 (A), 1.3.1 (A).
- Recommendation: Add a visually hidden "Skip to content" link targeting `<main id="main">`, `aria-label` on `<nav>` and `<aside>`, `aria-current="page"` on the active nav link, `role="tablist"/"tab"/"tabpanel"` with `aria-selected` (or `aria-current` if they stay links) on Settings and the jobs tabs, and `aria-pressed` on the theme toggle.
- Suggested command: `/impeccable harden`

**[P2] 8. No `prefers-reduced-motion`; one infinite animation** [S]
- Location: `static/style.css` `.dock-dot` (pulses infinitely while running); hover `transform: translateY(-1px)` on buttons and cards; toast and dock transitions.
- Category: Accessibility
- Impact: Motion cannot be turned off. The pulse is paired with text ("Running"), so this is a courtesy fix, but it contradicts `DESIGN.md` ("no decorative motion").
- WCAG: 2.3.3 Animation from Interactions (AAA), 2.2.2 Pause, Stop, Hide (A) for any auto-playing motion over 5s [P].
- Recommendation: One `@media (prefers-reduced-motion: reduce)` block that disables the pulse, the lift transforms and the transitions.
- Suggested command: `/impeccable animate`

**[P2] 9. Theme is applied at the end of `<body>`, so dark users may see a light flash on every load** [S] (flash itself [P])
- Location: `templates/base.html` (no inline script in `<head>`), `static/app.js` (reads `localStorage` key `jh_theme` after the body has parsed).
- Category: Theming
- Impact: A dark-theme user gets a white frame before the script runs. Because finding 4 reloads the page after most actions, they see it constantly.
- Recommendation: Set `data-theme` on `<html>` from a tiny inline script in `<head>` (still offline and no external script; there is no CSP header in `app.py` to block it). If a strict CSP is added later, use a small blocking static `theme.js` in `<head>` instead.
- Suggested command: `/impeccable polish`

**[P2] 10. No `color-scheme` declaration, so native controls stay light in dark theme** [S: none found in `tokens.css` or the style.css rules reviewed] (rendering [P])
- Location: `static/tokens.css` (`:root` and `:root[data-theme="dark"]`).
- Category: Theming
- Impact: Scrollbars, `<select>` popups, `datetime-local` pickers, `<dialog>` default chrome and form autofill can render as light widgets on a navy page. The interview date picker and filter selects are the visible cases.
- Recommendation: Add `color-scheme: light` on `:root` and `color-scheme: dark` on the dark selector. It belongs in `tokens.css`.
- Suggested command: `/impeccable polish`

**[P2] 11. Colours hard-coded outside `tokens.css`** [S]
- Location: `static/style.css`: `.btn` border `#cbd5e1`; `rgba(249,115,22,…)` in `body` radial, `.hero::after`, `.hero-logo` drop-shadow; `rgba(15,23,42,…)` shadows on tab, dock, modal and notice; modal scrim `rgba(15,23,42,.55)`; `.toast` `rgba(0,0,0,.25)`; `.tag button:hover`, `.afchip button:hover` `rgba(0,0,0,.12)`; `.bar.warn` gradient.
- Category: Theming
- Impact: These do not change with the theme (only some have dark overrides), so dark mode inherits light-tuned shadows and scrims, and any palette change needs a CSS-wide search. It also breaks the stated rule that tokens live in `tokens.css`.
- Recommendation: Add `--shadow-float`, `--scrim`, `--glow` (as a channel triplet), `--btn-border` and `--overlay-hover` to `tokens.css` with dark values, then reference them. No new colours are introduced.
- Suggested command: `/impeccable extract`

**[P2] 12. Status classes do not cover every status** [S]
- Location: `app.py` `STATUS_LABELS` (14 statuses) versus the `.st-*` rules in `style.css`.
- Category: Theming and Implementation
- Impact: Statuses without a rule fall back to the neutral badge, so some states (for example ones the pipeline adds later) look identical to "new", which weakens the scan-by-colour model in `DESIGN.md`.
- Recommendation: Map each status to one of the four semantic pairs (info, good, warn, bad) or neutral on purpose, and add a test that fails when a status has no class.
- Suggested command: `/impeccable colorize`

**[P2] 13. Applications board turns into scrolling 230px columns at 1280px** [S]
- Location: `static/style.css` `.board` (`repeat(5, 230px)` at `max-width: 1280px`); `DESIGN.md` says this happens below 860px.
- Category: Responsive
- Impact: On a 1280 or 1366px laptop (the common case), the main column is about 1000px, so the last stage columns sit off-screen behind a horizontal scroll and cards in late stages (offers, rejected) are easy to miss. The switch itself is reasonable (five equal columns would be about 190px) but it is undocumented.
- Recommendation: Keep five columns down to about 1100px by tightening card padding, or collapse empty columns, and add a visible scroll affordance. Update `DESIGN.md` either way.
- Suggested command: `/impeccable adapt`

**[P2] 14. Fixed-width rows and always-sticky bars on small screens** [S] (layout [P])
- Location: `.funnel-row` (fixed 150/110/96px label columns, about 356px before the bar), `.grid-2` (min 360px) and `.grid-3` (min 290px) auto-fit tracks, `.form-actions` (sticky on every instance), inline widths in Settings, run dock width.
- Category: Responsive
- Impact: On a 360-390px phone the funnel bar gets almost no width, tracks wider than the viewport can overflow if the 860px collapse does not override them, and a sticky save bar plus the dock plus an on-screen keyboard can cover most of the screen. Mobile web is secondary in `PRODUCT.md`, so this is P2.
- WCAG: 1.4.10 Reflow (AA) [P].
- Recommendation: Use `minmax(min(100%, 360px), 1fr)`, let funnel labels shrink or stack under 480px, make the save bar sticky only when the form is dirty, and cap the dock at `calc(100vw - 2rem)`.
- Suggested command: `/impeccable adapt`

**[P2] 15. Static files have no cache policy and the font is not preloaded** [S] (timing [P])
- Location: `app.py` (`StaticFiles` mount, no `Cache-Control`); `templates/base.html` (no `<link rel="preload">` for `/static/fonts/PlusJakartaSans.woff2`); `asset_url` already adds an mtime `?v=`.
- Category: Performance
- Impact: Without `max-age`, browsers revalidate or heuristically cache `tokens.css`, `style.css`, `app.js` and the variable font on navigation. Combined with finding 4's reloads, text re-renders with `font-display: swap` fallback on each load. On localhost the cost is small but visible as a font flicker.
- Recommendation: Because `?v=` already busts the cache, serve `/static` with `Cache-Control: public, max-age=31536000, immutable`. Add a local `rel="preload" as="font" type="font/woff2" crossorigin` for the font. Both stay offline.
- Suggested command: `/impeccable optimize`

**[P2] 16. Fixed-attachment radial background and per-card glows** [S] (jank [P])
- Location: `style.css` `body { background-attachment: fixed }` with a radial gradient; `.ring` conic gradient plus glow box-shadow on every row; `backdrop-filter: blur(2px)` on the modal scrim.
- Category: Performance
- Impact: `background-attachment: fixed` forces a repaint of the whole viewport on scroll in several engines (notably Safari and some Chromium paths). With 50 rings each carrying a glow, long lists can stutter on low-power laptops. `DESIGN.md` also says nothing but the primary action may glow.
- Recommendation: Move the gradient to a `position: fixed; inset: 0; z-index: -1` pseudo-element (`will-change` not needed), drop the glow from rows or reduce it to hover, and keep the blur to the modal only.
- Suggested command: `/impeccable optimize`

**[P2] 17. Orange carries too many meanings** [S]
- Location: `tokens.css` and `style.css`: active nav, links, tags, match badges, rings, active filter chips, step badges, hero glow, halos, primary buttons.
- Category: Anti-pattern (design intent)
- Impact: `DESIGN.md`'s One Voice Rule says a screen with orange everywhere has no next action. On Jobs and Home, the primary button, a link, three badges and a nav item can all be orange at once, so "act here" is not unique. Related critique finding: next action clarity.
- Recommendation: Keep orange fill for the one primary action and match signals (ring, match badge). Move links, tags and active filter chips to ink/slate with an underline or sky tint.
- Suggested command: `/impeccable quieter`

**[P2] 18. Layered CSS with repeated selectors** [S]
- Location: `static/style.css` (349 lines, six passes labelled in the file: base, refinement, second, polish, spec 22, spec 23).
- Category: Implementation Integrity
- Impact: Later rules silently override earlier ones, so changing a value in the first block does nothing and the visible value lives in a different block. This is how `.btn` and `.tag button` ended up with unthemed colours (finding 11). It raises the cost of every other fix here.
- Recommendation: Consolidate per component in one pass, with no visual change, behind the existing smoke tests, before the colour migration.
- Suggested command: `/impeccable polish`

### P3 Low

**[P3] 19. Score ring has no accessible name; star toggle sits inside the `h1`** [S]
- Location: `templates/_macros.html` (`<span class="ring" title="AI match score">`), `templates/job.html` (star button inside `<h1>`).
- Impact: The number is readable text, but "AI match score" is only a tooltip, and the score is also colour-coded (red/amber/green) with no text for the band. The star inside the heading makes the page title read "Star Senior Engineer ...".
- WCAG: 1.4.1 (A), 4.1.2 (A).
- Recommendation: `role="img" aria-label="Match score 3 of 4, good"` on the ring, and move the star next to the `h1`.
- Suggested command: `/impeccable harden`

**[P3] 20. Table headers without `scope`; `target="_blank"` without `rel`** [S]
- Location: `templates/run.html` history table; PDF links in `packages.html`.
- Impact: Minor: assistive tech infers header scope in simple tables, and modern browsers imply `noopener`. New-tab links do not tell the user a tab will open.
- Recommendation: `scope="col"`, `rel="noopener"`, and "(opens in new tab)" in the link's accessible name.
- Suggested command: `/impeccable harden`

**[P3] 21. Native `confirm()` for Hide, Delete and Block** [S]
- Location: `static/app.js:515,519`.
- Impact: Accessible and keyboard-friendly, but unstyled, blocks the page and cannot name the posting. "Block this company" asks twice. It is inconsistent with the `<dialog>` used for "Not for me" and "Add posting".
- Recommendation: Reuse the `<dialog>` pattern with the company or posting name in the text and a clear destructive button. Optional.
- Suggested command: `/impeccable clarify`

**[P3] 22. Dark-theme hover overlay and button border** [S]
- Location: `.tag button:hover`, `.afchip button:hover` (`rgba(0,0,0,.12)`); `.btn` border `#cbd5e1` (about 1.5:1 on white) versus the `#8391a7` control rule in `DESIGN.md`.
- Impact: A black overlay on a navy chip is nearly invisible. The button border passes 1.4.11 only because the label identifies the button, which conflicts with the stated "controls at 3:1" rule.
- Recommendation: Use a tokenised overlay (`color-mix` with `--ink`) and decide whether buttons follow the 3:1 rule or the doc changes.
- Suggested command: `/impeccable colorize`

**[P3] 23. Very small uppercase labels** [S]
- Location: label style at 0.72-0.78rem, uppercase, +0.06em (about 11.5-12.5px).
- Impact: Legible but at the lower limit for filter labels and table headers, especially with Plus Jakarta's wide forms. Users who raise the browser font size are fine because it is in `rem`.
- Recommendation: Hold the floor at 0.75rem (12px) and keep weight 700.
- Suggested command: `/impeccable typeset`

**[P3] 24. Per-request config parse, DB connect, and 1s polling** [S] (impact [P])
- Location: `app.py` `cfg()` and `db()` run on every request; run dock polls `/api/runs/{id}` every second; `/jobs` uses a correlated `MAX(created_at)` subquery for scores.
- Impact: Fine for one local user and 50 rows. It would show up with a large `scores` table and no composite index on `(job_id, created_at)`, or with several tabs polling.
- Recommendation: Verify an index exists, back off polling after 10s, and close connections per request. Measure before changing.
- Suggested command: `/impeccable optimize`

**[P3] 25. Docs drift from code** [S]
- Location: `DESIGN.md` Layout section says the board scrolls only below 860px (code: 1280px); "no decorative motion" versus pulse and hover lift; `PRODUCT.md` lists "dark theme" as undecided, but a dark theme ships with a sidebar toggle.
- Impact: The next contributor or agent will trust the doc over the CSS.
- Recommendation: Update whichever side is wrong when the related finding is fixed (CLAUDE.md rule 4).
- Suggested command: `/impeccable document`

**[P3] 26. Hover lift on cards and buttons** [S]
- Location: `style.css` hover `transform: translateY(-1px)` with `.12s` transitions.
- Impact: Small and tasteful, but it contradicts `DESIGN.md` ("shadows follow state, no decorative motion") and moves click targets under the pointer.
- Recommendation: Keep border and shadow change on hover and drop the translate, or document it as allowed.
- Suggested command: `/impeccable quieter`

## Patterns & Systemic Issues

- **Labels and names are added by hand per control.** Findings 1, 2 and 19 are the same miss in three templates. A shared macro that requires a label (and a test that scans every template for unlabelled controls) would prevent repeats.
- **Feedback is visual only.** Findings 3 and 4 share one cause: actions finish with a reload or a transient toast instead of an announced in-place update.
- **Tokens exist but are not the only source of colour.** Findings 10, 11 and 22 are all colours or theme properties defined outside `tokens.css` or missing from it.
- **Layering over rewriting.** Finding 18 explains why findings 11, 22 and 26 persist.
- **Desktop-first sizing.** Findings 6, 13 and 14 all trace to fixed pixel widths and small icon targets tuned for a mouse.

## Positive Findings

- Offline discipline: no CDN, no external font, inline SVG icons, bundled Plus Jakarta Sans (`font-display: swap`). This matches the project constraint.
- Complete light and dark token set with lifted dark status colours and a stronger dark control border (`#5f6f88`).
- Control borders (`#8391a7`) and input focus meet 3:1; orange text and fill pairs were chosen for contrast (`#c2410c` with white, `#582200` on `#f97316`).
- Visible `:focus-visible` rings (3px, offset) on buttons, links, stars, summaries and tabs.
- `<html lang="en">`, a viewport meta tag, one `<main>`, one `h1` per page (smoke-tested).
- `<dialog>` with `showModal()`, `aria-labelledby` and `role="radiogroup"` in "Not for me" is the right base for keyboard and screen-reader behaviour.
- `bar_width` is log-scaled with a 3% floor, so small funnel stages stay visible.
- Static files are versioned with an mtime query, ready for long caching.
- Server-side safety is intact: Host/Origin check, JSON-only writes, files served only from `out/` with a suffix allow-list and path resolution.
- Cheap pages: no client framework, no build, and the JS is about 520 lines.

### Correction to the critique

`impeccable-critique.md` raised a concern that small funnel stages could shrink to slivers. Source shows `bar_width` is log-scaled with a 3% minimum, so that concern is mostly mitigated. I did not edit the critique file because this task allows only this report.

## Recommended Actions

1. **[P1] `/impeccable harden`**: findings 1, 2, 3, 7, 19, 20. Label every control, announce statuses, add skip link, landmark labels and `aria-current`.
2. **[P1] `/impeccable optimize`**: findings 4, 15, 16, 24. Replace reload-after-action with in-place updates (or restore focus and scroll), add cache headers and font preload, move the fixed background.
3. **[P2] `/impeccable extract`**: findings 11, 22, 18, 10. Consolidate `style.css` per component, move leaked colours into `tokens.css`, add `color-scheme`.
4. **[P2] `/impeccable adapt`**: findings 6, 13, 14. Target sizes, board breakpoint, fluid grids.
5. **[P2] `/impeccable colorize` and `/impeccable quieter`**: findings 12, 17, 26. Cover every status and reserve orange for act and match.
6. **[P3] `/impeccable clarify` and `/impeccable document`**: findings 21 and 25.
7. **`/impeccable polish`**: final pass after the above (findings 5, 8, 9, 23).

CLAUDE.md applies to all of these: each fix starts as a spec in `specs/`, ships one task at a time with tests, and updates `README.md` and `specs/08-roadmap.md` in the same change.

## Constraint Check

- **No external fonts, CDNs or scripts:** every recommendation is local. The font preload (finding 15) points at the bundled file, and the theme script (finding 9) is inline or a static local file.
- **Tokens stay in `static/tokens.css`:** findings 10, 11 and 22 add tokens there and remove literals from `style.css`; nothing moves the tokens out.
- **Existing tests keep passing:** not run in this session (Bash blocked). All changes are additive attributes, tokens and CSS, none rename ids, `data-run`, `data-cfg` or `aria-label` values that `tests/test_web.py` asserts. Finding 12 suggests adding a test, not changing one.
- **Not verified here:** detector output, browser rendering (flash, jank, overflow at 320-390px), real contrast on every dark pair (including the dark focus ring colour), and screen-reader behaviour. Re-run `impeccable detect`, `pytest -q`, `scripts/check_docs.py` and a browser pass (light and dark, 360 / 768 / 1280 / 1440px) once tools are available.

You can ask me to run these one at a time, all at once, or in any order you prefer. Re-run `/impeccable audit` after fixes to see your score improve.
