import asyncio

import httpx
import pytest
import respx

from jobhunter.db import connect
from jobhunter.http import HttpClient
from jobhunter.pipeline import fetch_stage
from jobhunter.sources.aggregators import RemotiveSource
from jobhunter.sources.greenhouse import GreenhouseSource
from jobhunter.sources.lever import LeverSource


@pytest.fixture
def conn(tmp_path):
    return connect(tmp_path / "t.db")


def run_fetch(conn, sources):
    async def go():
        async with HttpClient(backoff=0) as http:
            return await fetch_stage(conn, sources, http)

    return asyncio.run(go())


@respx.mock
def test_failing_source_does_not_stop_others_and_is_logged(conn, fixture_json):
    respx.get("https://boards-api.greenhouse.io/v1/boards/gone/jobs").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=fixture_json("remotive.json"))
    )
    respx.get("https://api.lever.co/v0/postings/palantir").mock(
        return_value=httpx.Response(200, json=fixture_json("lever.json"))
    )
    summary = run_fetch(
        conn,
        [GreenhouseSource("Gone", "gone"), RemotiveSource(), LeverSource("Palantir", "palantir")],
    )
    assert (summary.sources_ok, summary.sources_failed) == (2, 1)
    assert summary.upsert.new == 6
    logs = {
        (r["source"], r["target"], r["status"])
        for r in conn.execute("SELECT * FROM fetch_log").fetchall()
    }
    assert ("greenhouse", "gone", "error") in logs
    assert ("remotive", "", "ok") in logs
    error = conn.execute("SELECT error FROM fetch_log WHERE status='error'").fetchone()[0]
    assert "404" in error


@respx.mock
def test_rerun_creates_no_duplicates(conn, fixture_json):
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=fixture_json("remotive.json"))
    )
    first = run_fetch(conn, [RemotiveSource()])
    second = run_fetch(conn, [RemotiveSource()])
    assert first.upsert.new == 3
    assert (second.upsert.new, second.upsert.unchanged) == (0, 3)
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 3


@respx.mock
def test_same_posting_twice_in_one_feed_counts_once(conn, fixture_json):
    data = fixture_json("remotive.json")
    data["jobs"].append({**data["jobs"][0], "description": "different text"})
    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=data)
    )
    summary = run_fetch(conn, [RemotiveSource()])
    assert summary.upsert.new == 3
    assert summary.upsert.updated == 0
