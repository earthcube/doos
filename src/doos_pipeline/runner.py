"""Subprocess the existing project CLIs and write a wrapper-level run.json."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .providers.registry import Provider, Step


def strip_forwarded(forward: list[str] | None) -> list[str]:
    """Drop a leading ``--`` used to separate wrapper flags from project flags."""
    args = list(forward or [])
    if args and args[0] == "--":
        args = args[1:]
    return args


def build_command(
    *,
    python: str,
    cwd: Path,
    step: Step,
    forwarded: list[str],
) -> list[str]:
    """Build ``python <script> <args>``. Forwarded args replace default_args."""
    script_path = (cwd / step.script).resolve()
    args = forwarded if forwarded else list(step.default_args)
    return [python, str(script_path), *args]


def run_step(
    *,
    python: str,
    cwd: Path,
    step: Step,
    forwarded: list[str],
    dry_run: bool = False,
) -> dict:
    """Run one project script. Stdout/stderr are inherited."""
    command = build_command(python=python, cwd=cwd, step=step, forwarded=forwarded)
    record = {
        "name": step.name,
        "script": step.script,
        "command": command,
        "cwd": str(cwd),
        "dry_run": dry_run,
    }
    if dry_run:
        record["returncode"] = None
        return record

    started = datetime.now(timezone.utc)
    completed = subprocess.run(command, cwd=cwd)
    finished = datetime.now(timezone.utc)
    record["returncode"] = completed.returncode
    record["started_at"] = started.isoformat()
    record["finished_at"] = finished.isoformat()
    record["duration_s"] = round((finished - started).total_seconds(), 3)
    return record


def output_status(root: Path, provider: Provider) -> list[dict]:
    """Describe published output paths without modifying them."""
    rows = []
    for path, fmt, shacl in provider.resolve_outputs(root):
        rows.append(
            {
                "path": str(path),
                "format": fmt,
                "shacl": shacl,
                "exists": path.exists(),
            }
        )
    return rows


def write_manifest(work_dir: Path, manifest: dict) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / "run.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def default_work_dir(root: Path, runs_dir: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / runs_dir / stamp


def run_provider(
    *,
    root: Path,
    provider: Provider,
    steps: list[Step],
    forwarded: list[str],
    work_dir: Path,
    dry_run: bool = False,
    python: str | None = None,
) -> dict:
    """Run selected steps for one provider and write run.json."""
    if forwarded and len(steps) != 1:
        raise ValueError(
            "Extra args after -- can only be forwarded when a single step is "
            "selected. Pass --step NAME."
        )

    python = python or sys.executable
    cwd = provider.resolve_cwd(root)
    if not cwd.is_dir():
        raise FileNotFoundError(f"Provider cwd does not exist: {cwd}")

    started = datetime.now(timezone.utc)
    step_records = []
    exit_code = 0
    for step in steps:
        script_path = cwd / step.script
        if not script_path.is_file():
            raise FileNotFoundError(f"Project script not found: {script_path}")
        record = run_step(
            python=python,
            cwd=cwd,
            step=step,
            forwarded=forwarded,
            dry_run=dry_run,
        )
        step_records.append(record)
        code = record.get("returncode")
        if code not in (0, None):
            exit_code = int(code)
            break

    finished = datetime.now(timezone.utc)
    manifest = {
        "wrapper": "doos_pipeline",
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "provider": provider.name,
        "graph": provider.graph,
        "dry_run": dry_run,
        "steps": step_records,
        "outputs": output_status(root, provider),
        "exit_code": exit_code,
    }
    manifest_path = write_manifest(work_dir, manifest)
    manifest["manifest"] = str(manifest_path)
    return manifest
