⚠️ DEGRADED: single-context (sub-agent tool calls were blocked by a classifier outage; detector and browser evidence did not run)

# Impeccable critique: Home, Job matches, Posting detail, Applications, Settings

- **Date:** 2026-10-15
- **Scope:** `dashboard.html`, `jobs.html`, `job.html`, `pipeline.html`, `settings.html`, plus `_top.html`, `_macros.html`, `base.html`, `static/style.css`, `static/tokens.css` (light theme), `static/app.js`. Compared against `PRODUCT.md` and `DESIGN.md`.
- **Mode:** Operate (app UI).
- **Method:** one reviewer, one context, reading source only. Not run: `impeccable detect`, browser screenshots at desktop and mobile, `pytest tests/test_web.py`, `scripts/check_docs.py`. Dark theme not reviewed.
- **Evidence tags:** **[S]** read directly in source. **[C]** computed from CSS values (contrast, widths). **[P]** plausible from source, needs a browser or screen reader to confirm.
- **Audit only.** No existing file was changed. Persisting to `.impeccable/critique/` was skipped on purpose so this file is the only write.

## Design Health Score (Nielsen's 10)

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | Run dock, funnel and notices are good. Score ring has no accessible name, toasts and save states are not announced, LLM spend is never shown next to the buttons that cause it. |
| 2 | Match between system and real world | 3 | Plain labels ("Not for me", "Verify before applying"). Raw tokens leak: `remote`/`onsite`, `apply/maybe/skip`, ISO dates with `T` replaced. |
| 3 | User control and freedom | 3 | Undo notice for "Not for me", confirms on Hide/Block/Delete. Stage `<select>` autosaves with no undo; Hide is permanent. |
| 4 | Consistency and standards | 2 | Layered CSS passes, orange doing both "act" and "status", three overlapping dismiss verbs, cards nested in cards against DESIGN.md. |
| 5 | Error prevention | 3 | Verified packages, confirms. "I applied" sits beside "Build package" on unreviewed postings; Save in one Settings card silently drops edits made in another. |
| 6 | Recognition rather than recall | 3 | Active filter chips, labelled filter bar, hints on every setting. Settings is one long page with five tabs that only scroll. |
| 7 | Flexibility and efficiency | 2 | Live filters are good. No multi-select, no bulk score/build/dismiss, no keyboard path through a list of postings, stage moves are one select per card. |
| 8 | Aesthetic and minimalist design | 2 | Home repeats the same three numbers up to four times. A job card carries about 14 elements. Settings hints run to 40+ words. |
| 9 | Error recovery | 3 | Field-level errors, red run state. "Needs review" lists problems but gives no path to fix them. |
| 10 | Help and documentation | 3 | Empty states name the next action. Hints under fields. Step copy on Home is clear. |
| **Total** | | **27/40** | Acceptable: solid bones, real gaps in focus and accessibility. |

## Design-specificity verdict

**Brand-specific skin on a template skeleton.** The mascot, the orange and slate pairing, the amber-for-warnings rule and the "100% local" voice are particular to this product. The page structures are not: slate hero, KPI tiles, three numbered step cards, then pairs of white cards is the standard SaaS dashboard. The cockpit idea in DESIGN.md ("one clearly marked next action") is not yet true on screen, see issue 1.

## Overall impression

A calm, trustworthy, honest tool with a likeable identity. The central design promise is "one orange next action", and the interface breaks it in almost every view: orange marks actions, matches, statuses, avatars, tags, filters and step badges at once, so nothing stands out as the next move. The second gap is the review path on the posting page, where the thing the person must verify (posting text, package contents) is the least visible content.

## What's working

- **Warnings are amber and specific.** The "Verify before applying" callout, per-card "N things to verify" line and "Possible gaps" chips keep to the Warning Is Amber rule and make the no-invented-facts principle visible.
- **Honest empty states and fill logic.** Every empty view says what to do next ("Only 3 of 5 matches so far… Score the 2 most promising"). That is the best copy in the product.
- **Live filter bar.** Filters apply as you choose, the URL syncs, active filters show as removable chips, and it falls back to a full page load on failure (`app.js`).
- **Run dock survives navigation.** A run in progress reopens after a reload (`sessionStorage`) and every run button disables while it runs.
- **Offline discipline.** Bundled font, inline SVG sprite, no external URLs in the five templates.

