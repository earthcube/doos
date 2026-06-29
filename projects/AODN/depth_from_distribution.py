#!/usr/bin/env python3
"""
Probe AODN dataset distributions for depth columns and min/max values.

Reads a schema.org JSON-LD metadata file, downloads tabular distribution(s),
and reports depth-related column statistics with optional metadata cross-check.

Usage:
    python depth_from_distribution.py --jsonld demo-output/528f280c-....jsonld
    python depth_from_distribution.py --jsonld record.jsonld --try-all --verbose
    python depth_from_distribution.py --jsonld record.jsonld --enrich-jsonld --engine polars
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

import pandas as pd

from defs.depth_columns import (
    aggregate_depth_range,
    classify_distribution,
    compare_depth_to_metadata,
    depth_hints_from_jsonld,
    distribution_url,
    enrich_jsonld_depth,
    find_depth_columns,
    flatten_depth_columns,
    iso19139_sibling_path,
    rank_distributions,
    select_best_attempt,
    vertical_extent_from_iso19139,
)
from defs.prefix_listing import tabular_urls_from_prefix

USER_AGENT = "DOOS-AODN-depth-probe/1.0"
TIMEOUT = 30
TableEngine = Literal["pandas", "polars"]


def log(verbose: bool, message: str) -> None:
    """Write a diagnostic line to stderr when verbose mode is enabled."""
    if verbose:
        print(message, file=sys.stderr)


def load_jsonld(path: Path) -> dict:
    """Load and validate a JSON-LD dataset document."""
    with path.open(encoding="utf-8") as handle:
        doc = json.load(handle)
    if doc.get("@type") != "Dataset":
        raise ValueError(f"Expected @type Dataset, got {doc.get('@type')!r}")
    return doc


def download_distribution(url: str, dest_dir: Path) -> Path:
    """Download a distribution URL to dest_dir and return the local path."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            content = response.read()
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} fetching {url}") from e
    except URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e.reason}") from e

    if b"<html" in content[:500].lower():
        raise RuntimeError(f"URL returned HTML instead of tabular data: {url}")

    filename = unquote(Path(urlparse(url).path).name) or "distribution.bin"
    dest_path = dest_dir / filename
    dest_path.write_bytes(content)
    return dest_path


def _polars_to_pandas(frame: Any) -> pd.DataFrame:
    """Convert a polars DataFrame to pandas."""
    return frame.to_pandas()


def load_tables(
    path: Path,
    *,
    engine: TableEngine = "pandas",
) -> list[tuple[str, pd.DataFrame]]:
    """Load a tabular file into one or more named sheets/tables."""
    ext = path.suffix.lower()

    if engine == "polars":
        try:
            import polars as pl
        except ImportError as e:
            raise RuntimeError(
                "Polars engine requested but polars is not installed. "
                "Install with: uv pip install polars"
            ) from e

        if ext == ".csv":
            return [("default", _polars_to_pandas(pl.read_csv(path)))]
        if ext == ".tsv":
            return [("default", _polars_to_pandas(pl.read_csv(path, separator="\t")))]
        if ext == ".parquet":
            return [("default", _polars_to_pandas(pl.read_parquet(path)))]
        if ext in {".xls", ".xlsx", ".xlsm"}:
            log(True, f"polars cannot read Excel; using pandas for {path.name}")
            engine = "pandas"
        else:
            raise ValueError(f"Unsupported tabular format: {ext or path.name}")

    if ext == ".csv":
        return [("default", pd.read_csv(path))]
    if ext == ".tsv":
        return [("default", pd.read_csv(path, sep="\t"))]
    if ext == ".parquet":
        return [("default", pd.read_parquet(path))]
    if ext in {".xls", ".xlsx", ".xlsm"}:
        try:
            workbook = pd.ExcelFile(path)
        except ImportError as e:
            raise RuntimeError(
                "Excel support requires openpyxl (.xlsx) and xlrd (.xls). "
                "Install with: uv pip install openpyxl xlrd"
            ) from e
        tables: list[tuple[str, pd.DataFrame]] = []
        for sheet in workbook.sheet_names:
            frame = pd.read_excel(path, sheet_name=sheet)
            if not frame.empty:
                tables.append((sheet, frame))
        return tables

    raise ValueError(f"Unsupported tabular format: {ext or path.name}")


