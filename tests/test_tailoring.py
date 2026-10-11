import json
from datetime import date
from pathlib import Path

import pytest

from jobhunter import latex, tailoring
from jobhunter.config import Config
from jobhunter.db import connect
from jobhunter.language import detect_language
from jobhunter.llm import LlmClient, LlmResponse
from jobhunter.models import Job
from jobhunter.store import upsert_jobs
from jobhunter.tailoring import (
    SelectionOut,
    fill_letter,
    format_date,
    resolve_selection,
    tailor_stage,
    trim_once,
    verify_letter,
)
from jobhunter.translate import check_unit, save_translation, translate_cv

CV = (Path(__file__).parent / "fixtures" / "master_marked.tex").read_text()
TEMPLATE = (
    "\\documentclass{article}\\begin{document}\nTO: %%RECIPIENT_LABEL%% %%COMPANY%%\n"
    "%%DATE%%\n%%SUBJECT%%\n%%GREETING%%\n%%BODY%%\n%%CLOSING%%\n\\end{document}\n"
)
DAY = date(2026, 10, 11)


def good_paragraphs():
    filler = (
        "I build reliable backend services and I enjoy turning slow, fragile workflows into "
        "predictable ones that the business can depend on every single day. "
    ) * 2
    return [
        "Cutting order latency by 40% with Python and AWS showed me that reliability is a "
        "product feature. " + filler,
        "Your posting asks for ownership and API design. At Acme I built a TypeScript dashboard "
        "and mentored 4 engineers. " + filler,
        "I work remotely from Colombia and would welcome a conversation about the role. " + filler,
    ]


def tailor_payload(**over):
    payload = {
        "selection": {
            "entries": {"experience": ["exp-acme", "exp-beta"]},
            "items": {"exp-acme": ["exp-acme-2", "exp-acme-1", "exp-acme-3"]},
        },
        "letter": {"paragraphs": good_paragraphs()},
        "recruiter_message": "Hi! I'd love to chat about the role. — V",
        "notes": "Strong fit. Verify time zone.",
    }
    payload.update(over)
    return payload


class FakeLlm:
    def __init__(self, *payloads):
        self.payloads, self.prompts, self.calls = list(payloads), [], 0

    def complete(self, *, system, prompt, schema, model):
        self.calls += 1
        self.prompts.append(prompt)
        payload = self.payloads.pop(0) if len(self.payloads) > 1 else self.payloads[0]
        return LlmResponse(data=payload, model=model)


def fake_compile(max_items=99):
    """Pretend CV is 2 pages when it has more than `max_items` bullets; letters are 1 page."""

    def compile_fn(tex, engine, timeout):
        items = tex.count("\\item")
        if "TO:" in tex:  # the letter
            return latex.CompileResult(True, "ok", b"%PDF-letter", 1)
        return latex.CompileResult(True, "ok", b"%PDF-cv", 2 if items > max_items else 1)

    return compile_fn


@pytest.fixture
def setup(tmp_path):
    conn = connect(tmp_path / "t.db")
    upsert_jobs(
        conn,
        [Job(source="s", external_id="1", company="Acme & Sons", title="Senior Backend Engineer",
             description="We build payments APIs with Python. " * 20, url="https://x/1",
             remote="remote")],
    )  # fmt: skip
    conn.execute("UPDATE jobs SET status = 'selected'")
    conn.execute(
        "INSERT INTO scores(job_id, score, reasons, model, profile_hash, prompt_version, "
        "created_at) VALUES (1, 90, ?, 'm', 'h', 'v', 'now')",
        (json.dumps({"verdict": "apply", "must_have_match": ["python"], "gaps": ["go"],
                     "red_flags": ["check residency"], "reason": "great"}),),
    )  # fmt: skip
    conn.commit()
    cfg = Config.model_validate({"tailoring": {"max_cv_pages": 1}})
    return conn, cfg, latex.parse(CV), tmp_path


def run_stage(setup, llm, compile_fn=None, **kw):
    conn, cfg, doc, tmp = setup
    client = LlmClient(conn, llm, max_calls=kw.pop("max_calls", 10), sleep=lambda s: None)
    summary = tailor_stage(
        conn, client, cfg, doc, cv_dir=tmp / "cv", template=TEMPLATE, out_root=tmp / "out",
        compile_fn=compile_fn or fake_compile(), day=DAY, **kw,
    )  # fmt: skip
    return summary, client


