"""Paths and defaults for the DOOS Discovery MCP server."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

# src/mcp_server/config.py → repo root is parents[2]
DOOS_ROOT = Path(os.environ.get("DOOS_ROOT", Path(__file__).resolve().parents[2]))

DEFAULT_SPARQL_ENDPOINT = os.environ.get(
    "DOOS_SPARQL_ENDPOINT", "http://localhost:7878/query"
)
DEFAULT_TIMEOUT = int(os.environ.get("DOOS_SPARQL_TIMEOUT", "30"))
DEFAULT_LIMIT = int(os.environ.get("DOOS_SPARQL_DEFAULT_LIMIT", "100"))
MAX_LIMIT = int(os.environ.get("DOOS_SPARQL_MAX_LIMIT", "1000"))
MAX_ROWS_RETURNED = int(os.environ.get("DOOS_SPARQL_MAX_ROWS", "500"))

USER_AGENT = "DOOS-discovery-mcp/0.1 (+https://github.com/earthcube/doos)"

# MCP transport: streamable-http is the default (HTTP). stdio/sse still available.
TransportName = Literal["streamable-http", "sse", "stdio"]
DEFAULT_MCP_TRANSPORT: TransportName = os.environ.get(  # type: ignore[assignment]
    "DOOS_MCP_TRANSPORT", "streamable-http"
)
DEFAULT_MCP_HOST = os.environ.get("DOOS_MCP_HOST", "127.0.0.1")
DEFAULT_MCP_PORT = int(os.environ.get("DOOS_MCP_PORT", "8765"))
# Streamable HTTP mount path (FastMCP default is /mcp)
DEFAULT_MCP_PATH = os.environ.get("DOOS_MCP_PATH", "/mcp")

# Key monorepo paths
SKILLS_DIR = DOOS_ROOT / "skills"
PROMPTS_DIR = DOOS_ROOT / "prompts"
DOOS_SPARQL_DIR = SKILLS_DIR / "DOOS_bundle" / "doos-sparql"
QUERIES_DIR = DOOS_SPARQL_DIR / "queries"
CATALOG_PATH = QUERIES_DIR / "catalog.json"
PATTERNS_PATH = DOOS_ROOT / "scripts" / "text2query" / "patterns.txt"
COOKBOOK_PATH = Path(__file__).resolve().parent / "data" / "cookbook.md"
ASK_GRAPH_PROMPT_PATH = Path(__file__).resolve().parent / "data" / "ask_graph_prompt.md"