def probe_file(
    path: Path,
    hints: list[str],
    *,
    engine: TableEngine = "pandas",
) -> list[dict]:
    """Scan all tables in a file for depth columns."""
    findings: list[dict] = []
    for sheet, frame in load_tables(path, engine=engine):
        columns = find_depth_columns(frame, hints)
        if columns:
            findings.append(
                {
                    "sheet": sheet,
                    "rows": int(len(frame)),
                    "depth_columns": columns,
                }
            )
    return findings


def probe_downloaded_url(
    url: str,
    hints: list[str],
    work_dir: Path,
    *,
    engine: TableEngine,
    verbose: bool,
    source_name: str | None = None,
) -> dict:
    """Download one tabular URL and return an attempt record."""
    attempt: dict[str, Any] = {
        "distribution_name": source_name,
        "distribution_url": url,
        "kind": classify_distribution(url),
        "status": "skipped",
    }

    try:
        local_path = download_distribution(url, work_dir)
        findings = probe_file(local_path, hints, engine=engine)
        if not findings:
            attempt["status"] = "no_depth_columns"
            attempt["message"] = "tabular file loaded but no depth columns matched"
            attempt["format"] = local_path.suffix.lower().lstrip(".")
            log(verbose, f"no depth columns: {url}")
            return attempt

        attempt["status"] = "ok"
        attempt["format"] = local_path.suffix.lower().lstrip(".")
        attempt["findings"] = findings
        log(
            verbose,
            f"ok ({len(flatten_depth_columns(findings))} depth columns): {url}",
        )
        return attempt

    except (RuntimeError, ValueError, OSError) as e:
        attempt["status"] = "error"
        attempt["message"] = str(e)
        log(verbose, f"error: {url} ({e})")
        return attempt


def attempt_distribution(
    dist: dict,
    hints: list[str],
    work_dir: Path,
    *,
    verbose: bool,
    engine: TableEngine,
    crawl_prefix: bool,
) -> list[dict]:
    """Probe one distribution; prefix listings may expand to multiple attempts."""
    url = distribution_url(dist)
    name = dist.get("name")
    kind = classify_distribution(url) if url else "missing-url"

    if not url:
        return [
            {
                "distribution_name": name,
                "distribution_url": url,
                "kind": kind,
                "status": "skipped",
                "message": "distribution has no URL",
            }
        ]

    if kind == "prefix-listing":
        if not crawl_prefix:
            return [
                {
                    "distribution_name": name,
                    "distribution_url": url,
                    "kind": kind,
                    "status": "skipped",
                    "message": "prefix listing crawl disabled",
                }
            ]

        log(verbose, f"crawl prefix listing: {url}")
        try:
            tabular_urls = tabular_urls_from_prefix(url)
        except (RuntimeError, ValueError) as e:
            return [
                {
                    "distribution_name": name,
                    "distribution_url": url,
                    "kind": kind,
                    "status": "error",
                    "message": str(e),
                }
            ]

        if not tabular_urls:
            return [
                {
                    "distribution_name": name,
                    "distribution_url": url,
                    "kind": kind,
                    "status": "no_tabular_objects",
                    "message": "prefix listing contained no tabular objects",
                }
            ]

        attempts: list[dict] = []
        for item in tabular_urls:
            child = probe_downloaded_url(
                item["url"],
                hints,
                work_dir,
                engine=engine,
                verbose=verbose,
                source_name=item.get("name") or name,
            )
            child["parent_distribution_url"] = url
            child["kind"] = "prefix-listing-object"
            attempts.append(child)
        return attempts

    if kind != "tabular":
        return [
            {
                "distribution_name": name,
                "distribution_url": url,
                "kind": kind,
                "status": "skipped",
                "message": f"non-tabular distribution ({kind})",
            }
        ]

    return [
        probe_downloaded_url(
            url,
            hints,
            work_dir,
            engine=engine,
            verbose=verbose,
            source_name=name,
        )
    ]


