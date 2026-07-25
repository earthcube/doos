"""SPARQL helpers for the MCP server (no sys.exit; raise / return errors)."""

from __future__ import annotations

import csv
import json
import re
from io import StringIO
from pathlib import Path
from typing import Any

from .config import (
    CATALOG_PATH,
    DEFAULT_LIMIT,
    DEFAULT_TIMEOUT,
    MAX_LIMIT,
    MAX_ROWS_RETURNED,
    QUERIES_DIR,
    USER_AGENT,
)


class SparqlError(Exception):
    """Raised when SPARQL catalog/load/execute fails."""


def load_catalog() -> dict[str, Any]:
    """Load doos-sparql queries/catalog.json."""
    if not CATALOG_PATH.is_file():
        raise SparqlError(f"catalog not found: {CATALOG_PATH}")
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def catalog_by_id(catalog: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Index catalog entries by id."""
    cat = catalog if catalog is not None else load_catalog()
    return {entry["id"]: entry for entry in cat.get("queries", [])}


def list_templates() -> list[dict[str, Any]]:
    """Return a JSON-serializable list of template summaries."""
    catalog = load_catalog()
    out: list[dict[str, Any]] = []
    for entry in catalog.get("queries", []):
        out.append(
            {
                "id": entry["id"],
                "title": entry.get("title", ""),
                "description": entry.get("description", ""),
                "params": entry.get("params", []),
                "required_params": entry.get("required_params") or [],
                "tags": entry.get("tags", []),
                "file": entry.get("file", ""),
            }
        )
    return out


def escape_sparql_string(value: str) -> str:
    """Escape a string for embedding in a SPARQL double-quoted literal fragment."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def apply_params(
    template: str,
    *,
    limit: int | None,
    name: str | None,
    graph_contains: str | None,
) -> str:
    """Substitute {{LIMIT}}, {{NAME_FRAGMENT}}, {{GRAPH_FILTER}} in a template."""
    text = template

    if "{{LIMIT}}" in text:
        lim = DEFAULT_LIMIT if limit is None else int(limit)
        lim = max(1, min(lim, MAX_LIMIT))
        text = text.replace("{{LIMIT}}", str(lim))

    if "{{NAME_FRAGMENT}}" in text:
        if not name:
            raise SparqlError("this query requires name (NAME_FRAGMENT)")
        text = text.replace("{{NAME_FRAGMENT}}", escape_sparql_string(name))

    if "{{GRAPH_FILTER}}" in text:
        if graph_contains:
            frag = escape_sparql_string(graph_contains)
            filt = f'FILTER(CONTAINS(STR(?g), "{frag}"))'
        else:
            filt = ""
        text = text.replace("{{GRAPH_FILTER}}", filt)

    return text


def clamp_limit(limit: int | None) -> int:
    """Return a safe LIMIT value."""
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(int(limit), MAX_LIMIT))


def ensure_limit(sparql: str, limit: int | None = None) -> str:
    """
    Append LIMIT if the query looks like SELECT/CONSTRUCT and has no LIMIT.

    Does not rewrite ASK or queries that already contain LIMIT.
    """
    stripped = sparql.strip()
    # Skip if LIMIT already present (case-insensitive word)
    if re.search(r"\bLIMIT\b", stripped, flags=re.IGNORECASE):
        return stripped
    # Only auto-limit SELECT-like queries
    if not re.match(r"(?is)^\s*(PREFIX\b|BASE\b|SELECT\b|CONSTRUCT\b)", stripped):
        return stripped
    if re.match(r"(?is)^\s*(PREFIX\b|BASE\b)*\s*ASK\b", stripped):
        return stripped
    lim = clamp_limit(limit)
    return f"{stripped.rstrip()}\nLIMIT {lim}\n"


