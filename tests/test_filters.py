from datetime import UTC, datetime, timedelta

import pytest

from jobhunter.config import SearchConfig
from jobhunter.filters import JobFilter, infer_seniority, to_usd
from jobhunter.models import Job

NOW = datetime(2026, 10, 9, tzinfo=UTC)


def job(**kw) -> Job:
    base = dict(
        source="greenhouse", external_id="1", company="Acme", title="Senior Backend Engineer",
        location="Remote", remote="remote", description="We use Python and AWS.", url="u",
        posted_at=NOW - timedelta(days=2),
    )  # fmt: skip
    return Job(**(base | kw))


def verdict(search: dict, j: Job, fx=None):
    return JobFilter(SearchConfig(**search), fx).evaluate(j, NOW)


def test_empty_criteria_only_applies_defaults():
    assert verdict({"work_mode": []}, job()).passed


# --- age ---------------------------------------------------------------------------------


def test_max_age_days():
    old = job(source="remotive", posted_at=NOW - timedelta(days=45))
    result = verdict({"max_age_days": 30}, old)
    assert not result.passed and result.reason.startswith("max_age_days")
    assert verdict({"max_age_days": 30}, job(posted_at=None)).passed  # unknown date passes


def test_age_limit_applies_to_aggregators_but_ats_postings_are_open_by_definition():
    old = NOW - timedelta(days=300)
    assert not verdict({"max_age_days": 30}, job(source="remotive", posted_at=old)).passed
    assert verdict({"max_age_days": 30}, job(source="greenhouse", posted_at=old)).passed
    limited = {"max_age_days": 30, "max_age_days_ats": 120}
    assert not verdict(limited, job(source="lever", posted_at=old)).passed
    assert verdict(limited, job(source="ashby", posted_at=NOW - timedelta(days=100))).passed


# --- titles ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "passed"),
    [
        ("Senior Backend Engineer", True),
        ("Backend Engineering Manager", False),  # excluded by "manager"
        ("Software Engineering Intern", False),
        ("Internal Tools Engineer", True),  # "intern" must not match inside "Internal"
        ("Data Scientist", False),  # matches none of titles_include
    ],
)
def test_titles(title, passed):
    search = {
        "titles_include": ["backend", "engineer"],
        "titles_exclude": ["intern", "manager"],
        "work_mode": [],
    }
    result = verdict(search, job(title=title))
    assert result.passed is passed
    if not passed:
        assert result.reason.split(":")[0] in {"titles_exclude", "titles_include"}


def test_title_exclude_reason_names_the_match():
    result = verdict({"titles_exclude": ["manager"]}, job(title="Project Manager"))
    assert result.reason == 'titles_exclude: title contains "Manager"'


# --- seniority ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "level"),
    [
        ("Senior Software Engineer", "senior"),
        ("Sr. Engineer", "senior"),
        ("Staff Engineer", "lead"),
        ("Principal Engineer", "lead"),
        ("Tech Lead", "lead"),
        ("Junior Developer", "junior"),
        ("Jr Developer", "junior"),
        ("Graduate Engineer", "junior"),
        ("Software Engineer", "mid"),
        ("Senior Staff Engineer", "lead"),
    ],
)
def test_infer_seniority(title, level):
    assert infer_seniority(title) == level


def test_seniority_filter():
    search = {"seniority": ["mid", "senior"], "work_mode": []}
    assert verdict(search, job(title="Senior Engineer")).passed
    assert verdict(search, job(title="Software Engineer")).passed
    assert not verdict(search, job(title="Staff Engineer")).passed
    assert not verdict(search, job(title="Junior Engineer")).passed


# --- work mode ---------------------------------------------------------------------------


def test_work_mode_and_unknown_flag():
    search = {"work_mode": ["remote"]}
    assert verdict(search, job(remote="remote")).passed
    rejected = verdict(search, job(remote="onsite"))
    assert not rejected.passed and rejected.reason.startswith("work_mode")
    unknown = verdict(search, job(remote="unknown"))
    assert unknown.passed and "unknown_mode" in unknown.flags


# --- locations ---------------------------------------------------------------------------

LOC = {"locations_allowed": ["Colombia", "LATAM", "Worldwide"], "work_mode": []}


