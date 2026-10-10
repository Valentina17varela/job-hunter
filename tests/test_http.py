import asyncio

import httpx
import pytest
import respx

from jobhunter.http import USER_AGENT, FetchError, HttpClient

URL = "https://example.test/api"


def run(coro):
    return asyncio.run(coro)


@respx.mock
def test_get_json_sends_user_agent():
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"a": 1}))

    async def go():
        async with HttpClient(backoff=0) as http:
            return await http.get_json(URL)

    assert run(go()) == {"a": 1}
    assert route.calls.last.request.headers["user-agent"] == USER_AGENT


@respx.mock
def test_404_is_not_retried():
    route = respx.get(URL).mock(return_value=httpx.Response(404))

    async def go():
        async with HttpClient(backoff=0) as http:
            await http.get(URL)

    with pytest.raises(FetchError) as exc:
        run(go())
    assert exc.value.status == 404
    assert route.call_count == 1


@respx.mock
def test_5xx_is_retried_then_succeeds():
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(429), httpx.Response(200, json={"ok": 1})]
    )

    async def go():
        async with HttpClient(backoff=0) as http:
            return await http.get_json(URL)

    assert run(go()) == {"ok": 1}
    assert route.call_count == 3


@respx.mock
def test_gives_up_after_retries():
    route = respx.get(URL).mock(return_value=httpx.Response(500))

    async def go():
        async with HttpClient(backoff=0, retries=2) as http:
            await http.get(URL)

    with pytest.raises(FetchError, match="after 2 attempts"):
        run(go())
    assert route.call_count == 2


@respx.mock
def test_network_error_is_retried():
    respx.get(URL).mock(side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json=[])])

    async def go():
        async with HttpClient(backoff=0) as http:
            return await http.get_json(URL)

    assert run(go()) == []


@respx.mock
def test_invalid_json_raises_fetch_error():
    respx.get(URL).mock(return_value=httpx.Response(200, text="<html>nope"))

    async def go():
        async with HttpClient(backoff=0) as http:
            await http.get_json(URL)

    with pytest.raises(FetchError, match="Invalid JSON"):
        run(go())
