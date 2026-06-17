#!/usr/bin/env python3
"""
Verify BODC depth data is queryable locally and on the federated SPARQL endpoint.

Runs SPARQL/varMes_bodc.rq against a local validated N-Quads file and optionally
against the live deepoceans QLever endpoint. Reports Geocodes search UI status.

Usage:
  python BodcVerifyFederation.py
  python BodcVerifyFederation.py --endpoint https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans
  python BodcVerifyFederation.py --local ../output/bodc_validated.nq --skip-remote
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pyoxigraph
from SPARQLWrapper import SPARQLWrapper, JSON

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_QUERY = REPO_ROOT / "SPARQL" / "varMes_bodc.rq"
DEFAULT_ENDPOINT = (
    "https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans"
)
DEFAULT_SEARCH_UI = "https://qlever-test.geocodes-aws-dev.earthcube.org/"
USER_AGENT = "DOOS-BODC-Verify/1.0"


def parse_args():
    """Parse command-line arguments."""
    project_root = Path(__file__).resolve().parent.parent
    default_local = project_root / "output" / "bodc_validated.nq"
    default_report = project_root / "output" / "federation_verify.json"

    parser = argparse.ArgumentParser(
        description="Verify BODC DepBelowSurf data via SPARQL and search UI."
    )
    parser.add_argument(
        "--local",
        type=Path,
        default=default_local,
        help="Local N-Quads file to query (default: ../output/bodc_validated.nq)",
    )
    parser.add_argument(
        "--query",
        type=Path,
        default=DEFAULT_QUERY,
        help="SPARQL query file (default: repo SPARQL/varMes_bodc.rq)",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="Federated SPARQL endpoint URL",
    )
    parser.add_argument(
        "--search-ui",
        default=DEFAULT_SEARCH_UI,
        help="Geocodes search UI base URL to check availability",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_report,
        help="Verification report JSON path",
    )
    parser.add_argument(
        "--skip-remote",
        action="store_true",
        help="Skip federated endpoint and search UI checks",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of sample rows to include in the report",
    )
    return parser.parse_args()


def load_query(query_path):
    """Read a SPARQL query from disk."""
    return query_path.read_text(encoding="utf-8")


def select_variables(query):
    """Extract SELECT variable names from a SPARQL query string."""
    match = re.search(r"SELECT\s+(?:DISTINCT\s+)?(.+?)\s+WHERE", query, re.I | re.S)
    if not match:
        return []
    return [
        part.strip().lstrip("?")
        for part in match.group(1).split()
        if part.strip().startswith("?")
    ]


def bindings_to_rows(results):
    """Convert SPARQL JSON bindings to plain dict rows."""
    columns = results["head"]["vars"]
    rows = []
    for binding in results["results"]["bindings"]:
        rows.append(
            {var: binding.get(var, {}).get("value") for var in columns}
        )
    return rows


def query_remote(endpoint, query):
    """
    Execute a SPARQL SELECT against a remote endpoint.

    Returns:
        tuple: (row_count, sample_rows, error or None)
    """
    try:
        client = SPARQLWrapper(endpoint)
        client.setQuery(query)
        client.setReturnFormat(JSON)
        results = client.query().convert()
        rows = bindings_to_rows(results)
        return len(rows), rows, None
    except Exception as exc:
        return 0, [], str(exc)


def query_local(nq_path, query):
    """
    Execute a SPARQL SELECT against a local N-Quads file.

    Returns:
        tuple: (row_count, sample_rows, error or None)
    """
    try:
        store = pyoxigraph.Store()
        store.bulk_load(nq_path, "application/n-quads")
        columns = select_variables(query)
        rows = []

        for solution in store.query(query):
            row = {}
            for var in columns:
                value = solution[var]
                row[var] = str(value) if value is not None else None
            rows.append(row)

        return len(rows), rows, None
    except Exception as exc:
        return 0, [], str(exc)


def check_search_ui(base_url):
    """
    Check whether the Geocodes search UI responds.

    Returns:
        dict: status report
    """
    try:
        req = Request(base_url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=30) as response:
            status = response.status
            return {
                "url": base_url,
                "reachable": True,
                "http_status": status,
                "note": "Search UI reachable; query 'bodc' manually to confirm records.",
            }
    except HTTPError as exc:
        return {
            "url": base_url,
            "reachable": False,
            "http_status": exc.code,
            "error": str(exc),
        }
    except URLError as exc:
        return {
            "url": base_url,
            "reachable": False,
            "http_status": None,
            "error": str(exc),
        }


def count_bodc_graphs_remote(endpoint):
    """Count distinct BODC named graphs on the federated endpoint."""
    query = """
    SELECT (COUNT(DISTINCT ?g) AS ?count) WHERE {
      GRAPH ?g { ?s a <https://schema.org/Dataset> }
      FILTER(CONTAINS(LCASE(STR(?g)), "bodc"))
    }
    """
    _, rows, error = query_remote(endpoint, query)
    if error:
        return {"count": None, "error": error}
    if not rows:
        return {"count": 0}
    return {"count": int(rows[0].get("count", 0))}


def build_report(args, query_text, local_result, remote_result, search_status, bodc_graph_count):
    """Assemble the verification report payload."""
    local_count, local_rows, local_error = local_result
    remote_count, remote_rows, remote_error = remote_result

    report = {
        "query_file": str(args.query),
        "local": {
            "file": str(args.local),
            "available": args.local.exists(),
            "result_count": local_count,
            "sample": local_rows[: args.limit],
            "error": local_error,
            "passed": local_count > 0 and local_error is None,
        },
        "remote": {
            "endpoint": args.endpoint,
            "skipped": args.skip_remote,
            "bodc_graph_count": bodc_graph_count,
            "result_count": remote_count,
            "sample": remote_rows[: args.limit],
            "error": remote_error,
            "passed": remote_count > 0 and remote_error is None,
        },
        "search_ui": search_status,
        "load_instructions": {
            "file": str(args.local),
            "tool": "scripts/SPARQLupdate/insertUpdates.py",
            "example": (
                "python scripts/SPARQLupdate/insertUpdates.py "
                f"--token <TOKEN> --endpoint <UPDATE_ENDPOINT> "
                f"--file {args.local} --format nquads"
            ),
            "note": (
                "BODC is not yet present on the federated endpoint. "
                "Load bodc_validated.nq, then re-run this script."
            ),
        },
    }

    report["passed"] = report["local"]["passed"] and (
        args.skip_remote or report["remote"]["passed"]
    )
    return report


def print_report(report):
    """Print verification summary to stderr."""
    local = report["local"]
    remote = report["remote"]

    print("Local SPARQL (bodc_validated.nq):", file=sys.stderr)
    if not local["available"]:
        print(f"  file missing: {local['file']}", file=sys.stderr)
    elif local["error"]:
        print(f"  error: {local['error']}", file=sys.stderr)
    else:
        print(f"  DepBelowSurf rows: {local['result_count']}", file=sys.stderr)
        for row in local["sample"][:3]:
            print(f"    min={row.get('minValue')} max={row.get('maxValue')}", file=sys.stderr)

    if not remote["skipped"]:
        print("Federated SPARQL:", file=sys.stderr)
        print(f"  endpoint: {remote['endpoint']}", file=sys.stderr)
        print(f"  bodc graphs: {remote['bodc_graph_count']}", file=sys.stderr)
        if remote["error"]:
            print(f"  error: {remote['error']}", file=sys.stderr)
        else:
            print(f"  DepBelowSurf rows: {remote['result_count']}", file=sys.stderr)

    search = report["search_ui"]
    if search:
        print("Search UI:", file=sys.stderr)
        print(f"  {search['url']} -> HTTP {search.get('http_status', 'n/a')}", file=sys.stderr)

    if remote["bodc_graph_count"] == 0 and not remote["skipped"]:
        print(report["load_instructions"]["note"], file=sys.stderr)


def main():
    """Run local and remote federation verification checks."""
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    if not args.query.exists():
        print(f"Error: query file not found: {args.query}", file=sys.stderr)
        sys.exit(1)

    try:
        query_text = load_query(args.query)

        if args.local.exists():
            local_result = query_local(args.local, query_text)
        else:
            local_result = (0, [], f"file not found: {args.local}")

        if args.skip_remote:
            remote_result = (0, [], None)
            bodc_graph_count = None
            search_status = None
        else:
            remote_result = query_remote(args.endpoint, query_text)
            bodc_count_info = count_bodc_graphs_remote(args.endpoint)
            bodc_graph_count = bodc_count_info.get("count")
            search_status = check_search_ui(args.search_ui)

        report = build_report(
            args,
            query_text,
            local_result,
            remote_result,
            search_status,
            bodc_graph_count,
        )

        with args.output.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

        print_report(report)
        print(f"Wrote {args.output}", file=sys.stderr)

        if not report["local"]["passed"]:
            sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()