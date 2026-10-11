"""Tailoring: pick CV items, write the cover letter, verify and export (specs/06-tailoring.md)."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from jobhunter import latex
from jobhunter.config import Config
from jobhunter.filters import job_from_row
from jobhunter.language import detect_language
from jobhunter.latex import Document, Entry, Selection
from jobhunter.llm import LlmClient, LlmError, LlmLimitReached
from jobhunter.models import Job
from jobhunter.store import HUMAN_STATUSES
from jobhunter.translate import load_translation

PROMPT_VERSION = "tailor-v2"
CHARS_PER_TOKEN = 4
MAX_ATTEMPTS = 2
OPTIONAL_SECTION_HINTS = ("certif", "course", "award", "publication", "interest", "hobb")

LETTER_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "greeting": "Dear Hiring Team,",
        "closing": "Sincerely,",
        "recipient": "Hiring Team",
        "subject": "Application — {role}",
    },
    "es": {
        "greeting": "Estimado equipo de selección,",
        "closing": "Atentamente,",
        "recipient": "Equipo de selección",
        "subject": "Postulación — {role}",
    },
}
MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
           "octubre", "noviembre", "diciembre"],
}  # fmt: skip
BANNED = {
    "en": ["passionate", "dynamic", "team player", "fast-paced", "rockstar", "ninja", "synergy",
           "go-getter", "hard-working", "results-driven", "self-starter", "think outside the box"],
    "es": ["apasionado", "apasionada", "dinámico", "dinámica", "jugador de equipo", "proactivo",
           "proactiva", "orientado a resultados", "orientada a resultados"],
}  # fmt: skip
_TECH_TEXT = """
python golang typescript javascript java kotlin php django fastapi nestjs postgresql postgres
mysql mongodb redis kafka rabbitmq sqs sns aws gcp azure docker kubernetes terraform graphql grpc
airflow elasticsearch snowflake aurora firebase fargate dynamodb bigquery celery sqlalchemy pytest
jenkins
"""
TECH_TERMS = _TECH_TEXT.split()

TAILOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "selection": {
            "type": "object",
            "properties": {
                "entries": {
                    "type": "object",
                    "additionalProperties": {"type": "array", "items": {"type": "string"}},
                },
                "items": {
                    "type": "object",
                    "additionalProperties": {"type": "array", "items": {"type": "string"}},
                },
            },
            "required": ["entries", "items"],
        },
        "letter": {
            "type": "object",
            "properties": {"paragraphs": {"type": "array", "items": {"type": "string"}}},
            "required": ["paragraphs"],
        },
        "recruiter_message": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["selection", "letter", "recruiter_message", "notes"],
}


class SelectionOut(BaseModel):
    entries: dict[str, list[str]] = {}
    items: dict[str, list[str]] = {}


class LetterOut(BaseModel):
    paragraphs: list[str] = Field(min_length=2, max_length=6)


class TailorOut(BaseModel):
    selection: SelectionOut
    letter: LetterOut
    recruiter_message: str
    notes: str = ""


# --- prompt -----------------------------------------------------------------------------------


def build_system_prompt(doc: Document, cfg: Config) -> str:
    tone = cfg.tailoring.tone.strip() or "formal but warm, concrete and confident"
    context = cfg.scoring.candidate_context.strip() or "(not provided)"
    return f"""You tailor a job application for ONE candidate. Return strict JSON only.

## What to produce
1. selection: which CV parts to keep for this posting.
   - "entries": for each CV section you want to trim or reorder, the ids of the entries/items to
     keep, in order. Sections you omit are kept as they are. Never reorder jobs: keep the original
     chronological order of entries. Keep every entry marked required.
   - "items": for each entry, its bullet ids ordered most relevant to this posting first. Drop
     bullets that are irrelevant. Use ONLY ids from the CV below.
2. letter.paragraphs: 3 or 4 plain-text paragraphs (no LaTeX, no greeting, no signature), 190-260
   words in total, tone: {tone}.
   - Paragraph 1: open with one concrete, quantified achievement from the CV that relates to the
     company's product or problem.
   - Paragraph 2: map two or three requirements stated in the posting to proven results in the CV.
   - Paragraph 3: why this company, using specifics from the posting.
   - Paragraph 4: a short close with a clear call to action and availability; mention the remote
     and time-zone situation from the candidate context only when it helps.
