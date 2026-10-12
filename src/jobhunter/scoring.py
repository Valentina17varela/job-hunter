"""LLM scoring of postings that passed the hard filter (see specs/05-scoring.md)."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from jobhunter.config import Config
from jobhunter.filters import job_from_row
from jobhunter.latex import Document, digest
from jobhunter.llm import LlmClient, LlmError, LlmLimitReached

PROMPT_VERSION = "score-v2"
CHARS_PER_TOKEN = 4

SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "verdict": {"type": "string", "enum": ["apply", "maybe", "skip"]},
                    "must_have_match": {"type": "array", "items": {"type": "string"}},
                    "gaps": {"type": "array", "items": {"type": "string"}},
                    "red_flags": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["id", "score", "verdict", "reason"],
            },
        }
    },
    "required": ["results"],
}


class ScoreItem(BaseModel):
    id: int
    score: int = Field(ge=0, le=100)
    verdict: Literal["apply", "maybe", "skip"]
    must_have_match: list[str] = []
    gaps: list[str] = []
    red_flags: list[str] = []
    reason: str = ""


class BatchResult(BaseModel):
    results: list[ScoreItem]


RUBRIC = """\
Score each posting from 0 to 100 for how well it fits the candidate:
- 85-100: meets almost all key requirements, level and stack aligned, no blocker.
- 70-84: good match, 1-2 minor gaps.
- 50-69: partial match, relevant gaps.
- below 50: not a fit, or a hard blocker the candidate cannot meet.
Verdict: "apply" (worth applying), "maybe" (borderline), "skip" (do not apply).

Hard blockers go in red_flags, and ONLY when the posting explicitly states them: citizenship,
residency or legal work authorization requirements, W-2/employee-only hiring in a country the
candidate cannot work in as described in the candidate context, a required time zone the
candidate cannot meet, or a list of eligible countries that excludes the candidate's country.
Do NOT infer a blocker from the location alone or from the industry: a posting located in a
country where the candidate can work as a contractor is fine unless it says otherwise.
Be strict about requirements the posting actually states; do not invent any.

