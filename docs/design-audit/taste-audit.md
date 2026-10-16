# Taste audit: web UI (`src/jobhunter/web`)

- **Date:** 2026-10-15
- **Lens:** the `redesign-existing-projects` checklist (typography, color and surfaces, layout, states, content, components, iconography, code quality, omissions), applied to this stack and filtered through `PRODUCT.md` / `DESIGN.md`.
- **Scope:** all nine page templates, `_macros.html`, `_top.html`, `base.html`, `static/style.css`, `static/tokens.css`, and the theme, toast and star code in `static/app.js`. `app.py` was read only for error handling.
- **Mode:** audit only. The one file written is this one. No template, stylesheet, script, token or test was touched.
- **Method:** source reading, no browser, no screenshots, `pytest` not run. Tags: **[S]** read in source, **[C]** computed from CSS values, **[P]** plausible, needs a browser to confirm. Line numbers refer to the files as they are today and will drift.
- **Relation to `impeccable-critique.md`:** that file covers heuristics, accessibility and flow (27/40). This one covers taste: surface language, hierarchy, polish, and the stylesheet underneath. Where an issue overlaps, it is cross-referenced as *(critique #N)* and not repeated.

## Constraints every recommendation respects

- **Offline, no CDN.** No external font, image, script or placeholder photo. The checklist's `picsum.photos` background suggestion is rejected for this reason.
- **`tokens.css` stays.** New values (neutral surfaces, type and space scales, z-index scale, status colors) are added to it, light and dark side by side. Nothing is renamed or removed in the first pass.
- **Tests stay green.** The smoke tests in `tests/test_web.py` (no external assets, one `h1`, labelled controls) assert on text, ids and `data-*`. The changes below are CSS, attributes and small markup edits. Where a change moves or removes text, the test is updated in the same change.
- **Spec-driven.** Items marked **needs spec** change user-visible behaviour or layout and go through `specs/` first (CLAUDE.md, "How we work").
- **Stack.** Vanilla CSS, Jinja, vanilla JS. No framework, no build step.

## Verdict

The identity is real: warm orange on slate, a mascot, honest copy. The execution is a stack of three design passes ("refinement", "second pass", "polish pass") laid over the original stylesheet, and it shows. Every surface is a card, every label is a pill, and orange is the default tint for anything that needs to look styled. The interface is calm and legible but undifferentiated: the eye has no resting place and no hierarchy beyond "bold or not". None of the failures is an AI cliché in the purple-gradient sense. The fingerprint here is the generic SaaS dashboard: slate hero, four KPI tiles, three equal step cards, pairs of white cards.

## What is already right (keep)

- Off-white canvas (`#f8f9ff`), no pure black or pure white backgrounds, one accent, no purple or blue gradient. Shadows are slate-tinted (`rgba(15,23,42,…)`), not generic black, and all fall downward, so the light direction is consistent.
- Contrast is a tracked property in `tokens.css`, with a dark set next to the light set.
- `tabular-nums` is on the body, so scores, counts and the funnel align.
- A tight negative tracking on `h1` (`-.035em`) gives the headline weight.
- Bundled variable font, inline SVG sprite, a favicon set, no external URL anywhere.
- Plain sentence-case copy, no exclamation marks, no "Oops". Empty states name the next action.
- The icon set is custom and drawn at one stroke width (1.8), apart from `i-check` (2.2), `i-spark` (filled) and the target's filled center dot.

## Findings, ordered by impact

### 1. [P1] Everything is a card and everything is a pill

**Evidence.**
- **Cards inside cards, up to four deep [S].** Applications "Closed" is `details.card` → `.board` → `.column` → `.kcard` (`pipeline.html:40-50`, four stacked surfaces, each with a fill or a border). Job matches top board is `.card.top-board` → `.job-card` → `.chip` (`_top.html:50`, `style.css:317-318`). Home "Your workflow" is `.card` → `.step` (a card with its own border and fill, `style.css:234`). `DESIGN.md` says "don't nest cards inside cards".
- **Radii are not graded [S].** Outer card and inner job card are both `--r-xl` (24px) (`style.css:195`, `204`). A 24px curve inside a 24px curve leaves an uneven rim. Inner elements should be tighter than their container.
- **About ten components share one pill silhouette [S].** `.badge`, `.chip`, `.count`, `.eyebrow`, `.tag`, `.check`, `.afchip`, `.btn.primary`, `.tabs` and `.tabs a`, all `border-radius: 999px` (`style.css:49, 83, 104, 163, 165, 200, 216-217, 345`). A status, a filter, a removable tag, a count and a primary button read as the same object. The checklist flags pill "New/Beta" badges for this reason.
- **Orange is the default tint [S].** `--badge-soft` (`#fff7ed`) fills avatars, tags, badges, active filters, the active tab and nav item, `code`, KPI and todo icons, the Ready column, and anything with no `.st-*` rule. The sameness is the problem, more than the amount. *(critique #1, #7)*
- **Every company avatar is the same orange tile [S].** `.avatar` has one fill and one border for all names (`style.css:202`). It adds a colored block to every row, and its two letters carry little. On a list scanned for the ring score, it competes with the ring.
- **Generic card recipe [S].** Nearly every surface is white + 1px border + 1px shadow (`.card`, `.kpi`, `.job-card`, `.kcard`, `.dock`). The checklist's own advice is to keep elevation for hierarchy and use fill or spacing elsewhere.

**Fix.**
- Add neutral tokens to `tokens.css` (`--surface-neutral`, `--ink-neutral`, light and dark) and make `.badge`, `.chip`, `.avatar`, `.tag` neutral by default. Orange stays on the primary button, the active nav item, the focus ring, the match ring and `.badge.match`.
- Give shapes a job: status badge = small rect (`--r-sm`), filter chip and tag = pill with a remove control, count = plain tabular text with no background, primary button = pill. Keep the pill only where a thing can be pressed or removed.
- Flatten one level everywhere it nests: the top board loses its outer `.card` (use a section with a heading and dividers), `.step` loses its fill inside the workflow card, the Closed group uses plain columns.
- Make avatars neutral monograms (no border), or drop them from the compact Home rows. If kept on job cards, size them to the title line, not the card height.
- Grade radii: containers `--r-xl`, rows and inner panels `--r-md`, controls `--r-sm`.

### 2. [P1] Home is the template skeleton: hero, four KPI tiles, three equal steps

**Evidence.**
- The page is the stock sequence of a dark slate hero, a row of four equal KPI tiles, a row of three equal numbered cards, then pairs of equal cards (`dashboard.html:7-132`). The checklist names "three equal card columns" as the most generic layout; this is it, with arrow connectors added.
- The hero is the only dark block on a light page (`style.css:46`, 222). It reads as a marketing banner above an app. Its radial orange glow (`::after`, `style.css:47`) plus a second radial orange wash on the body (`style.css:181`, `background-attachment: fixed`) is decoration with no information in it. `background-attachment: fixed` is ignored on iOS and forces repaint on scroll in several browsers [P].
- **Arrow connectors point nowhere when the steps wrap [C].** `.steps` is `auto-fit, minmax(240px, 1fr)` and `.step:not(:last-child)::after` draws `→` at `right: -1.15rem` (`style.css:235`). At a 1000-1100px viewport the main column is about 710px inside the card, three steps need about 765px, so they wrap to two rows. The arrow after step 2 then points off the card edge at nothing. It also hides below 860px only.
- Three variants of one tagline are on the first screen: sidebar "Your private job-search copilot", hero eyebrow "Personal job-search copilot", hero `h1` "Find the roles that fit you…". *(critique #4 covers the stats duplication and the missing next action.)*

**Fix.**
- Replace the hero with a slim header band at the page's own scale: `h1` "Home", one line of state ("12 matches, 3 packages ready"), and the single next action. Keep the mascot there at 56-72px. Dark block gone, one voice.
- Replace the three equal cards with a single vertical "Pipeline" list: rows `1 Search · 2 Review · 3 Prepare`, each a label, one sentence, and its one control aligned right. Left-aligned reading order beats a card row that can wrap. The arrows disappear.
- Fold the four KPI tiles into one inline strip of figures with labels beneath (no tile, no icon chip). They are links, so keep the underline-on-hover and a visible focus ring.
- Keep one radial wash at most, and drop `fixed` attachment.
- **Needs spec** (Home layout is in spec 09/18).

### 3. [P1] The stylesheet has no system under the tokens

**Evidence.** This is the cause of most inconsistency in 1 and 4, and the reason later fixes will fight each other.
- **Override layering [S].** `style.css` is the original sheet followed by "refinement pass" (line 180), "second pass" (243) and "polish pass" (276), then specs 22 and 23. More than 30 selectors are declared two or three times with different values: `body`, `h1`, `h2`, `.card`, `.card-head`, `.btn`, `.btn.small`, `.sidebar` and its children, `main`, `.job-card`, `.chip`, `.ring`, `.hero` and its children, `.eyebrow`, `.kpi`, `.steps`, `.step`, `.step-n`, `.tabs` (restyled from underline to pill), `.board`, `.column`, `.kcard`, `.empty-state`, `.empty-ic`, `.badge`, `.tag`, `.form-actions`, `.big-link`. `@media (max-width: 860px)` appears four times, and the later blocks silently override the earlier ones. Dead declarations remain (the flex `.board` at line 138 under the grid `.board` at 248).
- **No type scale [S].** At least 15 distinct `font-size` values between `.7rem` and `1.2rem` (`.72, .75, .78, .8, .82, .84, .85, .86, .88, .9, .92, 1, 1.02, 1.05, 1.1`). Body is 15px, `h2` is 17.6px, so a section title is only 1.17x body and relies on weight alone. `DESIGN.md` documents a scale that the CSS does not use.
- **No spacing scale [S].** `DESIGN.md` lists `xs…xl` spacing tokens, but `tokens.css` defines none. Spacing is literal rems (`.35, .4, .45, .5, .55, .6, .62, .65, .7, .75, .8, .85, .9, .95, 1, 1.1 …`).
- **Radii are half-tokenised [S].** `--r-sm…--r-xl` exist, but literal `6px, 9px, 10px, 12px, 14px, 18px, 20px` appear throughout (`.kcard`, `.step`, `.side-card`, `.callout`, `.kpi-ic`, `.empty-ic`, `dialog.modal`, `.top-notice`, `.btn`).
- **Weights [S].** Eight values in use (400, 500, 550, 600, 650, 700, 750, 800). 550/650/750 are indistinguishable from their neighbours and add noise to every rule that sets one.
- **z-index [S].** Literal 1, 2, 50, 60, 70 with no scale (`style.css:148, 147, 321, 295, 235`).
- **Inline styles [S].** `style="width:{{ width }}"` in the settings macros (`settings.html:10, 13`) hardcodes widths in markup. The `--size` and `width: N%` inline values on rings, avatars and bars are legitimate custom properties and stay.
- **Shadows [S].** `--shadow`, `--shadow-hover`, `--halo` are tokens, but `.toast` uses pure black (`rgba(0,0,0,.25)`) and `.dock`, `dialog.modal`, `.top-notice` use three more literal blurs.

**Fix (do this first, it changes nothing visible).**
- Add to `tokens.css`: `--text-xs…--text-2xl` (a 1.2 ratio from 15px), `--space-1…--space-8`, `--weight-regular/medium/semibold/bold`, `--z-sticky/dock/toast/modal`, `--shadow-pop` for floating layers.
- Collapse `style.css` in place into one pass per component: merge each duplicate, keep the last-winning value, delete the dead ones, one mobile block at the end. Verify by diffing computed styles for a representative element per component in the demo workspace.
- Keep a single, documented set of weights: 400, 500 (labels), 600 (controls), 700 (titles), 800 (display only).

### 4. [P2] Typographic hierarchy is flat; the family is fine

**Evidence.**
- **The family is not the problem [S].** Plus Jakarta Sans is on every "SaaS template" shortlist, but it is bundled, licensed (OFL) and legible, and the mascot carries the brand. Swapping it costs a new woff2 and buys little. The hierarchy is the weak point, per issue 3: `h2` 17.6px against 15px body, `h3` as 12.5px uppercase muted labels *(critique #11)*, and almost all emphasis done with weight.
- **All-caps is the label style in seven places [S]:** `h3`, `th`, `h2.group`, `.eyebrow`, `.verdict`, `.column h2`, `.fb-sel > span` (`style.css:11, 40, 49, 94, 123, 250, 336`). On the Actions page the group titles are orange, caps, weight 800 and tracked at once (`style.css:265`). The checklist advises sentence case or small caps for most of these.
- **No `text-wrap` anywhere [S].** Card titles, job titles, the hero `h1` and step copy can end on a single orphan word. `text-wrap: balance` on headings and `pretty` on paragraphs is one line each, supported in current Chromium and Safari, and ignored harmlessly elsewhere.
- **Measure is only capped on the page intro [S].** `.page-head p` is 60ch. Hints, callouts and the Settings intro paragraph (`settings.html:20`, several lines long) run the full card width, 80+ characters on a wide card.
- **Numbers are fine,** and a few of them are the product (scores, funnel). `ring i` at weight 750 and `.kpi b` at 800 are strong. The funnel counts could drop to 600 so the label, bar and number do not all shout.

**Fix.**
- Pick two label styles: sentence-case 13px/600 muted for section and table labels, and a single small caps (`font-variant-caps: all-small-caps` with `+.04em` tracking) for the rare cases that need to be quiet. Remove caps from `h2.group` and `.column h2`.
- Set `--text-xl` for card `h2` (about 1.25rem, 700) so section titles beat body by a visible step, and `--text-2xl` for `h1`.
- Add `text-wrap: balance` to `h1, h2, h3, .job-title, .ktitle` and `text-wrap: pretty` to `p, .hint, .job-reason`. Cap `.hint`, `.callout p` and `.card > p` at `68ch`.
- Optional, not recommended now: a bundled serif for the display `h1` only. It adds a font file and a second voice to a tool whose strength is quiet.

### 5. [P2] Interaction polish is uneven

**Evidence.** *(critique #3 covers focus loss, silent toasts and reduced motion; this is about feel.)*
- **No pressed state anywhere [S].** The stylesheet has no `:active` rule. Buttons lift on hover (`translateY(-1px)`, `style.css:69`) and then do nothing on press, so a click has no physical response.
- **Transitions are patchy [S].** `.btn`, `.job-card`, `.fb-sel` and `#jobs-results` use `transition: .12s`. `.kpi`, `.kcard`, `.sidebar nav a`, `.tabs a`, `.star`, `.afchip button` and `.icon-btn` change on hover with no transition, so they snap, next to neighbours that ease. `.btn` uses the `all` shorthand, which animates `border-color`, `background`, `box-shadow` and `transform` alike.
- **Hover lift on a dense list [S].** `.kpi:hover` also shifts by 1px with no `transition`, so the tile jumps.
- **Search field focus is the weakest indicator in the app [P].** `.fb-search` is a wrapper with a 3px orange glow at 22% alpha on a `--soft` fill (`style.css:332-334`); the input itself has `outline: 0` and no border change. A 22% orange on near-white is likely under 3:1 as a non-text indicator, and the other filter controls get a border change on top of the glow.
- **Every action reloads the page [S].** `act()` and the run dock call `location.reload()` *(critique #12)*. Visually this is a white flash and a scroll reset on each stage change. A CSS-only mitigation exists: `@view-transition { navigation: auto; }` cross-fades same-origin navigations in current Chromium and Safari, costs three lines and is a no-op elsewhere.
- **No loading shape [S].** Loading is a 55% opacity fade on `#jobs-results` and the text "Checking…" in System check (`style.css:327`, `dashboard.html:131`). Skeleton rows are not needed for local, fast requests, but the System check call and the live filter fetch both show an unstyled gap.
- **Anchors jump [S].** Settings tab links and the "Package" anchor on the posting page scroll instantly; there is no `scroll-behavior`.

**Fix.**
- One shared transition token (`--ease: 120ms cubic-bezier(.2,.7,.2,1)`) on a named property list (`background-color, border-color, box-shadow, transform, color`) for `.btn, .kpi, .kcard, .job-card, nav a, .tabs a, .star, .icon-btn`.
- Add `.btn:active { transform: translateY(0) scale(.98); }` and the same for `.kpi`, `.star`.
- Give `.fb-search:focus-within` a border-color change to `--focus-ring` (matching `.fb-sel`) and raise the glow to 35%.
- Add `@view-transition { navigation: auto; }` and, inside `@media (prefers-reduced-motion: no-preference)`, `html { scroll-behavior: smooth; }`.
- Skip skeletons. A single-line placeholder for the health list is enough.

### 6. [P2] Icons: one reads as the wrong thing, one is a cliché, three systems are mixed

**Evidence.**
- **The "gear" is a sun [S].** `i-gear` is a circle with eight radial ticks (`base.html:21`). That is a brightness or light-mode symbol, and the app also has a theme toggle. A reader looking for Settings sees a sun.
- **The sparkle is the AI cliché [S].** `i-spark` (`base.html:22`) marks "Score with AI", "Why it matches" and every hint line (`_top.html:56`). It is the most recognisable 2024 "AI feature" icon and it is filled where the rest of the set is outlined.
- **Three icon systems [S].** The SVG sprite, text glyphs (`★ ☆ ◐ ◑ ✕ × – → ←`) and the unicode star used as a button and as a chip prefix (`app.js:417, 501`, `_top.html:6`, `jobs.html:23`). Glyphs render from whatever the system font provides, so weight, size and baseline vary by OS, and `★` can fall to emoji presentation on some platforms.
- **Sprite icons are not hidden from assistive tech [S].** `macros.icon()` emits `<svg class="ic"><use/></svg>` with no `aria-hidden` or `focusable="false"`, next to text that already names the control (`_macros.html:13`).
- **Stroke and fill are inconsistent [S].** Outline icons at 1.8, the check at 2.2, the sparkle and target center solid.
- The set looks like Feather/Lucide (home, calendar, send, search, alert). The checklist counts that as default. It is internally consistent and offline, so redrawing it is not worth the cost beyond the two icons above.

**Fix.**
- Redraw `i-gear` as a real cog (or a sliders icon, which fits "everything is configurable here"), and keep the current ray shape for a new `i-sun` used only by the theme toggle.
- Replace `i-spark` on "Why it matches" and hints with a quiet "note" or "reason" icon; keep a sparkle only on the one control that spends AI quota, or drop it for text ("AI") to follow "show costs plainly".
- Add `i-star` and `i-star-fill`, `i-x`, `i-arrow` to the sprite; replace the glyphs; give `icon()` `aria-hidden="true" focusable="false"`.
- Make `i-check` 1.8 and fill the target dot with a stroke-width dot, or accept the two solids as intentional and document them.

### 7. [P2] Dark theme is opt-in, but not fully built

**Evidence.** *(Not reviewed in `impeccable-critique.md`.)*
- **Flash of the wrong theme [S].** The theme is applied from `localStorage` in `app.js`, which loads at the end of `<body>` (`base.html:76`, `app.js:412-421`). A person who chose dark sees one light frame on every navigation, and with the reload-after-action pattern that is a flash on every click.
- **No `color-scheme` [S].** `tokens.css` never sets it, so in dark mode the browser draws light native widgets: scrollbars, the `datetime-local` picker, `<select>` popups, the autofill tint, and `<dialog>` default chrome.
- **Hero merges with the page [S].** In dark, `--slate: #111a2e` and `--panel: #111a2e` are the same value, so the "dark hero" is a card-colored rectangle with a glow and loses its separation from every card below it.
- **The toggle is unreachable on small screens [S].** It lives inside `.side-card`, which is `display: none` below 860px (`style.css:154`). So is the "100% local" trust note.
- **Smaller:** inline `code` takes the orange `--badge-soft` fill in both themes (`style.css:8`), which reads as a selected state; `.btn { border-color: #cbd5e1 }` is a literal that bypasses `--control-border` in light (`style.css:197`).

**Fix.** Add a three-line inline `<script>` in `<head>` that sets `data-theme` before first paint (same-origin, no CDN, but check it against the CSP if one is added later). Set `color-scheme: light` on `:root` and `color-scheme: dark` on the dark block. Give dark `--slate` its own step (`#162036`) or make the header band (issue 2) neutral. Move the theme toggle to Settings and a compact control in the nav bar, so it survives the mobile layout. Make `code` neutral.

### 8. [P2] Layout and chrome

**Evidence.**
- **Wide screens leave a dead strip on the right [C].** `main` is `flex: 1; max-width: 1320px` with no `margin-inline: auto`, inside a flex `body` (`style.css:4, 31`). At 1920px wide, the sidebar (248px) plus main (1320px) leave about 350px empty on the right, and content sits off-center.
- **`100vh` instead of `100dvh` [S].** `body { min-height: 100vh }` and `.sidebar { height: 100vh }` (`style.css:4, 19`). On mobile Safari the sidebar and the page will overshoot the visible viewport.
- **The sidebar can clip [P].** It is `position: sticky; height: 100vh` with a column of brand, six links and the side card (about 6 lines) and no `overflow-y`. On a short laptop window the side card or the last links can fall out of reach with no way to scroll them.
- **A permanent 248px sidebar for six destinations [S].** That is about 19% of a 1280px laptop and the direct cause of the Applications board no longer fitting *(critique #6)*. It is also the checklist's "dashboard always has a left sidebar". Because every destination already has an icon, an opt-in icon rail (56-72px, labels visually hidden, tooltips on hover and focus, 44px targets, an `aria-expanded` toggle persisted in `localStorage`) is cheap, and below the tablet breakpoint the existing top bar stays. Default stays expanded.
- **Equal-height stretch [S].** `.grid-2` stretches both cards. "Your criteria" (three lines) sits beside "Why it matches" and leaves a large empty panel *(critique, minor observations)*. `align-items: start` on `.grid-2` fixes it.
- **Card padding is symmetric [S].** `.card { padding: 1.5rem 1.7rem }` is the same top and bottom. A card ending in a button row or a list needs about 0.15rem more at the bottom to look balanced.
- **Hard pixel widths [S].** `.funnel-row` 150px, `dl.profile` 130px, `.column` 258/230px, `.job-actions` 128px, and the inline settings widths. Most are fine as `rem`/`ch`, but `.column`'s fixed 230px is what forces the board to scroll.

**Fix.** `main { margin-inline: auto; }` or wrap content in `.page { max-width: 1280px; margin-inline: auto; }`. Switch to `min-height: 100dvh` and `height: 100dvh` with `overflow-y: auto` on the sidebar. `align-items: start` on `.grid-2`. Rail option is **needs spec**, the rest is not.

### 9. [P3] Voice and vocabulary

**Evidence.**
- **First and second person are mixed [S].** Settings and the detail page speak as the user ("What I'm looking for", "My application", "My CV & letter", "Roles I want"), everything else addresses the user ("Your top 5", "Your workflow", "Your criteria"). Pick one. Second person is used more and matches the copilot framing.
- **Three taglines on Home** (see issue 2).
- **Nav and page labels drift [S].** The nav item "Actions" (page `h1` "Actions") contains the buttons that run the pipeline, and each card's button is just "Run" (`run.html:28`), 13 times, all filled orange. The nav item "Documents" lists what the rest of the app calls "packages" (the Home button says "Build packages"). The nav item "Job matches" opens a page with tabs for everything including filtered-out postings.
- **"Run" says nothing out of context.** The button could carry its verb ("Search", "Score", "Build"), which also makes the filled orange meaningful.
- **Jargon reaches the person [S]:** "blocker" (Product terminology), `score_failed`, `below_threshold`, `refilter`, `companies-discover` as run ids and table values on the Actions history (`run.html:39` prints `r.spec_id`), and the raw `remote/onsite/unknown`. *(critique #9 covers the raw tokens and dates.)*
- Settings hints are written for a spec reader rather than for the person ("compared with the top of the published range. Monthly pay × 12. 0 turns it off.") *(critique #5)*.

**Fix.** One text pass: "you/your" throughout; the nav labels "Home, Matches, Applications, Documents, Actions, Settings" with "package" used once and explained once; button labels carry their verb; run history uses `s.label`, not `s.id`.

### 10. [P3] Missing pieces

- **No skip link [S].** `base.html` opens with the sprite, then `<aside>` with the brand and six nav links, then `<main>`. A keyboard user tabs through seven stops on every page. Add `<a class="skip" href="#main">Skip to content</a>` (visible on focus) and `id="main"` on `<main>`. `nav` has no `aria-label`. *(Not listed in the critique.)*
- **No custom 404 for unknown pages [S].** `app.py` registers handlers only for `ConfigError` and `TrackingError`. An unknown URL falls through to the framework's JSON `{"detail":"Not Found"}`. The posting-not-found case reuses `error.html` with the title "Something went wrong" (`error.html:3`), which is wrong for a 404. Add an `HTTPException` handler for page routes that renders `error.html` with a status-specific title and a back link ("Back to Home", plus the previous page when there is one).
- **`error.html` is a dead end [S].** One button, to Home, no retry, and `<title>` is the same for every status.
- **`<meta name="theme-color">`** is absent. Cosmetic, one line per theme.
- **`<head>` has no `description` or `og:*`** and should not get them: the app is served on 127.0.0.1 and never shared. Declined on purpose.

### 11. [P3] Smaller craft points

- **The ring's glow is decoration [S].** `box-shadow: 0 0 0 4px var(--panel), 0 0 18px -2px color-mix(…)` (`style.css:211`) adds a neon halo in red, amber or green to every card. The 4px panel gap is the useful part; the colored blur adds noise to a scan list and makes red scores glow. Keep the gap, drop the blur.
- **Orange glow on primary buttons and `.step-n`** (`--halo`, `style.css:71, 236`) repeats the same effect. With issue 1 (fewer filled primaries) the halo can stay on the one remaining primary.
- **Kanban column top rules** (`border-top: 4px` on a 24px radius) taper into crescents *(critique #14)*. A 3px inner bar via `box-shadow: inset 0 3px 0 …` keeps the corners clean.
- **Step arrows use a text glyph** that screen readers can announce *(critique, minor)*. Resolved if issue 2 removes them.
- **The top notice and toast use two slightly different dark styles** (`--slate` with border versus `--ink` on `--bg`), and `.toast` is `hidden` by attribute with no entry transition. A single "floating message" component, one token for its shadow.
- **Detail-page header is crowded [P].** Avatar (64px), `h1` with the star inside it *(critique #2)*, ring (64px) and a three-button column share one `flex-wrap` row (`job.html:6-27`), so a long title wraps early. Let the title take the row and move the ring beside the actions.

## Checklist items declined (and why)

| Checklist suggestion | Verdict |
|---|---|
| Grain or noise overlay, mesh gradients | Skip. A calm work tool does not need texture, and a fixed full-page overlay costs repaint on every scroll. |
| Background photos (`picsum.photos`) behind sections | Reject. Violates "offline, no CDN" and would put a third-party request in a local-first product. |
| Glassmorphism, spotlight borders, parallax stacks, split-screen scroll | Skip. They add motion and cost to a list-and-form product used daily. |
| Staggered entrance animation | Skip. People return to this page many times a day. The view-transition in issue 5 gives the continuity without per-element motion. |
| Variable-font weight animation, outlined-to-fill text | Skip. No hero text worth animating. |
| Replace the font | Keep the current one (issue 4). |
| Replace the icon set wholesale | Skip. Fix the gear and the sparkle (issue 6). |
| Lorem, "John Doe", "Acme" placeholder content | Not present in templates. The demo workspace seed is outside this audit. |
| Cookie consent, legal links, `og:image` | Not applicable to a local single-user app. |
| Pure `#000`, purple/blue AI gradient, oversaturated accent | Not present. `#f97316` is about 93% saturation in HSL but is used as a fill and tint, with `#c2410c` for text. Leave it. |
| FAQ accordions, testimonials, pricing towers, footer link farm | Not present. |

## Suggested order of work

Each step is independently shippable and testable. Steps 1, 3, 4, 5, 6 and 8 stay within CSS, attributes and tokens. Steps 2, 7 and 9 change layout or behaviour and need a spec first.

1. **Foundation (issue 3).** Add scale tokens, merge the duplicate rules, one mobile block. No visual change expected. Gate: computed-style diff on the demo workspace, `uv run pytest -q`, `ruff`.
2. **Quick wins (issues 4, 5, 7, 8, 10, parts of 6 and 11).** `color-scheme`, early theme script, `text-wrap`, `:active`, one transition token, search focus, skip link, `main` centering, `dvh`, `aria-hidden` on icons, gear and star icons, ring glow, 404 handler.
3. **Surface language (issue 1).** Neutral tokens, shape-by-role, one level of nesting removed, graded radii. This is the biggest visible change; do it after step 1 so the orange removal is a token edit.
4. **Voice (issue 9).** One copy pass across templates, with matching text updates in `tests/test_web.py`.
5. **Home and the optional rail (issues 2, 8).** After a spec change.

## What was not verified

- No browser run, so every **[P]** and every pixel estimate is unconfirmed. Overflow at 1000-1100px, the wrapped step arrows, the clipped sidebar on a short viewport and the search focus contrast are the first to check.
- Dark theme was read from `tokens.css` only; no dark screenshots.
- The font subset was not inspected. If `PlusJakartaSans.woff2` is Latin-only, postings in Cyrillic, Greek or CJK fall back to a system font with different metrics.
- `app.py` was read around the error handlers only. The 404 claim is that no handler for unknown routes is registered in the module; a mount or middleware elsewhere would change it.
- `pytest` and `scripts/check_docs.py` were not run. The audit changed no code.
