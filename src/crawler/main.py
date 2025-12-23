"""Main crawler entry point."""

import argparse
import asyncio
import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions
from tqdm import tqdm

from ..shared.config import settings
from ..shared.models import Section
from .chunker import DocumentChunker
from .fetcher import DocumentFetcher
from .parser import ContentParser
from .sitemap import SitemapParser
from .state import StateManager


def get_collection():
    """Get or create ChromaDB collection."""
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_path))

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.embedding_model
    )

    return client.get_or_create_collection(
        name="databricks_docs",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )


def generate_sections_index(collection) -> None:
    """Generate sections index for fast list-sections lookup."""
    # Get all unique paths and their metadata
    results = collection.get(include=["metadatas"])

    if not results["ids"]:
        return

    # Deduplicate by path, keeping first chunk's metadata
    path_to_metadata: dict = {}
    path_child_counts: dict[str, int] = {}

    for metadata in results["metadatas"]:
        path = metadata["path"]
        if path not in path_to_metadata:
            path_to_metadata[path] = metadata

        # Count children for parent paths
        parts = path.strip("/").split("/")
        for i in range(len(parts) - 1):
            parent_path = "/" + "/".join(parts[: i + 1])
            path_child_counts[parent_path] = path_child_counts.get(parent_path, 0) + 1

    # Build sections list
    sections = []
    categories = set()

    for path, metadata in path_to_metadata.items():
        category = metadata.get("category", "other")
        categories.add(category)

        section = Section(
            title=metadata.get("title", "Untitled"),
            path=path,
            category=category,
            subcategory=metadata.get("subcategory"),
            use_cases=get_use_cases(category),
            child_count=path_child_counts.get(path, 0),
        )
        sections.append(section.model_dump())

    # Sort by category then title
    sections.sort(key=lambda s: (s["category"], s["title"]))

    index = {
        "sections": sections,
        "categories": sorted(categories),
        "total_count": len(sections),
    }

    settings.sections_index_path.parent.mkdir(parents=True, exist_ok=True)
    settings.sections_index_path.write_text(json.dumps(index, indent=2))
    print(f"Generated sections index with {len(sections)} sections")


def get_use_cases(category: str) -> list[str]:
    """Return common use cases for a category."""
    use_case_map = {
        "compute": ["Create and manage clusters", "Configure autoscaling", "Use serverless compute"],
        "delta": ["Create Delta tables", "Optimize table performance", "Use time travel"],
        "admin": ["Manage workspaces", "Configure users and groups", "Set up SSO"],
        "data-governance": ["Set up Unity Catalog", "Configure access control", "Track data lineage"],
        "dev-tools": ["Use Databricks CLI", "Configure asset bundles", "API authentication"],
        "connect": ["Connect to storage", "Set up streaming", "External integrations"],
        "sql": ["Write SQL queries", "Use SQL functions", "Query optimization"],
        "machine-learning": ["Train ML models", "Track experiments", "Deploy models"],
        "generative-ai": ["Use AI features", "Build AI applications", "LLM integration"],
        "workflows": ["Create jobs", "Schedule workflows", "Monitor runs"],
        "notebooks": ["Create notebooks", "Use magic commands", "Visualize data"],
        "dashboards": ["Create dashboards", "Build visualizations", "Share insights"],
    }
    return use_case_map.get(category, ["General documentation"])


