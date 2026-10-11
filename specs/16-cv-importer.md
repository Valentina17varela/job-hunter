# 16 — CV importer: from any CV to a marked LaTeX master

**Status:** PLANNED (spec only, not implemented)

## 1. Problem

The tool needs a LaTeX CV with `% jh:` markers (spec 06). Writing LaTeX and placing the markers is the hardest step for anyone who is not the author; most people have a PDF or a Word/Google Docs export, not LaTeX.

## 2. Goal

The person gives their CV as **pasted text, a text PDF, a Markdown/text file or an unmarked LaTeX file**, reviews a structured preview, and the tool writes a **ready-to-use, marked LaTeX master CV** (`config/cv/master.tex`) built from a shipped template. **No fact may be lost or invented**, and **the person's contact details never reach the LLM** (the project's privacy rule).

## 3. Principles

- **Code writes the LaTeX, the LLM only structures text.** The LLM returns JSON; a deterministic renderer produces the `.tex` with `latex.escape` and the markers. The LLM never writes LaTeX or markers.
- **Contact details are redacted before the LLM and re-inserted by code** (§5).
- **Verify, then ask the person.** A coverage check compares source and result; anything uncertain is shown for the person to fix. Nothing is saved without an explicit approval.
- **Non-destructive.** An existing `master.tex` is backed up (`.bak`, one-time `.orig`) like every other write.

## 4. Inputs

| Input | Handling |
|---|---|
| Pasted text / `.txt` / `.md` | used as is |
| Text-based PDF | text extracted with `pypdf` (already a dependency); the raw text is shown so the person can fix columns or ordering before continuing |
| Scanned PDF / image | **not supported in v1** (no OCR); a clear message asks for a text PDF or pasted text |
| Unmarked LaTeX (`.tex`) | existing `propose_markers` for `\item` bullets plus an optional LLM pass that wraps job/project blocks as entries |
| Word/DOCX | not in v1 (would add a dependency); the person exports to PDF or text |

Upload goes through the JSON API as base64 (PDF ≤ 5 MB, text ≤ 200 KB) so the CSRF protections (JSON-only writes, Host/Origin checks) stay unchanged.

## 5. Pipeline

1. **Extract** text (above) and show it; the person may edit it.
2. **Identity form** (3-4 fields, filled by the person, not guessed): full name, headline/role title, location, and the contact links (email, phone, LinkedIn, GitHub, website). These become the LaTeX header.
3. **Redact.** Before any LLM call, every occurrence (case-insensitive) of the identity values is replaced by placeholders (`[NAME]`, `[EMAIL]`, `[PHONE]`, `[URL1]`…), and a regex pass catches emails, phone numbers and URLs the person did not list. The redacted text is shown to the person ("this is exactly what will be sent") before the call.
4. **Structure (one LLM call, `tailoring.model`).** Strict JSON:
   ```json
   {
     "summary": "text or null",
     "experience": [{"company": "", "title": "", "location": "", "start": "", "end": "", "bullets": [""]}],
     "education": [{"institution": "", "degree": "", "start": "", "end": "", "details": [""]}],
     "skills": [{"label": "Languages", "items": ["Python", "Go"]}],
     "certifications": [""], "projects": [{"name": "", "bullets": [""]}],
     "languages": [""], "other": [{"title": "", "lines": [""]}]
   }
   ```
   Rules in the prompt: copy wording, numbers, dates and names exactly as in the source; do not summarize, merge, translate or improve; unknown fields stay empty; anything that does not fit goes to `other` (so nothing is dropped).
5. **Verify (deterministic):**
   - **Coverage:** every number, percentage, year/date, capitalized token and technology term of the redacted source must appear in the structured result; missing ones are listed.
   - **No additions:** every number and technology term in the result must appear in the source; additions are listed.
   - **Bullet fidelity:** each bullet must be a (near-)verbatim span of the source (normalized whitespace); differences are shown side by side.
   - Failures never block: they are shown as a REVIEW list for the person to resolve in the editor.
