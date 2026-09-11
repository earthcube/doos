#!/usr/bin/env python3
"""Wrapper CLI over existing DOOS provider graph generators.

Does not reimplement ingest, transform, or serialization. Each provider is an
existing project script invoked as a subprocess.

Usage:
    PYTHONPATH=src python -m doos_pipeline list
    PYTHONPATH=src python -m doos_pipeline run --provider aodn
    PYTHONPATH=src python -m doos_pipeline run --provider aodn -- --uuid <uuid>
    PYTHONPATH=src python -m doos_pipeline run --all
    PYTHONPATH=src python -m doos_pipeline validate --provider bodc
    PYTHONPATH=src python -m doos_pipeline report --provider cchdo
    PYTHONPATH=src python -m doos_pipeline load -- --wait
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG, repo_root
from .providers.registry import get_provider, load_providers
from .report import (
    build_report,
    build_report_set,
    report_summary_line,
    write_report,
)
from .runner import (
    default_work_dir,
    output_status,
    run_provider,
    strip_forwarded,
    write_manifest,
)
from .shacl import validate_provider_outputs


def _print_json(data) -> None:
    print(json.dumps(data, indent=2))


def cmd_list(args: argparse.Namespace) -> int:
    root = repo_root()
    _raw, providers = load_providers(args.config)
    rows = []
    for name, provider in providers.items():
        outputs = output_status(root, provider)
        rows.append(
            {
                "name": name,
                "status": provider.status,
                "runnable": provider.runnable,
                "run_on_all": provider.run_on_all,
                "description": provider.description,
                "cwd": str(provider.resolve_cwd(root)),
                "steps": [step.name for step in provider.steps],
                "default_steps": list(provider.default_steps)
                or [step.name for step in provider.steps],
                "graph": provider.graph,
                "outputs": outputs,
            }
        )
    if args.json:
        _print_json(rows)
        return 0

    name_w = max((len(r["name"]) for r in rows), default=8)
    print(
        f"{'provider':<{name_w}}  {'run':<4}  {'all':<4}  {'status':<16}  "
        f"{'steps':<28}  output exists"
    )
    for row in rows:
        exists = any(item["exists"] for item in row["outputs"])
        run = "yes" if row["runnable"] else "no"
        on_all = "yes" if row["run_on_all"] else "no"
        steps = ",".join(row["default_steps"]) or "-"
        print(
            f"{row['name']:<{name_w}}  {run:<4}  {on_all:<4}  "
            f"{row['status']:<16}  {steps:<28}  {'yes' if exists else 'no'}"
        )
        print(f"  {row['description']}")
    return 0


def _work_dir(args: argparse.Namespace, raw: dict, root: Path) -> Path:
    if args.work_dir:
        return Path(args.work_dir).resolve()
    return default_work_dir(root, raw.get("runs_dir") or "runs/doos_pipeline")


def cmd_run(args: argparse.Namespace) -> int:
    root = repo_root()
    raw, providers = load_providers(args.config)
    forwarded = strip_forwarded(args.forward)
    work_dir = _work_dir(args, raw, root)

    if args.all:
        names = [
            name
            for name, provider in providers.items()
            if provider.runnable
            and (provider.run_on_all or args.include_heavy)
        ]
        if not names:
            print("No runnable providers selected.", file=sys.stderr)
            return 1
        if forwarded:
            print(
                "Extra args after -- cannot be used with --all "
                "(providers do not share a CLI).",
                file=sys.stderr,
            )
            return 1
    else:
        if not args.provider:
            print("Provide --provider NAME or --all.", file=sys.stderr)
            return 2
        names = [args.provider]

    overall = 0
    summaries = []
    for name in names:
        try:
            provider = get_provider(name, providers)
        except KeyError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        if not provider.runnable:
            print(
                f"Error: provider {name!r} is not a transform pipeline "
                f"({provider.status}).",
                file=sys.stderr,
            )
            return 2
        try:
            steps = provider.selected_steps(args.step)
            provider_dir = work_dir / name if args.all else work_dir
            manifest = run_provider(
                root=root,
                provider=provider,
                steps=steps,
                forwarded=forwarded,
                work_dir=provider_dir,
                dry_run=args.dry_run,
            )
        except (KeyError, ValueError, FileNotFoundError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        summaries.append(manifest)
        print(f"[{name}] exit {manifest['exit_code']}  manifest {manifest['manifest']}")
        if not args.dry_run and not args.no_report:
            document = build_report(
                root=root,
                provider=provider,
                work_dir=provider_dir,
                manifest=manifest,
                max_files=args.max_files,
            )
            report_path = write_report(document, provider_dir / "report.jsonld")
            print(f"[{name}] report {report_path}  {report_summary_line(document)}")
            manifest["report"] = str(report_path)
        if manifest["exit_code"] != 0:
            overall = manifest["exit_code"]

    if args.all:
        bundle = {
            "wrapper": "doos_pipeline",
            "mode": "all",
            "include_heavy": args.include_heavy,
            "dry_run": args.dry_run,
            "providers": [m["provider"] for m in summaries],
            "exit_code": overall,
            "runs": [
                {
                    "provider": m["provider"],
                    "manifest": m["manifest"],
                    "report": m.get("report"),
                    "exit_code": m["exit_code"],
                }
                for m in summaries
            ],
        }
        write_manifest(work_dir, bundle)
        if not args.dry_run and not args.no_report:
            parts = []
            for name in names:
                part_path = (work_dir / name / "report.jsonld")
                if part_path.is_file():
                    parts.append(json.loads(part_path.read_text(encoding="utf-8")))
            if parts:
                set_doc = build_report_set(parts, work_dir)
                set_path = write_report(set_doc, work_dir / "report.jsonld")
                print(f"[all] report {set_path}")
    return overall


def cmd_report(args: argparse.Namespace) -> int:
    """Write JSON-LD metrics for published outputs (no generator run)."""
    root = repo_root()
    raw, providers = load_providers(args.config)
    work_dir = _work_dir(args, raw, root)

    if args.all:
        names = [name for name, provider in providers.items() if provider.runnable]
    else:
        if not args.provider:
            print("Provide --provider NAME or --all.", file=sys.stderr)
            return 2
        names = [args.provider]

    parts = []
    for name in names:
        try:
            provider = get_provider(name, providers)
        except KeyError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        provider_dir = work_dir / name if args.all else work_dir
        document = build_report(
            root=root,
            provider=provider,
            work_dir=provider_dir,
            manifest=None,
            max_files=args.max_files,
        )
        if args.output and not args.all:
            path = Path(args.output)
        else:
            path = provider_dir / "report.jsonld"
        write_report(document, path)
        print(f"[{name}] report {path}  {report_summary_line(document)}")
        parts.append(document)

    if args.all:
        set_doc = build_report_set(parts, work_dir)
        set_path = Path(args.output) if args.output else work_dir / "report.jsonld"
        write_report(set_doc, set_path)
        print(f"[all] report {set_path}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root = repo_root()
    raw, providers = load_providers(args.config)
    shapes = Path(args.shapes) if args.shapes else root / raw.get("shapes", "SHACL/depth_one.ttl")
    if not shapes.is_file():
        print(f"Error: SHACL shapes not found: {shapes}", file=sys.stderr)
        return 1

    if args.all:
        names = [name for name, provider in providers.items() if provider.runnable]
    else:
        if not args.provider:
            print("Provide --provider NAME or --all.", file=sys.stderr)
            return 2
        names = [args.provider]

    limit = args.limit
    reports = []
    overall = 0
    for name in names:
        try:
            provider = get_provider(name, providers)
        except KeyError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        report = validate_provider_outputs(
            root=root,
            provider=provider,
            shapes_path=shapes,
            limit=limit,
        )
        reports.append(report)
        status = "PASS" if report["conforms"] else "FAIL"
        print(
            f"[{name}] {status}  passed={report['passed']} "
            f"failed={report['failed']} missing={len(report['missing_outputs'])}"
        )
        if not report["conforms"]:
            overall = 1

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = reports[0] if len(reports) == 1 else {"reports": reports}
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out}")
    elif args.json:
        _print_json(reports if len(reports) > 1 else reports[0])
    return overall


def cmd_load(args: argparse.Namespace) -> int:
    root = repo_root()
    raw, _providers = load_providers(args.config)
    script = root / raw.get("load_script", "scripts/loadToOxigraph/loadToOxigraph.py")
    if not script.is_file():
        print(f"Error: load script not found: {script}", file=sys.stderr)
        return 1
    command = [sys.executable, str(script), *strip_forwarded(args.forward)]
    if args.dry_run:
        print(" ".join(command))
        return 0
    completed = subprocess.run(command, cwd=root)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doos_pipeline",
        description="Run existing DOOS provider generators as sub-tasks.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Provider registry YAML (default: src/doos_pipeline/config.yaml)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="Show providers, steps, and published outputs")
    list_p.add_argument("--json", action="store_true", help="JSON instead of a table")
    list_p.set_defaults(func=cmd_list)

    run_p = sub.add_parser("run", help="Subprocess an existing provider CLI")
    run_p.add_argument("--provider", help="Provider name from the registry")
    run_p.add_argument(
        "--all",
        action="store_true",
        help="Run providers with run_on_all: true (local sample defaults)",
    )
    run_p.add_argument(
        "--include-heavy",
        action="store_true",
        help="With --all, also run catalog-scale / network-heavy providers",
    )
    run_p.add_argument(
        "--step",
        action="append",
        default=None,
        metavar="NAME",
        help="Run only this named step (repeatable). Default: provider default_steps",
    )
    run_p.add_argument(
        "--work-dir",
        type=Path,
        help="Directory for wrapper run.json (default: runs/doos_pipeline/<utc>)",
    )
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands and write a manifest without executing",
    )
    run_p.add_argument(
        "--no-report",
        action="store_true",
        help="Skip writing report.jsonld after the run",
    )
    run_p.add_argument(
        "--max-files",
        type=int,
        default=None,
        metavar="N",
        help="Cap RDF files scanned for the JSON-LD report",
    )
    run_p.add_argument(
        "forward",
        nargs=argparse.REMAINDER,
        help="Args after -- replace that step's default_args",
    )
    run_p.set_defaults(func=cmd_run)

    report_p = sub.add_parser(
        "report",
        help="Write JSON-LD metrics for published outputs (no generator run)",
    )
    report_p.add_argument("--provider", help="Provider name from the registry")
    report_p.add_argument(
        "--all",
        action="store_true",
        help="One report per runnable provider plus a roll-up",
    )
    report_p.add_argument(
        "--work-dir",
        type=Path,
        help="Directory for report.jsonld (default: runs/doos_pipeline/<utc>)",
    )
    report_p.add_argument(
        "--output",
        type=Path,
        help="Write the report to this path (single provider, or the --all roll-up)",
    )
    report_p.add_argument(
        "--max-files",
        type=int,
        default=None,
        metavar="N",
        help="Cap RDF files scanned (useful for large ARGO directories)",
    )
    report_p.set_defaults(func=cmd_report)

    val_p = sub.add_parser(
        "validate",
        help="SHACL-check published outputs (does not rewrite them)",
    )
    val_p.add_argument("--provider", help="Provider name from the registry")
    val_p.add_argument("--all", action="store_true", help="Validate every runnable provider")
    val_p.add_argument(
        "--shapes",
        type=Path,
        help="SHACL shapes file (default: SHACL/depth_one.ttl)",
    )
    val_p.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max files/graphs to check (default: 25; 0 = no limit)",
    )
    val_p.add_argument("--output", type=Path, help="Write JSON report to this path")
    val_p.add_argument("--json", action="store_true", help="Print JSON report")
    val_p.set_defaults(func=cmd_validate)

    load_p = sub.add_parser(
        "load",
        help="Wrap scripts/loadToOxigraph/loadToOxigraph.py",
    )
    load_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the load command without executing",
    )
    load_p.add_argument(
        "forward",
        nargs=argparse.REMAINDER,
        help="Args after -- forwarded to loadToOxigraph.py",
    )
    load_p.set_defaults(func=cmd_load)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate" and args.limit == 0:
        args.limit = None
    if getattr(args, "max_files", None) == 0:
        args.max_files = None
    try:
        code = args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(code)


if __name__ == "__main__":
    main()
