"""Polite async HTTP client: identifiable UA, timeouts, retries and concurrency limits."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from types import TracebackType
from typing import Any
from urllib.parse import urlparse

import httpx

USER_AGENT = "jobhunter/0.1 (personal use)"


class FetchError(Exception):
    """A request failed permanently (after retries where applicable)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class HttpClient:
    def __init__(
        self,
        *,
        timeout: float = 15.0,
        retries: int = 3,
        backoff: float = 0.5,
        max_concurrency: int = 5,
        max_per_host: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )
        self._retries = retries
        self._backoff = backoff
        self._global = asyncio.Semaphore(max_concurrency)
        self._per_host: defaultdict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(max_per_host)
        )

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    async def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        host = urlparse(url).netloc
        last_error = "unknown error"
        for attempt in range(self._retries):
            async with self._global, self._per_host[host]:
                try:
                    response = await self._client.get(url, params=params)
                except httpx.HTTPError as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                else:
                    if response.status_code < 400:
                        return response
                    last_error = f"HTTP {response.status_code}"
                    retryable = response.status_code == 429 or response.status_code >= 500
                    if not retryable:
                        raise FetchError(f"{last_error} for {url}", status=response.status_code)
            if attempt < self._retries - 1:
                await asyncio.sleep(self._backoff * 2**attempt)
        raise FetchError(f"{last_error} for {url} after {self._retries} attempts")

    async def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = await self.get(url, params)
        try:
            return response.json()
        except ValueError as exc:
            raise FetchError(f"Invalid JSON from {url}: {exc}") from exc

    async def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        return (await self.get(url, params)).text