async def crawl(full: bool = False, new_only: bool = False, limit: int | None = None) -> None:
    """Main crawl workflow.

    Args:
        full: Force full re-crawl (ignore freshness check)
        new_only: Only crawl pages that have never been crawled before
        limit: Maximum pages to crawl (for testing)
    """
    state = StateManager()
    sitemap = SitemapParser()
    fetcher = DocumentFetcher()
    parser = ContentParser()
    chunker = DocumentChunker()
    collection = get_collection()

    # 1. Get URLs from sitemap
    print("Fetching sitemap...")
    all_urls = await sitemap.fetch_urls()
    print(f"Found {len(all_urls)} documentation pages")

    if limit:
        all_urls = all_urls[:limit]
        print(f"Limiting to {limit} pages")

    # 2. Determine which URLs need updating (if not full crawl)
    if not full:
        deleted = state.get_deleted_urls(set(all_urls))
        if deleted:
            print(f"Removing {len(deleted)} deleted pages from index...")
            for url in deleted:
                doc_id = state.compute_hash(url)
                try:
                    collection.delete(where={"document_id": doc_id})
                except Exception:
                    pass

    # 3. Filter URLs based on mode
    if full:
        # Full mode: crawl everything
        urls = all_urls
        skipped = 0
    elif new_only:
        # New-only mode: only crawl pages never seen before
        urls = [url for url in all_urls if not state.has_been_crawled(url)]
        skipped = len(all_urls) - len(urls)
        if skipped > 0:
            print(f"Skipping {skipped} previously crawled pages (--new-only)")
    else:
        # Default mode: skip pages fetched within 7 days
        urls = [url for url in all_urls if not state.is_fresh(url)]
        skipped = len(all_urls) - len(urls)
        if skipped > 0:
            print(f"Skipping {skipped} pages fetched within the last 7 days")

    if not urls:
        print("No pages need updating.")
        generate_sections_index(collection)
        return

    # 4. Fetch and process pages
    updated = 0
    errors = 0
    total_chunks = 0

    print(f"Crawling {len(urls)} documentation pages...")
    pbar = tqdm(total=len(urls), desc="Crawling")

    async for url, html, error in fetcher.fetch_batch(urls):
        pbar.update(1)

        if error:
            tqdm.write(f"Error fetching {url}: {error}")
            errors += 1
            continue

        if html is None:
            continue

        content_hash = state.compute_hash(html)

        # Skip if unchanged (unless full crawl)
        if not full and not state.needs_update(url, content_hash):
            continue

        try:
            # Parse HTML
            markdown, metadata = parser.parse(html, url)
            metadata.content_hash = content_hash

            # Chunk content
            chunks = chunker.chunk(markdown, metadata)

            if not chunks:
                continue

            # Delete old chunks for this document
            doc_id = chunks[0].document_id
            try:
                collection.delete(where={"document_id": doc_id})
            except Exception:
                pass

            # Store new chunks
            collection.upsert(
                ids=[c.id for c in chunks],
                documents=[c.content for c in chunks],
                metadatas=[
                    {
                        "url": c.metadata.url,
                        "path": c.metadata.path,
                        "title": c.metadata.title,
                        "category": c.metadata.category,
                        "subcategory": c.metadata.subcategory or "",
                        "breadcrumb": json.dumps(c.metadata.breadcrumb),
                        "chunk_index": c.chunk_index,
                        "heading_context": json.dumps(c.heading_context),
                        "document_id": c.document_id,
                        "content_hash": c.metadata.content_hash,
                    }
                    for c in chunks
                ],
            )

            # Update state
            state.mark_crawled(url, content_hash)
            updated += 1
            total_chunks += len(chunks)

        except Exception as e:
            tqdm.write(f"Error processing {url}: {e}")
            errors += 1

    pbar.close()

    # 4. Save state and generate sections index
    state.update_stats(len(urls), collection.count())
    state.save()

    generate_sections_index(collection)

    print(f"\nCrawl complete:")
    print(f"  - Pages processed: {updated}")
    if skipped > 0:
        print(f"  - Pages skipped (fresh): {skipped}")
    print(f"  - Errors: {errors}")
    print(f"  - Total chunks in database: {collection.count()}")


def main():
    """CLI entry point."""
    arg_parser = argparse.ArgumentParser(description="Crawl Databricks documentation")
    arg_parser.add_argument("--full", action="store_true", help="Force full re-crawl (ignore freshness)")
    arg_parser.add_argument("--new-only", action="store_true", help="Only crawl new pages (never crawled before)")
    arg_parser.add_argument("--limit", type=int, help="Limit pages to crawl (for testing)")
    args = arg_parser.parse_args()

    if args.full and args.new_only:
        arg_parser.error("--full and --new-only are mutually exclusive")

    asyncio.run(crawl(full=args.full, new_only=args.new_only, limit=args.limit))


if __name__ == "__main__":
    main()
