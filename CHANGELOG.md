# Changelog

All notable changes. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The project is not versioned for release yet; everything below is under *Unreleased*.

## Unreleased

### Added
- Pipeline: public sources (Greenhouse, Lever, Ashby and five aggregators), hard filter, LLM scoring, tailored LaTeX CV and cover letter with verification, application tracking.
- Local web UI with settings editor, favorites, block list, postings added by hand, and the Kinetic Horizon visual identity (optional dark theme).
- `jobhunter init`, `jobhunter demo`, a source registry with a contract test, MIT license, CI, contribution files and a Docker image.
- The Muse as a source (no key needed), credential redaction, key status in `doctor` and Settings.
- `jobhunter doctor` prints how to fix each problem for your system.

### Changed
- `latex.engine` defaults to `auto` (tectonic if installed, else latexmk).
