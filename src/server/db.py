"""ChromaDB query interface for MCP server."""

import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from ..shared.config import settings
from ..shared.models import DocumentationContent, Section, SectionList


class DocumentDatabase:
    """Query interface for documentation storage."""

    def __init__(
        self,
        persist_directory: Path = settings.chroma_path,
        sections_index_path: Path = settings.sections_index_path,
    ):
        self.client = chromadb.PersistentClient(path=str(persist_directory))
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )

        try:
            self.collection = self.client.get_collection(
                name="databricks_docs",
                embedding_function=self.embedding_fn,
            )
        except Exception:
            # Collection doesn't exist yet - crawler hasn't run
            self.collection = None

        self.sections_index = self._load_sections_index(sections_index_path)

    def _load_sections_index(self, path: Path) -> dict:
        """Load pre-computed sections index."""
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"sections": [], "categories": [], "total_count": 0}

    def list_sections(
        self,
        category: str | None = None,
        search_query: str | None = None,
        limit: int = 50,
    ) -> SectionList:
        """List documentation sections.

        If search_query provided, uses semantic search.
        Otherwise, returns from pre-computed index.
        """
        if search_query and self.collection:
            # Semantic search using embeddings
            results = self.collection.query(
                query_texts=[search_query],
                n_results=min(limit * 3, 100),  # Get more to deduplicate
                include=["metadatas"],
            )

            # Deduplicate by path and convert to sections
            seen_paths: set[str] = set()
            sections = []

            if results["metadatas"]:
                for metadata in results["metadatas"][0]:
                    path = metadata["path"]
                    if path in seen_paths:
                        continue

                    # Apply category filter if specified
                    if category and metadata.get("category") != category:
                        continue

                    seen_paths.add(path)
                    sections.append(
                        Section(
                            title=metadata.get("title", "Untitled"),
                            path=path,
                            category=metadata.get("category", "other"),
                            subcategory=metadata.get("subcategory") or None,
                            use_cases=self._get_use_cases(metadata.get("category", "other")),
                            child_count=0,
                        )
                    )

                    if len(sections) >= limit:
                        break

            return SectionList(
                sections=sections,
                total_count=len(sections),
                categories=self.sections_index.get("categories", []),
            )
        else:
            # Use pre-computed index
            all_sections = self.sections_index.get("sections", [])

            if category:
                all_sections = [s for s in all_sections if s.get("category") == category]

            sections = [Section(**s) for s in all_sections[:limit]]

            return SectionList(
                sections=sections,
                total_count=len(all_sections),
                categories=self.sections_index.get("categories", []),
            )

    def get_documentation(
        self,
        path: str,
        include_related: bool = False,
    ) -> DocumentationContent | None:
        """Retrieve full documentation for a path.

        Fetches all chunks for the path and reassembles them.
        """
        if not self.collection:
            return None

        # Query all chunks for this path
        results = self.collection.get(
            where={"path": path},
            include=["documents", "metadatas"],
        )

        if not results["ids"]:
            return None

        # Sort chunks by index and reassemble
        chunks = sorted(
            zip(results["documents"], results["metadatas"]),
            key=lambda x: x[1].get("chunk_index", 0),
        )

        full_content = "\n\n".join(doc for doc, _ in chunks)
        first_metadata = chunks[0][1]

        # Parse breadcrumb from JSON string
        breadcrumb = []
        breadcrumb_str = first_metadata.get("breadcrumb", "[]")
        if breadcrumb_str:
            try:
                breadcrumb = json.loads(breadcrumb_str)
            except json.JSONDecodeError:
                pass

        related_paths: list[str] = []
        if include_related:
            related_paths = self._find_related(path, limit=5)

        return DocumentationContent(
            path=path,
            title=first_metadata.get("title", "Untitled"),
            content=full_content,
            breadcrumb=breadcrumb,
            related_paths=related_paths,
        )

    def _find_related(self, path: str, limit: int = 5) -> list[str]:
        """Find related documentation paths using embedding similarity."""
        if not self.collection:
            return []

        # Get first chunk for current document
        doc_results = self.collection.get(
            where={"path": path, "chunk_index": 0},
            include=["embeddings"],
        )

        if not doc_results["embeddings"]:
            return []

        # Find similar documents
        similar = self.collection.query(
            query_embeddings=doc_results["embeddings"],
            n_results=limit + 10,  # Get extra to deduplicate
            include=["metadatas"],
        )

        # Deduplicate and return paths (excluding self)
        seen: set[str] = {path}
        related = []

        if similar["metadatas"]:
            for metadata in similar["metadatas"][0]:
                result_path = metadata["path"]
                if result_path not in seen:
                    seen.add(result_path)
                    related.append(result_path)
                    if len(related) >= limit:
                        break

        return related

    def _get_use_cases(self, category: str) -> list[str]:
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