3. recruiter_message: at most 80 words, plain text, for a direct message to a recruiter.
4. notes: English. Why it fits, gaps and how to address them in an interview, anything to verify
   in the posting (residency, time zone, contractor eligibility).

## Hard rules
- Use ONLY facts and numbers that appear in the CV below; copy metrics exactly. Never invent
  employers, dates, technologies, titles or results.
- Never claim a skill the CV lacks. Gaps go only in "notes", never in the letter.
- A technology that only appears in the CV's skills list may be mentioned as a skill, but never as
  "production experience", "years of experience" or an achievement; only describe work, scope and
  results that a CV bullet actually states.
- No clichés (passionate, dynamic, team player, fast-paced, results-driven), no flattery.
- Mirror the posting's own vocabulary where it is true to the CV.
- Write the letter and recruiter_message in the language requested in the posting message.

## Candidate context
{context}

## Candidate CV (ids in brackets)
{latex.digest(doc)}"""


def posting_prompt(row: sqlite3.Row, score: sqlite3.Row | None, lang: str, max_tokens: int) -> str:
    from jobhunter.scoring import truncate_description

    job = job_from_row(row)
    info = json.loads(score["reasons"]) if score else {}
    block = {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "work_mode": job.remote,
        "language_of_letter_and_recruiter_message": lang,
        "scoring_matches": info.get("must_have_match", []),
        "scoring_gaps": info.get("gaps", []),
        "description": truncate_description(job.description, max_tokens),
    }
    return "Tailor the application for this posting.\n\n" + json.dumps(block, ensure_ascii=False)


# --- selection --------------------------------------------------------------------------------


def resolve_selection(doc: Document, out: SelectionOut) -> tuple[Selection, list[str]]:
    """Turn the LLM's lists into a valid Selection (required kept, jobs in original order)."""
    problems: list[str] = []
    sel = Selection()
    for section in doc.sections:
        wanted = out.entries.get(section.name)
        if not wanted:
            continue
        known = {c.id: c for c in section.children}
        valid = [w for w in dict.fromkeys(wanted) if w in known]
        problems += [
            f"unknown id '{w}' in section '{section.name}'" for w in wanted if w not in known
        ]
        if not valid:
            continue  # nothing usable listed: keep the section as it is
        keep = set(valid)
        keep |= {c.id for c in section.children if isinstance(c, Entry) and c.required}
        if any(isinstance(c, Entry) for c in section.children):
            ordered = [c.id for c in section.children if c.id in keep]  # keep chronology
        else:
            ordered = valid + [c.id for c in section.children if c.id in keep and c.id not in valid]
        sel.sections[section.name] = ordered
    entries = {c.id: c for s in doc.sections for c in s.children if isinstance(c, Entry)}
    for eid, wanted in out.items.items():
        entry = entries.get(eid)
        if entry is None:
            problems.append(f"unknown entry '{eid}'")
            continue
        known_items = {i.id for i in entry.items}
        valid = [w for w in dict.fromkeys(wanted) if w in known_items]
        problems += [f"unknown item '{w}' in '{eid}'" for w in wanted if w not in known_items]
        if valid:
            sel.items[eid] = valid
    return sel, problems


def full_selection(doc: Document, sel: Selection) -> Selection:
    """Make every list explicit so trimming can remove single elements."""
    out = Selection()
    for section in doc.sections:
        out.sections[section.name] = list(
            sel.sections.get(section.name, [c.id for c in section.children])
        )
        for child in section.children:
            if isinstance(child, Entry):
                out.items[child.id] = list(sel.items.get(child.id, [i.id for i in child.items]))
    return out


def trim_once(doc: Document, sel: Selection) -> Selection | None:
    """Remove the least valuable remaining element; None when nothing is left to remove."""
    sel = Selection({k: list(v) for k, v in sel.sections.items()},
                    {k: list(v) for k, v in sel.items.items()})  # fmt: skip
    sections = doc.sections
    # 1. optional item-only sections (certifications, ...): drop the last item
    for section in reversed(sections):
        if not any(h in section.name for h in OPTIONAL_SECTION_HINTS):
            continue
        required = {c.id for c in section.children if isinstance(c, Entry) and c.required}
        droppable = [cid for cid in sel.sections[section.name] if cid not in required]
        if droppable:
            sel.sections[section.name].remove(droppable[-1])
            return sel
    # 2. optional (not required) entries, newest-listed last, never from education
    for section in reversed(sections):
        if "educ" in section.name:
            continue
        by_id = {c.id: c for c in section.children}
        for cid in reversed(sel.sections[section.name]):
            child = by_id[cid]
            if isinstance(child, Entry) and not child.required:
                sel.sections[section.name].remove(cid)
                return sel
    # 3. the last-ranked bullet of entries that still have more than two
    for section in reversed(sections):
        for cid in reversed(sel.sections[section.name]):
            if len(sel.items.get(cid, [])) > 2:
                sel.items[cid].pop()
                return sel
    return None


