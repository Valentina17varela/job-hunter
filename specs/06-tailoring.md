# 06 — Tailoring (quality LLM)

Goal: for `selected` postings, generate a package the person can review and send in minutes, **with no invented content**. The CV and cover letter are produced in **LaTeX** (and compiled to PDF), starting from the person's own LaTeX CV.

## 1. Input

- `config/cv/master.tex` — the person's LaTeX CV, annotated with markers (see §2). Source of truth.
- `config/cv/letter_template.tex` — LaTeX cover-letter template (same look as the CV).
- Full posting (title, company, description).
- Scoring result (`must_have_match`, `gaps`) to guide emphasis.
- Default model: `claude-sonnet-5-5` (configurable).

## 2. `master.tex` format

The person's existing LaTeX CV, kept as-is, plus lightweight **marker comments** so code can tell which parts are selectable. Nothing else about the file changes (class, packages, layout stay the person's).

```latex
% jh:section experience
\section{Experience}
% jh:entry exp-instaleap          ← groups items under one employer/role
\cventry{2022--Present}{Software Engineer}{Instaleap}{Remote}{}{
\begin{itemize}
  % jh:item exp-instaleap-1 tags=python,aws
  \item Cut order-assignment latency by 40\% by ...
  % jh:item exp-instaleap-2 tags=typescript
  \item Built ...
\end{itemize}}
```

Rules:
- Everything **outside** `jh:` markers (preamble, header with name/contact, education if fixed, etc.) is copied **verbatim** and is **never sent to the LLM**. This keeps contact details out of any API call.
- `jh:item` = a bullet that can be kept, dropped or reordered. `jh:entry` = a block (job, project) that can be kept or dropped as a whole. `jh:section` = a section whose entries can be reordered.
- A `skills` section may be marked as `jh:list skills` (comma-separated tokens) so skills can be reordered/filtered.
- Each ID is stable and unique. A one-time conversion helper (`jobhunter cv init`) inserts markers with proposed IDs; the person reviews them.
- The loader parses `master.tex` into a `Profile` model: sections → entries → items, each with ID, raw LaTeX and plain text. The LLM only ever sees the **plain text + IDs** (cheaper than raw LaTeX and no LaTeX noise), never the preamble.

## 3. Outputs per posting

Folder `out/YYYY-MM-DD/{company}-{role}/`:

| File | Content |
|---|---|
| `cv.tex` | Tailored CV: `master.tex` with entries/items selected and reordered for the posting |
| `cv.pdf` | Compiled from `cv.tex` |
| `cover_letter.tex` / `cover_letter.pdf` | Short letter (≤ 200 words) from `letter_template.tex` |
| `recruiter_message.md` | Brief message for the recruiter/hiring manager (≤ 80 words), plain text for copy-paste |
| `notes.md` | Posting summary, why it fits, gaps and how to address them in the interview, apply link |
| `meta.json` | job_id, model, tokens, master hash, verification result, page count |

## 4. Generation

### 4.0 Language adaptation (CV is written in English only)

The master CV is English-only, but every package must match the **posting's language** (`tailoring.languages`, default `["en", "es"]`; unsupported languages fall back to English).

- **Translate once, reuse forever.** `jobhunter cv translate --lang es` translates every `jh:` item, entry title/role text and section label from `master.tex` **once** (Sonnet) into `config/cv/translations/es.json`, keyed by item ID. The person **reviews and edits** this file once. Cost is a one-time ~USD 0.05 per language, not per posting.
- Translations are checked deterministically: same figures (`\d+%`, `\$\d+`, `\d+x`), same technology/proper-noun tokens (kept untranslated), same LaTeX commands, valid escaping. Failures are listed for the person to fix.
- Assembling a CV in language `L` copies the master's LaTeX structure and substitutes each kept item's text with its reviewed translation (select mode still means **no new wording per posting**).
- Section headings and fixed labels (`Experience`, `Education`, `Skills`) are marked `% jh:label` in `master.tex` and translated the same way.
- If a posting's language has no reviewed translation file, the package falls back to English and `notes.md` says so.
- Language detection of the posting is deterministic (`langdetect`/`lingua`-style library, no LLM); ambiguous → English.
- The cover letter and recruiter message are generated directly in the posting's language by the same call that produces them.

