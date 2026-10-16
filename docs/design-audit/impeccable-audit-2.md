# Impeccable Audit 2: whole web UI after spec 24

Target: `src/jobhunter/web/` (templates, `static/tokens.css`, `static/style.css`, `static/app.js`, `app.py`).
Date: 2026-10-15. Standard: WCAG 2.2 AA, `DESIGN.md` ("The Quiet Cockpit"). Mode: audit; the findings below that were cheap and in scope were fixed in the same pass (listed under *Fixed during this audit*).

**Evidence this time (the first audit had none):** `impeccable detect` against the running demo workspace (7 pages, real rendered DOM), a Playwright pass over 9 URLs at 1280 and 390 px (heading count, horizontal overflow, controls without an accessible name, targets under 24 px, console errors), screenshots in light, dark and 390 px, the test suite (480 passing) and `scripts/check_docs.py`.
**Not tested:** a screen reader, real touch gestures (emulated viewport only), the detector in dark theme (it drives its own light browser), a full keyboard walk-through (focus restore after actions was checked, tab order was not).

## Audit Health Score

| # | Dimension | Before | After | Key finding |
|---|---|---|---|---|
| 1 | Accessibility | 2 | **3** | Every control named, one `h1`, live regions, skip link, `aria-current`; a few inline links under 24 px tall |
| 2 | Performance | 3 | **3** | Immutable cache headers, preloaded font, no external requests; every action still reloads the page (focus and scroll are restored, in-place updates deferred) |
| 3 | Theming | 2 | **4** | One token file (light and dark side by side), `color-scheme`, theme applied before paint, no literals in `style.css` (test-enforced) |
| 4 | Responsive Design | 2 | **3** | Board fits 1280 px, no horizontal scroll at 390 px on any page after the fixes below; some row links shorter than 44 px |
| 5 | Implementation Integrity | 2 | **3** | One rule per selector, one orange voice, shape by role, state-based statuses; the kanban card-in-column is the only nested surface, and the font is a known deliberate choice |
| | **Total** | **11 / 20** | **16 / 20** | **Good** (14-17: address the weak dimensions) |

Critique score was not re-run in this pass (it was 27/40); run `/impeccable critique` to compare.

## Implementation Integrity Verdict

**Pass.** The detector reports two findings on the whole UI after the fixes: `overused-font` (Plus Jakarta Sans, a documented author-confirmed keep, `DESIGN.md` §Typography) and `nested-cards` on Applications (kanban cards inside a column, the one documented exception). Orange is now one voice (primary button, match ring, active-nav bar), statuses are explicit rules, and `tests/test_css.py` fails the build on literals, duplicate selectors, glyph icons and stray caps.

## Fixed during this audit

- **[P1→done] Wordmark contrast.** "Hunter" in the sidebar was `#f97316` on white (2.8:1, below even the 3:1 large-text bar). Now `--accent-text` (5.2:1 light, readable in dark).
- **[P2→done] Horizontal scroll at 390 px** on the posting page (History table with `nowrap` cells) and Settings (the long config path in `<code>`): `nowrap` is released under 860 px and `code` wraps anywhere.
- **[P2→done] Cramped chips.** Chip vertical padding raised so text has the recommended space inside its box (the interview chip on board cards).
- **[P2→done] Side-stripe on board columns.** The 3 px top stripe was flagged as a side-tab tell; the stage is now an 8 px dot before the column title.

## Remaining findings

- **[P3] Small targets.** Header links such as "All matches →" and the job-title links in rows are about 21-23 px tall (the 24 px minimum is met by controls, not by these inline links; 44 px on mobile is not met for them). Category: Responsive/Accessibility. Suggested: `/impeccable adapt`.
- **[P3] Every action reloads the page.** Focus and scroll are restored (`reloadHere()`), which removes the disorientation, but a full reload remains. Category: Performance. Suggested: `/impeccable optimize` when the in-place row updates of spec 24 D5 are taken.
- **[P3] No inline CV and letter preview or named verification checks** on the posting page (deferred in slice 6). Category: Implementation. Suggested: `/impeccable shape`.
- **[P3] Dark theme not detector-checked.** Contrast pairs were verified when the tokens were made and the dark screenshots were reviewed, but the detector only saw light. Suggested: `/impeccable audit` with a dark-mode capture.
- **[P3] Accepted detector notes:** `overused-font` and `nested-cards` above.

## Positive findings

- A single token source, with a test that keeps it that way.
- Honest states: every posting status and application stage has a rule; empty, error (404) and loading states exist.
- Accessibility floor: labels tied to controls, `fieldset/legend`, live regions for toasts, saves and filter results, skip link, landmarks, `aria-current`, reduced motion with an alternative (state still changes, motion does not).
- Calm hierarchy: one filled action per area, flat rows, shape by role, plain voice with verbs and amounts on buttons.
- Delivery: long-lived cache on versioned assets, preloaded bundled font, no request leaves the machine.

## Recommended actions

1. **[P3] `/impeccable adapt`**: lift row and header links to a comfortable touch height on mobile.
2. **[P3] `/impeccable critique`**: re-score the UX (previous 27/40) against the shipped result.
3. **[P3] `/impeccable shape`**: design the inline package review (preview and named checks).
4. **[P3] `/impeccable polish`**: final pass once the above land.
