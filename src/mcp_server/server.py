"""DOOS Discovery MCP — SPARQL tools, graph context resources, and prompts."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from . import __version__
from .catalog import (
    list_prompt_files,
    list_skills,
    read_cookbook,
    read_patterns,
    read_prompt_file,
    read_skill,
)
from .config import (
    ASK_GRAPH_PROMPT_PATH,
    DEFAULT_MCP_HOST,
    DEFAULT_MCP_PATH,
    DEFAULT_MCP_PORT,
    DEFAULT_MCP_TRANSPORT,
    DEFAULT_SPARQL_ENDPOINT,
    DEFAULT_TIMEOUT,
    DOOS_ROOT,
    MAX_LIMIT,
    PROMPTS_DIR,
    TransportName,
)


def _default_mcp_url() -> str:
    display_host = (
        "localhost" if DEFAULT_MCP_HOST in ("0.0.0.0", "::") else DEFAULT_MCP_HOST
    )
    path = DEFAULT_MCP_PATH if DEFAULT_MCP_PATH.startswith("/") else f"/{DEFAULT_MCP_PATH}"
    return f"http://{display_host}:{DEFAULT_MCP_PORT}{path}"
from .sparql_lib import (
    SparqlError,
    get_template_body,
    list_templates,
    run_adhoc,
    run_template,
)

mcp = FastMCP(
    "doos-discovery",
    instructions=(
        "DOOS Discovery MCP: query local Oxigraph (default "
        f"{DEFAULT_SPARQL_ENDPOINT}) with curated SPARQL templates or ad-hoc "
        "SPARQL. For natural-language graph questions, load the ask_graph "
        "prompt and resources doos://graph/cookbook + doos://graph/patterns, "
        "then call sparql_query / sparql_run_template. Never invent SPARQL "
        "result rows. FAIR/Blueprint interviews are available as prompts."
    ),
    host=DEFAULT_MCP_HOST,
    port=DEFAULT_MCP_PORT,
    streamable_http_path=DEFAULT_MCP_PATH,
)


def _endpoint(endpoint: str | None) -> str:
    return (endpoint or DEFAULT_SPARQL_ENDPOINT).strip()


def _err(exc: Exception) -> str:
    return json.dumps({"ok": False, "error": str(exc)}, indent=2)


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_capabilities() -> str:
    """Describe this server's tools, resources, prompts, and default SPARQL endpoint."""
    return _ok(
        {
            "name": "doos-discovery",
            "version": __version__,
            "doos_root": str(DOOS_ROOT),
            "default_transport": DEFAULT_MCP_TRANSPORT,
            "mcp_url": _default_mcp_url(),
            "mcp_host": DEFAULT_MCP_HOST,
            "mcp_port": DEFAULT_MCP_PORT,
            "mcp_path": DEFAULT_MCP_PATH,
            "default_endpoint": DEFAULT_SPARQL_ENDPOINT,
            "timeout_seconds": DEFAULT_TIMEOUT,
            "max_limit": MAX_LIMIT,
            "text_to_sparql": "host-side (use ask_graph prompt + graph resources + sparql tools)",
            "tools": [
                "list_capabilities",
                "sparql_list_templates",
                "sparql_run_template",
                "sparql_query",
                "graph_probe",
            ],
            "resources": [
                "doos://config",
                "doos://graph/patterns",
                "doos://graph/cookbook",
                "doos://sparql/templates",
                "doos://sparql/templates/{id}",
                "doos://prompts",
                "doos://prompts/{name}",
                "doos://skills",
                "doos://skills/{name}",
            ],
            "prompts": [
                "ask_graph",
                "fair_blueprint_interview",
                "blueprint_context",
            ],
            "v1_scope": (
                "Layer A graph discovery + Layer B prompts + thin skill catalog. "
                "No server-side LLM; no SHACL/load/index tools yet. "
                "Default MCP transport is streamable-http."
            ),
        }
    )


@mcp.tool()
def sparql_list_templates() -> str:
    """List curated DOOS schema.org SPARQL template ids (from doos-sparql skill)."""
    try:
        templates = list_templates()
        return _ok({"ok": True, "count": len(templates), "templates": templates})
    except SparqlError as exc:
        return _err(exc)