def resolve_iso19139_path(jsonld_path: Path, explicit: str | None) -> Path | None:
    """Resolve the ISO 19139 path from CLI flag or pipeline naming convention."""
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None
    sibling = iso19139_sibling_path(jsonld_path)
    return sibling if sibling.is_file() else None


def build_report(
    doc: dict,
    *,
    best: dict | None,
    attempts: list[dict],
    vertical_extent: dict[str, float] | None,
    iso19139_path: Path | None,
    try_all: bool,
    depth_range: dict[str, Any] | None = None,
) -> dict:
    """Assemble the final JSON report."""
    report: dict = {
        "dataset_id": doc.get("@id"),
        "dataset_name": doc.get("name"),
        "metadata_depth_hints": depth_hints_from_jsonld(doc),
    }

    if iso19139_path:
        report["iso19139_path"] = str(iso19139_path)
    if vertical_extent:
        report["metadata_vertical_extent"] = vertical_extent
    if depth_range:
        report["observed_depth_range"] = depth_range

    if try_all:
        report["attempts"] = attempts

    if best and best.get("status") == "ok":
        best_payload = {
            "distribution_name": best.get("distribution_name"),
            "distribution_url": best.get("distribution_url"),
            "format": best.get("format"),
            "findings": best.get("findings"),
        }
        if best.get("parent_distribution_url"):
            best_payload["parent_distribution_url"] = best["parent_distribution_url"]
        report["best"] = best_payload
        report["distribution"] = best_payload
        report["metadata_comparison"] = compare_depth_to_metadata(
            flatten_depth_columns(best.get("findings") or []),
            vertical_extent,
        )
    else:
        report["best"] = None
        report["metadata_comparison"] = compare_depth_to_metadata([], vertical_extent)

    return report


