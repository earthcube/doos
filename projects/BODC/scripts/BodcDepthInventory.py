#!/usr/bin/env python3
"""
Parse a BODC Gleaner/OIH N-Quads release and classify depth-profile presence.

Usage:
  python BodcDepthInventory.py
  python BodcDepthInventory.py --input ../bodc_release.nq --output-dir ../output
"""

import argparse
import json
import sys
from pathlib import Path

from bodc_depth import (
    load_graph_records,
    summarize_records,
    write_inventory_csv,
)


def parse_args():
    """Parse command-line arguments."""
    default_input = Path(__file__).resolve().parent.parent / "bodc_release.nq"
    default_output = Path(__file__).resolve().parent.parent / "output"

    parser = argparse.ArgumentParser(
        description="Classify BODC depth profiles from a Gleaner/OIH N-Quads release."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Path to bodc_release.nq (default: ../bodc_release.nq)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help="Directory for depth_inventory.json and depth_inventory.csv",
    )
    return parser.parse_args()


def print_summary(summary):
    """Print a human-readable summary to stderr."""
    graphs = summary["graphs"]
    series = summary["series"]

    print("Graph-level counts:", file=sys.stderr)
    for tier, count in sorted(graphs["by_tier"].items()):
        print(f"  {tier}: {count}", file=sys.stderr)
    print(f"  with DepBelowSurf: {graphs['with_dep_below_surf']}", file=sys.stderr)

    print("Series-level counts (best tier per series_id):", file=sys.stderr)
    print(f"  unique series: {series['unique_count']}", file=sys.stderr)
    for tier, count in sorted(series["by_tier"].items()):
        print(f"  {tier}: {count}", file=sys.stderr)
    print(
        f"  Tier 1 (DepBelowSurf): {series['tier1_count']} "
        f"({series['tier1_pct']}%)",
        file=sys.stderr,
    )
    print(
        f"  Tier 2 only: {series['tier2_only_count']} "
        f"({series['tier2_only_pct']}%)",
        file=sys.stderr,
    )


def main():
    """Load the release file, classify depth tiers, and write inventory outputs."""
    args = parse_args()

    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Loading {args.input} ...", file=sys.stderr)
        records, load_stats = load_graph_records(args.input)
        summary = summarize_records(records)
        summary["load"] = load_stats

        payload = {
            "source": str(args.input),
            "harvest": "Gleaner/OIH 2026-01-18",
            "summary": summary,
            "records": records,
        }
        json_path = args.output_dir / "depth_inventory.json"
        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

        csv_path = write_inventory_csv(args.output_dir, records, "depth_inventory.csv")

        print_summary(summary)
        print(f"Wrote {json_path}", file=sys.stderr)
        print(f"Wrote {csv_path}", file=sys.stderr)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()