@mcp.tool()
def sparql_run_template(
    query_id: str,
    endpoint: str | None = None,
    limit: int | None = None,
    name: str | None = None,
    graph_contains: str | None = None,
    format: Literal["json", "table", "csv"] = "json",
) -> str:
    """
    Run a curated SPARQL template against an endpoint.

    Use sparql_list_templates for ids. Examples: probe_triples, list_graphs,
    depth_assay, depth_minmax, variable_measured, dataset_by_name (requires name).
    Default endpoint is local Oxigraph (http://localhost:7878/query).
    """
    try:
        result = run_template(
            query_id,
            endpoint=_endpoint(endpoint),
            limit=limit,
            name=name,
            graph_contains=graph_contains,
            fmt=format,
            timeout=DEFAULT_TIMEOUT,
            show_query=True,
        )
        return _ok(result)
    except SparqlError as exc:
        return _err(exc)


@mcp.tool()
def sparql_query(
    sparql: str,
    endpoint: str | None = None,
    limit: int | None = None,
    format: Literal["json", "table", "csv"] = "json",
    auto_limit: bool = True,
) -> str:
    """
    Execute ad-hoc SPARQL 1.1 (SELECT/ASK) against an endpoint.

    Prefer writing SPARQL after reading doos://graph/cookbook and
    doos://graph/patterns (host-side text→SPARQL). Never invent results —
    only report bindings returned here. A LIMIT is auto-appended for SELECT
    queries that lack one (default 100, max 1000).
    """
    try:
        result = run_adhoc(
            sparql,
            endpoint=_endpoint(endpoint),
            limit=limit,
            fmt=format,
            timeout=DEFAULT_TIMEOUT,
            show_query=True,
            auto_limit=auto_limit,
        )
        return _ok(result)
    except SparqlError as exc:
        return _err(exc)


@mcp.tool()
def graph_probe(endpoint: str | None = None, limit: int = 10) -> str:
    """
    Health check: sample triples from the store (template probe_triples).

    Use to verify the endpoint is up and has data before deeper queries.
    """
    try:
        result = run_template(
            "probe_triples",
            endpoint=_endpoint(endpoint),
            limit=limit,
            fmt="json",
            timeout=DEFAULT_TIMEOUT,
            show_query=True,
        )
        summary = {
            "ok": result.get("ok"),
            "endpoint": result.get("endpoint"),
            "sample_count": result.get("count"),
            "message": (
                "Store returned sample triples."
                if result.get("count")
                else "No triples returned — store may be empty or path wrong."
            ),
            "sparql": result.get("sparql"),
            "result": result.get("result"),
        }
        return _ok(summary)
    except SparqlError as exc:
        return _err(exc)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("doos://config")
def resource_config() -> str:
    """Server config: default endpoint, paths, limits."""
    return _ok(
        {
            "default_endpoint": DEFAULT_SPARQL_ENDPOINT,
            "timeout_seconds": DEFAULT_TIMEOUT,
            "max_limit": MAX_LIMIT,
            "doos_root": str(DOOS_ROOT),
            "prompts_dir": str(PROMPTS_DIR),
        }
    )


@mcp.resource("doos://graph/patterns")
def resource_patterns() -> str:
    """Triple patterns context for host-side text→SPARQL generation."""
    return read_patterns()


@mcp.resource("doos://graph/cookbook")
def resource_cookbook() -> str:
    """Schema.org + GeoSPARQL SPARQL cookbook for DOOS graphs."""
    return read_cookbook()


@mcp.resource("doos://sparql/templates")
def resource_templates_index() -> str:
    """JSON index of curated SPARQL templates."""
    try:
        return _ok({"templates": list_templates()})
    except SparqlError as exc:
        return _err(exc)


@mcp.resource("doos://sparql/templates/{query_id}")
def resource_template_body(query_id: str) -> str:
    """Raw SPARQL body for a curated template id."""
    try:
        return get_template_body(query_id)
    except SparqlError as exc:
        return f"Error: {exc}"


@mcp.resource("doos://prompts")
def resource_prompts_index() -> str:
    """Index of markdown prompts under prompts/."""
    return _ok({"prompts": list_prompt_files()})


@mcp.resource("doos://prompts/{name}")
def resource_prompt_body(name: str) -> str:
    """Full text of a prompt file from prompts/."""
    try:
        return read_prompt_file(name)
    except FileNotFoundError as exc:
        return f"Error: {exc}"