# --- verification -----------------------------------------------------------------------------

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)*\s?%?")


def cv_facts(doc: Document) -> str:
    return latex.digest(doc).lower()


def verify_letter(paragraphs: list[str], doc: Document, lang: str) -> list[str]:
    """Deterministic checks on the letter text (facts, clichés, length)."""
    text = "\n".join(paragraphs)
    lower = text.lower()
    facts = cv_facts(doc)
    problems = []
    words = len(text.split())
    if not 150 <= words <= 280:
        problems.append(f"letter has {words} words (expected 150-280)")
    for banned in BANNED.get(lang, BANNED["en"]):
        if banned in lower:
            problems.append(f"letter uses the cliché '{banned}'")
    facts_flat = facts.replace(",", "")
    for match in _NUM_RE.findall(text):
        token = match.strip().rstrip("%").replace(",", "")
        is_percent = match.strip().endswith("%")
        numeric = token.replace(".", "").isdigit()
        if not numeric or not (is_percent or float(token) > 10):
            continue
        if not re.search(rf"(?<![\d.]){re.escape(token)}(?![\d])", facts_flat):
            problems.append(f"letter mentions '{match.strip()}' which is not in the CV")
    for term in TECH_TERMS:
        pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        if re.search(pattern, lower) and not re.search(pattern, facts):
            problems.append(f"letter mentions '{term}' which is not in the CV")
    return problems


# --- letter ------------------------------------------------------------------------------------


def format_date(day: date, lang: str) -> str:
    months = MONTHS.get(lang, MONTHS["en"])
    if lang == "es":
        return f"{day.day} de {months[day.month - 1]} de {day.year}"
    return f"{months[day.month - 1]} {day.day}, {day.year}"


def fill_letter(template: str, job: Job, paragraphs: list[str], lang: str, day: date) -> str:
    strings = LETTER_STRINGS.get(lang, LETTER_STRINGS["en"])
    values = {
        "%%DATE%%": format_date(day, lang),
        "%%RECIPIENT_LABEL%%": latex.escape(strings["recipient"]),
        "%%COMPANY%%": latex.escape(job.company),
        "%%SUBJECT%%": latex.escape(strings["subject"].format(role=job.title)),
        "%%GREETING%%": latex.escape(strings["greeting"]),
        "%%BODY%%": "\n\n".join(latex.escape(p.strip()) for p in paragraphs),
        "%%CLOSING%%": latex.escape(strings["closing"]),
    }
    out = template
    for key, value in values.items():
        out = out.replace(key, value)
    return out


# --- stage ------------------------------------------------------------------------------------


@dataclass
class PackageResult:
    job_id: int
    path: Path
    verified: bool
    problems: list[str] = field(default_factory=list)
    language: str = "en"


@dataclass
class TailorSummary:
    candidates: int = 0
    packaged: int = 0
    needs_review: int = 0
    calls: int = 0
    stopped: str | None = None
    errors: list[str] = field(default_factory=list)
    results: list[PackageResult] = field(default_factory=list)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "x"


CompileFn = Callable[[str, str, int], latex.CompileResult]


def _fit_cv(
    doc: Document, sel: Selection, translation: dict[str, list[str]] | None,
    cfg: Config, compile_fn: CompileFn,
) -> tuple[str, latex.CompileResult, Selection, list[str]]:  # fmt: skip
    """Assemble and compile the CV, trimming deterministically until it fits the page limit."""
    notes: list[str] = []
    current = full_selection(doc, sel)
    for _ in range(40):
        tex = latex.assemble(doc, current, translation)
        result = compile_fn(tex, cfg.latex.engine, cfg.latex.timeout_seconds)
        if not result.ok:
            return tex, result, current, [f"CV {result.detail}"]
        if result.pages <= cfg.tailoring.max_cv_pages:
            return tex, result, current, notes
        trimmed = trim_once(doc, current)
        if trimmed is None:
            return (
                tex,
                result,
                current,
                [
                    f"CV has {result.pages} pages (limit {cfg.tailoring.max_cv_pages}) and cannot "
                    "be trimmed further"
                ],
            )
        current = trimmed
        notes.append("trimmed to fit the page limit")
    return tex, result, current, ["CV did not fit after repeated trimming"]


