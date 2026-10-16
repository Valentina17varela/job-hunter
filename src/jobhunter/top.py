"""The Top matches board: the best-fit postings you have not dismissed (see specs/22).

Ranking is pure data already stored (free and instant). Scoring more postings to fill the board
is a separate, person-started step; `fill_candidates` only chooses which ones deserve the calls.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from typing import Any

from jobhunter.config import Config
from jobhunter.filters import to_usd

# Statuses of postings that have a score and are still on the table.
SCORED_STATUSES = ("scored", "selected", "packaged", "below_threshold")
# Postings that met the hard criteria but have no (usable) score yet.
UNSCORED_STATUSES = ("passed", "score_failed")

REASONS: dict[str, str] = {
    "role": "Wrong role",
    "location": "Location or visa",
    "pay": "Pay",
    "company": "Company",
    "seniority": "Seniority",
    "other": "Other",
}
# What a reason suggests changing in Settings (shown as a suggestion only, never applied).
REASON_HINTS: dict[str, str] = {
    "role": "add words to *Words you do not want in the title*, or narrow *Roles you want*",
    "location": "tighten *Where you can work*",
    "pay": "raise the minimum salary",
    "company": "use *Block this company* on the posting page",
    "seniority": "adjust *Seniority*",
}
SUGGESTION_MIN = 3  # a reason needs this many dismissals before it becomes a suggestion

_BOARD_SQL = (
    "SELECT j.id, j.company, j.title, j.location, j.remote, j.source, j.status, "
    "j.salary_min, j.salary_max, j.salary_currency, j.posted_at, s.score, "
    "json_extract(s.reasons, '$.verdict') AS verdict, "
    "json_extract(s.reasons, '$.reason') AS reason, "
    "json_array_length(json_extract(s.reasons, '$.red_flags')) AS flags, "
    "EXISTS(SELECT 1 FROM packages WHERE job_id = j.id) AS has_package, "
    "NULL AS stage, "
    "f.job_id IS NOT NULL AS is_favorite, f.note AS favorite_note "
    "FROM jobs j JOIN scores s ON s.job_id = j.id AND s.created_at = "
    "(SELECT MAX(created_at) FROM scores WHERE job_id = j.id) "
    "LEFT JOIN favorites f ON f.job_id = j.id "
    f"WHERE j.status IN ({','.join('?' for _ in SCORED_STATUSES)}) "
    "AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.job_id = j.id)"
)


def top_matches(
    conn: sqlite3.Connection, cfg: Config, n: int | None = None
) -> list[dict[str, Any]]:
    """The `n` best scored postings: above the threshold first, then the best of the rest.

    Each row carries ``below_threshold`` so the UI never presents a weaker posting as a match.
    """
    limit = n or cfg.scoring.top_matches_count
    threshold = cfg.scoring.score_threshold
    rows = [dict(r) for r in conn.execute(_BOARD_SQL, SCORED_STATUSES)]
    for row in rows:
        row["below_threshold"] = row["score"] < threshold or row["verdict"] == "skip"
    rows.sort(key=lambda r: (r["below_threshold"], -r["score"], -r["id"]))
    return rows[:limit]


def _words(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])", text) is not None


def prerank(row: sqlite3.Row | dict[str, Any], cfg: Config, favorite: bool = False) -> int:
    """Free, deterministic guess of how likely an unscored posting is to score well.

    Keyword and title hits, a published salary that clears the minimum, recency, and postings
    the person chose themselves (favorites, added by hand). Higher is better.
    """
    title = (row["title"] or "").lower()
    description = (row["description"] or "").lower()
    points = 0
    for keyword in cfg.search.keywords_include:
        if _words(title, keyword):
            points += 2
        elif _words(description, keyword):
            points += 1
    if any(_words(title, t) for t in cfg.search.titles_include):
        points += 3
    if row["salary_max"]:
        points += 1
        usd = to_usd(row["salary_max"], row["salary_currency"], cfg.fx_rates_to_usd)
        if usd is not None and usd >= cfg.search.salary.min_usd:
            points += 2
    if row["posted_at"]:
        try:
            posted = datetime.fromisoformat(row["posted_at"])
            age = (
                datetime.now(UTC) - (posted if posted.tzinfo else posted.replace(tzinfo=UTC))
            ).days
            points += 2 if age <= 7 else 1 if age <= 30 else 0
        except ValueError:
            pass
    if favorite:
        points += 5
    if row["source"] == "manual":
        points += 5
    return points


def fill_candidates(conn: sqlite3.Connection, cfg: Config, need: int) -> list[int]:
    """Ids of the unscored postings worth scoring to refill `need` missing places.

    Asks for twice as many as missing (some will score below the threshold), never more than
    the per-run call cap can score at the configured batch size.
    """
    if need <= 0:
        return []
    cap = cfg.budget.max_llm_calls_per_run * max(1, cfg.scoring.batch_size)
    count = min(need * 2, cap)
    favorites = {r[0] for r in conn.execute("SELECT job_id FROM favorites")}
    rows = conn.execute(
        f"SELECT * FROM jobs WHERE status IN ({','.join('?' for _ in UNSCORED_STATUSES)})",
        UNSCORED_STATUSES,
    ).fetchall()
    ranked = sorted(
        rows,
        key=lambda r: (-prerank(r, cfg, r["id"] in favorites), r["posted_at"] is None, r["id"]),
    )
    return [r["id"] for r in ranked[:count]]


def unscored_count(conn: sqlite3.Connection) -> int:
    marks = ",".join("?" for _ in UNSCORED_STATUSES)
    return conn.execute(
        f"SELECT COUNT(*) FROM jobs WHERE status IN ({marks})", UNSCORED_STATUSES
    ).fetchone()[0]


def plan(conn: sqlite3.Connection, cfg: Config) -> dict[str, Any]:
    """Everything the UI needs: the board, how many places are empty and what could fill them."""
    board = top_matches(conn, cfg)
    target = cfg.scoring.top_matches_count
    need = max(0, target - len(board))
    above = sum(1 for r in board if not r["below_threshold"])
    return {
        "board": board,
        "target": target,
        "need": need,
        "above": above,
        "below": len(board) - above,
        "fill_ids": fill_candidates(conn, cfg, need) if need else [],
        "unscored_left": unscored_count(conn),
    }


def reason_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """How many postings were dismissed with each *Not for me* reason."""
    counts: dict[str, int] = {}
    for (note,) in conn.execute("SELECT note FROM events WHERE note LIKE 'not for me: %'"):
        reason = note.split(":", 1)[1].split("|", 1)[0].strip()
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def suggestions(conn: sqlite3.Connection) -> list[str]:
    """Plain-language hints from repeated dismissals. Suggestions only; nothing is changed."""
    out = []
    for reason, n in sorted(reason_counts(conn).items(), key=lambda kv: -kv[1]):
        if n >= SUGGESTION_MIN and reason in REASON_HINTS:
            label = REASONS[reason].lower()
            out.append(f"You marked {n} postings as “{label}”: consider to {REASON_HINTS[reason]}.")
    return out
