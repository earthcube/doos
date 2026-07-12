#!/usr/bin/env python3
"""
Unified CLI for BCO-DMO dataset discovery, ERDDAP inventory, and ISO transform.

Subcommands:
    datasets  — Playwright site search (deprecated; prefer ``erddap --search``)
    erddap    — ERDDAP catalog/search inventory builder
    iso       — ISO 19115 depth/pressure scan → schema.org JSON-LD

Examples:
    python main.py erddap --search depth --output scan_results.json
    python main.py iso --input scan_results.json --output iso_summary.json \\
        --output-nt output.nt
    python main.py datasets --keyword depth --output depth_urls.json
"""

import argparse
import sys
from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parent
if str(_ASSETS_DIR) not in sys.path:
    sys.path.insert(0, str(_ASSETS_DIR))

from defs.datasets import run_scan_datasets
from defs.erddap import run_scan_erddap
from defs.iso_measurements import run_scan_iso_measurements
from defs.rdf_export import export_jsonld_to_nt


def _add_datasets_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "datasets",
        help="Search the BCO-DMO website for dataset landing pages (deprecated)",
        description=(
            "Collect BCO-DMO dataset landing page URLs via Playwright site search. "
            "Prefer ``erddap --search`` for keyword discovery."
        ),
    )
    parser.add_argument(
        "--keyword",
        default="depth",
        help="Search keyword (default: depth)",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Write the result JSON to this path",
    )
    parser.add_argument(
        "--urls-output",
        type=Path,
        default=None,
        help="Optional plain-text file with one landing-page URL per line",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show the browser window while scanning",
    )
    parser.add_argument(
        "--print-urls",
        action="store_true",
        help="Echo landing-page URLs to stdout after writing output files",
    )


def _add_erddap_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "erddap",
        help="Build an ERDDAP dataset access inventory",
        description=(
            "Enumerate or search BCO-DMO's ERDDAP catalog and record per-dataset "
            "access routes."
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Write the inventory JSON to this path",
    )
    parser.add_argument(
        "--search",
        default=None,
        metavar="KEYWORD",
        help=(
            "Full-text search ERDDAP metadata instead of fetching the whole "
            'catalog (Google-like syntax: words AND, "phrases", -exclude)'
        ),
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Probe each dataset's access routes for reachability",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N datasets",
    )


def _add_iso_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "iso",
        help="Scan ISO 19115 metadata for depth/pressure variables",
        description=(
            "Read an ERDDAP inventory JSON, fetch ISO 19115 records, and emit "
            "merged N-Triples following the ODIS depth pattern."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="ERDDAP inventory JSON produced by the ``erddap`` subcommand",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Write the summary JSON here",
    )
    parser.add_argument(
        "--output-nt",
        type=Path,
        default=None,
        help="Merged N-Triples path (default: <output-parent>/output.nt)",
    )
    parser.add_argument(
        "--no-nt",
        action="store_true",
        help="Skip writing merged output.nt",
    )
    parser.add_argument(
        "--jsonld-dir",
        type=Path,
        default=None,
        help="Optional directory for per-dataset <datasetID>.jsonld files",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=None,
        help="Optional plain-text findings report",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N datasets from the input",
    )
    parser.add_argument(
        "--print-jsonld",
        action="store_true",
        help="Echo findings and JSON-LD to stdout (in addition to file output)",
    )


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        description="BCO-DMO discovery, ERDDAP inventory, and ISO transform tools"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_datasets_parser(subparsers)
    _add_erddap_parser(subparsers)
    _add_iso_parser(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatch to the selected subcommand."""
    args = build_parser().parse_args(argv)

    try:
        if args.command == "datasets":
            run_scan_datasets(
                args.keyword,
                output=args.output,
                urls_output=args.urls_output,
                headless=not args.no_headless,
                print_urls=args.print_urls,
            )
        elif args.command == "erddap":
            run_scan_erddap(
                output=args.output,
                search=args.search,
                probe=args.probe,
                limit=args.limit,
            )
        elif args.command == "iso":
            iso_result = run_scan_iso_measurements(
                args.input,
                output=args.output,
                jsonld_dir=args.jsonld_dir,
                report_output=args.report_output,
                limit=args.limit,
                print_jsonld=args.print_jsonld,
            )
            if not args.no_nt:
                output_nt = args.output_nt or (args.output.parent / "output.nt")
                documents = [
                    match["jsonld"] for match in iso_result.get("matches", [])
                ]
                export_jsonld_to_nt(documents, output_nt)
        else:
            raise ValueError(f"Unknown command: {args.command}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())