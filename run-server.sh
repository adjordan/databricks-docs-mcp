#!/bin/bash

# Add common paths where uv might be installed
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

# Change to script directory
cd "$(dirname "$0")"

# Run the MCP server
exec uv run mcp-server
