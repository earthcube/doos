#!/usr/bin/env python3
"""BCO-DMO indexer facade: run the skill pipeline and publish output.nt.

Does not reimplement ERDDAP inventory or ISO mapping. Subprocesses
``skills/DOOS_bundle/doos-bco-dmo-index/assets/run_pipeline.py``, then copies
the run's ``output.nt`` to ``projects/BCO-DMO/output/output.nt``.

Usage:
    python projects/BCO-DMO/run_pipeline.py --search depth --limit 5
    python projects/BCO-DMO/run_pipeline.py --catalog --limit 10
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
SKILL_SCRIPT = (
    REPO_ROOT
    / "skills"
    / "DOOS_bundle"
    / "doos-bco-dmo-index"
    / "assets"
    / "run_pipeline.py"
)
PUBLISH_PATH = PROJECT_DIR / "output" / "output.nt"


def default_work_dir() -> Path:
    """Return a timestamped run directory under this project's runs/ folder."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_DIR / "runs" / stamp


def build_parser() -> argparse.ArgumentParser:
    """Construct the facade argument parser (same flags as the skill CLI)."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the BCO-DMO skill pipeline and publish output.nt "
            "for Oxigraph load."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--search",
        metavar="KEYWORD",
        help="ERDDAP full-text search term (skill default when omitted: depth)",
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
        help="Run directory (default: projects/BCO-DMO/runs/<UTC-stamp>)",
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
        help="Skip writing merged output.nt (also skips publish)",
    )
    parser.add_argument(
        "--write-jsonld",
        action="store_true",
        help="Also write per-dataset JSON-LD files under jsonld/",
    )
    parser.add_argument(
        "--publish",
        type=Path,
        default=PUBLISH_PATH,
        help=f"Published N-Triples path (default: {PUBLISH_PATH})",
    )
    return parser


def skill_argv(args: argparse.Namespace, work_dir: Path) -> list[str]:
    """Build argv for the skill CLI. Omits --search/--catalog when unset."""
    argv: list[str] = ["--work-dir", str(work_dir)]
    if args.catalog:
        argv.append("--catalog")
    elif args.search is not None:
        argv.extend(["--search", args.search])
    if args.probe:
        argv.append("--probe")
    if args.limit is not None:
        argv.extend(["--limit", str(args.limit)])
    if args.no_report:
        argv.append("--no-report")
    if args.no_nt:
        argv.append("--no-nt")
    if args.write_jsonld:
        argv.append("--write-jsonld")
    return argv


def publish_output(work_dir: Path, publish_path: Path) -> None:
    """Copy the run's output.nt to the published path."""
    source = work_dir / "output.nt"
    if not source.is_file():
        raise FileNotFoundError(f"Skill run did not write {source}")
    publish_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, publish_path)
    print(f"Published {publish_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)
    if not SKILL_SCRIPT.is_file():
        print(f"Error: skill pipeline not found: {SKILL_SCRIPT}", file=sys.stderr)
        return 1

    work_dir = (args.work_dir or default_work_dir()).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(SKILL_SCRIPT), *skill_argv(args, work_dir)]

    try:
        completed = subprocess.run(command, cwd=REPO_ROOT)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if completed.returncode != 0:
        return completed.returncode

    if args.no_nt:
        return 0

    try:
        publish_output(work_dir, args.publish.resolve())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
