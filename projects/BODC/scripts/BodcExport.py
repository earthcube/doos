#!/usr/bin/env python3
"""
Export SHACL-validated BODC graphs to a federated-load-ready N-Quads file.

Selects one passing graph per series from shacl_results.json and copies those
named graphs from the source release into bodc_validated.nq.

Usage:
  python BodcExport.py
  python BodcExport.py --input ../bodc_release.nq --shacl ../output/shacl_results.json
"""

import argparse
import json
import sys
from pathlib import Path

import pyoxigraph
from pyoxigraph import NamedNode
from tqdm import tqdm


def parse_args():
    """Parse command-line arguments."""
    project_root = Path(__file__).resolve().parent.parent
    default_input = project_root / "bodc_release.nq"
    default_shacl = project_root / "output" / "shacl_results.json"
    default_output = project_root / "output"

    parser = argparse.ArgumentParser(
        description="Export SHACL-validated BODC graphs to bodc_validated.nq."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Source N-Quads file (default: ../bodc_release.nq)",
    )
    parser.add_argument(
        "--shacl",
        type=Path,
        default=default_shacl,
        help="SHACL results JSON from BodcShaclValidate.py",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help="Output directory (default: ../output)",
    )
    return parser.parse_args()


def select_export_graphs(shacl_results):
    """
    Pick one passing graph URI per series (deterministic: lexicographically first).

    Returns:
        tuple: (series_id -> graph_uri dict, list of graph URIs)
    """
    passing_by_series = {}
    for record in shacl_results.get("results", []):
        if not record.get("conforms"):
            continue
        series_id = record.get("series_id")
        graph_uri = record.get("graph_uri")
        if not series_id or not graph_uri:
            continue

        current = passing_by_series.get(series_id)
        if current is None or graph_uri < current:
            passing_by_series[series_id] = graph_uri

    graph_uris = sorted(set(passing_by_series.values()))
    return passing_by_series, graph_uris


def export_graphs(source_nq, graph_uris, output_nq):
    """
    Copy selected named graphs from source N-Quads into a new store.

    Returns:
        int: number of quads exported
    """
    source = pyoxigraph.Store()
    source.bulk_load(source_nq, "application/n-quads")

    target = pyoxigraph.Store()
    quad_count = 0

    for graph_uri in tqdm(graph_uris, desc="Exporting", unit="graph"):
        graph_node = NamedNode(graph_uri)
        for quad in source.quads_for_pattern(None, None, None, graph_node):
            target.add(quad)
            quad_count += 1

    target.dump(output_nq, "application/n-quads")
    return quad_count


def write_manifest(output_dir, source_nq, shacl_path, series_graphs, quad_count):
    """Write export_manifest.json describing the validated export."""
    manifest = {
        "source": str(source_nq),
        "shacl_results": str(shacl_path),
        "output": str(output_dir / "bodc_validated.nq"),
        "series_count": len(series_graphs),
        "graph_count": len(set(series_graphs.values())),
        "quad_count": quad_count,
        "series_graphs": [
            {"series_id": series_id, "graph_uri": graph_uri}
            for series_id, graph_uri in sorted(series_graphs.items(), key=lambda x: int(x[0]))
        ],
    }
    out_path = output_dir / "export_manifest.json"
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return out_path


def main():
    """Export validated BODC graphs for federated SPARQL loading."""
    args = parse_args()

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not args.shacl.exists():
        print(f"Error: SHACL results not found: {args.shacl}", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_nq = args.output_dir / "bodc_validated.nq"

    try:
        shacl_results = json.loads(args.shacl.read_text(encoding="utf-8"))
        series_graphs, graph_uris = select_export_graphs(shacl_results)

        if not graph_uris:
            print("Error: no passing graphs found in SHACL results", file=sys.stderr)
            sys.exit(1)

        print(
            f"Exporting {len(graph_uris)} graphs ({len(series_graphs)} series) "
            f"from {args.input} ...",
            file=sys.stderr,
        )
        quad_count = export_graphs(args.input, graph_uris, output_nq)
        manifest_path = write_manifest(
            args.output_dir,
            args.input,
            args.shacl,
            series_graphs,
            quad_count,
        )

        print(f"Exported {quad_count} quads", file=sys.stderr)
        print(f"Wrote {output_nq}", file=sys.stderr)
        print(f"Wrote {manifest_path}", file=sys.stderr)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()