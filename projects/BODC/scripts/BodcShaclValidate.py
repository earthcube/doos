#!/usr/bin/env python3
"""
Validate BODC N-Quads graphs against the OIH depth-profile SHACL shape.

Runs pyshacl per named graph, records pass/fail, and cross-references depth
tiers from the Phase 1 inventory.

Usage:
  python BodcShaclValidate.py
  python BodcShaclValidate.py --input ../bodc_release.nq
  python BodcShaclValidate.py --input ../output/bodc_harvest.nq
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from rdflib import Dataset
from tqdm import tqdm

from rdflib.namespace import RDF

from bodc_depth import DATASET_URI_RE, SCHEMA, load_release_series_index

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_ROOT = REPO_ROOT / "scripts" / "shapeValidator"
sys.path.insert(0, str(VALIDATOR_ROOT))

from defs.shaclValidator import validate_with_shacl_results  # noqa: E402


def parse_args():
    """Parse command-line arguments."""
    project_root = Path(__file__).resolve().parent.parent
    default_input = project_root / "bodc_release.nq"
    default_output = project_root / "output"
    default_shapes = REPO_ROOT / "SHACL" / "depth_one.ttl"
    default_inventory = default_output / "depth_inventory.json"

    parser = argparse.ArgumentParser(
        description="Validate BODC graphs against SHACL/depth_one.ttl."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="N-Quads file to validate (default: ../bodc_release.nq)",
    )
    parser.add_argument(
        "--shapes",
        type=Path,
        default=default_shapes,
        help="SHACL shapes file (default: repo SHACL/depth_one.ttl)",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=default_inventory,
        help="Depth inventory JSON for tier cross-reference",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help="Directory for shacl_results.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Validate only the first N named graphs (for testing)",
    )
    return parser.parse_args()


def series_id_from_graph(graph):
    """Extract a BODC series ID from Dataset subjects in a graph."""
    for subject in graph.subjects(RDF.type, SCHEMA.Dataset):
        match = DATASET_URI_RE.search(str(subject))
        if match:
            return match.group(1)
    return None


def load_inventory_tiers(inventory_path):
    """
    Load per-series depth tiers from a depth inventory JSON file.

    Returns:
        dict: series_id -> tier string
    """
    if not inventory_path.exists():
        return {}

    index = load_release_series_index(inventory_path)
    return {
        series_id: record.get("tier", "unknown")
        for series_id, record in index.items()
    }


def validate_graphs(nq_path, shapes_text, limit=None):
    """
    Validate each named graph in an N-Quads file.

    Returns:
        list: per-graph validation result dicts
    """
    dataset = Dataset()
    dataset.parse(str(nq_path), format="nquads")

    graphs = list(dataset.graphs())
    if limit is not None:
        graphs = graphs[:limit]

    results = []
    for graph in tqdm(graphs, desc="Validating", unit="graph"):
        graph_uri = str(graph.identifier)
        series_id = series_id_from_graph(graph)

        try:
            ttl = graph.serialize(format="turtle")
            conforms, violations = validate_with_shacl_results(ttl, shapes_text)
            results.append(
                {
                    "series_id": series_id,
                    "graph_uri": graph_uri,
                    "conforms": conforms,
                    "violation_count": len(violations),
                    "violations": violations,
                    "error": None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "series_id": series_id,
                    "graph_uri": graph_uri,
                    "conforms": False,
                    "violation_count": None,
                    "violations": [],
                    "error": str(exc),
                }
            )

    return results


def summarize_results(results, tier_by_series):
    """Build graph-level and series-level SHACL summaries."""
    graph_pass = sum(1 for r in results if r["conforms"])
    graph_fail = sum(1 for r in results if not r["conforms"])
    graph_errors = sum(1 for r in results if r.get("error"))

    series_graphs = defaultdict(list)
    for record in results:
        if record.get("series_id"):
            series_graphs[record["series_id"]].append(record)

    series_pass_any = 0
    series_all_pass = 0
    for series_id, records in series_graphs.items():
        if any(r["conforms"] for r in records):
            series_pass_any += 1
        if records and all(r["conforms"] for r in records):
            series_all_pass += 1

    by_tier = defaultdict(lambda: {"count": 0, "shacl_pass": 0})
    for series_id, records in series_graphs.items():
        tier = tier_by_series.get(series_id, "unknown")
        by_tier[tier]["count"] += 1
        if any(r["conforms"] for r in records):
            by_tier[tier]["shacl_pass"] += 1

    tier_summary = {}
    for tier, counts in sorted(by_tier.items()):
        count = counts["count"]
        passed = counts["shacl_pass"]
        tier_summary[tier] = {
            "series_count": count,
            "shacl_pass": passed,
            "pass_pct": round(100 * passed / count, 1) if count else 0.0,
        }

    unique_series = len(series_graphs)
    return {
        "graphs": {
            "total": len(results),
            "pass": graph_pass,
            "fail": graph_fail,
            "errors": graph_errors,
            "pass_pct": round(100 * graph_pass / len(results), 1) if results else 0.0,
        },
        "series": {
            "unique_count": unique_series,
            "pass_any_graph": series_pass_any,
            "pass_all_graphs": series_all_pass,
            "pass_any_pct": round(100 * series_pass_any / unique_series, 1)
            if unique_series
            else 0.0,
        },
        "by_depth_tier": tier_summary,
    }


def attach_depth_tiers(results, tier_by_series):
    """Add depth tier from inventory to each result record."""
    for record in results:
        series_id = record.get("series_id")
        record["depth_tier"] = tier_by_series.get(series_id, "unknown")
    return results


def write_results(output_dir, payload):
    """Write shacl_results.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "shacl_results.json"
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return out_path


