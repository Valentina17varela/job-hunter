import json

import httpx
import pytest

from jobhunter import fetch_url, postings
from jobhunter.config import SearchConfig
from jobhunter.db import connect
from jobhunter.filters import JobFilter
from jobhunter.models import Job
from jobhunter.store import mark_duplicates, upsert_jobs

GOOD = {"title": "Backend Engineer", "company": "Acme", "description": "Build APIs in Python."}


def public(host, port, **_):
    return [(2, 1, 6, "", ("93.184.216.34", port))]


def resolver_for(ip):
    return lambda host, port, **_: [(2, 1, 6, "", (ip, port))]


def ok_transport(html="<html><title>Hi</title></html>", ctype="text/html"):
    return httpx.MockTransport(
        lambda req: httpx.Response(200, headers={"content-type": ctype}, text=html)
    )


# --- normalization / validation ------------------------------------------------------------


def test_normalize_url_drops_tracking_and_noise():
    a = postings.normalize_url("HTTPS://Acme.com:443/jobs/1/?utm_source=x&id=7#frag")
    assert a == postings.normalize_url("https://acme.com/jobs/1?id=7")


def test_external_id_is_stable_for_same_url():
    one = postings.manual_external_id("https://a.com/j?utm_x=1", "T", "C", "d")
    two = postings.manual_external_id("https://a.com/j", "Other", "C", "other")
    assert one == two


@pytest.mark.parametrize(
    "patch",
    [
        {"title": ""},
        {"company": "  "},
        {"description": ""},
        {"url": "javascript:alert(1)"},
        {"remote": "somewhere"},
        {"salary_min": 200, "salary_max": 100},
        {"salary_min": 100, "salary_currency": "dollars"},
    ],
)
def test_validation_errors(patch):
    with pytest.raises(postings.PostingError):
        postings.validate_manual({**GOOD, **patch})


def test_validation_accepts_blank_optional_fields():
    job = postings.validate_manual({**GOOD, "url": "", "salary_min": "", "location": ""})
    assert job.source == "manual" and job.salary_min is None


# --- storage -------------------------------------------------------------------------------


def test_add_manual_is_passed_and_deduped(tmp_path):
    conn = connect(tmp_path / "t.db")
    jid, created = postings.add_manual(conn, {**GOOD, "url": "https://acme.com/j/1"})
    again, created2 = postings.add_manual(conn, {**GOOD, "url": "https://acme.com/j/1?utm_a=b"})
    assert created and not created2 and jid == again
    row = conn.execute("SELECT status, filter_flags FROM jobs WHERE id=?", (jid,)).fetchone()
    assert row["status"] == "passed" and row["filter_flags"] == "manual"


def test_manual_posting_skips_filter_and_duplicate_marking(tmp_path):
    conn = connect(tmp_path / "t.db")
    other = Job(
        source="greenhouse", external_id="1", company="Acme", title="Backend Engineer",
        description="x", url="https://a/1",
    )  # fmt: skip
    upsert_jobs(conn, [other])
    jid, _ = postings.add_manual(conn, GOOD)
    mark_duplicates(conn)
    status = conn.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()["status"]
    assert status == "passed"
    job = postings.validate_manual({**GOOD, "title": "Sales Intern"})
    result = JobFilter(SearchConfig(titles_include=["engineer"])).evaluate(job)
    assert result.passed and result.flags == ["manual"]


# --- fetch_url -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://a.com/x",
        "http://user:pw@a.com/",
        "http://a.com:22/",
        "http:///x",
    ],
)
def test_fetch_rejects_bad_urls(url):
    with pytest.raises(fetch_url.FetchPageError):
        fetch_url.fetch_page(url, resolver=public, transport=ok_transport())


@pytest.mark.parametrize(
    "ip", ["127.0.0.1", "::1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::ffff:127.0.0.1"]
)
def test_fetch_rejects_private_addresses(ip):
    with pytest.raises(fetch_url.FetchPageError):
        fetch_url.fetch_page("https://x.com/", resolver=resolver_for(ip), transport=ok_transport())


def test_fetch_rejects_ip_literal_and_mixed_resolution():
    with pytest.raises(fetch_url.FetchPageError):
        fetch_url.fetch_page("http://127.0.0.1/", resolver=public, transport=ok_transport())

    def mixed(host, port, **_):
        return [(2, 1, 6, "", ("93.184.216.34", port)), (2, 1, 6, "", ("10.0.0.1", port))]

    with pytest.raises(fetch_url.FetchPageError):
        fetch_url.fetch_page("https://x.com/", resolver=mixed, transport=ok_transport())


def test_fetch_revalidates_redirects():
    def handler(req):
        return httpx.Response(302, headers={"location": "http://localhost:8080/admin"})

    def resolver(host, port, **_):
        return [(2, 1, 6, "", ("93.184.216.34" if host == "x.com" else "127.0.0.1", port))]

    with pytest.raises(fetch_url.FetchPageError):
        fetch_url.fetch_page(
            "https://x.com/", resolver=resolver, transport=httpx.MockTransport(handler)
        )


def test_fetch_limits_and_types():
    with pytest.raises(fetch_url.FetchPageError, match="large"):
        fetch_url.fetch_page(
            "https://x.com/", resolver=public, transport=ok_transport("a" * 500), max_bytes=100
        )
    with pytest.raises(fetch_url.FetchPageError, match="not a web page"):
        fetch_url.fetch_page(
            "https://x.com/", resolver=public, transport=ok_transport("%PDF", "application/pdf")
        )
    page = fetch_url.fetch_page("https://x.com/a?b=1", resolver=public, transport=ok_transport())
    assert "Hi" in page.html


def test_extract_json_ld():
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "JobPosting",
                "title": "Platform Engineer",
                "hiringOrganization": {"name": "Globex"},
                "jobLocationType": "TELECOMMUTE",
                "description": "<p>Run <b>things</b></p>",
                "baseSalary": {
                    "currency": "USD",
                    "value": {"minValue": 100000, "maxValue": 140000, "unitText": "YEAR"},
                },
            }
        ],
    }
    html = f'<html><script type="application/ld+json">{json.dumps(ld)}</script></html>'
    got = fetch_url.extract_posting(html, "https://globex.com/j")
    assert got["title"] == "Platform Engineer" and got["company"] == "Globex"
    assert got["remote"] == "remote" and got["salary_min"] == 100000
    assert "Run" in got["description"] and "<" not in got["description"]


def test_extract_falls_back_to_title_and_handles_empty():
    got = fetch_url.extract_posting("<html><title>Dev at Foo</title><body>Hello</body></html>", "u")
    assert got["title"] and "Hello" in got["description"]
    assert fetch_url.extract_posting("", "https://a.com/")["title"] in ("", None)
