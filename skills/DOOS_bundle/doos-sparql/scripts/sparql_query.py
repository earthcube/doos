#!/usr/bin/env python3
"""
SPARQL query skill CLI: list templates, run curated queries, or execute ad-hoc SPARQL.

Usage:
  python sparql_query.py list
  python sparql_query.py run --endpoint URL --query ID [--limit N] [--name FRAG] ...
  python sparql_query.py query --endpoint URL --sparql 'SELECT ...'
  python sparql_query.py file --endpoint URL --query-file path.rq
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

USER_AGENT = "DOOS-sparql-skill/1.0 (+https://github.com/earthcube)"
DEFAULT_TIMEOUT = 30
SKILL_ROOT = Path(__file__).resolve().parent.parent
QUERIES_DIR = SKILL_ROOT / "queries"
CATALOG_PATH = QUERIES_DIR / "catalog.json"


def load_catalog() -> dict[str, Any]:
    """Load queries/catalog.json."""
    if not CATALOG_PATH.is_file():
        print(f"Error: catalog not found: {CATALOG_PATH}", file=sys.stderr)
        sys.exit(1)
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def catalog_by_id(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index catalog entries by id."""
    return {entry["id"]: entry for entry in catalog.get("queries", [])}


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
        lim = 100 if limit is None else limit
        text = text.replace("{{LIMIT}}", str(int(lim)))

    if "{{NAME_FRAGMENT}}" in text:
        if not name:
            print(
                "Error: this query requires --name (NAME_FRAGMENT)",
                file=sys.stderr,
            )
            sys.exit(1)
        text = text.replace("{{NAME_FRAGMENT}}", escape_sparql_string(name))

    if "{{GRAPH_FILTER}}" in text:
        if graph_contains:
            frag = escape_sparql_string(graph_contains)
            filt = f'FILTER(CONTAINS(STR(?g), "{frag}"))'
        else:
            filt = ""
        text = text.replace("{{GRAPH_FILTER}}", filt)

    return text


