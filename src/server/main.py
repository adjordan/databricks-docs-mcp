"""MCP server entry point."""

from mcp.server.fastmcp import FastMCP

from ..shared.config import settings
from .db import DocumentDatabase
from .tools import register_tools

# Initialize FastMCP server
mcp = FastMCP(
    name="databricks-docs",
)

# Initialize database connection
db = DocumentDatabase(
    persist_directory=settings.chroma_path,
    sections_index_path=settings.sections_index_path,
)

# Register tools
register_tools(mcp, db)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
