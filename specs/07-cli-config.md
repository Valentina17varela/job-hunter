# 07 — CLI, config and privacy

## 1. Commands

| Command | What it does |
|---|---|
| `jobhunter run` | Full pipeline (fetch → filter → score → tailor → export) |
| `jobhunter run --stage fetch\|filter\|score\|tailor` | A single stage |
| `jobhunter run --dry-run` | Shows what it would do and the estimated cost, without calling the LLM |
| `jobhunter refilter` | Re-applies filters to already-downloaded postings; prints how many each rule rejected |
| `jobhunter review` | Lists packages pending review (score, company, link) |
| `jobhunter show <id>` | Posting detail + score + package path |
| `jobhunter explain <id>` | Why it was filtered / its score |
| `jobhunter mark <id> applied\|replied\|rejected\|closed [--note]` | Updates status |
| `jobhunter stats` | Funnel (fetched → passed → scored → packaged → applied → replied) and cumulative cost |
| `jobhunter companies check` | Validates `companies.yaml` slugs (200 vs 404) |
| `jobhunter companies discover` | Probes names in `company_candidates.txt` and adds boards that exist to `companies.yaml` |
| `jobhunter calibrate` | Scoring calibration (see 05) |
| `jobhunter cv init` | One-time helper: proposes `jh:` markers and IDs for a plain LaTeX CV (output reviewed by the person) |
| `jobhunter cv check` | Validates `master.tex` markers (unique IDs, balanced sections) and compiles it |
| `jobhunter cv translate --lang <code>` | One-time translation of the master CV items/labels into `config/cv/translations/<code>.json` for the person to review |
| `jobhunter doctor` | Checks the LaTeX toolchain, config, and the LLM backend (`claude` logged in, or API key) |

## 2. Full `config.yaml` (reference)

The committed template is `config/config.example.yaml`; each person copies it to `config/config.yaml`, which is gitignored (as are `config/companies.yaml`, `config/cv/`, `data/` and `out/`), so the repository contains only code and examples.

```yaml
sources:                           # see 03-sources.md
  aggregators: [remotive, remoteok, weworkremotely, arbeitnow, jobicy]
  wwr_categories: [remote-programming-jobs, remote-back-end-programming-jobs]
  arbeitnow_pages: 3
  companies_file: config/companies.yaml
  candidates_file: config/company_candidates.txt
  max_concurrency: 5
  max_per_host: 2
  stale_days: 7

search: { ... }                    # see 04-filtering.md

llm:
  backend: claude_cli              # claude_cli (subscription) | anthropic_api (API key)
  claude_path: claude              # executable for claude_cli
  timeout_seconds: 180             # per call
  max_attempts: 3
  effort: low                      # claude --effort
  max_thinking_tokens: 0           # 0 = extended thinking off (fast, cheap)

scoring:
  model: haiku                     # alias for claude_cli; e.g. claude-haiku-5-5 for the API
  score_threshold: 75
  batch_size: 8                    # postings per LLM call
  max_description_tokens: 1500
  max_profile_tokens: 3000
  candidate_context: ""            # ← where you live and how you can work; read by the scorer
  use_batch: false                 # API backend only

tailoring:
  model: sonnet                    # alias for claude_cli; e.g. claude-sonnet-5-5 for the API
  mode: select                     # select | rewrite
  max_packages_per_day: 10
  languages: ["en", "es"]          # package language = posting language if it is in the list, else "en"
  tone: ""                         # ← defined by the person
  max_cv_pages: 1

latex:
  engine: tectonic                 # tectonic | latexmk
  timeout_seconds: 60

budget:
  max_llm_calls_per_run: 60        # claude_cli backend
  daily_budget_usd: 1.00           # anthropic_api backend

fx_rates_to_usd: { EUR: 1.08, COP: 0.00025, GBP: 1.27 }   # manual updates

paths:
  cv_master: config/cv/master.tex
  letter_template: config/cv/letter_template.tex
  db: data/jobhunter.db
  out: out/
```

## 3. Environment variables

| Variable | Use |
|---|---|
| `ANTHROPIC_API_KEY` | Only for `llm.backend: anthropic_api`. Never in files or logs. Ignored (and stripped) by the default `claude_cli` backend, which uses your `claude auth login` session |

## 4. Daily scheduling

v1: manual run or `cron`/`launchd` on the Mac calling `jobhunter run`. A `launchd` example is documented in the README. No server.

## 5. Privacy and data limits

- **Sent to the LLM:** plain text of the `jh:`-marked items from `master.tex` (or a summary of them) and the posting text.
- **Never sent:** the LaTeX preamble and everything outside `jh:` markers (header with name, phone, email, address, links). Those parts are copied verbatim into the output by code.
- **Must not be inside `jh:` items:** phone, address, documents, date of birth, current salary. A check on load warns if it detects such patterns inside marked items and asks for confirmation.
- Logs: no CV content or full LLM responses by default (`--verbose` enables them).

## 6. Logging

Standard `logging`, INFO level by default. Summary at the end of `run`:

```
fetched 1,240 · new 87 · passed 22 · scored 22 · selected 6 · packaged 6
LLM cost today: $0.18 / $1.00
```

## 7. Acceptance criteria

- [ ] `--dry-run` makes no network call to the LLM.
- [ ] Invalid config → clear error with the field and line.
- [ ] Without a logged-in `claude` (or an API key for the API backend), the fetch and filter stages work; score/tailor fail with an actionable message (`claude auth login`).
- [ ] Marked items with detected sensitive data → warning before any send.
- [ ] `jobhunter doctor` reports the LaTeX engine found, compiles a minimal document and `master.tex`, and exits non-zero with an actionable message if either fails.
