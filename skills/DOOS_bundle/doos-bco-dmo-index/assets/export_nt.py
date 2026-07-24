#!/usr/bin/env python3
"""
Build a merged output.nt from existing JSON-LD files.

Usage:
    python export_nt.py --jsonld-dir ../output --output ../output/output.nt
    python export_nt.py --iso-summary runs/<ts>/iso_summary.json --output output.nt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ASSETS_DIR = Path(__file__).resolve().parent
if str(_ASSETS_DIR) not in sys.path:
    sys.path.insert(0, str(_ASSETS_DIR))

from defs.rdf_export import export_jsonld_paths_to_nt, export_jsonld_to_nt


def documents_from_iso_summary(path: Path) -> list[dict]:
    """Extract JSON-LD documents embedded in an iso_summary.json file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [match["jsonld"] for match in data.get("matches", []) if match.get("jsonld")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Merge JSON-LD files into a single N-Triples output"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--jsonld-dir",
        type=Path,
        help="Directory of per-dataset .jsonld files",
    )
    source.add_argument(
        "--iso-summary",
        type=Path,
        help="iso_summary.json with embedded JSON-LD matches",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Merged N-Triples output path",
    )
    args = parser.parse_args(argv)

    try:
        if args.jsonld_dir:
            paths = sorted(args.jsonld_dir.glob("*.jsonld"))
            if not paths:
                print(f"Error: no .jsonld files in {args.jsonld_dir}", file=sys.stderr)
                return 1
            export_jsonld_paths_to_nt(paths, args.output)
        else:
            documents = documents_from_iso_summary(args.iso_summary)
            if not documents:
                print(
                    f"Error: no JSON-LD matches in {args.iso_summary}",
                    file=sys.stderr,
                )
                return 1
            export_jsonld_to_nt(documents, args.output)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())