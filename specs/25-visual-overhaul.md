# 25 — Visual overhaul: "Flight Deck"

**Status:** DONE (approved by the author in conversation: mode, levers, four pipeline stages, new fonts and palette)

## 1. Problem

Spec 24 made the UI disciplined but not memorable. Every page is the same skeleton (sidebar, header, white rounded cards on a pale canvas), Home is a stock dashboard, the pipeline (search, score, package, apply) is not the visual spine, and the type and palette (one family, grey and orange) have no point of view. The mascot barely shows.

## 2. Goal / Design

Mode: **preserve brand, overhaul the visual language.** The mascot PNG (never redrawn), the name "Job Hunter" and the meaning stay. Composition, layout, hierarchy, palette, type and density change.

1. **The pipeline is the spine.** A four-stage strip (Search, Score, Package, Apply) is visible on every page, with a count per stage and the current next step marked. Home is built around it.
2. **New shell.** The 248px sidebar becomes a top bar: mascot, wordmark, the six nav links (labels unchanged), theme toggle. The strip sits under it.
3. **Palette from the mascot.** Navy-tinted neutrals, teal for information, one amber accent for the single primary action and match rings, with navy text on amber (never white). Status hues stay separate from the accent. Light and dark in `tokens.css`.
4. **Type with a point of view.** Bricolage Grotesque for display and big numerals, Atkinson Hyperlegible Next for UI and body, Spline Sans Mono for scores, counts and logs. All bundled woff2 (Latin and Latin-extended), OFL licences next to the files. No external requests.
5. **Posting page** gets a decision rail (score, verdict, the one primary, package state) beside the reading column.
6. **Actions** become rows grouped by stage; **Documents** a dense list; **Applications** columns aligned with the stages.
7. **Motion and states:** the strip and the ring animate once on load, all behind `prefers-reduced-motion`; mascot in empty, loading and error states.
8. Home absorbs the funnel; "why postings were left out" becomes a disclosure.

Not done: any change to routes, nav labels, form field names, `data-*` hooks, security rules, or the mascot art.

## 3. Principles and safety

Unchanged: manual only, no invented facts, local-first, no outbound requests, escape all posting text. Tokens-only CSS (`tests/test_css.py` stays as is; it is not weakened). One `h1` per page, labelled controls. Dark theme applied before paint.

## 4. Tests

- Existing 480 tests keep passing (`test_css`, `test_web` smoke, hooks).
- New: `pipeline_steps` returns four steps with one current; every page render includes the strip; strip counts match the database; no external URL in any rendered page.
- Negative: no colour/shadow/z-index literal in `style.css` (existing guard); fonts referenced in CSS exist in `static/fonts/`.

## 5. Tasks

- [x] Spec approved and indexed
- [x] Fonts bundled with licences; `tokens.css` rewritten (light and dark) (`test_no_page_requests_an_external_asset_and_every_font_file_exists`, `test_css`)
- [x] `style.css` rewritten; `base.html` shell with top bar and strip
- [x] `pipeline_steps` four stages; strip context in `render()`; tests (`test_pipeline_steps_are_four_with_one_current`, `test_pipeline_strip_is_on_every_page_but_home_owns_a_big_one`)
- [x] Recomposed: Home, posting page (decision rail), Actions (rows by stage), Documents (dense list), Matches (lead line, actions on the right, score first in each row), Applications (five columns with *Ready to apply* leading the flow), Settings (section list beside the panel) (`test_applications_board_starts_with_the_ready_column`, `test_matches_and_settings_are_composed_pages`)
- [x] Mascot in empty, loading (bobs in the live log panel while a run works) and error states (tilted); inline style removed from `error.html` (`test_loading_and_error_states_show_the_mascot`)
- [x] Score ring sweeps in once on load; `@property --pct`, off under reduced motion (`test_ring_animates_once_and_respects_reduced_motion`)
- [x] Checked in a real browser, light and dark, 1440 / 1280 / 390px, demo workspace (fonts, no external requests, no console errors, no horizontal scroll, sticky rail, one `Next` stage, tokens-only focus ring)
- [x] README screenshots refreshed from the demo workspace

## 6. Acceptance criteria

- [x] The strip is on every page and shows the next step (`test_pipeline_strip_is_on_every_page_but_home_owns_a_big_one`)
- [x] One filled primary per area; amber only for next action and match rings (`test_web.py` asserts one primary on Home, one on the posting page and none per Matches card; amber use checked by eye in the browser pass)
- [x] No route, nav label, field name or `data-*` hook changed (full suite, 483 passed)
- [x] `uv run pytest -q`, ruff and `scripts/check_docs.py` pass
- [x] Light and dark both checked in a browser

## Deviations

- **Fonts:** the first picks (Geist, Geist Mono, then Instrument Sans) were replaced by Atkinson Hyperlegible Next and Spline Sans Mono because the design checks list the first three as overused. Cyrillic and Greek are not bundled and fall back to the system font.
- **Amber and warn:** the accent amber (`#f5a524`) and the warn colour (`#8a5200` on `#fcefcb`) are in the same hue family. They are separated by use: warn is only tinted text, chips and callouts, never a filled control or the current-stage marker.
- **Current stage:** marked with a faint amber wash and an amber number chip (strip) or "Next" badge (Home), not a side stripe.
- **Mascot:** shown without a background tile in the top bar and empty states (a tile read as a grey square in light theme).
- **Home headline:** the `h1` is now a value proposition ("Hundreds of postings in. The few that fit you, ready to send."), with "Home" as an eyebrow.
- **Funnel on Home:** kept, but behind a disclosure ("See where postings dropped out") instead of two always-open cards.
- **Actions groups:** headings are now Search, Score, Package, Everything in order, Single steps, Maintenance (were Find jobs, Score and prepare, ...); `test_actions_page_groups_every_command` was updated, hooks (`data-runcard`, `data-spec`, `data-opt`) are unchanged.
- **Matches:** the score ring moved to the left of each row (score first, then company, then actions); the page head gained a one-line summary and the two actions moved to the right.
- **Applications:** the *Ready to apply* strip became the first of five board columns (Ready to apply, Applied, Screening, Interviewing, Offer) with an amber wash, so the flow reads left to right; `ready-strip` stays as its class.
- **Settings:** the five section tabs became a sticky list beside the panel on wide screens and a row of tabs on narrow ones; panels, ids, save bar and `data-*` hooks are unchanged.
- **Loading and error states:** loading is the mascot bobbing in the live log panel while a run works (not a full-page loader); error is the same mascot tilted in the empty-state frame.
- **Second browser pass:** the Matches, Applications and Settings recompositions, the dock mascot and the ring sweep were added after the first pass; a second pass in the browser confirmed them, and the README screenshots were refreshed again.
- **Home header:** the headline is a three-line staircase, the logo and text are centred, a small CV illustration (inline SVG, tokens only) sits on the right, and one orange dry-brush stroke (a static SVG, `static/img/brush.svg`: about 120 bristle paths along an S-shaped ribbon plus a roughening filter, used as a CSS mask and painted with the colour token `--brush`, so the Home page stays small and the stroke follows light and dark) runs behind the three elements instead of a boxed banner, and the band has no button: the current pipeline stage carries the page's single primary action ("Build 6 packages" in the Package column).
