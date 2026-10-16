# Changelog

All notable changes. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project is not versioned for release yet; everything below is under *Unreleased*.

## Unreleased

### Added
- Pipeline: public sources (Greenhouse, Lever, Ashby and five aggregators), hard filter, LLM scoring, tailored LaTeX CV and cover letter with verification, application tracking.
- Local web UI with settings editor, favorites, block list, postings added by hand, and the Kinetic Horizon visual identity (optional dark theme).
- `jobhunter init`, `jobhunter demo`, a source registry with a contract test, MIT license, CI, contribution files and a Docker image.
- One orange voice: neutral avatars, badges, tags and chips, flat surfaces, a real type scale, honest icons (sliders for Settings, sprite stars and close buttons).
- Accessibility floor: labelled controls everywhere, announced status messages, skip link, landmarks, 24 px targets, reduced motion, a real 404 page, theme applied before first paint.
- Home as a cockpit: slim header with the one next action ("Score 12 postings"), inline KPI strip, "what to do next" first, a three-step pipeline list, system check only when something required fails.
- Quieter job cards and posting page: one visible button per row plus a ⋯ menu, *Hide* merged into *Not for me*, one filled primary per page area, "Build N packages for your top 5" at the board's head, posting text beside the package.
- Applications board fits 1280 px (ready strip + four columns, "applied N days ago", undo on stage change); Settings shows one tab at a time with a single save bar that enables itself when something changed.
- One voice: you/your everywhere, "Matches" in the nav, buttons that carry their verb (Search, Score, Build packages… instead of thirteen "Run"), readable work modes, dates and statuses instead of raw tokens.
- `DESIGN.md` and `PRODUCT.md` refreshed for "The Quiet Cockpit"; a second Impeccable audit (16/20, was 11/20) with detector and browser evidence; wordmark contrast, mobile overflow and board-stripe fixes.
- Interaction polish: focus and scroll position survive actions that reload the page, one transition token, pressed states, page cross-fades, long-lived caching for versioned assets and a preloaded font.
- *Posted* filter and live filters in Job matches.
- Top matches board (always your best 5), *Not for me* reasons, `jobhunter top --fill`.
- Get on Board and Himalayas as sources (no key needed).
- The Muse as a source (no key needed), credential redaction, key status in `doctor` and Settings.
- `jobhunter doctor` prints how to fix each problem for your system.

### Changed
- Home: the pipeline steps show their own state and the current one is marked "Next"; the KPI strip and the separate "What to do next" list are gone, and empty cards are hidden until there is data.
- Matches: *Source*, *Posted* and *Mode* fold into *More filters*, and the duplicate *Favorites* filter is gone (the *Favorites* tab stays). Actions: *Find jobs* and *Score and prepare* lead, single steps and maintenance are under *More tools*, and per-card posting ids, limit and rebuild are under *Only some postings*.
- Posting page: the posting text is set as readable prose (body font, 68-character lines, no code box) instead of monospace.
- Clearer copy: no "— → New" in a posting's history, "Matches" everywhere instead of "Job matches", and plain explanations for unscored postings and package cost.
- Home side notes carry an amber (needs follow-up) or sky (information) icon, and upcoming interviews use the amber tile DESIGN.md already specified.
- Home says what to do once packages are ready ("Apply on the company site, then mark it as applied here"), and marking a posting Applied or Offer gets a short human acknowledgement in the undo toast.
- `latex.engine` defaults to `auto` (tectonic if installed, else latexmk).
