"""HTML parsing and content extraction."""

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from ..shared.config import settings
from ..shared.models import DocumentMetadata
from .sitemap import SitemapParser


class ContentParser:
    """Extract main content from Databricks documentation pages."""

    # CSS selectors for Databricks docs (Docusaurus-based)
    CONTENT_SELECTORS = [
        "article",
        "main",
        "[role='main']",
        ".theme-doc-markdown",
        "#__docusaurus_skipToContent_fallback",
    ]

    REMOVE_SELECTORS = [
        "nav",
        "footer",
        "script",
        "style",
        "noscript",
        ".breadcrumbs",
        "[class*='sidebar']",
        "[class*='toc']",
        "[class*='pagination']",
        "[class*='feedback']",
        "[class*='edit-page']",
        ".theme-doc-toc-mobile",
        ".theme-doc-footer",
    ]

    def __init__(self):
        self.sitemap_parser = SitemapParser()

    def parse(self, html: str, url: str) -> tuple[str, DocumentMetadata]:
        """Parse HTML and return (markdown_content, metadata).

        1. Extract main content area
        2. Remove navigation elements
        3. Convert to markdown
        4. Extract metadata (title, breadcrumbs, etc.)
        """
        soup = BeautifulSoup(html, "lxml")

        # Extract metadata first
        title = self._extract_title(soup)
        breadcrumbs = self._extract_breadcrumbs(soup)
        category, subcategory = self.sitemap_parser.categorize_url(url)

        # Find main content
        content_element = None
        for selector in self.CONTENT_SELECTORS:
            content_element = soup.select_one(selector)
            if content_element:
                break

        if not content_element:
            content_element = soup.body or soup

        # Remove unwanted elements
        for selector in self.REMOVE_SELECTORS:
            for element in content_element.select(selector):
                element.decompose()

        # Convert to markdown
        markdown = md(
            str(content_element),
            heading_style="ATX",
            bullets="-",
            code_language="",
        )

        # Clean up markdown
        markdown = self._clean_markdown(markdown)

        # Build path from URL
        path = url.replace(settings.base_url, "")

        metadata = DocumentMetadata(
            url=url,
            path=path,
            title=title,
            category=category,
            subcategory=subcategory,
            breadcrumb=breadcrumbs,
        )

        return (markdown, metadata)

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title from H1 or meta tags."""
        # Try H1 first
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # Try meta title
        meta_title = soup.find("meta", property="og:title")
        if meta_title and meta_title.get("content"):
            return meta_title["content"]

        # Try title tag
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove " | Databricks" suffix
            if "|" in title:
                title = title.split("|")[0].strip()
            return title

        return "Untitled"

    def _extract_breadcrumbs(self, soup: BeautifulSoup) -> list[str]:
        """Extract navigation breadcrumb trail."""
        breadcrumbs = []

        # Try common breadcrumb selectors
        breadcrumb_selectors = [
            ".breadcrumbs",
            "[aria-label='breadcrumbs']",
            ".breadcrumb",
            "nav.breadcrumbs",
        ]

        for selector in breadcrumb_selectors:
            breadcrumb_nav = soup.select_one(selector)
            if breadcrumb_nav:
                links = breadcrumb_nav.find_all("a")
                breadcrumbs = [link.get_text(strip=True) for link in links if link.get_text(strip=True)]
                if breadcrumbs:
                    break

        return breadcrumbs

    def _clean_markdown(self, markdown: str) -> str:
        """Clean up converted markdown."""
        lines = markdown.split("\n")
        cleaned_lines = []

        for line in lines:
            # Skip empty lines at the start
            if not cleaned_lines and not line.strip():
                continue
            cleaned_lines.append(line)

        # Remove trailing empty lines
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()

        # Join and normalize multiple blank lines
        result = "\n".join(cleaned_lines)

        # Replace multiple consecutive blank lines with double
        while "\n\n\n" in result:
            result = result.replace("\n\n\n", "\n\n")

        return result