def test_happy_path_writes_a_verified_package(setup):
    conn, _, _, tmp = setup
    summary, _ = run_stage(setup, FakeLlm(tailor_payload()))
    assert (summary.packaged, summary.needs_review) == (1, 0)
    folder = summary.results[0].path
    assert folder == tmp / "out" / "2026-10-11" / "acme-sons-senior-backend-engineer-1"
    assert {p.name for p in folder.iterdir()} == {
        "cv.tex", "cv.pdf", "cover_letter.tex", "cover_letter.pdf",
        "recruiter_message.md", "notes.md", "meta.json",
    }  # fmt: skip
    cv = (folder / "cv.tex").read_text()
    assert cv.index("TypeScript") < cv.index("Cut order latency")  # bullets re-ranked
    assert "Jane Doe" in cv  # header copied verbatim
    letter = (folder / "cover_letter.tex").read_text()
    assert "Acme \\& Sons" in letter and "October 11, 2026" in letter
    assert "Dear Hiring Team," in letter and "%%" not in letter
    notes = (folder / "notes.md").read_text()
    assert "REVIEW" not in notes and "check residency" in notes and "Apply: https://x/1" in notes
    assert json.loads((folder / "meta.json").read_text())["verified"] is True
    row = conn.execute("SELECT status FROM jobs").fetchone()
    assert row["status"] == "packaged"
    assert conn.execute("SELECT verified FROM packages").fetchone()["verified"] == 1


def test_second_run_does_not_regenerate_unless_forced(setup):
    llm = FakeLlm(tailor_payload())
    run_stage(setup, llm)
    again, _ = run_stage(setup, llm)
    assert again.candidates == 0 and llm.calls == 1
    forced, _ = run_stage(setup, llm, force=True)
    assert forced.packaged == 1 and llm.calls == 2


def test_failed_checks_trigger_one_retry_with_feedback(setup):
    bad = tailor_payload(letter={"paragraphs": ["I am passionate about 99% uptime. " * 20] * 3})
    llm = FakeLlm(bad, tailor_payload())
    summary, _ = run_stage(setup, llm)
    assert llm.calls == 2 and summary.needs_review == 0
    assert "failed these checks" in llm.prompts[1] and "passionate" in llm.prompts[1]


def test_persistent_failure_still_writes_files_with_a_review_banner(setup):
    bad = tailor_payload(letter={"paragraphs": ["I am passionate about 99% uptime. " * 20] * 3})
    summary, _ = run_stage(setup, FakeLlm(bad))
    result = summary.results[0]
    assert not result.verified and summary.needs_review == 1
    notes = (result.path / "notes.md").read_text()
    assert notes.startswith("> **REVIEW") and "passionate" in notes and "99%" in notes
    assert (result.path / "cv.pdf").exists()


def test_unknown_ids_are_reported_and_required_entries_re_added(setup):
    payload = tailor_payload(
        selection={"entries": {"experience": ["exp-beta", "ghost"]}, "items": {}}
    )
    summary, _ = run_stage(setup, FakeLlm(payload))
    notes = (summary.results[0].path / "notes.md").read_text()
    assert "unknown id 'ghost'" in notes
    cv = (summary.results[0].path / "cv.tex").read_text()
    assert "Senior Engineer" in cv and "Beta" in cv  # exp-acme is required → kept
    assert cv.index("Acme") < cv.index("Beta")  # chronology preserved


def test_cv_is_trimmed_deterministically_to_fit_the_page_limit(setup):
    summary, client = run_stage(setup, FakeLlm(tailor_payload()), fake_compile(max_items=3))
    cv = (summary.results[0].path / "cv.tex").read_text()
    assert cv.count("\\item") <= 3
    assert "Senior Engineer" in cv  # required entry survives
    assert summary.results[0].verified and client.calls == 1  # no extra LLM calls
    assert "trimmed" in (summary.results[0].path / "notes.md").read_text()


def test_cv_that_cannot_fit_is_flagged_for_review(setup):
    summary, _ = run_stage(setup, FakeLlm(tailor_payload()), fake_compile(max_items=0))
    assert not summary.results[0].verified
    assert any("cannot be trimmed" in p for p in summary.results[0].problems)


