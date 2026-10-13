# 00 — Overview

**Status:** LIVING (describes the system as it works today)

## 1. Problem

Searching for jobs by hand is repetitive: checking many portals, filtering by salary/location/stack, and tailoring a CV and cover letter for each posting. "All-in-one" agents burn many tokens (the LLM acting as a browser) and automate mass-sending, which lowers quality and puts accounts at risk.

## 2. Goal

A local Python pipeline that, **whenever the person triggers it** (nothing runs in the background, there is no scheduler):

1. Discovers new postings on **direct portals** (public ATS APIs and aggregators).
2. Discards those that fail hard criteria, without using an LLM.
3. Scores the remainder with a cheap LLM.
4. For the best ones, generates a **ready-to-review package** (tailored CV, cover letter, notes).
5. Lets the **human review and send**.

## 3. Design principles

- **Code first, LLM last.** The LLM only does what needs judgment. Discovering, deduplicating and filtering are deterministic code.
- **Bounded, measurable cost.** Every LLM call logs tokens and cost. There is a configurable daily cap.
- **No hallucinations.** The LLM selects and reorders facts from the person's LaTeX master CV (`master.tex`); it never invents experience, metrics or technologies.
- **LaTeX in, LaTeX out.** The CV and cover letter are LaTeX documents (compiled to PDF), built from the person's own template.
- **Human in the loop.** The system never sends anything. It prepares; the person decides.
- **Idempotent.** Running the pipeline twice on the same day neither duplicates postings nor spends tokens twice.
- **Manual only.** Every stage is started by the person, from the CLI or the web UI. There is no cron/launchd job, daemon or notification; the tool only works while a command or the UI is running.
- **Local and simple.** SQLite, LaTeX/Markdown files, no servers.
- **English everywhere.** Code, comments, docs, specs, commit messages, config keys and generated artifacts' tooling text are in English (see `CLAUDE.md`).

## 4. Scope (v1)

**In scope:**
- Sources: Greenhouse, Lever, Ashby, and remote aggregators (RemoteOK, We Work Remotely, Remotive). See `03-sources.md`.
- Configurable hard filter.
- LLM scoring (Haiku) and tailoring (Sonnet) for the top-N.
- CLI (`jobhunter run`, `review`, `mark`, `stats`).
- Per-posting status tracker and application/interview tracking.
- Postings added by hand (URL or pasted text), favorites and a company block list, all feeding the same pipeline (10, 11).
- A **local web UI** (`jobhunter ui`, bound to `127.0.0.1`) to see the funnel, browse postings, run stages manually, follow applications through interview stages, open generated PDFs and inspect settings. See `09-web-ui.md`. Visual identity and design tokens: `18-frontend-redesign.md`.

What comes next is in `08-roadmap.md`; the plan to open the project to contributors is `19-open-source-ready.md`.

**Out of scope (v1 non-goals):**
- LinkedIn, Indeed, and any site that requires scraping against its terms or a login.
- Automatic sending of applications or recruiter messages.
- Browser/headless/computer-use navigation.
- A hosted or multi-user web app (the UI is local only, no accounts).
- Multi-user.

## 5. Success criteria

| Metric | Target |
|---|---|
| LLM cost per run | < USD 1 (configurable cap) |
| Postings reviewed manually per day | ≤ 10, all high-match |
| Time to review one package | < 5 min |
| False facts in generated CV/letter | 0 (verification in `06-tailoring.md`) |
| Same-day re-run | 0 tokens, 0 duplicates |

## 6. Risks

| Risk | Mitigation |
|---|---|
| Wrong company slug / ATS changed | Fetcher tolerates 404, logs it and continues |
| Hard filter too strict | `jobhunter explain <id>` shows why a posting was dropped |
| LLM invents content | Prompt rules + post-generation verification (see 06) |
| Cost spikes | Daily cap + hash cache + optional Batch API |
| Personal data sent to the LLM | Only plain text of CV items and the posting; preamble/header (name, contact) never sent (see 06, 07) |
| LaTeX fails to compile / breaks layout | Select mode copies original LaTeX verbatim; compile + page-count check is part of verification (see 06) |

## 7. Data needed from the person (by stage)

| Stage | Data |
|---|---|
| Search (sources) | Target company list (optional; a seed list is provided) |
| Filtering | Target roles, seniority, location/remote, salary range, keywords to include/exclude |
| Scoring | Master CV in LaTeX (`master.tex`) with achievements and stack; a sentence on where you live and how you can work (`scoring.candidate_context`) |
| Tailoring | Cover-letter LaTeX template (or "build one from my CV style"), letter tone, languages, max CV pages |
| Before calling the LLM | Either `claude auth login` once (default: uses your Claude subscription, no API key) or `ANTHROPIC_API_KEY` (see 05 §1) |
