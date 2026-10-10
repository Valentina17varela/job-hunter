import asyncio

import httpx
import respx

from jobhunter.http import HttpClient
from jobhunter.sources import aggregators as agg
from jobhunter.sources import ashby, greenhouse, lever
from jobhunter.sources.ashby import AshbySource
from jobhunter.sources.greenhouse import GreenhouseSource
from jobhunter.sources.lever import LeverSource


def fetch(source):
    async def go():
        async with HttpClient(backoff=0) as http:
            return await source.fetch(http)

    return asyncio.run(go())


def assert_valid(jobs, source, count=3):
    assert len(jobs) == count
    for job in jobs:
        assert job.source == source
        assert job.external_id and job.title and job.company and job.url.startswith("http")
        assert job.description
        assert job.content_hash


# --- ATS --------------------------------------------------------------------------------


def test_greenhouse_parse(fixture_json):
    jobs = greenhouse.parse(fixture_json("greenhouse.json"), "Stripe")
    assert_valid(jobs, "greenhouse")
    assert "<" not in jobs[0].description and "&lt;" not in jobs[0].description
    assert jobs[0].posted_at is not None


def test_lever_parse(fixture_json):
    jobs = lever.parse(fixture_json("lever.json"), "Palantir")
    assert_valid(jobs, "lever")
    assert jobs[0].remote == "hybrid"
    assert "\xa0" not in jobs[0].description


def test_lever_salary_range_is_annualized():
    raw = {
        "id": "x", "text": "Eng", "hostedUrl": "https://jobs.lever.co/a/x",
        "categories": {"location": "Remote"}, "workplaceType": "remote",
        "descriptionPlain": "desc", "salaryRange": {"min": 50, "max": 70, "currency": "USD",
        "interval": "per-hour-wage"},
    }  # fmt: skip
    (job,) = lever.parse([raw], "Acme")
    assert (job.salary_min, job.salary_max, job.salary_currency) == (104000, 145600, "USD")
    assert job.remote == "remote"


def test_ashby_parse(fixture_json):
    jobs = ashby.parse(fixture_json("ashby.json"), "Linear")
    assert_valid(jobs, "ashby")
    assert jobs[0].remote == "remote"


def test_ashby_compensation_and_unlisted():
    base = {
        "title": "Eng", "location": "Remote", "workplaceType": "Remote", "isRemote": True,
        "jobUrl": "https://jobs.ashbyhq.com/a/1", "descriptionPlain": "desc",
        "publishedAt": "2026-01-01T00:00:00.000+00:00",
    }  # fmt: skip
    comp = {"compensationTiers": [{"components": [
        {"compensationType": "EquityPercentage", "minValue": None, "maxValue": None},
        {"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD",
         "minValue": 211400, "maxValue": 290600},
    ]}]}  # fmt: skip
    data = {"jobs": [
        {**base, "id": "1", "compensation": comp},
        {**base, "id": "2", "isListed": False},
    ]}  # fmt: skip
    jobs = ashby.parse(data, "Acme")
    assert [j.external_id for j in jobs] == ["1"]
    assert (jobs[0].salary_min, jobs[0].salary_max, jobs[0].salary_currency) == (
        211400, 290600, "USD",
    )  # fmt: skip


def test_malformed_item_is_skipped_not_fatal(fixture_json):
    data = fixture_json("greenhouse.json")
    data["jobs"].insert(1, {"id": 1})  # missing title/absolute_url
    assert len(greenhouse.parse(data, "Stripe")) == 3


@respx.mock
def test_ats_fetch_calls_expected_endpoints(fixture_json):
    gh = respx.get("https://boards-api.greenhouse.io/v1/boards/stripe/jobs").mock(
        return_value=httpx.Response(200, json=fixture_json("greenhouse.json"))
    )
    lv = respx.get("https://api.lever.co/v0/postings/palantir").mock(
        return_value=httpx.Response(200, json=fixture_json("lever.json"))
    )
    ab = respx.get("https://api.ashbyhq.com/posting-api/job-board/linear").mock(
        return_value=httpx.Response(200, json=fixture_json("ashby.json"))
    )
    assert len(fetch(GreenhouseSource("Stripe", "stripe"))) == 3
    assert len(fetch(LeverSource("Palantir", "palantir"))) == 3
    assert len(fetch(AshbySource("Linear", "linear"))) == 3
    assert gh.calls.last.request.url.params["content"] == "true"
    assert lv.calls.last.request.url.params["mode"] == "json"
    assert ab.calls.last.request.url.params["includeCompensation"] == "true"