def execute_sparql(
    endpoint: str,
    query: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Run a SPARQL SELECT/ASK query; return parsed JSON results."""
    try:
        from SPARQLWrapper import JSON, SPARQLWrapper
    except ImportError as exc:
        raise SparqlError(
            "SPARQLWrapper is required. Install with: uv pip install SPARQLWrapper"
        ) from exc

    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.addCustomHttpHeader("User-Agent", USER_AGENT)
    sparql.setTimeout(timeout)

    try:
        return sparql.query().convert()
    except Exception as exc:
        raise SparqlError(f"SPARQL request failed: {exc}") from exc


def bindings_to_rows(
    results: dict[str, Any],
) -> tuple[list[str], list[dict[str, str | None]]]:
    """Convert SPARQL JSON results to column names and row dicts."""
    # ASK queries
    if "boolean" in results:
        return ["boolean"], [{"boolean": str(results["boolean"])}]

    columns = results.get("head", {}).get("vars", [])
    rows: list[dict[str, str | None]] = []
    for binding in results.get("results", {}).get("bindings", []):
        row = {
            var: binding.get(var, {}).get("value") if var in binding else None
            for var in columns
        }
        rows.append(row)
    return columns, rows


def format_table(columns: list[str], rows: list[dict[str, str | None]]) -> str:
    """Format rows as a simple aligned table."""
    if not columns:
        return "(no variables)"

    display_rows: list[list[str]] = []
    for row in rows:
        display_rows.append(
            ["" if row.get(c) is None else str(row[c]) for c in columns]
        )

    widths = [len(c) for c in columns]
    for drow in display_rows:
        for i, cell in enumerate(drow):
            cell_disp = cell if len(cell) <= 80 else cell[:77] + "..."
            drow[i] = cell_disp
            widths[i] = max(widths[i], len(cell_disp))

    def fmt_row(cells: list[str]) -> str:
        return " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))

    lines = [
        fmt_row(columns),
        "-+-".join("-" * w for w in widths),
    ]
    for drow in display_rows:
        lines.append(fmt_row(drow))
    lines.append(f"\n({len(rows)} row(s))")
    return "\n".join(lines)


def format_csv(columns: list[str], rows: list[dict[str, str | None]]) -> str:
    """Format rows as CSV."""
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") or "" for c in columns})
    return buf.getvalue()


def format_json(columns: list[str], rows: list[dict[str, str | None]]) -> str:
    """Format rows as JSON array."""
    return json.dumps(
        {"columns": columns, "rows": rows, "count": len(rows)},
        indent=2,
    )


def emit(
    columns: list[str],
    rows: list[dict[str, str | None]],
    fmt: str,
) -> str:
    """Return results as a string in the requested format."""
    if fmt == "table":
        return format_table(columns, rows)
    if fmt == "csv":
        return format_csv(columns, rows)
    if fmt == "json":
        return format_json(columns, rows)
    raise SparqlError(f"unknown format: {fmt}")


def run_template(
    query_id: str,
    *,
    endpoint: str,
    limit: int | None = None,
    name: str | None = None,
    graph_contains: str | None = None,
    fmt: str = "json",
    timeout: int = DEFAULT_TIMEOUT,
    show_query: bool = True,
) -> dict[str, Any]:
    """Run a named catalog template; return structured result dict."""
    by_id = catalog_by_id()
    entry = by_id.get(query_id)
    if not entry:
        known = ", ".join(sorted(by_id))
        raise SparqlError(f"unknown query id '{query_id}'. Known: {known}")

    rq_path = QUERIES_DIR / entry["file"]
    if not rq_path.is_file():
        raise SparqlError(f"query file missing: {rq_path}")

    required = entry.get("required_params") or []
    if "NAME_FRAGMENT" in required and not name:
        raise SparqlError(f"query '{query_id}' requires name")

    template = rq_path.read_text(encoding="utf-8")
    sparql = apply_params(
        template,
        limit=limit,
        name=name,
        graph_contains=graph_contains,
    )
    return _execute_and_package(
        endpoint, sparql, fmt=fmt, timeout=timeout, show_query=show_query
    )


def run_adhoc(
    sparql: str,
    *,
    endpoint: str,
    limit: int | None = None,
    fmt: str = "json",
    timeout: int = DEFAULT_TIMEOUT,
    show_query: bool = True,
    auto_limit: bool = True,
) -> dict[str, Any]:
    """Execute an ad-hoc SPARQL string; return structured result dict."""
    if not sparql or not sparql.strip():
        raise SparqlError("sparql must be a non-empty query")
    query = ensure_limit(sparql, limit) if auto_limit else sparql.strip()
    return _execute_and_package(
        endpoint, query, fmt=fmt, timeout=timeout, show_query=show_query
    )


def get_template_body(query_id: str) -> str:
    """Return the raw SPARQL template file for a catalog id."""
    by_id = catalog_by_id()
    entry = by_id.get(query_id)
    if not entry:
        known = ", ".join(sorted(by_id))
        raise SparqlError(f"unknown query id '{query_id}'. Known: {known}")
    rq_path = QUERIES_DIR / entry["file"]
    if not rq_path.is_file():
        raise SparqlError(f"query file missing: {rq_path}")
    return rq_path.read_text(encoding="utf-8")


def _execute_and_package(
    endpoint: str,
    sparql: str,
    *,
    fmt: str,
    timeout: int,
    show_query: bool,
) -> dict[str, Any]:
    results = execute_sparql(endpoint, sparql, timeout=timeout)
    columns, rows = bindings_to_rows(results)
    truncated = False
    if len(rows) > MAX_ROWS_RETURNED:
        rows = rows[:MAX_ROWS_RETURNED]
        truncated = True
    text = emit(columns, rows, fmt)
    out: dict[str, Any] = {
        "ok": True,
        "endpoint": endpoint,
        "count": len(rows),
        "truncated": truncated,
        "columns": columns,
        "format": fmt,
        "result": text,
    }
    if show_query:
        out["sparql"] = sparql
    # Include structured rows for JSON format consumers
    if fmt == "json":
        out["rows"] = rows
    return out