## Priority issues

### 1. [P1] Orange means everything, so there is no next action

**What.** Filled orange primaries and orange tints appear on every level at once.
- Job matches top board: the default `plan.target` is 5, so five "Build package" buttons plus the page-head "Search for new jobs" are all filled orange in one viewport [S] `_top.html:27`, `jobs.html:9`.
- Home: three filled step buttons (`dashboard.html:42,49,56`), plus a filled button on each "What to do next" row, plus the fill prompt [S].
- Applications: every card in "Ready to apply" has a full-width filled "I applied" [S] `pipeline.html:28`, `style.css:256`.
- Orange tint also marks company avatars on every card (`style.css:202`), tags, active filters, KPI icon, step badges, `applied` badges, and any status with no rule (see Further findings, 7).

**Why it matters.** DESIGN.md's own One Voice rule says a screen with orange on everything has no next action. This is the main place the shipped UI departs from the design system. For a person doing a daily 10-posting review, hunting for the next step is the cost.

**Fix.**
- Keep one filled primary per area. Per-card "Build package" becomes a secondary `.btn`; "View package" stays quiet too. A single primary at card-head level ("Build packages for the top N") is the natural filled action, but that is new behaviour: it needs a spec change and must respect `tailoring.max_packages_per_day`.
- On Home, make only the pipeline's next step filled. The `suggestions` list already computes it; the three step buttons become secondary.
- Avatars and generic badges go neutral: add `--surface-neutral` / `--ink-neutral` in `static/tokens.css`, default `.badge` to neutral, and keep orange for `.badge.match` and the match ring only.
- "I applied" in the Ready column becomes secondary.

**Command:** `/impeccable layout Job matches and Home: one primary action per area`, then `/impeccable colorize` (reverse direction: reduce orange).

### 2. [P1] Posting detail: the review path hides what must be reviewed

**What.** Order on `job.html`: header, why it matches, criteria, favorite note, package, application, posting text (collapsed `<details>`), history [S].
- The posting text that every claim must be checked against is below five cards and collapsed.
- The package card shows a green "Checks passed" or red "Needs review" badge and a list of file chips that open PDFs in new tabs [S] `job.html:63-66`. It does not say what was checked (facts against master CV, page count, language) or where a problem is. The reviewer leaves the page to read the CV and letter.
- The header's only filled button is "Open posting ↗". "Block this company" and "Hide posting" sit directly under it at equal weight, and are the two most consequential buttons on the page [S] `job.html:22-26`. The next stage action ("I applied") is five cards down.
- The star toggle is inside the `<h1>`, so the heading's accessible name starts with a glyph [S] `job.html:9`.

**Why it matters.** PRODUCT.md targets under 5 minutes to review a package and "zero false facts", with verification "surfaced prominently". Today the page proves the checks passed but does not help a person do the review.

**Fix.**
- Make the review a two-column layout on wide screens: posting text on the left (not collapsed, scrolls on its own), the "Why it matches", flags and package on the right.
- Show one line of what the verification covered and each problem as a plain sentence, using data already in `package.meta`.
- Preview CV and letter PDFs inline (`<object>` or `<iframe>` from the existing `out/` route; same origin, no new script).
- Header: primary = the next stage action; "Open posting" secondary; Block and Hide move into a quiet "More" `<details>` menu.
- Move the star out of the `<h1>` and give it `aria-label`.

**Command:** `/impeccable layout Posting detail: review layout`, then `/impeccable clarify` for the verification wording.

### 3. [P1] Accessibility gaps that the smoke tests do not catch

All from source; none confirmed with a screen reader.

