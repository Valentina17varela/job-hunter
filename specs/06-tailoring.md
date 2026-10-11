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
- **Marker grammar (implemented in `latex.py`):** `% jh:section <name>` … `% jh:endsection`; `% jh:entry <id> [required]` … `% jh:endentry` (a job/project block; may contain items or none); `% jh:item <id> [tags=a,b]` (a bullet). An item runs from its marker until the next marker, the next `\item`, an `\end{...}` line or a **blank line**, so both `\item` bullets and plain-text `• ...` bullets (possibly wrapped over several lines) work. Text between markers belongs to the container (`head`/`suffix`) or travels with the preceding sibling (`tail`), so dropping or reordering items keeps `\begin{itemize}`/`\end{itemize}` intact. Assembling without a selection reproduces the original file minus the marker comments (verified on the real CV).
- Everything **outside** `jh:` markers (preamble, header with name/contact, education if fixed, etc.) is copied **verbatim** and is **never sent to the LLM**. This keeps contact details out of any API call.
- `jh:item` = a bullet that can be kept, dropped or reordered. `jh:entry` = a block (job, project) that can be kept or dropped as a whole. `jh:section` = a section whose entries can be reordered.
- Skills lines can be marked as items (one per category line). A finer-grained `jh:list` for individual skill tokens is deferred until Phase 4 needs it.
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

One LLM call per posting returns **JSON only** (no prose), given the plain-text CV items with ids, the posting, and the scoring result (`must_have_match`, `gaps`):

```json
{
  "entries":  {"experience": ["exp-instaleap-2", "exp-instaleap-1", "exp-heru"], "certifications": ["cert-1", "cert-2"]},
  "items":    {"exp-instaleap-2": ["exp-instaleap-2-2", "exp-instaleap-2-1", "exp-instaleap-2-3"]},
  "emphasis": ["event-driven systems", "AWS"]
}
```

- `entries` = which entries/items of each section to keep (children of a section) and in what order; `items` = for each entry, its bullets ordered **most relevant first**. Anything omitted is dropped (except `required` entries, which code re-adds).
- Code assembles `cv.tex` from `master.tex`, copying each kept item's **original LaTeX verbatim** (or its reviewed translation, see 4.0). Nothing is reworded per posting, so no new facts and no LaTeX escaping issues are possible.
- **Page fit (deterministic, no extra LLM call):** if the compiled PDF exceeds `tailoring.max_cv_pages`, code drops content in this order until it fits: certification items (last first), optional (non-`required`) entries from the end, then the last-ranked bullet of entries that still have more than 2. If it still does not fit, the package is flagged **REVIEW**.
- Chronological order of experience is never changed (entries keep their original order; only bullets within an entry are re-ranked), because reordering jobs looks wrong on a CV.

### 4.2 Mode `rewrite` (optional, not in v1)
The LLM may reword bullets to mirror the posting's terminology (only if true). Each rewritten bullet keeps its source ID. Output text is passed through a LaTeX **escaper** (`& % $ # _ { } ~ ^ \`) and an allow-list of commands (`\textbf`, `\emph`, `\href`); anything else is rejected.

### 4.3 Cover letter

Generated in the **same call** as the recruiter message and notes (structured output): `{letter: {paragraphs[], subject}, recruiter_message, notes}`, in the posting's language.

**Template** (`config/cv/letter_template.tex`, the person's own, gitignored; a generic `config/letter_template.example.tex` is committed): one A4 page, same typographic family as the CV, formal but warm:

- Header: name and role title, thin accent rule, contact line (location, email, links). This lives in the template and **never** goes through the LLM.
- Right-aligned date; recipient block ("Hiring Team", company); bold subject line (`Application — <role>`).
- Body (3–4 short paragraphs, 190–260 words in total): (1) a hook that ties one concrete, quantified achievement to the company's problem or product; (2) two or three requirements from the posting each mapped to a proven result from the CV; (3) why this company, from specifics of the posting; (4) a short close with a clear call to action and availability, including the remote/time-zone context from `scoring.candidate_context` when it helps.
- Greeting/closing/date strings per language from a small built-in table (`en`, `es`): "Dear Hiring Team," / "Sincerely," / "Estimado equipo de selección," / "Atentamente,".
- Placeholders replaced by code after escaping: `%%DATE%%`, `%%COMPANY%%`, `%%ROLE%%`, `%%SUBJECT%%`, `%%GREETING%%`, `%%BODY%%`, `%%CLOSING%%`. The LLM never writes LaTeX; paragraphs are plain text, escaped by `latex.escape`.

**Letter rules (prompt):** only facts and numbers present in the CV items; use metrics verbatim; no clichés ("passionate", "dynamic", "team player", "fast-paced"); no flattery; no claim about skills the CV lacks (a gap goes in `notes`, never in the letter); mirror the posting's own vocabulary; tone from `tailoring.tone`.

### 4.4 Recruiter message and notes
- `recruiter_message.md`: ≤ 80 words, plain text for copy-paste, same language as the posting.
- `notes.md` (English): posting summary, why it fits (score reasons), gaps and how to address them in the interview, red flags to verify (e.g. residency), apply link, and any verification warnings.

### 4.5 Prompt rules
1. Use **only** facts present in the provided items. Do not invent companies, dates, metrics, technologies or titles.
2. Allowed: choosing which items to include, ordering them, and (letter) connecting them to the posting.
3. If the posting asks for something the profile lacks → do not claim it; list it in `notes` as a gap.

**Manual packaging.** `run --stage tailor --job <id>` (and the "Build package" button in the UI) builds a package for exactly the given postings whatever their status (filtered, below threshold, ...). The posting becomes `packaged` unless the person already recorded a status (`applied`, `replied`, `rejected`, `ignored`) or it is closed/duplicate. Without scoring data the prompt simply has no matches/gaps.

## 5. Verification (post-generation)

Deterministic checks (no LLM):

1. **IDs:** every id returned exists in `master.tex`; no duplicates; `required` entries present.
2. **Verbatim:** every kept item's LaTeX equals the master's (English) or the reviewed translation's (other languages), byte for byte.
3. **Letter facts:** every number/percentage in the letter appears in the CV text; every technology from a built-in vocabulary mentioned in the letter also appears in the CV; no banned cliché; 150–280 words.
4. **Compile:** `cv.tex` and `cover_letter.tex` compile; a failure is a verification failure.
5. **Length:** CV pages ≤ `tailoring.max_cv_pages`; letter exactly 1 page.
6. On failure: one retry of the LLM call with the error list; if it persists, `verified=0` and `notes.md` starts with a **REVIEW** banner listing the failed checks. The files are still written so the person can fix them by hand.

## 6. LaTeX toolchain

- Compiler: `tectonic` (self-contained, auto-fetches packages) preferred; `latexmk -pdf` as fallback. Configurable: `latex.engine`.
- Compilation runs in a temp directory with a timeout (60 s) and `-no-shell-escape`; no network needed beyond package fetching.
- Class, style, font and image files next to `master.tex` (`.cls .sty .bst .bib .png .jpg .pdf .ttf .otf`) are copied into the temp directory, so CVs with custom classes compile as they do in place.
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

- [x] 0 packages with `verified=1` containing facts not in `master.tex` (in adversarial tests).
- [x] `cv.tex` for every package compiles to PDF with page count within the limit.
- [x] Preamble/header content (name, contact) is never present in any LLM request (asserted in tests).
- [ ] Average cost per package < USD 0.05.
- [x] Re-running does not regenerate existing packages (unless `--force`).
- [ ] The person can review a full package in < 5 min.
