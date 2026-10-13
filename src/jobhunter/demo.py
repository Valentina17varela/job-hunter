"""Demo workspace with fictional data, to try or screenshot the web UI.

    uv run jobhunter demo            # writes data/demo/ and starts the UI on it

Nothing here touches your real database, CV or configuration.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jobhunter import applications, latex, resources
from jobhunter.db import connect
from jobhunter.models import Job
from jobhunter.store import log_fetch, upsert_jobs

NOW = datetime.now(UTC)

JOBS = [  # company, title, location, mode, source, salary, score, verdict, reason, flags
    (
        "Northwind Labs",
        "Senior Backend Engineer, Payments",
        "Remote, Americas",
        "remote",
        "greenhouse",
        168000,
        91,
        "apply",
        "Event-driven Python services on AWS: close match to the CV, strong overlap on queues and database work.",
        [],
    ),
    (
        "Lumen Health",
        "Software Engineer, Platform",
        "Remote, Worldwide",
        "remote",
        "ashby",
        142000,
        88,
        "apply",
        "Python and Kubernetes platform work; remote worldwide, level matches.",
        [],
    ),
    (
        "Cobalt Freight",
        "Backend Engineer (Go)",
        "LATAM",
        "remote",
        "lever",
        120000,
        84,
        "apply",
        "Go services for logistics routing; same domain as past routing work.",
        [],
    ),
    (
        "Atlas Cloud",
        "Senior Software Engineer, Data Pipelines",
        "Remote",
        "remote",
        "greenhouse",
        None,
        79,
        "maybe",
        "Strong Python and SQL fit; salary not published and the posting does not state eligible countries.",
        ["Posting does not say which countries it hires in"],
    ),
    (
        "Brightside",
        "Software Engineer II, Growth Platform",
        "Colombia",
        "remote",
        "greenhouse",
        96000,
        77,
        "apply",
        "Based in Colombia, TypeScript and Python stack, mid level.",
        [],
    ),
    (
        "Pinecone Works",
        "Backend Engineer, Search",
        "Remote, Global",
        "remote",
        "ashby",
        135000,
        74,
        "maybe",
        "Good backend fit; search relevance experience is a gap.",
        [],
    ),
    (
        "Harbor Analytics",
        "Senior Python Engineer",
        "Anywhere in the World",
        "remote",
        "remoteok",
        None,
        71,
        "maybe",
        "Python-heavy role; asks for overlap with CET working hours.",
        ["Requires a CET time zone overlap"],
    ),
    (
        "Granite Bank",
        "Software Engineer, Core Banking",
        "Remote - US",
        "remote",
        "greenhouse",
        150000,
        42,
        "skip",
        "Hiring only US residents.",
        ["Eligible: United States residents only"],
    ),
    (
        "Zenith Games",
        "Backend Engineer, Live Services",
        "Remote - Canada",
        "remote",
        "lever",
        118000,
        38,
        "skip",
        "Open to Canadian residents only.",
        ["Requires residency in Canada"],
    ),
]
FILTERED = [
    ("Frontend Software Engineer", 'titles_exclude: title contains "Frontend"'),
    ("Sales Engineer", "titles_include: title matches none of the wanted titles"),
    (
        "Senior Backend Engineer",
        'locations_allowed: location "Remote - Germany" is not in the allowed list',
    ),
    ("Junior Software Developer", 'titles_exclude: title contains "Junior"'),
    ("Staff Software Engineer", "seniority: title implies \"lead\", wanted ['mid', 'senior']"),
]


def seed(workspace: Path) -> Path:
    """Write the demo workspace into `workspace` and return the path of its config file."""
    workspace.mkdir(parents=True, exist_ok=True)
    out = workspace / "out"
    db_path = workspace / "demo.db"
    for old in (db_path,):
        old.unlink(missing_ok=True)
    conn = connect(db_path)

    jobs = [
        Job(
            source=src,
            external_id=str(i),
            company=company,
            title=title,
            location=loc,
            remote=mode,
            description=f"{title} at {company}. Build reliable services in Python and TypeScript on AWS.",
            url=f"https://example.com/jobs/{i}",
            salary_min=(sal - 20000) if sal else None,
            salary_max=sal,
            salary_currency="USD" if sal else None,
            posted_at=NOW - timedelta(days=i),
        )
        for i, (company, title, loc, mode, src, sal, *_rest) in enumerate(JOBS, start=1)
    ]
    upsert_jobs(conn, jobs)
    for i, (*_head, score, verdict, reason, flags) in enumerate(JOBS, start=1):
        reasons = json.dumps(
            {
                "verdict": verdict,
                "reason": reason,
                "red_flags": flags,
                "must_have_match": ["python", "aws", "distributed systems"][: 3 - (i % 2)],
                "gaps": ["kubernetes"] if i % 3 == 0 else [],
            }
        )
        conn.execute(
            "INSERT INTO scores(job_id, score, reasons, model, profile_hash, prompt_version, "
            "created_at, content_hash) VALUES (?,?,?,?,?,?,?,?)",
            (i, score, reasons, "haiku", "demo", "demo", NOW.isoformat(), jobs[i - 1].content_hash),
        )
        status = "selected" if score >= 75 else "below_threshold"
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, i))
    # filtered-out postings
    filtered = [
        Job(
            source="greenhouse",
            external_id=f"f{i}",
            company=f"Other Co {i}",
            title=title,
            location="Remote",
            remote="remote",
            description="x",
            url="https://example.com/x",
        )
        for i, (title, _r) in enumerate(FILTERED, start=1)
    ]
    upsert_jobs(conn, filtered)
    for title, reason in FILTERED:
        conn.execute(
            "UPDATE jobs SET status='filtered', filter_reason=? WHERE title=?", (reason, title)
        )
    # a few hundred more filtered rows so the funnel looks realistic
    bulk = [
        Job(
            source="greenhouse",
            external_id=f"b{k}",
            company=f"Bulk {k % 40}",
            title=f"Role {k}",
            location="Remote",
            remote="remote",
            description="x",
            url="https://example.com/b",
        )
        for k in range(1, 1201)
    ]
    upsert_jobs(conn, bulk)
    reasons = ["titles_include: title matches none of the wanted titles"] * 7 + [
        'titles_exclude: title contains "mobile"',
        'work_mode: posting is "onsite"',
        'seniority: title implies "junior"',
        "locations_allowed: not in the allowed list",
    ]
    for k in range(1, 1201):
        conn.execute(
            "UPDATE jobs SET status='filtered', filter_reason=? WHERE external_id=?",
            (reasons[k % len(reasons)], f"b{k}"),
        )
    conn.commit()

    # a built package, an application and an interview
    folder = out / NOW.date().isoformat() / "northwind-labs-senior-backend-engineer-payments-1"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "recruiter_message.md").write_text(
        "Hi, I'm a backend engineer with 4+ years building event-driven systems in Python on AWS. "
        "I'd love to talk about the Payments role. I work remotely from Colombia (UTC-5).\n"
    )
    (folder / "notes.md").write_text(
        "# Senior Backend Engineer, Payments — Northwind Labs\n\nStrong fit.\n"
    )
    (folder / "meta.json").write_text(
        json.dumps(
            {"language": "en", "cv_pages": 1, "letter_pages": 1, "verified": True, "problems": []}
        )
    )
    template = resources.read("letter_template.example.tex")
    demo_cv = (
        "\\documentclass[a4paper]{article}\\usepackage[margin=1in]{geometry}\\pagestyle{empty}"
        "\\begin{document}{\\Large\\bfseries ALEX RIVERA}\\par Backend Engineer\\par\\medskip "
        "Demo CV generated for the screenshots.\\end{document}"
    )
    letter = (
        template.replace("YOUR NAME", "ALEX RIVERA")
        .replace("%%DATE%%", "October 11, 2026")
        .replace("%%RECIPIENT_LABEL%%", "Hiring Team")
        .replace("%%COMPANY%%", "Northwind Labs")
        .replace("%%SUBJECT%%", "Application --- Senior Backend Engineer")
        .replace("%%GREETING%%", "Dear Hiring Team,")
        .replace("%%CLOSING%%", "Sincerely,")
        .replace("%%BODY%%", "Demo cover letter body.")
    )
    for name, tex in (("cv", demo_cv), ("cover_letter", letter)):
        (folder / f"{name}.tex").write_text(tex)
        result = latex.compile_pdf(tex, "tectonic", 120)
        if result.pdf:
            (folder / f"{name}.pdf").write_bytes(result.pdf)
    conn.execute(
        "INSERT INTO packages(job_id, path, model, created_at, verified) VALUES (1,?,?,?,1)",
        (str(folder), "sonnet", NOW.isoformat()),
    )
    conn.execute("UPDATE jobs SET status='packaged' WHERE id=1")
    conn.commit()
    for jid in (2, 3):
        applications.set_stage(conn, jid, "applied", "Applied through the company site")
    applications.set_stage(conn, 2, "interviewing", "Recruiter call done")
    applications.add_interview(
        conn, 2, "recruiter", (NOW - timedelta(days=2)).strftime("%Y-%m-%dT10:00"), "Went well"
    )
    conn.execute("UPDATE interviews SET outcome='passed'")
    applications.add_interview(
        conn,
        2,
        "technical",
        (NOW + timedelta(days=3)).strftime("%Y-%m-%dT15:30"),
        "Pair programming, bring examples",
    )
    applications.add_interview(
        conn, 3, "recruiter", (NOW + timedelta(days=5)).strftime("%Y-%m-%dT09:00")
    )
    for source, found in (
        ("greenhouse", 6420),
        ("lever", 1310),
        ("ashby", 2890),
        ("remoteok", 99),
        ("arbeitnow", 750),
    ):
        log_fetch(conn, source, "", "ok", found)
    conn.execute(
        "INSERT INTO llm_calls(stage, model, tokens_in, tokens_out, cost_usd, created_at) "
        "VALUES ('score','haiku',12000,1000,0,?)",
        (NOW.isoformat(),),
    )
    conn.commit()

    (workspace / "config.yaml").write_text(f"""\
paths:
  db: {db_path}
  out: {out}
  cv_master: {workspace / "master.tex"}
  letter_template: {workspace / "letter_template.tex"}
sources:
  companies_file: {workspace / "companies.yaml"}
search:
  titles_include: ["software engineer", "backend", "python"]
  titles_exclude: ["intern", "junior", "frontend", "mobile", "qa"]
  keywords_include: ["python", "typescript", "golang"]
  seniority: ["mid", "senior"]
  work_mode: ["remote"]
  locations_allowed: ["Colombia", "LATAM", "Americas", "Worldwide", "Anywhere", "Global"]
  salary: {{min_usd: 80000, on_missing: pass}}
scoring:
  candidate_context: "Based in Colombia and can only work remotely from Colombia."
tailoring:
  tone: "formal but warm, concrete and confident"
""")
    (workspace / "master.tex").write_text(resources.read("cv.example.tex"), encoding="utf-8")
    (workspace / "letter_template.tex").write_text(template, encoding="utf-8")
    latex.parse((workspace / "master.tex").read_text())
    return workspace / "config.yaml"