### 4.1 Mode `select` (default)
1. The LLM receives plain-text items with IDs and returns **JSON**: for each section, the ordered list of IDs to keep, plus the ordered skills list. No free text.
2. Code assembles `cv.tex` from `master.tex`, copying each kept item's **original LaTeX verbatim** (or its reviewed translation, see 4.0). Nothing is reworded per posting, so no new facts and no LaTeX escaping issues are possible.

### 4.2 Mode `rewrite` (optional)
The LLM may reword bullets to mirror the posting's terminology (only if true). Each rewritten bullet keeps its source ID. Output text is passed through a LaTeX **escaper** (`& % $ # _ { } ~ ^ \`) and an allow-list of commands (`\textbf`, `\emph`, `\href`); anything else is rejected.

### 4.3 Cover letter
- One call (together with the recruiter message and notes) with structured output: `{letter_body, recruiter_message, notes}`.
- `letter_body` is plain text paragraphs, escaped and inserted into `letter_template.tex` placeholders (`%%COMPANY%%`, `%%ROLE%%`, `%%BODY%%`). Header/contact details come from the template, never from the LLM.
- Rules: specific to the company/role, no clichés ("passionate", "dynamic"), one concrete idea of how to contribute, tone defined by the person (`tailoring.tone`).

### 4.4 Prompt rules
1. Use **only** facts present in the provided items. Do not invent companies, dates, metrics, technologies or titles.
2. Allowed: choosing which items to include, ordering them, (rewrite mode) rewording to reflect the posting's terminology if true.
3. If the posting asks for something the profile lacks → do not claim it; list it in `notes` as a gap.

## 5. Verification (post-generation)

Deterministic checks first, then a cheap LLM check:

1. **IDs:** every ID returned exists in `master.tex`; no duplicates; required entries (marked `required` in `master.tex`, e.g. current job) are present.
2. **Verbatim (select mode):** every kept item's LaTeX equals the master's (English) or the reviewed translation's (other languages), byte for byte.
3. **Figures/tech (rewrite mode and letter):** every figure (`\d+%`, `\$\d+`, `\d+x`) and technology mentioned appears in the source items / skills list.
4. **Compile:** `cv.tex` and `cover_letter.tex` compile without errors (see §6). A compile failure is a verification failure.
5. **Length:** page count ≤ `tailoring.max_cv_pages` (default 1). If exceeded, drop the lowest-ranked items until it fits (deterministic, no extra LLM call).
6. **LLM (Haiku), optional:** a yes/no question about the letter: "does it claim anything not supported by the provided items?".
7. On failure: one retry with the error list; if it persists, `verified=0` and the package is flagged **REVIEW** in `notes.md`.

## 6. LaTeX toolchain

- Compiler: `tectonic` (self-contained, auto-fetches packages) preferred; `latexmk -pdf` as fallback. Configurable: `latex.engine`.
- Compilation runs in a temp directory with a timeout (60 s) and `-no-shell-escape`; no network needed beyond package fetching.
- Phase 0 includes a toolchain check (`jobhunter doctor`) that reports which engine is installed and compiles a minimal document.
- Fonts/classes used by the person's CV must be available to the engine; `doctor` compiles `master.tex` as-is to catch this early.

## 7. Token savings

- Only generated for the daily top-N.
- Select mode sends plain-text items (not LaTeX) and gets back a short JSON list of IDs; the heavy lifting is code.
- Cached prefix: instructions + plain-text items (stable between postings).
- Letter, recruiter message and notes in a single call.

## 8. Tests

- `master.tex` fixture parses into the expected sections/entries/items; unmarked content is preserved verbatim.
- Mocked LLM returning unknown IDs, duplicate IDs, or missing required entries → verification fails.
- Select-mode output: kept items byte-identical to master; reordering works; assembled file compiles (compile test skipped if no engine is installed).
- Escaper: `& % $ # _ { } ~ ^ \` in letter text produce valid LaTeX; disallowed commands rejected.
- Page limit: oversized selection is trimmed to fit.

## 9. Acceptance criteria

- [ ] 0 packages with `verified=1` containing facts not in `master.tex` (in adversarial tests).
- [ ] `cv.tex` for every package compiles to PDF with page count within the limit.
- [ ] Preamble/header content (name, contact) is never present in any LLM request (asserted in tests).
- [ ] Average cost per package < USD 0.05.
- [ ] Re-running does not regenerate existing packages (unless `--force`).
- [ ] The person can review a full package in < 5 min.