- **Settings fields have no programmatic labels.** The `field` macro prints `<label class="flabel">` with no `for` and no wrapping, and the control comes after it [S] `settings.html:6`. The number inputs, selects and textareas have no accessible name; the tag input has only a placeholder ("Type and press Enter"). The checks groups have no `fieldset`/`legend`.
- **Interview rows have no names.** Each saved interview row and the add form use four unnamed controls (kind select, `datetime-local`, outcome select, notes input with placeholder only) [S] `job.html:95-98,104-106`. This is the rule in CLAUDE.md ("add `aria-label` to controls without a visible label").
- **Silent feedback.** `#toast` has no `role` or `aria-live` [S] `base.html:58`, yet it carries every error and "Notes saved". `.save-state` ("Saved ✓" / "Not saved: …") is also silent [S] `app.js:217-227`.
- **Focus loss after live filtering.** The filter chips and "Clear all" sit inside `#jobs-results`, whose `innerHTML` is replaced on each refresh [S] `app.js:281`. A keyboard user who clears a filter loses focus to `<body>`. The result count is not in a live region.
- **Small targets and glyph names.** `.star` is about 22×18px [C] (below WCAG 2.2 AA 2.5.8's 24×24px) and its name is the glyph "★"/"☆" plus `aria-pressed`, so it reads as "black star, pressed". The `.afchip` remove button is 22px.
- **Score ring has no name.** `<span class="ring" title="AI match score">` shows its meaning only on hover [S] `_macros.html:5`; assistive tech gets the bare number.
- **Links in muted text.** `#c2410c` links sit in `#475569` hint paragraphs at about 1.46:1 [C] and have no underline until hover [S] `style.css:6`. That fails WCAG 1.4.1. Links in ink text pass (about 3.4:1).
- **Nav state.** The active nav item and tab use a class only; no `aria-current="page"` [S] `base.html:42`.
- **No `prefers-reduced-motion` handling** anywhere in `style.css`; the run dock dot pulses forever [S] `style.css:150`.

**Fix.** Give the `field` macro a generated `id` and `for` (or wrap in `<label>`); add `aria-label`s to interview controls; add `role="status"` to `#toast` and `aria-live="polite"` to `.save-state`; move focus to `#jobs-results` (or the next chip) after refresh and make the count `aria-live`; pad `.star` and `.afchip button` to 24px; add `role="img" aria-label="Match score 78"` to the ring; underline links in running text (`text-decoration: underline` with offset, tokenised); add `aria-current`; wrap pulse and hover transforms in `@media (prefers-reduced-motion: no-preference)`. All of this stays offline and the tokens stay in `tokens.css`.

**Command:** `/impeccable harden accessibility on all five surfaces` (then `/impeccable audit` once the browser is available).

### 4. [P2] Home: the first screen is a tagline and repeated numbers, the next action is fourth

**What.** The order is hero (about 22rem tall), KPI tiles, top matches, the three-step workflow, then "What to do next" [S].
- "Postings found", "matches for you" and "applications" in the hero are the same figures as the KPI tiles ("Matches worth a look" is `kpis.matches` twice) and again in the funnel, so the page shows the same number up to three times.
- The hero `<h1>` is a tagline ("Find the roles that fit you…") while every other page's `<h1>` is the page name.
- "What to do next" is the one component that knows the state, and it is below three always-visible, always-filled step buttons.
- The AI steps ("Score with AI", "Build packages") start paid LLM work with no hint of how many postings or what the cap is, which cuts against the product's "show costs plainly" principle.
- "System check" sits at the bottom of Home and again in Settings → System.
- Both "Active applications" and "Interviews pending" tiles link to the same `/pipeline`, and each stage chip links to the unfiltered board [S] `dashboard.html:28-29,87`.
- [P] The funnel bars scale to "Postings found" (`bar_width(f.fetched)`), so later stages (packages, applied, offers) are likely slivers. `bar_width` was not read.

**Fix.** Put "What to do next" directly under a compact hero (or replace the hero stats with it). Drop the three duplicated hero stats. Show the plan size next to AI buttons ("Score 12 postings"). Keep System check on Settings only, and surface a warning on Home only when a check fails. Use a scale floor or a log scale for the funnel.

**Command:** `/impeccable distill Home`, then `/impeccable clarify` for button labels.

### 5. [P2] Settings: one long page where saving is local to a card but editing is not

**What.**
- `[data-save-cfg]` reads only the `[data-cfg]` fields inside its own `[data-card]` [S] `app.js:208-213`. A person who edits "Roles I want" and then clicks Save in the "AI & documents" card loses the first edit silently. There is no dirty indicator and no `beforeunload` warning.
- The five tabs are `<a href="#…">` anchors that only set an `on` class on click (`app.js:257`). They never update on scroll and are not really tabs.
- [P] `.form-actions` is `position: sticky; bottom: 0` for every instance (`style.css:295`). Sources and My CV and letter each have two or three, so several bars compete for the same bottom edge as you scroll, and the later one covers the earlier, which can leave you pressing "Save list" when you meant "Save". Needs a browser check.
- The intro paragraph spends two lines on `.bak` and `.orig` file mechanics; several hints exceed 40 words ("Where I can work").
- "Save" and "Save & re-filter" are both visible; the consequence of re-filter (what it changes among already downloaded postings) is only in the paragraph above.

**Fix.** Track a dirty flag per card and show "Unsaved changes" in the bar; warn on leaving; make each card save independently *or* make Save collect all cards. Make the tab bar real: scroll-spy with `aria-current`, or show one section at a time. Make only the last `.form-actions` of a card sticky. Move backup mechanics to a `<details>`. Trim hints to one sentence plus an example.

**Command:** `/impeccable layout Settings: tabs and save`, then `/impeccable clarify` for hints.

## Further findings, ordered by impact

6. **[P2] Applications board loses its last columns on laptops.** `.board` is five fluid columns, but at ≤1280px it switches to `repeat(5, 230px)` [S] `style.css:263`. Main content at 1280px is about 944px wide [C] (viewport minus the 248px sidebar and 2×44px padding), so the five columns need about 1207px and "Offer" scrolls off-screen. Between 1281px and 1440px the fluid columns are about 180-200px, with titles wrapping. The stage `<select>` autosaves and reloads the whole page [S] `app.js:126-129`, with no undo, so one wrong pick on "Rejected"/"Ghosted" is silent. Cards show no age cue to help decide "ghosted". *Fix:* tighten column min width and card chrome, or show the closed stages as a count strip; add an undo toast for stage changes; show "applied 12 days ago". **`/impeccable adapt Applications board`**
7. **[P2] Status colour semantics are loose.** `.st-*` rules exist only for some statuses [S] `style.css:108-109`. Statuses without a rule (for example `passed`, `scored`, `score_failed`) fall back to the default orange badge, so a neutral state looks like an action. `below_threshold`, `duplicate`, `filtered` and `closed` render in error red, though they are not errors. `applied` is orange while DESIGN.md calls the applied progress node sky. *Fix:* add neutral, info and warn-soft rules and keep red for errors.
8. **[P2] Job card is dense and DESIGN.md's nesting rule is broken.** The top board is a `.card` containing `.job-card` articles with their own border and 24px radius, and a `.top-fill` panel [S] `_top.html:50-57`; DESIGN.md says "don't nest cards inside cards". Each card shows avatar, star, title, source, location, mode, salary, status, stage, reason with verdict, warning line, ring and four buttons (about 14 elements). "Hide" (permanent) and "Not for me" (dismiss with reason, refills the board) sit side by side and read as the same action; "I applied" is one click from "Build package". *Fix:* flatten the board (list rows with a divider), fold Hide into "Not for me" (the dialog can offer "never show again"), and move "I applied" to the detail page or an overflow menu.
9. **[P3] Dates and raw tokens.** Interview times render as the raw ISO string with `T` replaced [S] `dashboard.html:82`, `pipeline.html:9`, while other timestamps go through the `|dt` filter. The work-mode filter lists lowercase `remote`/`onsite`/`unknown` [S] `jobs.html:22`; the header shows `job.remote` raw; verdict badges show `apply/maybe/skip`; interview outcomes show raw values.
10. **[P3] Native `confirm()` is the only confirmation.** Hide, Delete package, Delete interview and Block company (two sequential dialogs, `app.js:515,519`) use browser dialogs while a styled `<dialog>` system already exists (Not for me, Add posting).
11. **[P3] Small text carries essential content.** `.small` is 12.6px and badges 12.5px; company names on kanban cards and the sub-line on job cards use them. Section labels inside the review flow ("What matches your profile", "Possible gaps", "Message for the recruiter") are `h3` at 12.5px uppercase muted, quieter than the content they introduce.
12. **[P3] Whole-page reload after every action.** `act()` calls `location.reload()` [S] `app.js:21-24`, so each stage change, ignore or run resets focus and loses the user's place in a long list.
13. **[P3] Mascot disappears on narrower screens.** `.hero-logo` is hidden at ≤1100px [S] `style.css:228`, so the one confirmed brand asset is absent from the hero on small laptops.
14. **[P3] Kanban column top rules use `border-top: 4px` on a 24px radius**, which renders as a crescent that tapers at the corners [P].
15. **[P3] DESIGN.md drift to fix on its side.** The Named Rules text lists "match rings" as orange while the shipped ring is red/amber/green by score; the style sheet is a stack of "refinement", "second" and "polish" passes with overriding duplicates (for example `.column.stage-*` h2 colour overriding earlier `.stage-* h2`). Worth consolidating before more changes.

## Persona red flags

**Alex (power user, daily 10-posting review).** No way to select several postings and score, build or dismiss at once; five "Build package" buttons to press one by one. No keyboard route through a posting list or shortcuts. Moving applications is one select per card with a page reload each time. Settings edits can be lost by saving the wrong card.

**Sam (accessibility: keyboard, screen reader, low vision).** Settings controls have no names; toasts and "Saved" are silent; focus drops after clearing a filter; star and filter-chip targets are under 24px; muted-text links have no underline and about 1.46:1 against surrounding text; ring scores have no label; pulse animation ignores reduced motion.

**Jordan (first-timer, demo workspace).** Home explains the pipeline well, but three filled buttons say "press me", and "Score with AI" does not say how much it will do or cost. The hero has a tagline, not a "start here". "Hide" vs "Not for me" is unclear. Terms such as "blocker" and "package" are explained only after first use.

**The cautious applicant (project persona: must trust that nothing invented goes out).** Sees "Checks passed" but not what was checked; must open PDFs in new tabs to compare against the posting text, which is collapsed at the bottom of the page. "I applied" is easy to press before any review. "Needs review" does not point at the failing line.

## Minor observations

- `target="_blank"` on package file links has no `rel` [S] `job.html:66`; modern browsers imply `noopener`, but be explicit.
- `#dock` has `aria-live="polite"` around a log that appends every second; consider limiting the live region to the status line.
- "Your criteria" card on the detail page is much shorter than "Why it matches" next to it and leaves dead space.
- `.step:not(:last-child)::after { content: "→" }` is announced by some screen readers; add `speak: none` equivalents or move to a decorative element with `aria-hidden`.
- The Applications board reuses the label "Ready to apply" for a column that is not a stage; fine, but make it visually distinct (it is, via the tint) and describe it in the page intro.

## Questions to consider

- What if every list view had exactly one filled button, and it was always the next stage of the pipeline for the first posting in view?
- Should the posting page be a review workspace (posting text beside the package) rather than a stack of cards?
- Does "Hide" need to exist beside "Not for me", or can one dismiss action carry the reason and a "never show again" option?
- Should the UI show expected LLM spend before any AI button is pressed, in line with the under-USD-1-per-run target?

## Constraint check

- **Offline:** every fix above uses the bundled font, inline SVG and existing same-origin routes. Nothing needs an external font, CDN or script.
- **Tokens:** any new colour (neutral surface, link underline colour, status variants) goes in `src/jobhunter/web/static/tokens.css`, with the dark overrides next to it.
- **Tests:** `tests/test_web.py` smoke tests (no external assets, one `h1`, labelled controls) should keep passing; most fixes only add labels, `aria-*` attributes and neutral styling. Changes to button hierarchy and layout should assert on text and `data-*` attributes, per CLAUDE.md. Tests were not run for this audit.
- **Spec-driven rules:** issues 1, 2, 5, 6 and 8 change user-visible behaviour, so each needs a spec change in `specs/` (and README/roadmap updates) before code, per CLAUDE.md.
