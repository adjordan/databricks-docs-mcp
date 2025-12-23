"""Crawl state management for incremental updates."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import xxhash
from pydantic import BaseModel

from ..shared.config import settings


class UrlState(BaseModel):
    """State for a single URL."""

    content_hash: str
    last_fetched: datetime


class CrawlState(BaseModel):
    """Persistent state for incremental crawling."""

    last_crawl: datetime | None = None
    url_states: dict[str, UrlState] = {}  # url -> UrlState
    total_pages: int = 0
    total_chunks: int = 0

    # Legacy field for backwards compatibility
    url_hashes: dict[str, str] | None = None


class StateManager:
    """Manage crawl state for incremental updates."""

    # Don't re-fetch pages crawled within this period
    FRESHNESS_THRESHOLD = timedelta(days=7)

    def __init__(self, state_path: Path = settings.crawl_state_path):
        self.state_path = Path(state_path)
        self.state = self._load_state()

    def _load_state(self) -> CrawlState:
        """Load existing state or create new."""
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                state = CrawlState(**data)

                # Migrate legacy url_hashes to url_states
                if state.url_hashes and not state.url_states:
                    now = datetime.now()
                    for url, content_hash in state.url_hashes.items():
                        state.url_states[url] = UrlState(
                            content_hash=content_hash,
                            last_fetched=now,
                        )
                    state.url_hashes = None

                return state
            except (json.JSONDecodeError, ValueError):
                return CrawlState()
        return CrawlState()

    def is_fresh(self, url: str) -> bool:
        """Check if URL was fetched recently (within FRESHNESS_THRESHOLD)."""
        url_state = self.state.url_states.get(url)
        if not url_state:
            return False

        age = datetime.now() - url_state.last_fetched
        return age < self.FRESHNESS_THRESHOLD

    def needs_update(self, url: str, content_hash: str) -> bool:
        """Check if URL content has changed."""
        url_state = self.state.url_states.get(url)
        if not url_state:
            return True
        return url_state.content_hash != content_hash

    def compute_hash(self, content: str) -> str:
        """Compute fast hash of content."""
        return xxhash.xxh64(content.encode()).hexdigest()

    def mark_crawled(self, url: str, content_hash: str) -> None:
        """Update state for crawled URL."""
        self.state.url_states[url] = UrlState(
            content_hash=content_hash,
            last_fetched=datetime.now(),
        )

    def get_deleted_urls(self, current_urls: set[str]) -> set[str]:
        """Find URLs that were removed from sitemap."""
        return set(self.state.url_states.keys()) - current_urls

    def get_content_hash(self, url: str) -> str | None:
        """Get stored content hash for a URL."""
        url_state = self.state.url_states.get(url)
        return url_state.content_hash if url_state else None

    def has_been_crawled(self, url: str) -> bool:
        """Check if URL has ever been crawled."""
        return url in self.state.url_states

    def update_stats(self, total_pages: int, total_chunks: int) -> None:
        """Update statistics."""
        self.state.total_pages = total_pages
        self.state.total_chunks = total_chunks
        self.state.last_crawl = datetime.now()

    def save(self) -> None:
        """Persist state to disk."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(self.state.model_dump_json(indent=2))