def print_summary(summary):
    """Print SHACL summary to stderr."""
    graphs = summary["graphs"]
    series = summary["series"]

    print("Graph-level SHACL (depth_one.ttl):", file=sys.stderr)
    print(f"  total: {graphs['total']}", file=sys.stderr)
    print(f"  pass: {graphs['pass']} ({graphs['pass_pct']}%)", file=sys.stderr)
    print(f"  fail: {graphs['fail']}", file=sys.stderr)
    if graphs["errors"]:
        print(f"  errors: {graphs['errors']}", file=sys.stderr)

    print("Series-level SHACL:", file=sys.stderr)
    print(f"  unique series: {series['unique_count']}", file=sys.stderr)
    print(
        f"  pass (any graph): {series['pass_any_graph']} "
        f"({series['pass_any_pct']}%)",
        file=sys.stderr,
    )
    print(f"  pass (all graphs): {series['pass_all_graphs']}", file=sys.stderr)

    if summary.get("by_depth_tier"):
        print("SHACL pass rate by depth tier:", file=sys.stderr)
        for tier, stats in summary["by_depth_tier"].items():
            print(
                f"  {tier}: {stats['shacl_pass']}/{stats['series_count']} "
                f"({stats['pass_pct']}%)",
                file=sys.stderr,
            )


def main():
    """Validate BODC N-Quads graphs and write shacl_results.json."""
    args = parse_args()

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not args.shapes.exists():
        print(f"Error: shapes file not found: {args.shapes}", file=sys.stderr)
        sys.exit(1)

    try:
        shapes_text = args.shapes.read_text(encoding="utf-8")
        tier_by_series = load_inventory_tiers(args.inventory)

        print(f"Validating {args.input} against {args.shapes} ...", file=sys.stderr)
        results = validate_graphs(args.input, shapes_text, limit=args.limit)
        results = attach_depth_tiers(results, tier_by_series)
        summary = summarize_results(results, tier_by_series)

        payload = {
            "source": str(args.input),
            "shapes": str(args.shapes),
            "inventory": str(args.inventory) if args.inventory.exists() else None,
            "summary": summary,
            "results": results,
        }

        out_path = write_results(args.output_dir, payload)
        print_summary(summary)
        print(f"Wrote {out_path}", file=sys.stderr)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()