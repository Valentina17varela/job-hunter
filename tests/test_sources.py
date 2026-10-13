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


# --- The Muse ---------------------------------------------------------------------------

MUSE = "https://www.themuse.com/api/public/jobs"


def muse_page(fixture_json, page, page_count, remaining="499"):
    data = fixture_json("themuse.json")
    data["page"], data["page_count"] = page, page_count
    return httpx.Response(200, json=data, headers={"x-ratelimit-remaining": remaining})


def test_themuse_parse_maps_remote_location_company_and_link(fixture_json):
    from jobhunter.sources import themuse

    jobs = themuse.parse(fixture_json("themuse.json"))
    assert len(jobs) == 4  # the malformed item (no company) is skipped, not fatal
    first = jobs[0]
    assert first.source == "themuse" and first.remote == "remote"
    assert first.location == "Flexible / Remote; Mexico City, Mexico"
    assert first.url.startswith("https://www.themuse.com/jobs/")
    assert first.posted_at is not None and first.company and first.description
    assert all(j.remote == "remote" for j in jobs)  # every fixture item lists Flexible / Remote
    assert_valid(jobs, "themuse", count=4)


@respx.mock
def test_themuse_walks_pages_with_the_configured_filters(fixture_json, monkeypatch):
    from jobhunter.sources.themuse import TheMuseSource

    monkeypatch.delenv("THEMUSE_API_KEY", raising=False)
    route = respx.get(MUSE).mock(
        side_effect=[muse_page(fixture_json, 1, 2), muse_page(fixture_json, 2, 2)]
    )
    source = TheMuseSource(
        "Software Engineering", ["Mid Level", "Senior Level"], ["Flexible / Remote"]
    )
    jobs = fetch(source)
    assert len(jobs) == 8 and source.note is None
    first = route.calls[0].request.url.params
    assert first["category"] == "Software Engineering" and first["page"] == "1"
    assert first.get_list("level") == ["Mid Level", "Senior Level"]
    assert first.get_list("location") == ["Flexible / Remote"]
    assert "api_key" not in first and route.calls[1].request.url.params["page"] == "2"


@respx.mock
def test_themuse_stops_at_max_pages_and_says_so(fixture_json):
    from jobhunter.sources.themuse import TheMuseSource

    respx.get(MUSE).mock(side_effect=lambda r: muse_page(fixture_json, 1, 50))
    source = TheMuseSource("Software Engineering", [], [], max_pages=3)
    assert len(fetch(source)) == 12
    assert "max_pages=3" in source.note


@respx.mock
def test_themuse_stops_cleanly_when_the_rate_limit_is_nearly_used_up(fixture_json):
    from jobhunter.sources.themuse import TheMuseSource

    route = respx.get(MUSE).mock(
        side_effect=[muse_page(fixture_json, 1, 5, remaining="500"),
                     muse_page(fixture_json, 2, 5, remaining="12"),
                     muse_page(fixture_json, 3, 5, remaining="11")]
    )  # fmt: skip
    source = TheMuseSource("Software Engineering", [], [])
    jobs = fetch(source)
    assert len(jobs) == 8 and route.call_count == 2  # nothing lost, no further requests
    assert "12 requests" in source.note and "next run" in source.note


@respx.mock
def test_themuse_key_is_optional_and_never_leaks(fixture_json, monkeypatch):
    from jobhunter.http import FetchError
    from jobhunter.sources.themuse import TheMuseSource

    monkeypatch.setenv("THEMUSE_API_KEY", "secret-muse-key-123")
    route = respx.get(MUSE).mock(return_value=httpx.Response(401))
    try:
        fetch(TheMuseSource("Software Engineering", [], []))
        raise AssertionError("expected a FetchError")
    except FetchError as exc:
        assert "secret-muse-key-123" not in str(exc)
    assert route.calls[0].request.url.params["api_key"] == "secret-muse-key-123"


def test_redact_removes_query_credentials_and_env_values(monkeypatch):
    from jobhunter.http import redact

    monkeypatch.setenv("THEMUSE_API_KEY", "abcd1234efgh")
    text = "GET https://x.test/a?page=1&api_key=SECRET&app_id=1&app_key=2 failed: abcd1234efgh"
    out = redact(text)
    assert "SECRET" not in out and "abcd1234efgh" not in out and "page=1" in out
    assert "app_id=***" in out and "app_key=***" in out


# --- Get on Board -----------------------------------------------------------------------

GOB = "https://www.getonbrd.com/api/v0/categories/programming/jobs"


