"""MCP tool definitions."""

from mcp.server.fastmcp import FastMCP

from ..shared.models import DocumentationContent, SectionList
from .db import DocumentDatabase


def register_tools(mcp: FastMCP, db: DocumentDatabase) -> None:
    """Register all MCP tools with the server."""

    @mcp.tool()
    def list_sections(
        category: str | None = None,
        search_query: str | None = None,
        limit: int = 50,
    ) -> dict:
        """List available documentation sections with their titles, use cases, and paths.

        Use this tool to discover what documentation is available before retrieving
        specific content. You can filter by category or search for specific topics.

        Args:
            category: Filter by category (e.g., "compute", "delta", "admin")
            search_query: Search for sections matching this query
            limit: Maximum number of sections to return (default: 50)

        Returns:
            A list of sections with titles, paths, and common use cases

        Example categories:
            - admin: Workspace administration, users, groups
            - compute: Clusters, SQL warehouses, serverless
            - delta: Delta Lake tables, operations
            - data-governance: Unity Catalog, access control
            - dev-tools: CLI, APIs, bundles
            - connect: Storage, streaming integrations
            - sql: SQL queries and functions
            - machine-learning: ML models and experiments
            - generative-ai: AI features and LLM integration
            - workflows: Jobs and scheduling
            - notebooks: Notebooks and visualizations
            - dashboards: Dashboards and BI
        """
        result = db.list_sections(
            category=category,
            search_query=search_query,
            limit=limit,
        )
        return result.model_dump()

    @mcp.tool()
    def get_documentation(
        paths: list[str],
        include_related: bool = False,
    ) -> list[dict]:
        """Retrieve full documentation content for specified sections.

        Use this tool after list_sections to get detailed documentation.
        You can request multiple paths in a single call for efficiency.

        Args:
            paths: List of documentation paths to retrieve
                   (e.g., ["/aws/en/compute/clusters", "/aws/en/delta/optimize"])
            include_related: Also return related documentation page paths

        Returns:
            Full markdown content for each requested path

        Tips:
            - Use list_sections first to find relevant paths
            - Request multiple paths at once to reduce round trips
            - Content is returned in markdown format
        """
        results = []
        for path in paths:
            content = db.get_documentation(path, include_related=include_related)
            if content:
                results.append(content.model_dump())
        return results
