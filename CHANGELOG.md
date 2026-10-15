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
- Interaction polish: focus and scroll position survive actions that reload the page, one transition token, pressed states, page cross-fades, long-lived caching for versioned assets and a preloaded font.
- *Posted* filter and live filters in Job matches.
- Top matches board (always your best 5), *Not for me* reasons, `jobhunter top --fill`.
- Get on Board and Himalayas as sources (no key needed).
- The Muse as a source (no key needed), credential redaction, key status in `doctor` and Settings.
- `jobhunter doctor` prints how to fix each problem for your system.

### Changed
- `latex.engine` defaults to `auto` (tectonic if installed, else latexmk).