def test_getonboard_parse_maps_mode_location_salary_and_link(fixture_json):
    from jobhunter.sources import getonboard

    jobs = getonboard.parse(fixture_json("getonboard.json"))
    assert len(jobs) == 4  # the item without a company is skipped, not fatal
    assert_valid(jobs, "getonboard", count=4)
    by_title = {j.title: j for j in jobs}
    hybrid = by_title["Developer Java"]
    assert hybrid.remote == "hybrid" and hybrid.location == "Chile" and hybrid.salary_min is None
    assert hybrid.url.startswith("https://www.getonbrd.com/jobs/")
    assert hybrid.posted_at is not None
    remote = by_title["Back-end Software Engineer"]
    assert remote.remote == "remote" and remote.location == "Remote"
    # monthly USD is annualized (4000-6500 a month)
    assert (remote.salary_min, remote.salary_max, remote.salary_currency) == (48000, 78000, "USD")
    local = by_title["Product Builder"]
    assert local.remote == "remote" and "specific countries" in local.location
    assert "Developer" in hybrid.description  # headline + sections are joined


@respx.mock
def test_getonboard_walks_pages_and_reports_the_cap(fixture_json):
    from jobhunter.sources.getonboard import GetOnBoardSource

    def page(n, total):
        data = fixture_json("getonboard.json")
        data["meta"] = {"page": n, "per_page": 100, "total_pages": total}
        return httpx.Response(200, json=data)

    route = respx.get(GOB).mock(side_effect=[page(1, 5), page(2, 5)])
    source = GetOnBoardSource("programming", max_pages=2)
    assert len(fetch(source)) == 8 and route.call_count == 2
    params = route.calls[0].request.url.params
    assert params["per_page"] == "100" and params["page"] == "1" and "company" in params["expand"]
    assert "max_pages=2 of 5" in source.note


# --- Himalayas --------------------------------------------------------------------------

HIM = "https://himalayas.app/jobs/api/search"


def test_himalayas_parse_maps_worldwide_salary_period_and_skips_the_broken(fixture_json):
    from jobhunter.sources import himalayas

    data = fixture_json("himalayas.json")
    for job in data["jobs"]:
        job.pop("expiryDate", None)  # the recorded postings may have expired by now
    jobs = himalayas.parse(data)
    assert len(jobs) == 4  # the item without a company and link is skipped
    assert_valid(jobs, "himalayas", count=4)
    by_title = {j.title: j for j in jobs}
    assert all(j.remote == "remote" for j in jobs)
    worldwide = by_title["Senior Software Engineer"]
    assert worldwide.location == "Worldwide" and worldwide.salary_min is None
    hourly = by_title["CFD Engineer - AI Trainer"]
    assert hourly.salary_min == 50 * 2080 and hourly.salary_currency == "USD"  # hourly annualized
    annual = by_title["AI Innovation Engineer"]
    assert (annual.salary_min, annual.salary_max) == (135000, 210000)
    assert by_title["People Team Business Partner (East Coast)"].location == "United States"


def test_himalayas_drops_expired_postings_and_salary_without_currency():
    from jobhunter.sources import himalayas

    base = {"title": "T", "companyName": "C", "guid": "https://himalayas.app/x", "description": "d"}
    expired = {**base, "guid": "https://himalayas.app/y", "expiryDate": 1}
    no_currency = {**base, "minSalary": 100, "maxSalary": 200, "salaryPeriod": "annual"}
    jobs = himalayas.parse({"jobs": [expired, no_currency]})
    assert len(jobs) == 1 and jobs[0].salary_min is None


@respx.mock
def test_himalayas_searches_each_seniority_separately_and_dedupes(fixture_json):
    from jobhunter.sources.himalayas import HimalayasSource

    data = fixture_json("himalayas.json")
    for job in data["jobs"]:
        job.pop("expiryDate", None)
    empty = {"jobs": []}

    def answer(request):
        page = request.url.params["page"]
        return httpx.Response(200, json=data if page == "1" else empty)

    route = respx.get(HIM).mock(side_effect=answer)
    source = HimalayasSource("backend engineer", ["Mid-level", "Senior"], max_pages=3)
    jobs = fetch(source)
    assert len(jobs) == 4  # the same postings under both levels are stored once
    levels = [c.request.url.params.get("seniority") for c in route.calls]
    assert levels == ["Mid-level", "Mid-level", "Senior", "Senior"]  # stops at the empty page
    first = route.calls[0].request.url.params
    assert first["q"] == "backend engineer" and first["sort"] == "recent"