def test_spanish_posting_uses_spanish_letter_and_reviewed_translation(setup):
    conn, _, _, tmp = setup
    spanish = (
        "Buscamos un ingeniero para nuestro equipo con experiencia en el desarrollo de servicios "
        "y para trabajar con nuestros clientes en la región. Ofrecemos un trabajo remoto. " * 5
    )
    conn.execute("UPDATE jobs SET description = ?", (spanish,))
    conn.commit()
    doc = latex.parse(CV)
    units = latex.translation_units(doc)
    units["exp-acme-2"] = ["\\item Construí un panel en \\textbf{TypeScript} y una API."]
    save_translation(tmp / "cv", "es", units, {})
    cfg = setup[1].model_copy(update={"tailoring": setup[1].tailoring.model_copy(
        update={"languages": ["en", "es"]})})  # fmt: skip
    summary, _ = run_stage((conn, cfg, doc, tmp), FakeLlm(tailor_payload()))
    folder = summary.results[0].path
    assert summary.results[0].language == "es"
    assert "Estimado equipo de selección," in (folder / "cover_letter.tex").read_text()
    assert "Construí un panel" in (folder / "cv.tex").read_text()


def test_spanish_posting_without_translation_falls_back_with_a_warning(setup):
    conn, cfg, doc, tmp = setup
    conn.execute(
        "UPDATE jobs SET description = ?",
        ("Buscamos un ingeniero para nuestro equipo con experiencia en el trabajo y los clientes "
         "de la región y que se una a nuestra empresa como parte del equipo. " * 4,),
    )  # fmt: skip
    conn.commit()
    summary, _ = run_stage(setup, FakeLlm(tailor_payload()))
    notes = (summary.results[0].path / "notes.md").read_text()
    assert "no usable 'es' CV translation" in notes


def test_call_cap_stops_cleanly(setup):
    summary, _ = run_stage(setup, FakeLlm(tailor_payload()), max_calls=0)
    assert summary.stopped and summary.packaged == 0
    assert setup[0].execute("SELECT status FROM jobs").fetchone()["status"] == "selected"


def test_job_id_filter_and_limit(setup):
    summary, _ = run_stage(setup, FakeLlm(tailor_payload()), job_ids=[99])
    assert summary.candidates == 0
    summary, _ = run_stage(setup, FakeLlm(tailor_payload()), job_ids=[1])
    assert summary.packaged == 1


# --- units -------------------------------------------------------------------------------------


def test_verify_letter_rules():
    doc = latex.parse(CV)
    ok = verify_letter(good_paragraphs(), doc, "en")
    assert ok == []
    bad = verify_letter(["Passionate about 73% growth with Kubernetes. " * 30], doc, "en")
    joined = " ".join(bad)
    assert "passionate" in joined and "73%" in joined and "kubernetes" in joined
    assert any("words" in p for p in verify_letter(["Too short."], doc, "en"))


def test_resolve_selection_orders_and_validates():
    doc = latex.parse(CV)
    sel, problems = resolve_selection(
        doc,
        SelectionOut(
            entries={"experience": ["exp-beta"]}, items={"exp-acme": ["exp-acme-3", "zz"]}
        ),
    )
    assert sel.sections["experience"] == ["exp-acme", "exp-beta"]  # required re-added, chronology
    assert sel.items["exp-acme"] == ["exp-acme-3"]
    assert problems == ["unknown item 'zz' in 'exp-acme'"]


def test_trim_once_drops_optional_things_first_and_eventually_stops():
    doc = latex.parse(CV)
    sel = tailoring.full_selection(doc, latex.Selection())
    steps = 0
    while (nxt := trim_once(doc, sel)) is not None:
        sel, steps = nxt, steps + 1
    assert "exp-acme" in sel.sections["experience"]  # required stays
    assert "exp-beta" not in sel.sections["experience"]  # optional entry went first
    assert len(sel.items["exp-acme"]) == 2  # bullets trimmed down to two
    assert steps >= 2


def test_dates_and_letter_filling():
    assert format_date(date(2026, 3, 5), "en") == "March 5, 2026"
    assert format_date(date(2026, 3, 5), "es") == "5 de marzo de 2026"
    job = Job(source="s", external_id="1", company="A_B", title="Dev & Ops", url="u")
    out = fill_letter(TEMPLATE, job, ["One 50%.", "Two."], "es", DAY)
    assert "A\\_B" in out and "Postulación --- Dev \\& Ops" in out and "One 50\\%." in out


EN = "We are looking for an engineer to join our team and build the platform with you. "
ES = "Buscamos un ingeniero para nuestro equipo y trabajar con los clientes de la región. "
DE = "Wir suchen einen Entwickler für unser Team, der mit uns die Plattform betreut. "


