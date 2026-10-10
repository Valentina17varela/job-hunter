# Job Hunter

Local Python pipeline that finds job postings on direct portals, filters and scores them, and prepares LaTeX application packages for human review. Design lives in [`specs/`](specs/); conventions in [`CLAUDE.md`](CLAUDE.md).

## Setup

```bash
brew install uv tectonic
uv sync
uv run jobhunter doctor
```

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