Be terse: "reason" at most 30 words; at most 3 red_flags and 4 gaps, each at most 12 words;
at most 5 must_have_match items. Return every posting id exactly once."""


def build_system_prompt(doc: Document, cfg: Config) -> str:
    s = cfg.search
    context = cfg.scoring.candidate_context.strip() or "(not provided)"
    prefs = (
        f"Target titles: {', '.join(s.titles_include) or 'any'}. "
        f"Seniority: {', '.join(s.seniority) or 'any'}. "
        f"Work mode: {', '.join(s.work_mode) or 'any'}. "
        f"Minimum salary: ${s.salary.min_usd:,}/year (USD)."
    )
    return (
        "You evaluate job postings for one candidate and return strict JSON only.\n\n"
        f"{RUBRIC}\n\n## Candidate context\n{context}\n\n## Candidate preferences\n{prefs}\n\n"
        f"## Candidate CV (plain text)\n{digest(doc)}"
    )


def profile_hash(system_prompt: str) -> str:
    return hashlib.sha256(f"{PROMPT_VERSION}\n{system_prompt}".encode()).hexdigest()[:16]


_SECTION_RE = re.compile(
    r"^\s*(requirements|qualifications|what you.ll (?:do|bring|need)|responsibilities|"
    r"who you are|about you|you have|minimum qualifications)\b.*$",
    re.I | re.M,
)


def truncate_description(text: str, max_tokens: int) -> str:
    """Keep the start and the requirements/responsibilities section instead of a blind cut."""
    limit = max_tokens * CHARS_PER_TOKEN
    if len(text) <= limit:
        return text
    head_len = int(limit * 0.4)
    match = _SECTION_RE.search(text, head_len)
    start = match.start() if match else max(head_len, len(text) - (limit - head_len))
    tail = text[start : start + (limit - head_len)]
    return f"{text[:head_len].rstrip()}\n[...]\n{tail.strip()}"


def posting_block(row: sqlite3.Row, max_tokens: int) -> dict[str, Any]:
    job = job_from_row(row)
    salary = None
    if job.salary_max:
        salary = f"{job.salary_min}-{job.salary_max} {job.salary_currency} per year"
    note = (
        "Chosen on purpose by the candidate (added by hand). Do not penalize a missing salary "
        "or location; judge the fit and any explicit blockers."
        if job.source == "manual"
        else None
    )
    block = {
        "id": row["id"],
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "work_mode": job.remote,
        "salary": salary,
        "filter_flags": (row["filter_flags"] or "").split(",") if row["filter_flags"] else [],
        "description": truncate_description(job.description, max_tokens),
    }
    if note:
        block["note"] = note
    return block


@dataclass
class ScoreSummary:
    candidates: int = 0
    cached: int = 0
    scored: int = 0
    failed: int = 0
    calls: int = 0
    stopped: str | None = None
    selected: int = 0
    below_threshold: int = 0
    red_flagged: int = 0
    verdicts: dict[str, int] = field(default_factory=dict)


def _set_status(conn: sqlite3.Connection, job_id: int, new: str, note: str) -> None:
    old = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]
    if old == new:
        return
    conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (new, job_id))
    conn.execute(
        "INSERT INTO events(job_id, from_status, to_status, note, created_at) VALUES (?,?,?,?,?)",
        (job_id, old, new, note, datetime.now(UTC).isoformat()),
    )


def _store_score(
    conn: sqlite3.Connection, row: sqlite3.Row, item: ScoreItem, model: str, phash: str
) -> None:
    reasons = json.dumps(
        {
            "verdict": item.verdict,
            "must_have_match": item.must_have_match,
            "gaps": item.gaps,
            "red_flags": item.red_flags,
            "reason": item.reason,
        }
    )
    conn.execute(
        "INSERT INTO scores(job_id, score, reasons, model, profile_hash, prompt_version, "
        "created_at, content_hash) VALUES (?,?,?,?,?,?,?,?)",
        (row["id"], item.score, reasons, model, phash, PROMPT_VERSION,
         datetime.now(UTC).isoformat(), row["content_hash"]),
    )  # fmt: skip


def _cached_score(conn: sqlite3.Connection, row: sqlite3.Row, phash: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM scores WHERE job_id = ? AND content_hash = ? AND profile_hash = ? "
        "AND prompt_version = ? ORDER BY created_at DESC LIMIT 1",
        (row["id"], row["content_hash"], phash, PROMPT_VERSION),
    ).fetchone()


def score_stage(
    conn: sqlite3.Connection,
    client: LlmClient,
    cfg: Config,
    doc: Document,
    job_ids: list[int] | None = None,
) -> ScoreSummary:
    """Score `passed` (and previously failed) postings in batches, then apply the selection.

    With ``job_ids`` only those postings are considered (used when the person adds one by hand).
    """
    summary = ScoreSummary()
    system = build_system_prompt(doc, cfg)
    if len(system) > cfg.scoring.max_profile_tokens * CHARS_PER_TOKEN:
        raise LlmError(
            f"CV digest + context is about {len(system) // CHARS_PER_TOKEN} tokens, above "
            f"scoring.max_profile_tokens={cfg.scoring.max_profile_tokens}. Trim marked items "
            "or raise the limit."
        )
    phash = profile_hash(system)
    # Also re-score postings whose stored score is stale (new CV, context or prompt version).
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status IN ('passed', 'score_failed', 'scored', "
        "'below_threshold', 'selected') ORDER BY id"
    ).fetchall()
    if job_ids is not None:
        rows = [r for r in rows if r["id"] in set(job_ids)]

    todo: list[sqlite3.Row] = []
    for row in rows:
        if _cached_score(conn, row, phash):
            if row["status"] in ("passed", "score_failed"):
                summary.cached += 1
                with conn:
                    _set_status(conn, row["id"], "scored", "score reused")
        else:
            todo.append(row)
    summary.candidates = len(todo)

    size = max(1, cfg.scoring.batch_size)
    for start in range(0, len(todo), size):
        batch = todo[start : start + size]
        blocks = [posting_block(r, cfg.scoring.max_description_tokens) for r in batch]
        prompt = (
            'Evaluate these postings. Return {"results": [...]} with one entry per id.\n\n'
            + json.dumps(blocks, ensure_ascii=False)
        )
        try:
            result = client.call(
                stage="score", system=system, prompt=prompt, schema=SCORE_SCHEMA,
                model=cfg.scoring.model, parse=BatchResult,
            )  # fmt: skip
        except LlmLimitReached as exc:
            summary.stopped = str(exc)
            break
        except LlmError:
            summary.failed += len(batch)
            with conn:
                for row in batch:
                    _set_status(conn, row["id"], "score_failed", "LLM call failed")
            continue
        summary.calls = client.calls
        by_id = {item.id: item for item in result.results}
        with conn:
            for row in batch:
                item = by_id.get(row["id"])
                if item is None:
                    summary.failed += 1
                    _set_status(conn, row["id"], "score_failed", "missing from LLM response")
                    continue
                _store_score(conn, row, item, cfg.scoring.model, phash)
                _set_status(conn, row["id"], "scored", f"score {item.score}")
                summary.scored += 1
    summary.calls = client.calls
    apply_selection(conn, cfg, summary)
    return summary


def apply_selection(
    conn: sqlite3.Connection, cfg: Config, summary: ScoreSummary | None = None
) -> None:
    """below_threshold / scored / selected from the latest score of each scored posting."""
    threshold = cfg.scoring.score_threshold
    rows = conn.execute(
        "SELECT j.id, j.status, s.score, s.reasons FROM jobs j JOIN scores s ON s.job_id = j.id "
        "AND s.created_at = (SELECT MAX(created_at) FROM scores WHERE job_id = j.id) "
        "WHERE j.status IN ('scored', 'selected', 'below_threshold') ORDER BY s.score DESC, j.id"
    ).fetchall()
    selected_now = sum(1 for r in rows if r["status"] == "selected")
    slots = max(0, cfg.tailoring.max_packages_per_day - selected_now)
    with conn:
        for r in rows:
            verdict = json.loads(r["reasons"]).get("verdict")
            if r["score"] < threshold or verdict == "skip":
                _set_status(conn, r["id"], "below_threshold", f"score {r['score']} / {verdict}")
                if summary:
                    summary.below_threshold += 1
            elif r["status"] == "scored" and slots > 0:
                _set_status(conn, r["id"], "selected", f"top match (score {r['score']})")
                slots -= 1
                if summary:
                    summary.selected += 1
            elif r["status"] == "below_threshold":
                _set_status(conn, r["id"], "scored", f"score {r['score']} now above threshold")