@pytest.mark.parametrize(
    ("text", "lang"),
    [(EN * 3, "en"), (ES * 3, "es"), (DE * 3, "de"), ("short text", "en")],
)
def test_detect_language(text, lang):
    assert detect_language(text) == lang


def test_check_unit_detects_changed_numbers_commands_and_braces():
    src = ["\\textbf{Cut} latency by 40\\% \\\\"]
    assert check_unit(src, ["\\textbf{Reduje} la latencia en 40\\% \\\\"]) == []
    assert "numbers changed" in check_unit(src, ["\\textbf{Reduje} la latencia en 45\\% \\\\"])
    assert "LaTeX commands changed" in check_unit(src, ["Reduje la latencia en 40\\% \\\\"])
    assert "unbalanced braces" in check_unit(src, ["\\textbf{Reduje la latencia en 40\\% \\\\"])


def test_translate_cv_flags_bad_units_and_keeps_originals(tmp_path):
    conn = connect(tmp_path / "t.db")
    doc = latex.parse(CV)
    units = latex.translation_units(doc)

    class Translator:
        def complete(self, *, system, prompt, schema, model):
            chunk = json.loads(prompt.split("\n\n", 1)[1])
            out = {
                uid: [ln.replace("Built", "Construí") for ln in lines]
                for uid, lines in chunk.items()
            }
            out["exp-acme-1"] = ["\\item Redujo la latencia en 99\\%."]  # numbers changed
            out.pop("exp-beta-1", None)  # missing
            return LlmResponse(data={"units": out}, model=model)

    client = LlmClient(conn, Translator(), max_calls=20, sleep=lambda s: None)
    result, problems = translate_cv(client, Config(), doc, "es")
    assert set(result) == set(units)
    assert "numbers changed" in problems["exp-acme-1"]
    assert problems["exp-beta-1"] == ["missing from the response"]
    assert result["exp-beta-1"] == units["exp-beta-1"]  # falls back to the original
    assert "Construí" in result["exp-acme-2"][0]


# --- regressions found in review ---------------------------------------------------------------

REQ_CV = """\
% jh:section awards
\\section*{AWARDS}
% jh:entry award-main required
\\textbf{Main award}
\\begin{itemize}
% jh:item award-1
\\item First
% jh:item award-2
\\item Second
% jh:item award-3
\\item Third
\\end{itemize}
% jh:endentry
% jh:endsection

% jh:section certifications
\\section*{CERTIFICATIONS}
\\begin{itemize}
% jh:item cert-1
\\item One
\\end{itemize}
% jh:endsection
"""


def test_trim_never_drops_required_entries_in_optional_sections_and_always_terminates():
    doc = latex.parse(REQ_CV)
    sel = tailoring.full_selection(doc, latex.Selection())
    while (nxt := trim_once(doc, sel)) is not None:
        sel = nxt
        latex.assemble(doc, sel)  # must never raise
    assert sel.sections["awards"] == ["award-main"]
    assert sel.sections["certifications"] == []


def test_assemble_omits_a_section_that_ended_up_empty():
    doc = latex.parse(REQ_CV)
    out = latex.assemble(doc, latex.Selection(sections={"certifications": []}))
    assert "CERTIFICATIONS" not in out and "\\item One" not in out and "AWARDS" in out
    assert out.count("\\begin{itemize}") == out.count("\\end{itemize}")


def test_selection_listing_only_unknown_ids_keeps_the_section():
    doc = latex.parse(REQ_CV)
    sel, problems = resolve_selection(doc, SelectionOut(entries={"certifications": ["ghost"]}))
    assert "certifications" not in sel.sections and problems


def test_duplicate_section_names_are_rejected():
    text = "% jh:section a\n% jh:item x\n• 1\n% jh:endsection\n% jh:section a\n% jh:endsection\n"
    with pytest.raises(latex.CvError, match="duplicate section names"):
        latex.parse(text)


class ScriptedLlm:
    """Returns queued payloads; an Exception in the queue is raised instead."""

    def __init__(self, *items, on_call=None):
        self.items, self.on_call, self.calls = list(items), on_call, 0

    def complete(self, *, system, prompt, schema, model):
        self.calls += 1
        if self.on_call:
            self.on_call()
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return LlmResponse(data=item, model=model)


BAD = tailor_payload(letter={"paragraphs": ["I am passionate about 99% uptime. " * 20] * 3})


