#!/usr/bin/env python3
"""
Run the full BCO-DMO indexing pipeline: ERDDAP inventory → ISO depth scan → output.nt.

Used by the bco-dmo-scan skill. Writes all outputs under a single work directory
and emits a run.json manifest.

Usage:
    python run_pipeline.py --search depth --work-dir ../runs/20260618-120000
    python run_pipeline.py --catalog --work-dir ../runs/full-catalog --limit 10
    python run_pipeline.py --search "dissolved oxygen depth" --probe --limit 5
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parent
if str(_ASSETS_DIR) not in sys.path:
    sys.path.insert(0, str(_ASSETS_DIR))

from defs.common import log, write_json
from defs.erddap import run_scan_erddap
from defs.iso_measurements import run_scan_iso_measurements
from defs.rdf_export import export_jsonld_to_nt

SKILL_ROOT = _ASSETS_DIR.parent


def default_work_dir() -> Path:
    """Return a timestamped run directory under the skill's runs/ folder."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return SKILL_ROOT / "runs" / stamp


def run_pipeline(
    *,
    work_dir: Path,
    search: str | None = None,
    catalog: bool = False,
    probe: bool = False,
    limit: int | None = None,
    write_report: bool = True,
    write_nt: bool = True,
    write_jsonld: bool = False,
) -> dict:
    """
    Execute ERDDAP inventory + ISO depth scan and write a run manifest.

    Args:
        work_dir: Output root for inventory.json, iso_summary.json, output.nt, run.json
        search: ERDDAP full-text search term (mutually exclusive with catalog)
        catalog: Enumerate the full ERDDAP catalog instead of searching
        probe: Probe each dataset's access routes for reachability
        limit: Cap datasets at both pipeline stages
        write_report: Write report.txt with plain-text findings
        write_nt: Merge match JSON-LD into output.nt via pyoxigraph
        write_jsonld: Also write per-dataset files under jsonld/

    Returns:
        dict: Run manifest written to work_dir/run.json
    """
    if catalog and search:
        raise ValueError("Use either --search or --catalog, not both.")

    work_dir = work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    inventory_path = work_dir / "inventory.json"
    iso_summary_path = work_dir / "iso_summary.json"
    output_nt_path = work_dir / "output.nt"
    jsonld_dir = work_dir / "jsonld" if write_jsonld else None
    report_path = work_dir / "report.txt" if write_report else None

    started_at = datetime.now(timezone.utc).isoformat()

    inventory = run_scan_erddap(
        output=inventory_path,
        search=None if catalog else search,
        probe=probe,
        limit=limit,
    )

    iso_result = run_scan_iso_measurements(
        inventory_path,
        output=iso_summary_path,
        jsonld_dir=jsonld_dir,
        report_output=report_path,
        limit=limit,
    )

    nt_stats = None
    if write_nt:
        documents = [match["jsonld"] for match in iso_result.get("matches", [])]
        nt_stats = export_jsonld_to_nt(documents, output_nt_path)

    finished_at = datetime.now(timezone.utc).isoformat()

    manifest = {
        "skill": "bco-dmo-scan",
        "started_at": started_at,
        "finished_at": finished_at,
        "parameters": {
            "search": search,
            "catalog": catalog,
            "probe": probe,
            "limit": limit,
            "write_report": write_report,
            "write_nt": write_nt,
            "write_jsonld": write_jsonld,
        },
        "work_dir": str(work_dir),
        "outputs": {
            "inventory": str(inventory_path),
            "iso_summary": str(iso_summary_path),
            "output_nt": str(output_nt_path) if write_nt else None,
            "jsonld_dir": str(jsonld_dir) if jsonld_dir else None,
            "report": str(report_path) if report_path else None,
            "manifest": str(work_dir / "run.json"),
        },
        "counts": {
            "inventory_datasets": inventory.get("count", 0),
            "scanned": iso_result.get("scanned", 0),
            "depth_matches": iso_result.get("match_count", 0),
            "triples": nt_stats.get("triple_count") if nt_stats else 0,
        },
        "matches": [
            {
                "datasetID": m["datasetID"],
                "title": m.get("title"),
                "jsonld_file": m.get("jsonld_file"),
            }
            for m in iso_result.get("matches", [])
        ],
    }

    manifest_path = work_dir / "run.json"
    write_json(manifest_path, manifest)
    log(f"\nPipeline complete. Manifest: {manifest_path}")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    """Construct the run_pipeline argument parser."""
    parser = argparse.ArgumentParser(
        description="Run the BCO-DMO ERDDAP → ISO depth scan → N-Triples pipeline"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--search",
        metavar="KEYWORD",
        help="ERDDAP full-text search term (default when neither flag is set: depth)",
    )
    mode.add_argument(
        "--catalog",
        action="store_true",
        help="Enumerate the full ERDDAP catalog instead of keyword search",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Output directory (default: skills/bco-dmo-scan/runs/<timestamp>)",
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
        help="Only process the first N datasets at each stage",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip writing report.txt",
    )
    parser.add_argument(
        "--no-nt",
        action="store_true",
        help="Skip writing merged output.nt",
    )
    parser.add_argument(
        "--write-jsonld",
        action="store_true",
        help="Also write per-dataset JSON-LD files under jsonld/",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)
    work_dir = args.work_dir or default_work_dir()
    search = args.search
    if not args.catalog and search is None:
        search = "depth"

    try:
        run_pipeline(
            work_dir=work_dir,
            search=search,
            catalog=args.catalog,
            probe=args.probe,
            limit=args.limit,
            write_report=not args.no_report,
            write_nt=not args.no_nt,
            write_jsonld=args.write_jsonld,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())