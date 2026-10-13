## What and why

<!-- One or two sentences. Link the spec (specs/NN-*.md) and the roadmap task. -->

## Checklist

- [ ] There is an approved spec (or this only changes docs/tests), and its status, tasks and acceptance criteria are updated
- [ ] `uv run pytest -q`, `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run python scripts/check_docs.py` passes
- [ ] README updated for anything user-visible (commands, config keys, sources, UI, privacy)
- [ ] `config/config.example.yaml` in sync with the config model
- [ ] No personal data, keys, CVs or generated files are included
- [ ] No new network access beyond job sources, the configured LLM backend and the single page fetch of spec 10
