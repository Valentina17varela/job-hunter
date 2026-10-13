# AGENTS.md

Instructions for AI coding agents (Codex, Cursor, Claude Code, …). The full version is [`CLAUDE.md`](CLAUDE.md); read it. The essentials:

- **What this is:** a local, manual, human-in-the-loop job-search copilot (Python 3.12, uv, SQLite, FastAPI UI). It never applies or sends anything.
- **Spec-driven:** `specs/` is the source of truth (index and template in `specs/README.md`). No spec → no code. Work one task at a time from `specs/08-roadmap.md`, then stop for review. Do not commit unless asked.
- **Commands:** `uv sync` · `uv run pytest -q` · `uv run ruff check . && uv run ruff format --check .` · `uv run python scripts/check_docs.py` · demo data: `uv run python scripts/seed_demo.py`.
- **Definition of done:** tests + ruff pass; spec status/tasks/criteria updated; roadmap updated; **README updated for any user-visible change**; `config/config.example.yaml` in sync. Details in `CLAUDE.md` §"How we work".
- **Never:** commit personal data (`config/config.yaml`, `config/cv/`, `data/`, `out/`, keys); make real network/LLM calls in tests; run the real pipeline on the person's data; add scrapers that need a login or defeat bot protection; add telemetry, background jobs or auto-apply.
- **English everywhere** in code, docs, specs and commits.