@pytest.mark.parametrize(
    ("location", "description", "passed"),
    [
        ("Colombia", "", True),
        ("Remote - Colombia", "", True),
        ("Latin America", "", True),  # alias of LATAM
        ("Worldwide", "", True),
        ("Anywhere in the World", "", True),
        ("Remote", "", True),  # generic, no restriction
        (None, "", True),
        ("Remote - US", "", False),
        ("United States", "", False),
        ("Seattle, San Francisco", "", False),
        ("Remote", "Candidates must be located in the United States.", False),
        ("Remote", "US only. Great benefits.", False),
        ("Remote", "Must work in EU time zones", False),
        ("Remote", "Open to Colombia and the US only", True),  # snippet mentions allowed place
        ("Remote", "Contact us only through the portal", True),  # lowercase 'us' is not the US
        ("Remote", "You must work in a fast paced team", True),  # not a place name
        ("Remote", "We are a US-based startup with global team", True),
    ],
)
def test_locations(location, description, passed):
    result = verdict(LOC, job(location=location, description=description))
    assert result.passed is passed, result.reason


def test_unknown_location_is_flagged():
    result = verdict(LOC, job(location=None))
    assert result.passed and "unknown_location" in result.flags


# --- keywords ----------------------------------------------------------------------------


def test_keywords():
    inc = {"keywords_include": ["python", "go"], "work_mode": []}
    assert verdict(inc, job(description="We use Python")).passed
    assert not verdict(inc, job(description="We use Java")).passed
    assert not verdict(inc, job(description="Cargo and gopher")).passed  # word boundaries
    exc = {"keywords_exclude": ["security clearance"], "work_mode": []}
    result = verdict(exc, job(description="Requires Security Clearance"))
    assert not result.passed and result.reason.startswith("keywords_exclude")


# --- salary ------------------------------------------------------------------------------


def salary_job(low, high, cur="USD"):
    return job(salary_min=low, salary_max=high, salary_currency=cur)


def test_salary_rules():
    search = {"salary": {"min_usd": 60000}, "work_mode": []}
    assert verdict(search, salary_job(70000, 90000)).passed
    assert verdict(search, salary_job(40000, 65000)).passed  # range reaches the minimum
    low = verdict(search, salary_job(30000, 50000))
    assert not low.passed and low.reason.startswith("salary")


def test_salary_missing_policy():
    keep = verdict({"salary": {"min_usd": 60000, "on_missing": "pass"}, "work_mode": []}, job())
    assert keep.passed and "no_salary" in keep.flags
    drop = verdict({"salary": {"min_usd": 60000, "on_missing": "reject"}, "work_mode": []}, job())
    assert not drop.passed


def test_salary_currency_conversion_and_unknown_currency():
    search = {"salary": {"min_usd": 60000}, "work_mode": []}
    fx = {"EUR": 1.08}
    assert verdict(search, salary_job(60000, 70000, "EUR"), fx).passed  # 75,600 USD
    assert not verdict(search, salary_job(40000, 50000, "EUR"), fx).passed  # 54,000 USD
    unknown = verdict(search, salary_job(1, 2, "XYZ"), fx)
    assert unknown.passed and "unknown_currency" in unknown.flags


def test_salary_disabled_when_min_is_zero():
    assert verdict({"salary": {"min_usd": 0}, "work_mode": []}, salary_job(1, 2)).passed


def test_to_usd():
    assert to_usd(100, "USD", {}) == 100
    assert to_usd(100, None, {}) == 100
    assert to_usd(100, "EUR", {"EUR": 1.1}) == pytest.approx(110)
    assert to_usd(100, "XYZ", {}) is None


# --- order and determinism ---------------------------------------------------------------


def test_first_failing_rule_wins_and_result_is_deterministic():
    search = {"titles_exclude": ["manager"], "work_mode": ["onsite"]}
    j = job(title="Engineering Manager")  # also fails work_mode, but title comes first
    first, second = verdict(search, j), verdict(search, j)
    assert first == second
    assert first.reason.startswith("titles_exclude")


# --- acronym tokens (US, UK) ---------------------------------------------------------------

ENGLISH = {
    "locations_allowed": ["Colombia", "US", "UK", "Canada", "Ireland"],
    "work_mode": [],
}


@pytest.mark.parametrize(
    ("location", "description", "passed"),
    [
        ("Remote - US", "", True),
        ("Remote - U.S.", "", True),
        ("United Kingdom", "", True),
        ("Remote - Canada", "", True),
        ("Remote - Germany", "", False),
        ("Remote", "Contact us through the portal", True),
        ("Remote", "Must be located in Germany", False),  # 'us' inside words is not a match
        ("Remote", "Must be located in the US", True),  # US is allowed
        ("Remote - EMEA", "", False),
        ("Remote - Australia", "", False),
    ],
)
def test_acronym_tokens_are_case_sensitive(location, description, passed):
    result = verdict(ENGLISH, job(location=location, description=description))
    assert result.passed is passed, result.reason


def test_lowercase_us_in_text_is_not_an_allowed_place():
    # "Remote - us" must not match the acronym token "US"
    assert not verdict(ENGLISH, job(location="Remote - germany us")).passed
