from pathlib import Path

import pytest

from jobhunter import latex
from jobhunter.latex import CvError, Selection, assemble, digest, parse, propose_markers, to_plain

SOURCE = (Path(__file__).parent / "fixtures" / "master_marked.tex").read_text()


def test_parse_structure_and_ids():
    doc = parse(SOURCE)
    assert [s.name for s in doc.sections] == ["summary", "experience"]
    assert doc.ids() == [
        "summary-1", "exp-acme", "exp-acme-1", "exp-acme-2", "exp-acme-3", "exp-beta", "exp-beta-1",
    ]  # fmt: skip
    acme = doc.sections[1].children[0]
    assert acme.required and acme.items[0].tags == ["python", "aws"]


def strip_markers(text: str) -> str:
    return "".join(ln for ln in text.splitlines(keepends=True) if not latex.MARKER_RE.match(ln))


def test_assemble_without_selection_gives_the_source_minus_markers():
    assert assemble(parse(SOURCE)) == strip_markers(SOURCE)


def test_assemble_selects_reorders_and_keeps_text_verbatim():
    doc = parse(SOURCE)
    selection = Selection(
        sections={"experience": ["exp-acme"]},
        items={"exp-acme": ["exp-acme-2", "exp-acme-1"]},
    )
    out = assemble(doc, selection)
    assert "Beta" not in out and "Mentored" not in out
    assert out.index("TypeScript") < out.index("Cut order latency")
    assert "\\item Built a \\textbf{TypeScript} dashboard & API." in out  # original LaTeX
    assert "Jane Doe" in out and "\\section{Education}" in out  # unmarked text untouched
    assert out.count("\\begin{itemize}") == 1 and out.count("\\end{itemize}") == 1


def test_required_entries_cannot_be_dropped():
    with pytest.raises(CvError, match="required"):
        assemble(parse(SOURCE), Selection(sections={"experience": ["exp-beta"]}))


def test_unknown_ids_are_rejected():
    with pytest.raises(CvError, match="unknown ids"):
        assemble(parse(SOURCE), Selection(items={"exp-acme": ["nope"]}))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("% jh:item a\n\\item x\n", "outside a section"),
        ("% jh:section s\n\\section{S}\n", "endsection"),
        ("% jh:section s\n% jh:entry e\n", "endentry"),
        (
            "% jh:section s\n% jh:item a\n\\item x\n% jh:item a\n\\item y\n% jh:endsection\n",
            "duplicate",
        ),
        ("% jh:section\n", "needs a name"),
        ("% jh:section s\n% jh:item\n% jh:endsection\n", "needs an id"),
    ],
)
def test_malformed_markers(text, message):
    with pytest.raises(CvError, match=message):
        parse(text)


def test_to_plain_strips_latex():
    assert to_plain(r"Cut latency by 40\% with \textbf{Python} \& \href{http://x}{AWS}.") == (
        "Cut latency by 40% with Python & AWS."
    )
    assert to_plain("a -- b % comment\nc") == "a – b c"


def test_digest_lists_ids_and_plain_text_but_never_the_preamble():
    text = digest(parse(SOURCE))
    assert "[exp-acme-1] Cut order latency by 40% using Python and AWS." in text
    assert "### [exp-acme] Senior Engineer, Acme 2022–Present" in text
    assert "itemize" not in text
    assert "Jane Doe" not in text and "jane@example.com" not in text and "Education" not in text


def test_sensitive_warnings_only_look_at_marked_text():
    assert latex.sensitive_warnings(parse(SOURCE)) == []
    leaky = SOURCE.replace("Mentored 4 engineers.", "Call me at +57 300 123 4567 or a@b.co")
    warnings = latex.sensitive_warnings(parse(leaky))
    assert any("phone number" in w for w in warnings) and any("email" in w for w in warnings)


def test_propose_markers_marks_sections_and_bullets_and_result_parses():
    plain = (
        "\\documentclass{article}\n\\begin{document}\nName\n"
        "\\section{Work Experience}\n\\begin{itemize}\n\\item One\n\\item Two\n\\end{itemize}\n"
        "\\section{Skills}\n\\begin{itemize}\n\\item Python\n\\end{itemize}\n\\end{document}\n"
    )
    marked = propose_markers(plain)
    doc = parse(marked)
    assert [s.name for s in doc.sections] == ["work-experience", "skills"]
    assert doc.ids() == ["work-experience-1", "work-experience-2", "skills-1"]
    assert assemble(doc) == plain  # markers are the only difference from the original


BULLETS = """\
% jh:section work
\\section*{WORK}
% jh:entry job required
\\noindent
\\textbf{Engineer, Acme} \\\\
% jh:item job-1
• Cut latency
  by 40\\% \\\\
% jh:item job-2
• Built an API \\\\
% jh:endentry
% jh:endsection
"""


def test_plain_text_bullets_span_lines_and_end_at_markers_or_blank_lines():
    doc = parse(BULLETS)
    entry = doc.sections[0].children[0]
    assert [latex.item_text(i) for i in entry.items] == ["Cut latency by 40%", "Built an API"]
    out = assemble(doc, Selection(items={"job": ["job-2"]}))
    assert "Built an API" in out and "Cut latency" not in out and "\\noindent" in out


def test_blank_line_ends_an_item():
    text = "% jh:section s\n% jh:item a\n• one\n\n• not part of a\n% jh:endsection\n"
    section = parse(text).sections[0]
    assert section.children[0].lines == ["• one"]
    assert section.suffix == ["", "• not part of a"]  # after the last item: kept as section text


def test_to_plain_drops_line_break_spacing_arguments():
    assert to_plain(r"\textbf{Databases: } Postgres \\[2pt]") == "Databases: Postgres"


def test_escape_makes_plain_text_safe_and_handles_typographic_dashes():
    assert latex.escape("R&D 50% $5 #1 a_b {x} ~ ^ \\") == (
        r"R\&D 50\% \$5 \#1 a\_b \{x\} \textasciitilde{} \textasciicircum{} \textbackslash{}"
    )
    assert latex.escape("Application — Senior “API” engineer – remote…") == (
        "Application --- Senior ``API'' engineer -- remote\\ldots{}"
    )