def probe_depth_record(
    doc: dict,
    *,
    jsonld_path: Path | None = None,
    iso19139_path: Path | None = None,
    forced_distribution_url: str | None = None,
    try_all: bool = False,
    verbose: bool = False,
    engine: TableEngine = "pandas",
    crawl_prefix: bool = True,
) -> tuple[dict, dict | None]:
    """Probe depth columns for a dataset document.

    Returns:
        Tuple of (report dict, observed depth range dict or None).
    """
    hints = depth_hints_from_jsonld(doc)
    distributions = doc.get("distribution") or []
    if not isinstance(distributions, list) or not distributions:
        raise ValueError("JSON-LD has no distribution entries")

    vertical_extent = (
        vertical_extent_from_iso19139(iso19139_path) if iso19139_path else None
    )
    if verbose and iso19139_path:
        log(verbose, f"ISO 19139: {iso19139_path} extent={vertical_extent}")

    if forced_distribution_url:
        candidates = [
            dist
            for dist in distributions
            if isinstance(dist, dict)
            and distribution_url(dist) == forced_distribution_url
        ]
        if not candidates:
            candidates = [{"url": forced_distribution_url, "name": "forced"}]
    else:
        candidates = rank_distributions(
            [dist for dist in distributions if isinstance(dist, dict)]
        )
        if crawl_prefix:
            prefix_dists = [
                dist
                for dist in distributions
                if isinstance(dist, dict)
                and classify_distribution(distribution_url(dist) or "") == "prefix-listing"
            ]
            candidates = candidates + prefix_dists

    if not candidates:
        raise ValueError("No probeable distributions found in JSON-LD")

    attempts: list[dict] = []
    best: dict | None = None

    with tempfile.TemporaryDirectory(prefix="aodn-depth-") as tmp:
        work_dir = Path(tmp)
        for dist in candidates:
            for attempt in attempt_distribution(
                dist,
                hints,
                work_dir,
                verbose=verbose,
                engine=engine,
                crawl_prefix=crawl_prefix,
            ):
                attempts.append(attempt)
                if not try_all and attempt.get("status") == "ok":
                    best = attempt
                    break
            if not try_all and best is not None:
                break

        if try_all or best is None:
            best = select_best_attempt(attempts)

    if best is None or best.get("status") != "ok":
        errors = [
            f"{a.get('distribution_url')}: {a.get('message', a.get('status'))}"
            for a in attempts
            if a.get("status") in {"error", "no_depth_columns", "skipped", "no_tabular_objects"}
        ]
        detail = "; ".join(errors) if errors else "no depth columns found"
        raise RuntimeError(f"Failed to find depth columns in distributions: {detail}")

    depth_range = aggregate_depth_range(
        flatten_depth_columns(best.get("findings") or [])
    )
    report = build_report(
        doc,
        best=best,
        attempts=attempts,
        vertical_extent=vertical_extent,
        iso19139_path=iso19139_path,
        try_all=try_all,
        depth_range=depth_range,
    )
    return report, depth_range


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download AODN distribution(s) and compute depth column min/max"
    )
    parser.add_argument(
        "--jsonld",
        type=str,
        required=True,
        help="Path to schema.org Dataset JSON-LD file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional output JSON report path (default: stdout)",
    )
    parser.add_argument(
        "--distribution-url",
        type=str,
        default=None,
        help="Force a specific distribution URL instead of auto-ranking",
    )
    parser.add_argument(
        "--try-all",
        action="store_true",
        help="Probe every tabular distribution and report all attempts",
    )
    parser.add_argument(
        "--iso19139",
        type=str,
        default=None,
        help="ISO 19139 XML for vertical extent cross-check (default: sibling *_iso19139.xml)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log skipped and failed distributions to stderr",
    )
    parser.add_argument(
        "--engine",
        choices=["pandas", "polars"],
        default="pandas",
        help="Tabular loader for csv/tsv/parquet (Excel always uses pandas)",
    )
    parser.add_argument(
        "--no-crawl-prefix",
        action="store_true",
        help="Skip expanding ?prefix= S3 listing distributions",
    )
    parser.add_argument(
        "--enrich-jsonld",
        action="store_true",
        help="Write observed min/max into DepBelowSurf in the JSON-LD file",
    )
    args = parser.parse_args()

    jsonld_path = Path(args.jsonld)
    if not jsonld_path.is_file():
        print(f"Error: JSON-LD file not found: {jsonld_path}", file=sys.stderr)
        sys.exit(1)

    try:
        doc = load_jsonld(jsonld_path)
        iso_path = resolve_iso19139_path(jsonld_path, args.iso19139)
        report, depth_range = probe_depth_record(
            doc,
            jsonld_path=jsonld_path,
            iso19139_path=iso_path,
            forced_distribution_url=args.distribution_url,
            try_all=args.try_all,
            verbose=args.verbose,
            engine=args.engine,
            crawl_prefix=not args.no_crawl_prefix,
        )

        if args.enrich_jsonld and depth_range:
            enriched = enrich_jsonld_depth(doc, depth_range)
            jsonld_path.write_text(
                json.dumps(enriched, indent=2) + "\n",
                encoding="utf-8",
            )
            report["enriched_jsonld"] = str(jsonld_path)
            if args.verbose:
                log(args.verbose, f"enriched JSON-LD written to {jsonld_path}")

        output_text = json.dumps(report, indent=2)

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output_text + "\n", encoding="utf-8")
            print(f"Depth report written to {out_path}", file=sys.stderr)
        else:
            print(output_text)

    except (ValueError, RuntimeError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()