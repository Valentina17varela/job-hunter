# job-hunter

Local Python pipeline that finds job postings on direct portals, filters and scores them, and prepares application packages for human review. Full design in `specs/`.

## Conventions

- **Language: English for everything** — code, identifiers, comments, docstrings, docs, specs, commit messages, PR text, config keys, CLI output, and generated-package tooling text. The only non-English content is the person's own profile data and postings in other languages.
- **Spec-driven development:** specs in `specs/` are the source of truth. Do not implement a phase until its specs are approved. Propose spec changes before diverging from them; keep specs updated when decisions change.
- Work phase by phase (see `specs/08-roadmap.md`); stop for review at the end of each phase.
- Request personal data only when the current phase needs it (see `specs/00-overview.md` §7).
- **CV and cover letter are LaTeX** (input `config/cv/master.tex`, output `.tex` + compiled `.pdf`). Code copies the person's original LaTeX verbatim; the LLM never sees the preamble/header (contact details). See `specs/06-tailoring.md`.
- Never commit `config/cv/`, `data/`, `out/`, or any API key.
- Stack: Python 3.12, uv, httpx, pydantic v2, SQLite, typer, pytest, ruff.
- No test makes real network or LLM calls.
- The system never sends applications or messages; the human sends.