def test_failed_retry_keeps_the_first_draft_flagged_for_review(setup):
    from jobhunter.llm import LlmError

    summary, _ = run_stage(
        setup, ScriptedLlm(BAD, LlmError("down"), LlmError("down"), LlmError("down"))
    )
    result = summary.results[0]
    assert not result.verified and summary.packaged == 1
    assert any("first draft kept" in p for p in result.problems)
    assert (result.path / "cv.pdf").exists()


def test_rebuild_replaces_the_folder_instead_of_mixing_old_and_new_files(setup):
    conn = setup[0]
    first, _ = run_stage(setup, FakeLlm(tailor_payload()))
    folder = first.results[0].path
    (folder / "stale.pdf").write_bytes(b"old")
    again, _ = run_stage(setup, FakeLlm(tailor_payload()), force=True)
    assert again.results[0].path == folder and not (folder / "stale.pdf").exists()
    assert not list(folder.parent.glob(".*.tmp"))
    assert conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0] == 2


def test_a_posting_marked_applied_during_tailoring_is_not_reverted_to_packaged(setup):
    conn = setup[0]

    def mark_applied_meanwhile():
        conn.execute("UPDATE jobs SET status = 'applied'")
        conn.commit()

    run_stage(setup, ScriptedLlm(tailor_payload(), on_call=mark_applied_meanwhile))
    assert conn.execute("SELECT status FROM jobs").fetchone()["status"] == "applied"


def test_stage_survives_a_broken_cv_selection_error(setup, monkeypatch):
    def boom(*args, **kwargs):
        raise latex.CvError("selection drops required entries: x")

    monkeypatch.setattr(tailoring, "_fit_cv", boom)
    summary, _ = run_stage(setup, FakeLlm(tailor_payload()))
    assert summary.packaged == 0 and "selection drops required" in summary.errors[0]


def test_verify_letter_uses_boundaries_and_ignores_everyday_words():
    doc = latex.parse(CV)
    filler = good_paragraphs()
    ok = verify_letter(
        [*filler, "I would like to express my interest and react quickly."], doc, "en"
    )
    assert ok == []
    cv_with_140 = latex.parse(CV.replace("40\\%", "140\\%"))
    assert any("40%" in p for p in verify_letter(filler, cv_with_140, "en"))
    java = verify_letter([*filler, "I know Java well."], doc, "en")
    assert any("'java'" in p for p in java)  # CV has javascript, not java


def test_translation_is_ignored_when_the_cv_changed_and_bad_units_fall_back(tmp_path):
    from jobhunter.translate import load_translation

    doc = latex.parse(CV)
    units = latex.translation_units(doc)
    units["exp-acme-1"] = ["\\item Redujo la latencia en 99\\%."]  # numbers changed
    units["exp-acme-2"] = ["\\item Construí un panel en \\textbf{TypeScript} y una API."]
    save_translation(tmp_path, "es", units, {}, doc.source_hash)
    loaded, note = load_translation(tmp_path, "es", doc)
    assert "exp-acme-2" in loaded and "exp-acme-1" not in loaded and "exp-acme-1" in note
    changed = latex.parse(CV + "\n% edited\n")
    assert load_translation(tmp_path, "es", changed)[0] is None
    (tmp_path / "translations" / "es.json").write_text("{not json")
    assert load_translation(tmp_path, "es", doc)[0] is None
    assert load_translation(tmp_path, "pt", doc)[0] is None


def test_a_posting_chosen_by_hand_is_packaged_whatever_its_status(setup):
    conn = setup[0]
    for status in ("below_threshold", "filtered", "scored", "passed"):
        conn.execute("UPDATE jobs SET status = ?", (status,))
        conn.commit()
        summary, _ = run_stage(setup, FakeLlm(tailor_payload()), job_ids=[1])
        assert summary.packaged == 1, status
        assert conn.execute("SELECT status FROM jobs").fetchone()["status"] == "packaged"
    # without an explicit id such postings are never picked up automatically
    conn.execute("UPDATE jobs SET status = 'below_threshold'")
    conn.commit()
    assert run_stage(setup, FakeLlm(tailor_payload()))[0].candidates == 0


def test_manual_packaging_never_overrides_what_the_person_recorded(setup):
    conn = setup[0]
    conn.execute("UPDATE jobs SET status = 'applied'")
    conn.commit()
    summary, _ = run_stage(setup, FakeLlm(tailor_payload()), job_ids=[1])
    assert summary.packaged == 1
    assert conn.execute("SELECT status FROM jobs").fetchone()["status"] == "applied"
