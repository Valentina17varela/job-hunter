# 19 — Open source ready: license, contribution flow, install and plug-in sources

**Status:** DONE (the outside-reader trial was skipped by the author's decision; branch protection and labels are repository settings the author applies)

## 1. Goal

Anyone should be able to **find, install, try, trust and extend** the project without asking the author. Today it works for one person on one machine: there is no license, no CI, no contribution guide, sources are added by editing code, and setup assumes the author's folder layout. This spec closes those gaps without changing what the tool does or its principles (local-first, manual, no scraping of sites that forbid it).

Reviewed for ideas: *career-ops* (one-command init, doctor, per-provider modules, a "free / cheap" guide), *freehire* (add a source with one YAML line, CONTRIBUTING, MIT) and *JobSpy*. See §9 for what was deliberately not taken.

## 2. License and legal hygiene

- **MIT** (decided by the author). `LICENSE` at the root, `license = "MIT"` and `license-files` in `pyproject.toml`, a license line in the README. Copyright holder: the author, 2026.
- `NOTICE`-style credits in the README for third-party assets: Plus Jakarta Sans (SIL OFL, kept next to the font), the mascot logo (the author's), and the dependencies' own licenses (all permissive; `uv pip` license listing checked once before the first release).
- **Source terms** stay documented per source (03 §2): the project only uses public APIs and feeds, keeps the link back, and is for personal use. Contributors may not add sources that need a login, defeat bot protection or forbid automated use (§7).
- No personal data in the repository (already enforced by `.gitignore`); a CI check fails if files under `config/cv/`, `data/` or `out/` are tracked.

## 3. Contribution flow

| File | Content |
|---|---|
| `CONTRIBUTING.md` | Set up the dev environment in 3 commands; the spec-first rule (non-trivial changes start as a spec or a change to one); tests and ruff must pass; README and specs updated in the same change; commit/PR style; how to run the demo workspace |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1 (adopted as is, credited) with the author's contact for reports |
| `SECURITY.md` | How to report a vulnerability privately (GitHub security advisories), supported versions, and the threat model in one paragraph (local UI, SSRF-safe fetcher, locked config fields) |
| `.github/ISSUE_TEMPLATE/` | *Bug* (version, OS, what you ran, redacted log), *Source request* (site, link to its public API/terms), *Feature* (problem first, links the roadmap) |
| `.github/pull_request_template.md` | Checklist: tests, ruff, spec/README updated, no personal data, no new network access without a spec |
| `.github/workflows/ci.yml` | On every push and PR: `uv sync`, `ruff check`, `ruff format --check`, `pytest` on Python 3.12 and 3.13, Linux and macOS; the personal-data check of §2 |
| Doc-sync checks (in CI, `scripts/check_docs.py`) | Fail the build when the written rules are broken: every `jobhunter` CLI command and option appears in the README or `specs/07`; every key of the config model appears in `config/config.example.yaml`; every `specs/NN-*.md` has a valid `Status` and is listed in `specs/README.md`; every spec linked from the roadmap exists; no tracked file under `config/cv/`, `data/`, `out/`; no external URL in templates or CSS (also covered by tests). They turn the rules of `CLAUDE.md` into something a PR cannot skip |
| Labels | `good first issue` (new source adapters, new filter wording, docs), `needs-spec`, `source`, `ui` |

The README gets a short **Contributing** and **License** section pointing at these files. Branch protection and a release tag/changelog (`CHANGELOG.md`, Keep a Changelog) are done by the author in GitHub settings and recorded in `CONTRIBUTING.md`.

## 4. Install and first run for a stranger

Goal: from nothing to a working UI in a few minutes, with **no clone required**.

- **`uv tool install git+https://github.com/<owner>/job-hunter`** (and `pipx` equivalent) installs the `jobhunter` command. Publishing to PyPI is a later, optional step (the name must be checked first).
- **Workspace = the folder you run it in** (as today: `config/`, `data/`, `out/` relative to the current directory), created by **`jobhunter init [DIR]`**: copies `config.example.yaml` to `config/config.yaml`, the letter template and the sample CV, writes `.gitignore` entries, and prints the next two commands. It never overwrites an existing file. The first-run wizard (15) builds on it.
- Package data: the example config, sample CV, letter template and `company_candidates.txt` ship **inside the package** so `init` works from an installed tool.
- **Sample CV and sample profile** (fictional, marked with `% jh:` markers) so a newcomer can run the whole pipeline on the demo workspace before touching their own data: `jobhunter demo` (wraps `scripts/seed_demo.py`) writes `data/demo/` and starts the UI on it.
- `jobhunter doctor` already checks tectonic and the LLM backend; it gains **actionable fixes per OS** (macOS/Linux/Windows-WSL commands) and a link to the matching docs section.
- **Windows:** supported through WSL; documented, not tested natively.

### 4.1 Docker (optional path)

- `Dockerfile` (python:3.12-slim, `uv`, tectonic) and `compose.yaml` that mounts the workspace as a volume and publishes the UI **only on `127.0.0.1:8765`**.
- Inside a container the UI must listen on `0.0.0.0` for the port mapping to work, so `jobhunter ui` gets **`--bind ADDRESS`** (default `127.0.0.1`). The **Host/Origin allow-list does not change**: only `127.0.0.1`/`localhost` host names are accepted, so exposing the port beyond localhost needs an explicit `--allow-host` and prints a warning. Tests cover both.
- TeX Live (`latexmk`) instead of tectonic in the image, because tectonic has no official arm64 Linux binary. The `claude` CLI is **not** in the image; the container is meant for the OpenAI-compatible or Anthropic API backends (20). Using a subscription through a mounted CLI login is documented as unsupported.
- PDFs compile offline in the image (TeX Live).

## 5. Plug-in sources (add a source without touching core code)

Today `build_sources` has a hard-coded `if/elif` per aggregator and `ATS_SOURCES` for company boards (03).

- **Registry:** a decorator `@register_source("themuse", config_key="themuse")` in each module under `src/jobhunter/sources/`; the package imports its modules, `build_sources` asks the registry. A source declares: `name`, how to build instances from config (`build(config) -> list[Source]`), the **env keys** it needs (14 §3), and a one-line description and terms URL shown in Settings → Sources and in the docs table.
- **Company-board ATS** adapters register the same way (`ats="breezy"`), so `companies.yaml` accepts them with no other change.
- **`docs/ADDING_A_SOURCE.md`:** a 10-step recipe (check terms; find the public endpoint; save a trimmed real fixture; write `fetch()` returning `Job`s; map salary and remote conservatively; register; add the config block; tests with respx; add a row to the sources table; PR). Includes the "robust parsing" rules of 03 §6 and the **do-not-add list** of §7.
- **Contract test** (`tests/test_source_contract.py`): every registered source has a fixture, parses it into valid `Job`s, skips a malformed item without failing, and never calls the network without a mock. A new source that skips this test fails CI.
- **Third-party sources** (a package exposing the entry-point group `jobhunter.sources`) are **not** supported yet; trusting arbitrary code that runs with the person's CV and keys needs its own security spec.

## 6. Documentation for users (not only for developers)

- `docs/SETUP.md` (install, init, first run, tectonic, backend choice), `docs/FAQ.md` (why no LinkedIn, why manual, where is my data, what is sent to the LLM, how to delete everything), `docs/RUNNING_CHEAP.md` (costs per backend, local models, call caps; arrives with spec 20), `docs/SUPPORTED_SOURCES.md` (generated table from the registry: source, type, key needed, terms link).
- The README stays the front door (what works today) and links these. The roadmap and specs stay the source of truth for planned work.
- **Translations** of the README and a Spanish UI are listed as ideas, not part of this spec; they need a string-extraction pass first.

## 7. Do-not-add list (written into CONTRIBUTING and the source recipe)

- Sources behind a login, or that need defeating bot protection, proxy rotation or fingerprint spoofing (LinkedIn, Indeed, Glassdoor scrapers).
- Anything that applies, fills application forms, sends messages or emails on the person's behalf.
- Telemetry, analytics, remote logging, or any network access that is not a job source, the LLM backend the person configured, or the single page fetch of spec 10.
- Credentials stored in config files, the database or the UI (keys live in environment variables only, 14 §3).
- Hosted or multi-user deployments (the security model assumes one person on localhost).

## 8. Tasks

- [x] MIT `LICENSE`, `license` in `pyproject.toml`.
- [x] README: license and contributing sections, install paths (tool, clone, Docker), CLI reference for the new commands.
- [x] `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1, condensed with attribution), `SECURITY.md`, issue and PR templates, `CHANGELOG.md`.
- [x] CI workflow (`.github/workflows/ci.yml`: ruff, format check, pytest on 3.12/3.13, Linux/macOS) and `scripts/check_docs.py` (CLI and config documented, specs have a status and are indexed, roadmap links exist, no personal files tracked, generated sources doc current). *Not yet run on GitHub.*
- [x] Source registry (`sources/registry.py`, auto-import), existing sources migrated, `config.sources.aggregators` and `companies.yaml` `ats` validated against it, Settings reads it, contract test (`tests/test_source_contract.py`), `docs/ADDING_A_SOURCE.md`, generated `docs/SUPPORTED_SOURCES.md`.
- [x] Bundled examples (`resources.py`, wheel `force-include`), `jobhunter init` (never overwrites, updates `.gitignore`), `jobhunter demo`, fictional sample CV `config/cv.example.tex` (`tests/test_init_demo.py`). Verified by building the wheel and running `init`, `cv check`, `demo` and `doctor` from a clean virtualenv.
- [x] `jobhunter ui --bind` / `--allow-host`: warning when not loopback, Host allow-list unchanged (tests for foreign, local and extra hosts).
- [x] `Dockerfile`, `compose.yaml`, `.dockerignore`. *Written and `compose config` validates; the image has not been built yet.*
- [x] `docs/SETUP.md`, `docs/FAQ.md`.
- [x] Docker image built and the first-run flow run in it. Fixes found: `python:3.12-slim` is now Debian trixie (pinned to `-bookworm`), and tectonic has no official arm64 Linux build, so the image uses TeX Live (`latexmk`, about 1.1 GB) and `latex.engine` gained `auto` (tectonic if installed, else latexmk). Verified: `init --sample-cv`, `doctor` (latexmk compiles the CV), `cv check`, `demo`, UI answers 200 on 127.0.0.1:8765 and 403 for a foreign Host.
- [x] `doctor` hints per system: `detect_system()` (macOS, Linux, WSL, Docker, Windows) and a `fix:` line under each failing check with the install command and a link into `docs/SETUP.md` (`tests/test_cli_doctor.py`).
- [x] First CI run on GitHub: all jobs green (reported by the author). Branch protection, required checks and labels are set in the repository settings (recorded in `CONTRIBUTING.md`).
- [ ] Someone who has never seen the project follows only the README: **skipped by the author's decision**; revisit when the first outside user appears.
- [x] This spec marked done.

## 9. Not taken from the reviewed projects

- A hosted, multi-user service with Postgres, Meilisearch and Redis (freehire): a different product; ours is a single-person local tool.
- Scraping LinkedIn/Indeed/Glassdoor through proxies (JobSpy), auto-apply and form filling, Gmail/Notion plug-ins, Telegram or e-mail digests: against the principles above.
- A slash-command agent as the only interface (career-ops): our UI and CLI stay deterministic where possible; the LLM is used for scoring and writing only.

## 10. Acceptance criteria

- [ ] (skipped, see §8) A person who has never seen the repository installs it, runs the demo and starts the UI by following only the README, on macOS and Linux.
- [x] CI is green (first run on GitHub, reported by the author); a PR that breaks lint, tests or the source contract is blocked.
- [x] A new source can be added by creating one module and one fixture, with no edit to `pipeline.py` or `build_sources` (`tests/test_source_contract.py`; company-board types also add their name to `models.ATS_SOURCES`).
- [x] The repository contains a license, a code of conduct, a security policy and contribution templates; no personal data is tracked (`scripts/check_docs.py`).
