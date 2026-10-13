# Contributing

Thanks for helping. Job Hunter is a small, deliberately opinionated tool: **local, manual, human-in-the-loop, no scraping that sites forbid.** Contributions that fit that are very welcome.

## Set up (3 commands)

```bash
git clone https://github.com/Valentina17varela/job-hunter && cd job-hunter
uv sync                                   # Python 3.12+ and dependencies (install uv first)
uv run jobhunter demo --open              # the UI with fictional data; touches none of your data
```

Check your work with:

```bash
uv run pytest -q                                  # no network, no LLM
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_docs.py               # docs, specs, example config, personal files
```

LaTeX (tectonic) is only needed for the tests marked as such; they skip when it is missing.

## How we work: specs first

1. **Start from a spec.** Anything beyond a small fix begins as a new spec or a change to one in [`specs/`](specs/) (index, statuses and a template in [`specs/README.md`](specs/README.md)). Open an issue or a draft PR with the spec and wait for the maintainer's OK before building a big feature: it saves you work.
2. **One task at a time** from [`specs/08-roadmap.md`](specs/08-roadmap.md).
3. **Definition of done**, in the same PR: tests and ruff pass; the spec's status, tasks and acceptance criteria are updated (tick only what is verified); the roadmap is updated; **the README describes any user-visible change**; `config/config.example.yaml` matches the config model. The PR template has the checklist; CI enforces what it can.
4. **English everywhere:** code, comments, docs, specs, commits.

The details agents and humans both follow are in [`CLAUDE.md`](CLAUDE.md) (the short version for other tools is [`AGENTS.md`](AGENTS.md)).

## What we do not accept

These break the project's principles, so please do not send them (they will be closed politely):

- Sources behind a login, or that need to defeat bot protection, proxy rotation or fingerprint spoofing (LinkedIn, Indeed, Glassdoor scrapers).
- Anything that applies, fills application forms, or sends messages or e-mails on the person's behalf.
- Telemetry, analytics, remote logging, or any network access that is not a job source, the LLM backend the person configured, or the single page fetch of spec 10.
- Credentials in config files, the database or the UI (keys live in environment variables only).
- Background jobs, schedulers or notifications (everything is started by the person).
- Hosted or multi-user deployments.
- Loading third-party code as plug-ins.

## Adding a source (the easiest first contribution)

One module, one fixture, one test. Follow [`docs/ADDING_A_SOURCE.md`](docs/ADDING_A_SOURCE.md). Issues labelled `good first issue` and `source` are a good place to start.

## Tests

- Never a real network or LLM call: use `respx` and fake backends. Each test runs in an empty temp dir.
- Source adapters: a trimmed **real** response in `tests/fixtures/`.
- Security-relevant changes get a negative test (foreign Host, path traversal, private IP, key in a log, XSS payload).
- UI changes: keep the smoke tests in `tests/test_web.py` green (no external assets, one `h1`, labelled controls).

## Commits and pull requests

Short imperative subject with a tag, for example `[FEAT] - add Himalayas source`, `[FIX] - ...`, `[DOCS] - ...`. One topic per PR. Never include personal data (your CV, `config/config.yaml`, `data/`, `out/`, keys); CI fails if they are tracked.

## Maintainers

Releases are tagged by the maintainer, who keeps [`CHANGELOG.md`](CHANGELOG.md). Recommended repository settings: protect the default branch, require the CI checks, and label issues `good first issue`, `needs-spec`, `source`, `ui`.

## Conduct and security

Be kind: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Report vulnerabilities privately: [`SECURITY.md`](SECURITY.md).