@mcp.resource("doos://skills")
def resource_skills_index() -> str:
    """Catalog of agent skills under skills/ (name + description)."""
    return _ok({"skills": list_skills()})


@mcp.resource("doos://skills/{name}")
def resource_skill_body(name: str) -> str:
    """Full SKILL.md for a named skill."""
    try:
        text, _path = read_skill(name)
        return text
    except FileNotFoundError as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt()
def ask_graph() -> str:
    """
    Answer natural-language questions about the DOOS graph.

    Host writes SPARQL using cookbook + patterns resources, then executes tools.
    """
    if ASK_GRAPH_PROMPT_PATH.is_file():
        return ASK_GRAPH_PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "Use doos://graph/cookbook and doos://graph/patterns, then "
        "sparql_query or sparql_run_template. Never invent result rows."
    )


@mcp.prompt()
def fair_blueprint_interview() -> str:
    """Structured FAIR / NIAID Blueprint assessment interview (multi-turn)."""
    try:
        return read_prompt_file("fairAssessmentInterview")
    except FileNotFoundError:
        return (
            "Prompt file prompts/fairAssessmentInterview.md not found. "
            "Conduct a structured FAIR practices interview for a repository."
        )


@mcp.prompt()
def blueprint_context() -> str:
    """Short NIAID Blueprint alignment exploration conversation."""
    try:
        return read_prompt_file("contextPromptShort")
    except FileNotFoundError:
        return (
            "Prompt file prompts/contextPromptShort.md not found. "
            "Help align a repository with the NIAID Blueprint pillars."
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """CLI for transport selection. HTTP (streamable-http) is the default."""
    parser = argparse.ArgumentParser(
        description=(
            "DOOS Discovery MCP server. Default transport is streamable-http "
            f"(http://{DEFAULT_MCP_HOST}:{DEFAULT_MCP_PORT}{DEFAULT_MCP_PATH})."
        )
    )
    parser.add_argument(
        "--transport",
        choices=("streamable-http", "sse", "stdio"),
        default=DEFAULT_MCP_TRANSPORT,
        help=(
            "MCP transport (default: streamable-http). "
            "Use stdio for Claude Desktop-style process hosts."
        ),
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_MCP_HOST,
        help=f"Bind host for HTTP/SSE (default: {DEFAULT_MCP_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_MCP_PORT,
        help=f"Bind port for HTTP/SSE (default: {DEFAULT_MCP_PORT})",
    )
    parser.add_argument(
        "--path",
        default=DEFAULT_MCP_PATH,
        help=(
            f"Streamable HTTP path (default: {DEFAULT_MCP_PATH}). "
            "SSE uses FastMCP's /sse and /messages/ paths."
        ),
    )
    return parser.parse_args(argv)


def mcp_public_url(
    transport: TransportName,
    host: str,
    port: int,
    path: str,
) -> str | None:
    """Human-readable base URL for HTTP-family transports."""
    if transport == "stdio":
        return None
    display_host = "localhost" if host in ("0.0.0.0", "::") else host
    if transport == "streamable-http":
        p = path if path.startswith("/") else f"/{path}"
        return f"http://{display_host}:{port}{p}"
    # sse
    return f"http://{display_host}:{port}/sse"


def main(argv: list[str] | None = None) -> None:
    """Run the MCP server (default: streamable-http)."""
    args = parse_args(argv)
    transport: TransportName = args.transport  # type: ignore[assignment]

    # Apply bind settings (used by streamable-http and sse)
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.streamable_http_path = args.path

    url = mcp_public_url(transport, args.host, args.port, args.path)
    if url:
        print(
            f"DOOS Discovery MCP v{__version__}  transport={transport}\n"
            f"  listening: {url}\n"
            f"  SPARQL default: {DEFAULT_SPARQL_ENDPOINT}",
            file=sys.stderr,
        )
    else:
        print(
            f"DOOS Discovery MCP v{__version__}  transport=stdio\n"
            f"  SPARQL default: {DEFAULT_SPARQL_ENDPOINT}",
            file=sys.stderr,
        )

    if transport == "streamable-http":
        mcp.run(transport="streamable-http")
    elif transport == "sse":
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
