#!/usr/bin/env python3
"""
Single-threaded SHACL validator using pyoxigraph for storage.

Example:
    python validateToOxigraph.py http://localhost:7007 ../SHACL/ERDDAP.ttl \
        --output results.nq
"""

import argparse
import sys

import pyoxigraph
from tqdm import tqdm

from defs.getGraphs import query_sparql_endpoint
from defs.getShape import read_shapefile
from defs.getConstruct import construct_graph
from defs.shaclValidator import validate_with_shacl


def main():
    parser = argparse.ArgumentParser(
        description="Run SHACL validation over named graphs from a SPARQL endpoint "
        "and store results in pyoxigraph (N-Quads output)."
    )
    parser.add_argument(
        "endpoint", help="SPARQL endpoint URL (e.g. http://localhost:7007/sparql)"
    )
    parser.add_argument("shapefile", help="SHACL shapes file (local path or URL)")
    parser.add_argument(
        "--output",
        "-o",
        default="results.nq",
        help="Output N-Quads file for validation results (default: results.nq)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only the first N graphs (0 = all). Also pushes LIMIT into the initial SPARQL discovery query when > 0.",
    )
    args = parser.parse_args()

    store = pyoxigraph.Store()

    print(f"Querying SPARQL endpoint: {args.endpoint}")
    print(f"Using shapefile: {args.shapefile}")

    uris = query_sparql_endpoint(
        args.endpoint, endpoint=args.endpoint, limit=args.limit
    )

    if not uris:
        print("No URIs found or query failed.", file=sys.stderr)
        sys.exit(1)

    sf = read_shapefile(args.shapefile)

    # Keep the Python slice as a safety net (SPARQL LIMIT is best-effort for perf).
    if args.limit > 0:
        uris = uris[: args.limit]

    print(f"\nFound {len(uris)} unique URIs. Starting validation...")

    success = 0
    failed = 0

    for uri in tqdm(sorted(uris), desc="Processing URIs"):
        try:
            rdf_text = construct_graph(uri, endpoint=args.endpoint)
            if not rdf_text or not rdf_text.strip():
                print(f"Warning: empty graph for {uri}", file=sys.stderr)
                failed += 1
                continue

            shr = validate_with_shacl(rdf_text, sf)
            if shr:
                store.load(shr, "text/turtle", base_iri=None, to_graph=None)
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"Error processing {uri}: {e}", file=sys.stderr)
            failed += 1

    print(f"\nCompleted. Successful validations: {success}, failures: {failed}")

    try:
        store.dump(args.output, "application/n-quads")
        print(f"Wrote results to {args.output}")
    except Exception as e:
        print(f"Error writing output file {args.output}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
