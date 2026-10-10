import pytest

from jobhunter.text import (
    annualize,
    extract_salary,
    fix_mojibake,
    html_to_text,
    infer_remote,
    normalize_text,
)


def test_html_to_text_blocks_lists_and_entities():
    html = (
        "<h2>Role</h2><p>Build &amp; ship</p>"
        "<ul><li>Python</li><li>SQL</li></ul><script>x()</script>"
    )
    assert html_to_text(html) == "Role\n\nBuild & ship\n\n- Python\n- SQL"


def test_html_to_text_empty():
    assert html_to_text(None) == ""
    assert html_to_text("") == ""


def test_normalize_text_nbsp_and_blank_lines():
    assert normalize_text("a\xa0b\n\n\n\nc  d") == "a b\n\nc d"


@pytest.mark.parametrize(
    ("location", "title", "expected"),
    [
        ("Remote - US", "Engineer", "remote"),
        ("Anywhere in the World", "Engineer", "remote"),
        ("Hybrid - London", "Engineer", "hybrid"),
        ("Seattle, WA", "Engineer", "onsite"),
        (None, None, "unknown"),
        (None, "Remote Engineer", "remote"),
    ],
)
def test_infer_remote(location, title, expected):
    assert infer_remote(location, title) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Salary: $120,000 - $150,000 per year", (120000, 150000, "USD")),
        ("Pay $120k-$150k", (120000, 150000, "USD")),
        ("€70.000 – €90.000", (70000, 90000, "EUR")),
        ("£60k to £80k", (60000, 80000, "GBP")),
        ("$50 - $70 per hour", (104000, 145600, "USD")),
        ("$8,000 - $10,000 per month", (96000, 120000, "USD")),
        ("2-5 years of experience", None),
        ("$5 - $7 coffee budget", None),
        ("no salary here", None),
        (None, None),
    ],
)
def test_extract_salary(text, expected):
    assert extract_salary(text) == expected


def test_annualize():
    assert annualize(50, "hour") == 104000
    assert annualize(5000, "1 MONTH") == 60000
    assert annualize(100000, "1 YEAR") == 100000
    assert annualize(100000, None) == 100000


def test_fix_mojibake():
    assert fix_mojibake("fÃ¼r") == "für"
    assert fix_mojibake("plain ascii") == "plain ascii"
    assert fix_mojibake("já correto") == "já correto"  # already-correct text is left alone
    assert fix_mojibake(None) is None
