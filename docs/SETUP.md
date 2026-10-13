# Setup

Job Hunter runs on your own machine. You need Python 3.12+ (installed for you by `uv`), a LaTeX engine for the PDFs and an AI backend. Nothing runs by itself: you start every stage.

## 1. Install

### macOS

```bash
brew install uv tectonic
uv tool install git+https://github.com/Valentina17varela/job-hunter
```

### Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh          # uv
curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh   # tectonic
uv tool install git+https://github.com/Valentina17varela/job-hunter
```

(or your package manager's `tectonic`; see <https://tectonic-typesetting.github.io>). tectonic downloads its TeX bundle the first time it compiles, so the first PDF needs internet. Alternatively install TeX Live with `latexmk` (`sudo apt install latexmk texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended lmodern`); with `latex.engine: auto` (the default) the tool uses whichever it finds.

### Windows

Use WSL (Ubuntu) and follow the Linux steps. Native Windows is not tested.

### From a clone (to change the code)

```bash
git clone https://github.com/Valentina17varela/job-hunter && cd job-hunter
uv sync
uv run jobhunter --help
```

Use `uv run jobhunter …` instead of `jobhunter …` in the rest of this guide.

## 2. Create a workspace

```bash
mkdir my-job-search && cd my-job-search
jobhunter init --sample-cv      # config/, letter template and a fictional sample CV
jobhunter doctor                # tells you what is missing and how to fix it
```

Want to look around first? `jobhunter demo --open` starts the UI on fictional data and touches nothing of yours.

## 3. Choose the AI backend

| Backend | You need | Cost |
|---|---|---|
| `claude_cli` (default) | A Claude subscription and `claude auth login` once in your terminal (install the `claude` CLI first) | Your plan's usage limits |
| `anthropic_api` | `export ANTHROPIC_API_KEY=…` and `llm.backend: anthropic_api` | Pay per use; set `budget.daily_budget_usd` |

More options (Ollama, OpenRouter, OpenAI-style servers) are planned in [specs/20](../specs/20-openai-compatible-backend.md). Keys are only ever read from environment variables.

## 4. Tell it what you want

Edit the `search:` block of `config/config.yaml`, or use the UI (**Settings → What I'm looking for**). Put your LaTeX CV at `config/cv/master.tex` and mark it (README → *Your LaTeX CV*), or start from the sample CV. Describe how you can work in `scoring.candidate_context`.

## 5. Run

```bash
jobhunter ui --open     # Home → Search for new jobs → Score with AI → Build packages
```

or `jobhunter run --stage search` etc. from the terminal. You review the documents and apply yourself.

## Docker

For a machine without Python or LaTeX. The `claude` CLI is **not** in the image, so use an API key (`anthropic_api`).

```bash
mkdir workspace
docker compose run --rm jobhunter jobhunter init --sample-cv     # once
ANTHROPIC_API_KEY=… docker compose up                            # UI at http://127.0.0.1:8765
```

- Your data lives in `./workspace` (config, database, documents), outside the container.
- The port is published on `127.0.0.1` only. The UI has no login: never publish it on other interfaces.
- The image (about 1.1 GB) contains TeX Live and uses `latexmk` (`latex.engine: auto`), so PDFs compile offline and on both amd64 and arm64. It was built and run end to end (init, doctor, CV check, UI reachable on 127.0.0.1, foreign Host refused); CI does not build it yet.

## Troubleshooting

`jobhunter doctor` prints a `fix:` line under every problem it finds, for your system. The common ones:

| Symptom | Fix |
|---|---|
| `tectonic not found` | Install tectonic or a TeX Live with `latexmk` (above); `jobhunter doctor` shows which engine it found |
| `claude is not logged in` | Run `claude auth login` in your own terminal |
| UI says the host is not allowed | Open it as `http://127.0.0.1:8765` (not another host name) |
| No postings after Search | Loosen `search:` (see `jobhunter explain ID` for why one was dropped), check `jobhunter doctor` |