def execute_sparql(endpoint: str, query: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Run a SPARQL SELECT/ASK query; return parsed JSON results.

    Uses SPARQLWrapper with User-Agent and timeout.
    """
    try:
        from SPARQLWrapper import JSON, SPARQLWrapper
    except ImportError:
        print(
            "Error: SPARQLWrapper is required. "
            "Install with: uv pip install SPARQLWrapper "
            "(or activate the monorepo .venv).",
            file=sys.stderr,
        )
        sys.exit(1)

    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.addCustomHttpHeader("User-Agent", USER_AGENT)
    sparql.setTimeout(timeout)

    try:
        return sparql.query().convert()
    except Exception as exc:
        print(f"Error: SPARQL request failed: {exc}", file=sys.stderr)
        sys.exit(1)


def bindings_to_rows(results: dict) -> tuple[list[str], list[dict[str, str | None]]]:
    """Convert SPARQL JSON results to column names and row dicts."""
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
    """Format rows as a simple aligned table (no pandas required)."""
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
            # Cap cell width for readability
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
    from io import StringIO

    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c, "") or "" for c in columns})
    return buf.getvalue()


def format_json(columns: list[str], rows: list[dict[str, str | None]]) -> str:
    """Format rows as JSON array."""
    return json.dumps({"columns": columns, "rows": rows, "count": len(rows)}, indent=2)


def emit(
    columns: list[str],
    rows: list[dict[str, str | None]],
    fmt: str,
) -> None:
    """Print results in the requested format."""
    if fmt == "table":
        print(format_table(columns, rows))
    elif fmt == "csv":
        print(format_csv(columns, rows), end="")
    elif fmt == "json":
        print(format_json(columns, rows))
    else:
        print(f"Error: unknown format: {fmt}", file=sys.stderr)
        sys.exit(1)


def cmd_list(_args: argparse.Namespace) -> None:
    """Print curated query catalog."""
    catalog = load_catalog()
    entries = catalog.get("queries", [])
    if not entries:
        print("No queries in catalog.")
        return

    print(f"{'ID':<24} {'TITLE':<36} TAGS")
    print("-" * 80)
    for entry in entries:
        tags = ",".join(entry.get("tags", []))
        title = entry.get("title", "")
        if len(title) > 34:
            title = title[:31] + "..."
        print(f"{entry['id']:<24} {title:<36} {tags}")
    print(f"\n{len(entries)} template(s). Use: run --endpoint URL --query <id>")


def cmd_run(args: argparse.Namespace) -> None:
    """Run a named catalog query against the endpoint."""
    catalog = load_catalog()
    by_id = catalog_by_id(catalog)
    entry = by_id.get(args.query)
    if not entry:
        known = ", ".join(sorted(by_id))
        print(
            f"Error: unknown query id '{args.query}'. Known: {known}",
            file=sys.stderr,
        )
        sys.exit(1)

    rq_path = QUERIES_DIR / entry["file"]
    if not rq_path.is_file():
        print(f"Error: query file missing: {rq_path}", file=sys.stderr)
        sys.exit(1)

    required = entry.get("required_params") or []
    if "NAME_FRAGMENT" in required and not args.name:
        print(
            f"Error: query '{args.query}' requires --name",
            file=sys.stderr,
        )
        sys.exit(1)

    template = rq_path.read_text(encoding="utf-8")
    # Strip comment-only header lines starting with # (keep SPARQL intact)
    sparql = apply_params(
        template,
        limit=args.limit,
        name=args.name,
        graph_contains=args.graph_contains,
    )

    if args.show_query:
        print("--- SPARQL ---", file=sys.stderr)
        print(sparql, file=sys.stderr)
        print("--- results ---", file=sys.stderr)

    results = execute_sparql(args.endpoint, sparql, timeout=args.timeout)
    columns, rows = bindings_to_rows(results)
    emit(columns, rows, args.format)


def cmd_query(args: argparse.Namespace) -> None:
    """Execute an ad-hoc SPARQL string."""
    sparql = args.sparql
    if not sparql or not sparql.strip():
        print("Error: --sparql must be a non-empty query", file=sys.stderr)
        sys.exit(1)

    if args.show_query:
        print("--- SPARQL ---", file=sys.stderr)
        print(sparql, file=sys.stderr)
        print("--- results ---", file=sys.stderr)

    results = execute_sparql(args.endpoint, sparql, timeout=args.timeout)
    columns, rows = bindings_to_rows(results)
    emit(columns, rows, args.format)


def cmd_file(args: argparse.Namespace) -> None:
    """Execute a SPARQL query from a file path."""
    path = Path(args.query_file)
    if not path.is_file():
        print(f"Error: query file not found: {path}", file=sys.stderr)
        sys.exit(1)

    sparql = path.read_text(encoding="utf-8")
    sparql = apply_params(
        sparql,
        limit=args.limit,
        name=args.name,
        graph_contains=args.graph_contains,
    )

    if args.show_query:
        print("--- SPARQL ---", file=sys.stderr)
        print(sparql, file=sys.stderr)
        print("--- results ---", file=sys.stderr)

    results = execute_sparql(args.endpoint, sparql, timeout=args.timeout)
    columns, rows = bindings_to_rows(results)
    emit(columns, rows, args.format)


def add_endpoint_args(parser: argparse.ArgumentParser) -> None:
    """Shared endpoint / format / timeout flags."""
    parser.add_argument(
        "--endpoint",
        required=True,
        help="SPARQL endpoint URL (e.g. http://localhost:7878/query)",
    )
    parser.add_argument(
        "--format",
        choices=("table", "json", "csv"),
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--show-query",
        action="store_true",
        help="Print the SPARQL sent to the endpoint on stderr",
    )


def add_param_args(parser: argparse.ArgumentParser) -> None:
    """Shared template parameter flags."""
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Replace {{LIMIT}} (default 100 when placeholder present)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Replace {{NAME_FRAGMENT}} (required for dataset_by_name)",
    )
    parser.add_argument(
        "--graph-contains",
        default=None,
        dest="graph_contains",
        help='Inject FILTER(CONTAINS(STR(?g), "...")) for {{GRAPH_FILTER}}',
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build and parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Query a SPARQL endpoint with curated DOOS/schema.org templates "
            "or ad-hoc SPARQL."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List curated query templates")
    p_list.set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="Run a named template from queries/")
    add_endpoint_args(p_run)
    add_param_args(p_run)
    p_run.add_argument(
        "--query",
        required=True,
        help="Template id (see 'list')",
    )
    p_run.set_defaults(func=cmd_run)

    p_query = sub.add_parser("query", help="Run an ad-hoc SPARQL string")
    add_endpoint_args(p_query)
    p_query.add_argument(
        "--sparql",
        required=True,
        help="SPARQL query string",
    )
    p_query.set_defaults(func=cmd_query)

    p_file = sub.add_parser("file", help="Run SPARQL from a .rq file")
    add_endpoint_args(p_file)
    add_param_args(p_file)
    p_file.add_argument(
        "--query-file",
        required=True,
        dest="query_file",
        help="Path to a .rq / .sparql file",
    )
    p_file.set_defaults(func=cmd_file)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    args = parse_args(argv)
    try:
        args.func(args)
    except BrokenPipeError:
        # Allow piping to head
        sys.exit(0)


if __name__ == "__main__":
    main()