def tailor_job(
    conn: sqlite3.Connection, client: LlmClient, cfg: Config, doc: Document, row: sqlite3.Row,
    *, template: str, cv_dir: Path, out_root: Path, compile_fn: CompileFn, day: date,
) -> PackageResult:  # fmt: skip
    job = job_from_row(row)
    score = conn.execute(
        "SELECT * FROM scores WHERE job_id = ? ORDER BY created_at DESC LIMIT 1", (row["id"],)
    ).fetchone()
    lang = detect_language(job.description)
    if lang not in cfg.tailoring.languages:
        lang = "en"
    warnings: list[str] = []
    translation = None
    if lang != "en":
        translation, why = load_translation(cv_dir, lang, doc)
        if translation is None:
            warnings.append(f"no usable '{lang}' CV translation ({why}): the CV is in English")
        elif why:
            warnings.append(why)

    system = build_system_prompt(doc, cfg)
    prompt = posting_prompt(row, score, lang, 3000)
    feedback = ""
    out: TailorOut | None = None
    problems: list[str] = []
    for _attempt in range(MAX_ATTEMPTS):
        try:
            out = client.call(
                stage="tailor", system=system, prompt=prompt + feedback, schema=TAILOR_SCHEMA,
                model=cfg.tailoring.model, parse=TailorOut, job_id=row["id"],
            )  # fmt: skip
        except LlmError:
            if out is None:
                raise
            problems.append("a retry after failed checks did not complete; first draft kept")
            break  # keep the first (already paid for) draft and flag it for review
        selection, problems = resolve_selection(doc, out.selection)
        problems += verify_letter(out.letter.paragraphs, doc, lang)
        letter_tex = fill_letter(template, job, out.letter.paragraphs, lang, day)
        letter_pdf = compile_fn(letter_tex, cfg.latex.engine, cfg.latex.timeout_seconds)
        if not letter_pdf.ok:
            problems.append(f"letter {letter_pdf.detail}")
        elif letter_pdf.pages != 1:
            problems.append(f"letter has {letter_pdf.pages} pages (must be exactly 1); shorten it")
        if not problems:
            break
        feedback = "\n\nYour previous answer failed these checks, fix them:\n- " + "\n- ".join(
            problems
        )
    assert out is not None
    cv_tex, cv_pdf, final_sel, fit_notes = _fit_cv(doc, selection, translation, cfg, compile_fn)
    cv_problems = [n for n in fit_notes if n != "trimmed to fit the page limit"]
    problems += cv_problems
    warnings += [n for n in fit_notes if n == "trimmed to fit the page limit"][:1]
    verified = not problems

    folder = out_root / day.isoformat() / f"{slug(job.company)}-{slug(job.title)}-{row['id']}"
    staging = folder.parent / f".{folder.name}.tmp"  # written fully, then swapped in
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    final_folder, folder = folder, staging
    (folder / "cv.tex").write_text(cv_tex)
    if cv_pdf.pdf:
        (folder / "cv.pdf").write_bytes(cv_pdf.pdf)
    (folder / "cover_letter.tex").write_text(letter_tex)
    if letter_pdf.pdf:
        (folder / "cover_letter.pdf").write_bytes(letter_pdf.pdf)
    (folder / "recruiter_message.md").write_text(out.recruiter_message.strip() + "\n")
    (folder / "notes.md").write_text(
        render_notes(job, row, score, out.notes, problems, warnings, verified)
    )
    (folder / "meta.json").write_text(
        json.dumps(
            {
                "job_id": row["id"],
                "model": cfg.tailoring.model,
                "language": lang,
                "prompt_version": PROMPT_VERSION,
                "verified": verified,
                "problems": problems,
                "warnings": warnings,
                "cv_pages": cv_pdf.pages,
                "letter_pages": letter_pdf.pages,
                "created_at": datetime.now(UTC).isoformat(),
                "selection": {"sections": final_sel.sections, "items": final_sel.items},
            },
            indent=2,
            ensure_ascii=False,
        )  # fmt: skip
    )
    if final_folder.exists():
        shutil.rmtree(final_folder)
    staging.rename(final_folder)
    folder = final_folder
    with conn:
        conn.execute(
            "INSERT INTO packages(job_id, path, model, created_at, verified) VALUES (?,?,?,?,?)",
            (row["id"], str(folder), cfg.tailoring.model, datetime.now(UTC).isoformat(),
             int(verified)),
        )  # fmt: skip
        # Re-read the status: the person may have marked the posting as applied meanwhile.
        current = conn.execute("SELECT status FROM jobs WHERE id = ?", (row["id"],)).fetchone()
        if current and current["status"] not in HUMAN_STATUSES | {"closed", "duplicate"}:
            conn.execute("UPDATE jobs SET status = 'packaged' WHERE id = ?", (row["id"],))
            conn.execute(
                "INSERT INTO events(job_id, from_status, to_status, note, created_at) "
                "VALUES (?,?,?,?,?)",
                (row["id"], current["status"], "packaged",
                 "package " + ("verified" if verified else "needs review"),
                 datetime.now(UTC).isoformat()),
            )  # fmt: skip
    return PackageResult(row["id"], folder, verified, problems, lang)


