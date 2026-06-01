#!/usr/bin/env python3
"""
Single-threaded SHACL validator using pyrudof (the Python bindings for rudof)
and storing results in pyoxigraph (N-Quads output).

This is the pyrudof/rudof equivalent of validateToOxigraph.py.

Note:
- Use ERDDAP_simple.ttl (or equivalent) — the original ERDDAP.ttl contains
  regex backreferences that rudof cannot parse.
- Some datasets with very long graph URIs can trigger "File name too long"
  errors inside rudof (Linux filename limit). These graphs are skipped with
  a warning. If this affects many of your graphs, consider using PySHACL
  instead for those cases.

Example:
    # Basic run (recommended shapes file)
    python validateToRudof.py \
        http://ghost.lan:7007 \
        ../SHACL/ERDDAP_simple.ttl \
        --output results_rudof.nq \
        --limit 100

    # Skip skolemization
    python validateToRudof.py \
        http://ghost.lan:7007 \
        ../SHACL/ERDDAP_simple.ttl \
        --output results_rudof.nq \
        --limit 50 \
        --no-skolemize
"""

import argparse
import sys

import pyoxigraph
from tqdm import tqdm

from defs.getGraphs import query_sparql_endpoint
from defs.getShape import read_shapefile
from defs.getConstruct import construct_graph


def validate_with_rudof(data_graph_ttl: str, shapes_ttl: str, skolemize: bool = True) -> str:
    """
    Validate a Turtle data graph against Turtle SHACL shapes using pyrudof/rudof.

    The data is loaded into the *default graph* (no named graph is used),
    since your shapes do not appear to require graph-specific targeting.

    Args:
        data_graph_ttl: The data graph in Turtle format.
        shapes_ttl: The SHACL shapes in Turtle format.
        skolemize: Whether to skolemize the validation report with authority
                   "http://gleaner.io" (default: True). Set to False via
                   --no-skolemize to leave blank nodes as-is.

    Returns:
        The validation report serialized as N-Triples (possibly skolemized).
    """
    try:
        from pyrudof import Rudof, RudofConfig, ShaclFormat, RDFFormat, ResultShaclValidationFormat
    except ImportError:
        print(
            "Error: pyrudof is not installed. Install it with: pip install pyrudof",
            file=sys.stderr,
        )
        sys.exit(1)

    rudof = Rudof(RudofConfig())

    # Load shapes fresh for this validation
    rudof.read_shacl(input=shapes_ttl, format=ShaclFormat.Turtle)

    # Load this graph's data into the *default graph* (not a named graph).
    # This avoids potential internal storage issues in rudof when graph URIs are very long.
    rudof.read_data(input=data_graph_ttl, format=RDFFormat.Turtle)

    # Run validation
    rudof.validate_shacl()

    # Get the report as N-Triples
    report_nt = rudof.serialize_shacl_validation_results(
        format=ResultShaclValidationFormat.NTriples
    )

    if skolemize:
        # Skolemize for consistency with the PySHACL pipeline
        try:
            from rdflib import Graph

            g = Graph()
            g.parse(data=report_nt, format="nt")
            skolemized = g.skolemize(authority="http://gleaner.io")
            report_nt = skolemized.serialize(format="nt")
        except Exception:
            # Fall back to raw report if skolemization fails
            pass

    return report_nt


def main():
    parser = argparse.ArgumentParser(
        description="Run SHACL validation over named graphs from a SPARQL endpoint "
        "using pyrudof (rudof) and store results in pyoxigraph (N-Quads output)."
    )
    parser.add_argument("endpoint", help="SPARQL endpoint URL (e.g. http://localhost:7007/sparql)")
    parser.add_argument("shapefile", help="SHACL shapes file (local path or URL)")
    parser.add_argument(
        "--output",
        "-o",
        default="results.nq",
        help="Output N-Quads file for validation results (default: results.nq)",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Process only the first N graphs (0 = all)"
    )
    parser.add_argument(
        "--no-skolemize",
        action="store_true",
        help="Do not skolemize the validation report (leave blank nodes as-is)",
    )
    args = parser.parse_args()

    store = pyoxigraph.Store()

    print(f"Querying SPARQL endpoint: {args.endpoint}")
    print(f"Using shapefile: {args.shapefile}")

    uris = query_sparql_endpoint(args.endpoint, endpoint=args.endpoint)

    if not uris:
        print("No URIs found or query failed.", file=sys.stderr)
        sys.exit(1)

    shapes_ttl = read_shapefile(args.shapefile)

    if args.limit > 0:
        uris = uris[: args.limit]

    print(f"\nFound {len(uris)} unique URIs. Starting validation...")

    success = 0
    failed = 0
    file_name_too_long_count = 0

    for uri in tqdm(sorted(uris), desc="Processing URIs"):
        try:
            rdf_text = construct_graph(uri, endpoint=args.endpoint)
            if not rdf_text or not rdf_text.strip():
                print(f"Warning: empty graph for {uri}", file=sys.stderr)
                failed += 1
                continue

            report_nt = validate_with_rudof(rdf_text, shapes_ttl, skolemize=not args.no_skolemize)

            if report_nt:
                store.load(report_nt, "application/n-triples", base_iri=None, to_graph=None)
                success += 1
            else:
                failed += 1

        except Exception as e:
            error_msg = str(e)
            if "File name too long" in error_msg or "os error 36" in error_msg:
                file_name_too_long_count += 1
                print(
                    "  → Skipped (rudof internal file name too long for this graph URI)",
                    file=sys.stderr,
                )
            else:
                print(f"Error processing {uri}: {e}", file=sys.stderr)
            failed += 1

    if file_name_too_long_count > 0:
        print(
            f"\nNote: {file_name_too_long_count} graphs were skipped because rudof "
            "could not handle the very long graph URIs internally (Linux filename length limit). "
            "This is a known limitation when using pyrudof with certain datasets.",
            file=sys.stderr,
        )

    print(f"\nCompleted. Successful validations: {success}, failures: {failed}")

    try:
        store.dump(args.output, "application/n-quads")
        print(f"Wrote results to {args.output}")
    except Exception as e:
        print(f"Error writing output file {args.output}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
