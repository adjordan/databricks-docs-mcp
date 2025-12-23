"""Sitemap parsing and URL extraction."""

from xml.etree import ElementTree

import httpx

from ..shared.config import settings


class SitemapParser:
    """Parse Databricks sitemap.xml and extract documentation URLs."""

    SITEMAP_URL = settings.sitemap_url
    DISALLOWED_PATTERNS = ["/archive/", "/search-for", "?s="]

    async def fetch_urls(self) -> list[str]:
        """Fetch and parse sitemap, returning allowed URLs."""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.SITEMAP_URL, timeout=30.0)
            response.raise_for_status()

        urls = self._parse_sitemap(response.text)
        return self.filter_urls(urls)

    def _parse_sitemap(self, xml_content: str) -> list[str]:
        """Parse sitemap XML and extract URLs."""
        root = ElementTree.fromstring(xml_content)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        urls = []
        for url_element in root.findall(".//sm:url/sm:loc", namespace):
            if url_element.text:
                urls.append(url_element.text.strip())

        return urls

    def filter_urls(self, urls: list[str]) -> list[str]:
        """Filter URLs based on robots.txt rules."""
        filtered = []
        for url in urls:
            if not any(pattern in url for pattern in self.DISALLOWED_PATTERNS):
                filtered.append(url)
        return filtered

    def categorize_url(self, url: str) -> tuple[str, str | None]:
        """Extract category and subcategory from URL path.

        Example: /aws/en/compute/clusters --> ("compute", "clusters")
        """
        # Extract path from URL
        path = url.replace(settings.base_url, "")
        parts = [p for p in path.split("/") if p]

        # Skip cloud and language parts (aws, en)
        if len(parts) >= 2:
            parts = parts[2:]  # Skip "aws" and "en"

        if not parts:
            return ("other", None)

        category = parts[0] if parts else "other"
        subcategory = parts[1] if len(parts) > 1 else None

        return (category, subcategory)
