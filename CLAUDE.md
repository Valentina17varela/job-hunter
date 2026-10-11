# job-hunter

Local Python pipeline that finds job postings on direct portals, filters and scores them, and prepares application packages for human review. Full design in `specs/`.

## Conventions

- **Language: English for everything** — code, identifiers, comments, docstrings, docs, specs, commit messages, PR text, config keys, CLI output, and generated-package tooling text. The only non-English content is the person's own profile data and postings in other languages.
- **Spec-driven development:** specs in `specs/` are the source of truth. Do not implement a feature until its spec is approved. Propose spec changes before diverging from them; keep specs updated when decisions change.
- Work task by task from `specs/08-roadmap.md` (a flat list, no phases); stop for review after each task.
- Request personal data only when the task needs it (see `specs/00-overview.md` §7).
- **CV and cover letter are LaTeX** (input `config/cv/master.tex`, output `.tex` + compiled `.pdf`). Code copies the person's original LaTeX verbatim; the LLM never sees the preamble/header (contact details). See `specs/06-tailoring.md`.
- **The README describes only what works today.** Planned features, ideas and "coming soon" lists never go in it; they live in the specs and in `specs/08-roadmap.md`. When a task ships, move it from the roadmap to the README in the same change.
- **Keep `README.md` current, every time, in the same change:** any new, removed or altered feature must be reflected in the README before the work is reported as done. That covers commands and CLI options, config keys, sources, statuses, file layout, **web UI pages and what they can do**, security/privacy behaviour and new dependencies. Update the specs too. Screenshots are optional (only refresh them when a page changes a lot); the feature description is not optional.
- Repo holds only code, specs, tests, `config/config.example.yaml` and `config/company_candidates.txt`. Never commit `config/config.yaml`, `config/companies.yaml`, `config/cv/`, `data/`, `out/`, or any API key. Keep `config.example.yaml` in sync with the config model.
- Stack: Python 3.12, uv, httpx, pydantic v2, SQLite, typer, pytest, ruff.
- No test makes real network or LLM calls.
- The system never sends applications or messages; the human sends.
- **Manual only:** no cron/launchd, daemon, scheduler or notification. Every stage is triggered by the person from the CLI or the web UI.
