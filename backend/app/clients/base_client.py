"""Base async HTTP client with retry and rate limiting."""

import asyncio
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


class BaseAPIClient:
    """
    Async HTTP client base using httpx.AsyncClient.
    Features: configurable auth headers, timeout, retry with backoff, rate limiting.
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        rate_limit_delay: float = 1.0,
    ):
        self.base_url = base_url
        self._headers = headers or {}
        self._timeout = timeout
        self._rate_limit_delay = rate_limit_delay
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=self._timeout,
                follow_redirects=True,
            )
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with retry and rate limiting."""
        client = await self._get_client()

        logger.debug("API request", method=method, path=path, params=params)

        response = await client.request(method, path, params=params, json=json)

        logger.debug(
            "API response",
            method=method,
            path=path,
            status=response.status_code,
        )

        response.raise_for_status()

        # Rate limiting
        if self._rate_limit_delay > 0:
            await asyncio.sleep(self._rate_limit_delay)

        return response

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._request("GET", path, params=params)
        return response.json()

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        response = await self._request("POST", path, json=json)
        return response.json()

    async def get_bytes(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        response = await self._request("GET", path, params=params)
        return response.content

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
