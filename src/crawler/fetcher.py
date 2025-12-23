"""HTTP fetching with rate limiting and retry logic."""

import asyncio
from collections.abc import AsyncIterator

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..shared.config import settings


class DocumentFetcher:
    """Fetch documentation pages with rate limiting."""

    def __init__(self, rate_limit: float = settings.rate_limit):
        self.rate_limit = rate_limit
        self.delay = 1.0 / rate_limit  # Delay between requests
        self.semaphore = asyncio.Semaphore(settings.max_concurrent)
        self._last_request_time = 0.0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def fetch(self, url: str, client: httpx.AsyncClient) -> tuple[str, dict]:
        """Fetch URL, return (html_content, headers)."""
        async with self.semaphore:
            # Rate limiting
            now = asyncio.get_event_loop().time()
            time_since_last = now - self._last_request_time
            if time_since_last < self.delay:
                await asyncio.sleep(self.delay - time_since_last)

            response = await client.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()

            self._last_request_time = asyncio.get_event_loop().time()
            return (response.text, dict(response.headers))

    async def fetch_batch(
        self, urls: list[str]
    ) -> AsyncIterator[tuple[str, str | None, Exception | None]]:
        """Fetch multiple URLs with rate limiting.

        Yields (url, html_content, error) tuples.
        """
        async with httpx.AsyncClient(
            headers={
                "User-Agent": "DatabricksMCP/1.0 (documentation indexer)",
                "Accept": "text/html,application/xhtml+xml",
            }
        ) as client:
            for url in urls:
                try:
                    html, _ = await self.fetch(url, client)
                    yield (url, html, None)
                except Exception as e:
                    yield (url, None, e)