# --- Aggregators ------------------------------------------------------------------------


def test_remotive_parse(fixture_json):
    jobs = agg.parse_remotive(fixture_json("remotive.json"))
    assert_valid(jobs, "remotive")
    assert all(j.remote == "remote" for j in jobs)


def test_remoteok_parse_skips_legal_notice_and_fixes_encoding(fixture_json):
    jobs = agg.parse_remoteok(fixture_json("remoteok.json"))
    assert_valid(jobs, "remoteok")
    assert "Ã" not in jobs[0].title
    assert "Please mention the word" not in jobs[0].description


def test_remoteok_tracking_tag_does_not_change_hash():
    def raw(tag):
        return {
            "id": "1", "company": "A", "position": "Eng", "url": "https://remoteok.com/x",
            "description": f"<p>Real text</p><p>Please mention the word **WORD** and tag {tag} "
            f"when applying to show you read the job post completely (#{tag}).</p>",
        }  # fmt: skip

    (a,) = agg.parse_remoteok([raw("AAA=")])
    (b,) = agg.parse_remoteok([raw("BBB=")])
    assert a.content_hash == b.content_hash
    assert a.description == "Real text"


def test_wwr_parse(fixture_text):
    jobs = agg.parse_wwr(fixture_text("wwr.rss"))
    assert_valid(jobs, "weworkremotely")
    assert jobs[0].company == "Wisevu"
    assert jobs[0].title == "Web Development Project Manager"
    assert jobs[0].location == "Anywhere in the World"
    assert jobs[0].posted_at is not None


def test_wwr_invalid_xml_raises():
    import pytest

    with pytest.raises(ValueError, match="Invalid RSS"):
        agg.parse_wwr("<rss><not closed")


def test_arbeitnow_parse(fixture_json):
    assert_valid(agg.parse_arbeitnow(fixture_json("arbeitnow.json")), "arbeitnow")


def test_jobicy_parse_with_salary(fixture_json):
    jobs = agg.parse_jobicy(fixture_json("jobicy.json"))
    assert_valid(jobs, "jobicy")
    assert (jobs[0].salary_min, jobs[0].salary_max, jobs[0].salary_currency) == (
        120000, 145000, "USD",
    )  # fmt: skip


@respx.mock
def test_arbeitnow_paginates_and_stops_on_empty(fixture_json):
    page1 = fixture_json("arbeitnow.json")
    route = respx.get("https://www.arbeitnow.com/api/job-board-api").mock(
        side_effect=[httpx.Response(200, json=page1), httpx.Response(200, json={"data": []})]
    )
    assert len(fetch(agg.ArbeitnowSource(pages=3))) == 3
    assert route.call_count == 2


@respx.mock
def test_aggregator_fetch_endpoints(fixture_json, fixture_text):
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=fixture_json("remotive.json"))
    )
    respx.get("https://remoteok.com/api").mock(
        return_value=httpx.Response(200, json=fixture_json("remoteok.json"))
    )
    respx.get("https://jobicy.com/api/v2/remote-jobs").mock(
        return_value=httpx.Response(200, json=fixture_json("jobicy.json"))
    )
    respx.get("https://weworkremotely.com/categories/remote-programming-jobs.rss").mock(
        return_value=httpx.Response(200, text=fixture_text("wwr.rss"))
    )
    assert len(fetch(agg.RemotiveSource())) == 3
    assert len(fetch(agg.RemoteOkSource())) == 3
    assert len(fetch(agg.JobicySource())) == 3
    assert len(fetch(agg.WeWorkRemotelySource("remote-programming-jobs"))) == 3