6. **Edit.** A form shows the structured CV (sections → entries → bullets) with edit, delete, add and reorder; the person confirms the **identity**, dates and any flagged item.
7. **Render.** Choose a **template** (§6); code renders `master.tex`: header from the identity form, sections from the JSON, markers placed as in spec 06 (`jh:section`, `jh:entry`, `jh:item`, ids like `exp-<company>-<n>`, `edu-<n>`, `skills-<label>`, `cert-<n>`, `about-1`; the most recent job and the education entry are `required`). All text is escaped.
8. **Preview.** The file is compiled (`compile_pdf`) and shown as a PDF next to the original; page count is displayed.
9. **Approve & save.** Writes `config/cv/master.tex` (with backups), runs `latex.parse` + `assemble` round-trip as a final self-check, and offers **Next: what you're looking for** (the wizard) or **Back to Settings**.

## 6. Templates

- Shipped in `templates/cv/` with a `template.json` (name, description, page count, fonts) and a Python render function each: **classic** (the look of the author's CV: `extarticle`, ruled section titles), **compact** (denser, for long histories), **modern** (accent color, two-tone headings).
- All use only packages available in `tectonic`'s bundle; every template must compile with an empty and a very full CV; page limits are respected by dropping nothing (the person decides what to cut in the editor).
- A template can be added by dropping a folder in `templates/cv/`; tests iterate over all of them.

## 7. Language

If the source CV is not English, the importer keeps its language and records `cv_language` in the generated header comment; the translation feature (spec 06 §4.0) treats the master language as the source. Handling of a non-English master in tailoring and scoring prompts is an **open question** to settle when this is implemented.

## 8. Interfaces

- `POST /api/cv/import/extract {filename, content_base64 | text}` → `{text, warnings}`.
- `POST /api/cv/import/structure {text, identity}` → `{redacted_preview, cv, verification}` (this is the only LLM call; counted in `llm_calls`; refused with a clear message if no LLM is available, with the heuristic fallback offered).
- `POST /api/cv/import/render {cv, identity, template}` → `{tex, pdf_base64, pages, problems}`.
- `POST /api/cv/import/save {tex}` → writes `master.tex` after the parser check.
- CLI: `jobhunter cv import FILE --template classic --name "…" [--email …] [--phone …] [--link …]` (non-interactive: runs steps 1-5 and 7-9 and prints the REVIEW list; the interactive edit step is UI-only). 
- **Heuristic fallback (no LLM):** sections found by common headings (Experience, Education, Skills…), bullets by `•/-/*`; lower quality, flagged as such.

## 9. Privacy and safety

- The contact header and any redacted value never enter a prompt, a log or `llm_calls`; the preview shows the redacted text before sending.
- Source text is untrusted: rendered escaped in the UI and escaped in LaTeX; instructions found inside a CV are treated as text.
- Only the configured `paths.cv_master` is written; PDF parsing has size and page limits.

## 10. Tests

- Extraction fixtures: a text PDF with bullets, a two-column PDF (order warning), an empty/scanned PDF (clear error).
- Redaction: names (full/partial/uppercase), emails, phones in several formats, URLs, LinkedIn handles; the redacted text contains none of them; re-insertion restores them in the header only.
- Verification: a dropped number, an invented technology, a reworded bullet and a merged entry are each detected; a faithful structure passes.
- Renderer: every template compiles and passes `latex.parse`; `assemble()` without selection equals the rendered file minus markers; LaTeX specials in text (`& % $ # _ { } ~ ^ \`) are escaped; ids are unique; required entries set.
- Golden round trip: the project's sample CV text → structure (fake LLM) → render → parse yields the same items.
- API: JSON-only and Host/Origin rules hold; size limits; no LLM call when redaction preview was not confirmed.

## 11. Tasks

- [ ] `cv_import/extract.py` (text, PDF, `.tex`), `redact.py`, `verify.py`, schema models.
- [ ] `cv_import/render.py` + three templates + template tests.
- [ ] Structuring prompt and the heuristic fallback.
- [ ] API endpoints, `cv import` command, run/limits.
- [ ] UI: upload/paste, identity form, redaction preview, structured editor with REVIEW list, template picker, PDF preview, save.
- [ ] Wire into the wizard (spec 15, step 3).
- [ ] README (commands, UI, privacy statement) and this spec marked done.

## 12. Acceptance criteria

- [ ] A person with only a PDF CV ends with a compiled, marked `master.tex` without writing LaTeX.
- [ ] The tool reports every fact of the source that did not make it into the result, and every fact in the result that is not in the source.
- [ ] Name, email, phone and links are never sent to the LLM.
