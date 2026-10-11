# 17 — Offer decision and negotiation helper

**Status:** PLANNED (spec only, not implemented)

## 1. Problem

When an offer finally arrives, the person has the least information and the most pressure: is this good, what can I ask for, how do I say it. The tool already holds market data (published salaries of thousands of postings), the person's minimum, and the history of the process.

## 2. Goal

For an application at stage **`offer`**, an **Offer** page that (1) normalizes the offer, (2) compares it with evidence from the person's own data, (3) proposes a counter range and non-salary levers, and (4) drafts messages. Everything is **on demand** (nothing runs until the person asks), local, and clearly **not financial, tax or legal advice**.

## 3. Inputs (offer form, stored locally)

Base amount + currency + period (`year`/`month`/`hour`), bonus (amount or %), equity (free text), benefits (free text), **contract type** (`employee` / `contractor`), employer location, start date, **deadline to answer**, notes; and the person's own numbers: **target** and **walk-away** (default: `search.salary.min_usd` as the floor). Optional: **competing offers or processes** (the tool pre-fills applications at `interviewing`).

Storage: `offers(id, job_id, base_amount, currency, period, bonus, equity, benefits, contract_type, location, start_date, deadline, target_usd, walk_away_usd, notes, created_at)` and `offer_drafts(id, offer_id, kind, content, model, created_at)`.

## 4. Analysis (deterministic, no LLM)

1. **Normalization:** annualize hour/month/year (hour × 2,080, month × 12 like the rest of the tool) and convert with the configured FX table to **annual USD**; show the arithmetic.
2. **Market position** from the person's data (reuses the salary statistics of spec 13):
   - cohort = postings with a published salary that share the offer's **title keywords and seniority** and overlap the person's skills (fallbacks: seniority only, then all matches), preferring remote roles;
   - percentiles **p25 / p50 / p75 / p90** with **sample size**; hidden (with an explanation) when n < 10;
   - the offer's **percentile rank** and a position bar (below floor / below median / above median / top quartile).
   - Also compared with the **posting's own range** (if any), the **person's minimum** and **target**.
3. **Contract-type view:** for `contractor` offers, a neutral calculator converts between an invoiced rate and an employee-equivalent salary using **overhead percentages the person types** (social security, taxes, paid leave, equipment…). The tool supplies no tax rates and says so.
4. **Leverage factors (facts from the tool):** how many best matches and applications are active, whether other processes are at `interviewing`/`offer`, how rare the person's matching skills are in the market (spec 13 demand), days until the deadline, how long the posting had been open (posted-at).
5. **Counter range:** target = max(person's target, p75 of the cohort when n ≥ 10), floor = max(walk-away, offer, p50); both shown with the reasoning and **never above what the evidence supports** (when data is thin the page says "not enough data" and anchors on the posting range and the person's own numbers).
6. **Non-salary levers checklist** tailored to the contract type: sign-on bonus, equity/refresh, PTO, remote/time-zone flexibility, equipment, learning budget, title/level, 6-month review, start date, contractor terms (payment currency/schedule, notice, invoicing).

## 5. Drafts (LLM, on demand, one call per draft)

Kinds: **counteroffer**, **ask for more time**, **follow-up after the counter**, **accept**, **decline politely**. Each is short, plain text for the person to copy (and a `mailto:` button), in the language of the process, tone from `tailoring.tone`.

- Input to the LLM: job title, company, the numbers above, the chosen counter range, the levers the person ticked, `candidate_context`, and the person's own stories only if they cite CV item ids; **never the CV header**.
- Rules: use only provided numbers; any market claim must be phrased as coming from "my own collected postings (n = …)" or omitted; no threats, ultimatums or invented competing offers; polite and specific.
- **Verification:** every number in the draft must appear in the inputs; no invented employer names; length bounds; failures mark the draft **REVIEW** (still shown).

## 6. UI and CLI

- Application page at stage `offer`: **Offer** card → form → analysis page (position bar, percentile table, leverage list, counter range, levers checklist, scenario table "if they accept X → annual USD") → **Draft message** buttons → saved drafts with copy/delete.
- Gate: the page and commands are available only when the application is at `offer` or `accepted` (override with `--force` in the CLI).
- CLI: `jobhunter offer JOB_ID --base N --currency USD --period year [--bonus …] [--contract employee|contractor] [--deadline YYYY-MM-DD] [--target N --walk-away N]` prints the analysis; `--draft counter|extension|followup|accept|decline` writes a draft.
- Drafts and offers are deletable; deleting a job's package/offer never touches files outside the tool's folders.

## 7. Privacy

Offer numbers are sensitive: stored only in the local database, sent to the LLM only for a draft the person requested (minimal fields), never logged, shown only on `127.0.0.1`.

## 8. Dependencies and order

Needs the salary percentiles of spec 13; without them the analysis falls back to the posting range and the person's own numbers and says so. Built **after** 13 and, like 12, only reachable late in a process.

## 9. Tests

- Annualization and conversion table; contractor↔employee calculator with typed overheads.
- Percentile math on a fixture; hidden when n < 10; rank and position bar boundaries; fallback chain.
- Counter range rules (never above evidence, respects walk-away).
- Draft verification: an invented number or competing offer is flagged; clean draft passes; one LLM call per draft; budget cap stops cleanly.
- Gate by stage; UI renders with and without market data; deleting offers/drafts.

## 10. Tasks

- [ ] Migration: `offers`, `offer_drafts`.
- [ ] `offers.py`: normalization, percentile comparison (using spec 13 stats), leverage, counter range, contractor calculator.
- [ ] Draft prompts + verification + storage.
- [ ] API, `offer` CLI, run-whitelist entry for drafts.
- [ ] UI: Offer card, analysis page, drafts.
- [ ] README (commands, UI, privacy note, disclaimer) and this spec marked done.

## 11. Acceptance criteria

- [ ] Given an offer, the page shows where it sits against the person's own market data with the sample size, or says there is not enough data.
- [ ] The counter range and every number in a draft are traceable to the inputs.
- [ ] Nothing is generated before the application reaches `offer`, and the page states it is not financial or legal advice.
