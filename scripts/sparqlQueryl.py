#!/usr/bin/env python3
"""
Execute a SPARQL query file against an endpoint and print results as a DataFrame.

Usage:
  python sparqlQueryl.py
  python sparqlQueryl.py https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans
  python sparqlQueryl.py <endpoint> --query ../SPARQL/depthAssay.rq
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUERY = REPO_ROOT / "SPARQL" / "varMes_bodc.rq"
DEFAULT_ENDPOINT = (
    "https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans"
)


def sparql_to_dataframe(endpoint: str, query: str) -> pd.DataFrame:
    """
    Execute a SPARQL query against an endpoint and return results as a DataFrame.

    Args:
        endpoint: SPARQL endpoint URL
        query: SPARQL query string

    Returns:
        DataFrame with SPARQL variables as column headers
    """
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)

    results = sparql.query().convert()

    columns = results["head"]["vars"]
    rows = []

    for binding in results["results"]["bindings"]:
        row = {var: binding.get(var, {}).get("value", None) for var in columns}
        rows.append(row)

    return pd.DataFrame(rows, columns=columns)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a SPARQL query file against an endpoint."
    )
    parser.add_argument(
        "endpoint",
        nargs="?",
        default=DEFAULT_ENDPOINT,
        help=f"SPARQL endpoint URL (default: {DEFAULT_ENDPOINT})",
    )
    parser.add_argument(
        "--query",
        type=Path,
        default=DEFAULT_QUERY,
        help=f"SPARQL query file (default: {DEFAULT_QUERY.relative_to(REPO_ROOT)})",
    )
    return parser.parse_args()


def main():
    """Load a query file, execute it, and print the result DataFrame."""
    args = parse_args()

    if not args.query.exists():
        print(f"Error: query file not found: {args.query}", file=sys.stderr)
        sys.exit(1)

    try:
        query = args.query.read_text(encoding="utf-8")
        df = sparql_to_dataframe(args.endpoint, query)
        print(df)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