def render_notes(
    job: Job, row: sqlite3.Row, score: sqlite3.Row | None, llm_notes: str,
    problems: list[str], warnings: list[str], verified: bool,
) -> str:  # fmt: skip
    lines = []
    if not verified:
        lines += ["> **REVIEW — automatic checks failed:**", *[f"> - {p}" for p in problems], ""]
    lines += [f"# {job.title.strip()} — {job.company}", "", f"- Apply: {job.url}",
              f"- Location: {job.location or 'n/a'} ({job.remote})"]  # fmt: skip
    if job.salary_max:
        lines.append(f"- Salary: {job.salary_min}–{job.salary_max} {job.salary_currency}")
    if score:
        info = json.loads(score["reasons"])
        lines += [f"- Score: {score['score']} ({info.get('verdict')}) — {info.get('reason', '')}"]
        if info.get("red_flags"):
            lines += ["- **Verify before applying:** " + "; ".join(info["red_flags"])]
        if info.get("gaps"):
            lines += ["- Gaps: " + "; ".join(info["gaps"])]
    if warnings:
        lines += ["", "## Warnings", *[f"- {w}" for w in warnings]]
    lines += ["", "## Notes", llm_notes.strip() or "(none)", ""]
    return "\n".join(lines)


def tailor_stage(
    conn: sqlite3.Connection, client: LlmClient, cfg: Config, doc: Document, *,
    cv_dir: Path, template: str, out_root: Path,
    compile_fn: CompileFn = latex.compile_pdf, day: date | None = None,
    force: bool = False, limit: int | None = None, job_ids: list[int] | None = None,
) -> TailorSummary:  # fmt: skip
    """Package `selected` postings, or exactly the postings in `job_ids` whatever their status."""
    day = day or datetime.now(UTC).date()
    if job_ids:  # the person picked these by hand: any posting qualifies, whatever its status
        marks = ",".join("?" for _ in job_ids)
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE id IN ({marks}) ORDER BY id", tuple(job_ids)
        ).fetchall()
    else:
        statuses = ("selected", "packaged") if force else ("selected",)
        marks = ",".join("?" for _ in statuses)
        rows = conn.execute(
            f"SELECT * FROM jobs WHERE status IN ({marks}) ORDER BY id", statuses
        ).fetchall()
    if limit:
        rows = rows[:limit]
    summary = TailorSummary(candidates=len(rows))
    for row in rows:
        try:
            result = tailor_job(
                conn, client, cfg, doc, row, template=template, cv_dir=cv_dir,
                out_root=out_root, compile_fn=compile_fn, day=day,
            )  # fmt: skip
        except LlmLimitReached as exc:
            summary.stopped = str(exc)
            break
        except (LlmError, latex.CvError, OSError) as exc:
            summary.errors.append(f"#{row['id']} {row['title']}: {exc}")
            continue
        summary.results.append(result)
        summary.packaged += 1
        summary.needs_review += 0 if result.verified else 1
    summary.calls = client.calls
    return summary
