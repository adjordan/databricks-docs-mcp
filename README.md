# Databricks Documentation MCP Server

An MCP (Model Context Protocol) server that provides Claude with access to Databricks documentation through semantic search.

## Features

- **Crawler**: Fetches and indexes ~3500 Databricks documentation pages
- **Vector Search**: ChromaDB with sentence-transformers for semantic search
- **MCP Tools**: `list-sections` and `get-documentation` for Claude integration
- **Incremental Updates**: By default, re-fetches pages that haven't been updated in 7 or more days

## Installation

```bash
# Install dependencies
uv sync

# Run the crawler to index documentation (takes ~1 hour at 1 req/sec)
uv run crawl

# Or test with a few pages first
uv run crawl --limit 20

# Only crawl new pages (skip all previously crawled pages; ignores 7-day freshness)
uv run crawl --new-only

# Force re-crawl of all pages (ignores 7-day freshness)
uv run crawl --full
```

## Configuration

### Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "databricks-docs": {
      "command": "/path/to/databricks-docs-mcp/run-server.sh"
    }
  }
}
```

Replace `/path/to/databricks-docs-mcp` with the actual path to this repository.

> **Note**: The wrapper script `run-server.sh` is recommended because Claude Desktop doesn't inherit your shell's PATH, so it may not find `uv` directly.

### Claude Code

Add the MCP server to your Claude Code settings (same as above). You can do this globally or per-project:

- Globally: `~/.claude/settings.json`
- Per-project: `.claude/settings.json` in your project

## CLAUDE.md Setup

Add the following to your `CLAUDE.md` file (global or per-project) to help Claude use the MCP effectively:

```markdown
## Databricks Documentation MCP

You have access to comprehensive Databricks documentation through the `databricks-docs` MCP server.

### Available Tools

**1. list-sections**
Use this FIRST to discover available documentation. Returns titles, paths, use_cases, and categories.

- `list-sections()` - List all sections
- `list-sections(category="compute")` - Filter by category
- `list-sections(search_query="autoscaling")` - Semantic search

**2. get-documentation**
Retrieves full markdown content for specific paths. Use after list-sections to get details.

- `get-documentation(paths=["/aws/en/compute/clusters"])` - Single doc
- `get-documentation(paths=["/aws/en/delta/optimize", "/aws/en/delta/vacuum"])` - Multiple docs
- `get_documentation(paths=[...], include_related=True)` - Include related pages

### Workflow

1. When asked about Databricks topics, call `list-sections` first to find relevant documentation
2. Analyze the returned sections (especially `use_cases`) to identify what's relevant
3. Call `get-documentation` with the paths you need
4. Synthesize the documentation into a helpful response

### Categories

admin, compute, delta, data-governance, dev-tools, connect, sql, machine-learning, generative-ai, workflows, notebooks, dashboards
```

## MCP Tools

### list-sections

Discover available documentation sections with titles, use cases, and paths.

**Parameters:**
- `category` (optional): Filter by category (e.g., "compute", "delta", "admin")
- `search_query` (optional): Semantic search for relevant sections
- `limit` (optional): Maximum sections to return (default: 50)

**Returns:**
```json
{
  "sections": [
    {
      "title": "Compute clusters",
      "path": "/aws/en/compute/clusters",
      "use_cases": ["Create and manage clusters", "Configure autoscaling"],
      "category": "compute"
    }
  ],
  "total_count": 150,
  "categories": ["admin", "compute", "delta", ...]
}
```

### get-documentation

Retrieve full documentation content for specified sections.

**Parameters:**
- `paths` (required): List of documentation paths to retrieve
- `include_related` (optional): Include related page paths (default: false)

**Returns:**
```json
[
  {
    "path": "/aws/en/compute/clusters",
    "title": "Compute clusters",
    "content": "# Compute clusters\n\nDatabricks compute clusters...",
    "breadcrumb": ["Compute", "Clusters"],
    "related_paths": ["/aws/en/compute/cluster-policies"]
  }
]
```
