#!/usr/bin/env python3
"""
Benchmark PySHACL vs pyrudof (Rust) for SHACL validation performance.

This script is designed for the DOOS shapeValidator workload:
- Fetch named graphs via SPARQL CONSTRUCT from QLever
- Run SHACL validation
- Compare wall-clock validation time + result counts

Usage example:
    pip install pyrudof tqdm

    # Basic performance comparison
    python benchmark_shacl_engines.py \
        http://ghost.lan:7007 \
        ../SHACL/ERDDAP_simple.ttl \
        --limit 100 \
        --output benchmark_results.csv

    # Compare counts + violation overlap
    python benchmark_shacl_engines.py \
        http://ghost.lan:7007 \
        ../SHACL/ERDDAP_simple.ttl \
        --limit 50 \
        --compare-reports \
        --output detailed_comparison.csv

    # Full forensic mode: also dump raw reports + structured violations per graph
    python benchmark_shacl_engines.py \
        http://ghost.lan:7007 \
        ../SHACL/ERDDAP_simple.ttl \
        --limit 20 \
        --compare-reports \
        --diff-dir diff_artifacts/

The script measures *only* the validation step (data fetching time is excluded
so the comparison is fair).

Requirements:
- PySHACL + rdflib (already used in the project)
- Optional: pyrudof for the Rust comparison
"""

import argparse
import csv
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tqdm import tqdm

# Project code (reused for fair comparison)
from defs.getConstruct import construct_graph
from defs.getGraphs import query_sparql_endpoint
from defs.getShape import read_shapefile
from defs.shaclValidator import validate_with_shacl

# For reliable result counting (used by both engines)
from rdflib import Graph, Namespace, RDF

SH = Namespace("http://www.w3.org/ns/shacl#")


def count_validation_results(report_nt: str) -> int:
    """
    Reliably count the number of sh:ValidationResult nodes in an N-Triples report.
    Works for both PySHACL and pyrudof output.
    """
    if not report_nt or not report_nt.strip():
        return 0
    try:
        g = Graph()
        g.parse(data=report_nt, format="nt")
        return len(list(g.subjects(RDF.type, SH.ValidationResult)))
    except Exception:
        # Fallback to string count on full URI if parsing fails
        return report_nt.count("http://www.w3.org/ns/shacl#ValidationResult")


def extract_violations(report_nt: str) -> set:
    """
    Extract a set of normalized violation signatures from an N-Triples SHACL report.
    Used for --compare-reports mode.
    Signature = (focusNode, resultPath, resultMessage, resultSeverity)
    """
    if not report_nt or not report_nt.strip():
        return set()
    try:
        g = Graph()
        g.parse(data=report_nt, format="nt")
        violations = set()
        for res in g.subjects(RDF.type, SH.ValidationResult):
            focus = str(g.value(res, SH.focusNode) or "")
            path = str(g.value(res, SH.resultPath) or "")
            message = str(g.value(res, SH.resultMessage) or "")
            severity = str(g.value(res, SH.resultSeverity) or "")
            sig = (focus, path, message, severity)
            violations.add(sig)
        return violations
    except Exception:
        return set()


def extract_violation_dicts(report_nt: str) -> list[dict]:
    """
    Extract structured list of violations for detailed inspection / diffing.
    """
    if not report_nt or not report_nt.strip():
        return []
    try:
        g = Graph()
        g.parse(data=report_nt, format="nt")
        results = []
        for res in g.subjects(RDF.type, SH.ValidationResult):
            d = {
                "focus_node": str(g.value(res, SH.focusNode) or ""),
                "result_path": str(g.value(res, SH.resultPath) or ""),
                "result_message": str(g.value(res, SH.resultMessage) or ""),
                "result_severity": str(g.value(res, SH.resultSeverity) or ""),
                "source_shape": str(g.value(res, SH.sourceShape) or ""),
                "source_constraint": str(
                    g.value(res, SH.sourceConstraintComponent) or ""
                ),
                "value": str(g.value(res, SH.value) or ""),
            }
            results.append(d)
        return results
    except Exception:
        return []


def _write_graph_diff(
    diff_dir: str,
    idx: int,
    graph_uri: str,
    pyshacl_report: str,
    pyrudof_report: str,
    pyshacl_viols: set,
    pyrudof_viols: set,
):
    """Write detailed per-graph artifacts for manual inspection."""
    base = Path(diff_dir)
    base.mkdir(parents=True, exist_ok=True)

    # Create safe subdirectory name
    safe_name = graph_uri.replace(":", "_").replace("/", "_").replace("#", "_")
    if len(safe_name) > 80:
        safe_name = safe_name[:80]
    subdir = base / f"{idx:05d}_{safe_name}"
    subdir.mkdir(exist_ok=True)

    # Raw reports
    (subdir / "pyshacl_report.nt").write_text(pyshacl_report, encoding="utf-8")
    (subdir / "pyrudof_report.nt").write_text(pyrudof_report, encoding="utf-8")

    # Structured violations
    (subdir / "violations_pyshacl.json").write_text(
        json.dumps(extract_violation_dicts(pyshacl_report), indent=2), encoding="utf-8"
    )
    (subdir / "violations_pyrudof.json").write_text(
        json.dumps(extract_violation_dicts(pyrudof_report), indent=2), encoding="utf-8"
    )

    # Human readable diff summary
    common = pyshacl_viols & pyrudof_viols
    only_pyshacl = pyshacl_viols - pyrudof_viols
    only_pyrudof = pyrudof_viols - pyshacl_viols

    diff_text = f"""Graph: {graph_uri}

Counts:
  PySHACL : {len(pyshacl_viols)}
  pyrudof : {len(pyrudof_viols)}
  Common  : {len(common)}
  Only PySHACL : {len(only_pyshacl)}
  Only pyrudof : {len(only_pyrudof)}

"""
    if only_pyshacl:
        diff_text += "\n=== Only in PySHACL ===\n"
        for v in sorted(only_pyshacl)[:10]:
            diff_text += f"  {v}\n"
        if len(only_pyshacl) > 10:
            diff_text += f"  ... and {len(only_pyshacl)-10} more\n"

    if only_pyrudof:
        diff_text += "\n=== Only in pyrudof ===\n"
        for v in sorted(only_pyrudof)[:10]:
            diff_text += f"  {v}\n"
        if len(only_pyrudof) > 10:
            diff_text += f"  ... and {len(only_pyrudof)-10} more\n"

    (subdir / "diff_summary.txt").write_text(diff_text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# PySHACL wrapper
# --------------------------------------------------------------------------- #


def validate_pyshacl(
    data_graph_ttl: str, shapes_ttl: str, return_report: bool = False
) -> Tuple:
    """
    Run validation using PySHACL.

    Args:
        return_report: If True, also return the raw N-Triples report as 4th value.

    Returns:
        If return_report=False:
            (time, count, error)
        If return_report=True:
            (time, count, error, report_nt or None)
    """
    tracemalloc.start()
    start = time.perf_counter()
    try:
        report_nt = validate_with_shacl(data_graph_ttl, shapes_ttl)
        duration = time.perf_counter() - start

        num_results = count_validation_results(report_nt)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        if return_report:
            return duration, num_results, None, report_nt
        return duration, num_results, None

    except Exception as e:
        tracemalloc.stop()
        if return_report:
            return 0.0, 0, str(e), None
        return 0.0, 0, str(e)


# --------------------------------------------------------------------------- #
# pyrudof wrapper (Rust engine via Python bindings)
# --------------------------------------------------------------------------- #

HAS_PYRUDOF = False
try:
    from pyrudof import (
        RDFFormat,
        ResultShaclValidationFormat,
        Rudof,
        RudofConfig,
        ShaclFormat,
        ShaclValidationMode,
    )

    HAS_PYRUDOF = True
except ImportError:
    pass


def validate_pyrudof(
    data_graph_ttl: str,
    shapes_ttl: str,
    rudof_instance: "Rudof",
    return_report: bool = False,
) -> Tuple:
    """
    Run validation using pyrudof (Rust) - correct API for pyrudof 0.3.x.
    """
    if not HAS_PYRUDOF:
        if return_report:
            return 0.0, 0, "pyrudof not installed", None
        return 0.0, 0, "pyrudof not installed"

    tracemalloc.start()
    start = time.perf_counter()
    try:
        # Reset state from previous graph (keep shapes loaded)
        try:
            rudof_instance.reset_data()
            rudof_instance.reset_validation_results()
        except Exception:
            pass

        # Load this graph's data
        rudof_instance.read_data(
            input=data_graph_ttl, format=RDFFormat.Turtle, merge=False
        )

        # Run validation using the fast native Rust engine
        rudof_instance.validate_shacl(mode=ShaclValidationMode.Native)

        duration = time.perf_counter() - start

        # Serialize results as N-Triples
        report_nt = rudof_instance.serialize_shacl_validation_results(
            format=ResultShaclValidationFormat.NTriples
        )

        num_results = count_validation_results(report_nt)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        if return_report:
            return duration, num_results, None, report_nt
        return duration, num_results, None

    except Exception as e:
        tracemalloc.stop()
        if return_report:
            return 0.0, 0, str(e), None
        return 0.0, 0, str(e)


def create_pyrudof_instance(shapes_ttl: str) -> Optional["Rudof"]:
    """Create and configure a pyrudof instance with shapes pre-loaded."""
    if not HAS_PYRUDOF:
        return None

    try:
        config = RudofConfig()
        rudof = Rudof(config)
        # Correct API for pyrudof >= 0.3.x
        rudof.read_shacl(input=shapes_ttl, format=ShaclFormat.Turtle)
        return rudof
    except Exception as e:
        msg = str(e)
        print(f"Failed to initialize pyrudof: {msg}", file=sys.stderr)
        if "backreferences" in msg.lower() or "regex" in msg.lower():
            print(
                "\nThis is likely because your SHACL shapes contain a sh:pattern "
                "using regex backreferences (e.g. \\1), which pyrudof/rudof does not support "
                "(Rust regex engine limitation). PySHACL supports it via Python re.",
                file=sys.stderr,
            )
        return None


# --------------------------------------------------------------------------- #
# Main benchmark logic
# --------------------------------------------------------------------------- #


def run_benchmark(
    endpoint: str,
    shapes_path: str,
    limit: int = 0,
    warmup: int = 2,
    compare_reports: bool = False,
    diff_dir: Optional[str] = None,
) -> List[Dict]:
    """
    Run the benchmark and return a list of result rows.

    If compare_reports=True, also computes detailed violation overlap
    between the two engines (slower but useful for analysis).

    If diff_dir is provided, writes raw reports + structured violations
    per graph into that directory for deep manual inspection.
    """
    print("Loading shapes...")
    shapes_ttl = read_shapefile(shapes_path)
    print(f"Shapes loaded ({len(shapes_ttl):,} characters)")

    print(f"Querying endpoint: {endpoint}")
    uris = query_sparql_endpoint(endpoint, endpoint=endpoint, limit=limit)
    if not uris:
        print("No URIs found!", file=sys.stderr)
        sys.exit(1)

    # Keep the Python slice as a safety net (SPARQL LIMIT gives arbitrary order).
    if limit > 0:
        uris = uris[:limit]
    print(f"Will benchmark {len(uris)} graphs\n")

    # Prepare pyrudof (if available)
    pyrudof = None
    if HAS_PYRUDOF:
        print("Initializing pyrudof (Rust engine)...")
        pyrudof = create_pyrudof_instance(shapes_ttl)
        if pyrudof:
            print("pyrudof ready.\n")
        else:
            print("pyrudof initialization failed. Will only run PySHACL.\n")
            if compare_reports:
                print(
                    "WARNING: --compare-reports was requested, but pyrudof could not be initialized.\n"
                    "         No violation overlap data will be collected.\n"
                    "         Tip: Use ERDDAP_simple.ttl instead of ERDDAP.ttl when benchmarking with pyrudof.\n"
                )
    else:
        print("pyrudof not installed. Install with: pip install pyrudof\n")

    results = []

    # Optional warmup (helps with JIT / caching effects)
    if warmup > 0 and uris:
        print(f"Running {warmup} warmup graph(s)...")
        warmup_uri = uris[0]
        rdf = construct_graph(warmup_uri, endpoint=endpoint)
        if rdf:
            validate_pyshacl(rdf, shapes_ttl)
            if pyrudof:
                validate_pyrudof(rdf, shapes_ttl, pyrudof)
        print("Warmup complete.\n")

    print("Starting benchmark...")

    for uri in tqdm(uris, desc="Benchmarking graphs"):
        row = {"graph_uri": uri}

        # Fetch data once (we exclude this time from the comparison)
        rdf_ttl = construct_graph(uri, endpoint=endpoint)
        if not rdf_ttl or not rdf_ttl.strip():
            row["error"] = "empty_graph"
            results.append(row)
            continue

        if compare_reports:
            # Detailed mode: get reports for comparison
            pyshacl_time, pyshacl_count, pyshacl_err, pyshacl_report = validate_pyshacl(
                rdf_ttl, shapes_ttl, return_report=True
            )
            row["pyshacl_time_s"] = round(pyshacl_time, 4)
            row["pyshacl_results"] = pyshacl_count
            row["pyshacl_error"] = pyshacl_err

            if pyrudof:
                pyrudof_time, pyrudof_count, pyrudof_err, pyrudof_report = (
                    validate_pyrudof(rdf_ttl, shapes_ttl, pyrudof, return_report=True)
                )
                row["pyrudof_time_s"] = round(pyrudof_time, 4)
                row["pyrudof_results"] = pyrudof_count
                row["pyrudof_error"] = pyrudof_err

                # Compute overlap
                pyshacl_viols = (
                    extract_violations(pyshacl_report) if pyshacl_report else set()
                )
                pyrudof_viols = (
                    extract_violations(pyrudof_report) if pyrudof_report else set()
                )

                common = len(pyshacl_viols & pyrudof_viols)
                only_pyshacl = len(pyshacl_viols - pyrudof_viols)
                only_pyrudof = len(pyrudof_viols - pyshacl_viols)

                row["common_results"] = common
                row["only_pyshacl"] = only_pyshacl
                row["only_pyrudof"] = only_pyrudof
                row["reports_match"] = (
                    (common == pyshacl_count == pyrudof_count)
                    and only_pyshacl == 0
                    and only_pyrudof == 0
                )

                # Write detailed diff artifacts if requested
                if diff_dir and pyshacl_report and pyrudof_report:
                    _write_graph_diff(
                        diff_dir=diff_dir,
                        idx=len(results),
                        graph_uri=uri,
                        pyshacl_report=pyshacl_report,
                        pyrudof_report=pyrudof_report,
                        pyshacl_viols=pyshacl_viols,
                        pyrudof_viols=pyrudof_viols,
                    )
            else:
                row["pyrudof_time_s"] = None
                row["pyrudof_results"] = None
                row["pyrudof_error"] = "not_available"
                row["common_results"] = None
                row["only_pyshacl"] = None
                row["only_pyrudof"] = None
                row["reports_match"] = None
        else:
            # Fast counting-only mode
            pyshacl_time, pyshacl_count, pyshacl_err = validate_pyshacl(
                rdf_ttl, shapes_ttl
            )
            row["pyshacl_time_s"] = round(pyshacl_time, 4)
            row["pyshacl_results"] = pyshacl_count
            row["pyshacl_error"] = pyshacl_err

            if pyrudof:
                pyrudof_time, pyrudof_count, pyrudof_err = validate_pyrudof(
                    rdf_ttl, shapes_ttl, pyrudof
                )
                row["pyrudof_time_s"] = round(pyrudof_time, 4)
                row["pyrudof_results"] = pyrudof_count
                row["pyrudof_error"] = pyrudof_err
            else:
                row["pyrudof_time_s"] = None
                row["pyrudof_results"] = None
                row["pyrudof_error"] = "not_available"

        results.append(row)

    return results


def print_summary(results: List[Dict], compare_reports: bool = False):
    """Print nice summary statistics."""
    pyshacl_times = [
        r["pyshacl_time_s"] for r in results if r.get("pyshacl_time_s") is not None
    ]
    pyrudof_times = [
        r["pyrudof_time_s"] for r in results if r.get("pyrudof_time_s") is not None
    ]

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)

    if pyshacl_times:
        print(f"\nPySHACL ({len(pyshacl_times)} graphs):")
        print(f"  Mean:   {statistics.mean(pyshacl_times):.4f}s")
        print(f"  Median: {statistics.median(pyshacl_times):.4f}s")
        if len(pyshacl_times) > 1:
            print(f"  Stdev:  {statistics.stdev(pyshacl_times):.4f}s")
        print(f"  Total:  {sum(pyshacl_times):.2f}s")

    if pyrudof_times:
        print(f"\npyrudof / Rust ({len(pyrudof_times)} graphs):")
        print(f"  Mean:   {statistics.mean(pyrudof_times):.4f}s")
        print(f"  Median: {statistics.median(pyrudof_times):.4f}s")
        if len(pyrudof_times) > 1:
            print(f"  Stdev:  {statistics.stdev(pyrudof_times):.4f}s")
        print(f"  Total:  {sum(pyrudof_times):.2f}s")

        if pyshacl_times:
            speedup = (
                sum(pyshacl_times) / sum(pyrudof_times)
                if sum(pyrudof_times) > 0
                else float("inf")
            )
            print(f"\n  → Approximate speedup (total time): {speedup:.1f}×")

    # Basic count agreement
    agreements = 0
    disagreements = 0
    for r in results:
        p1 = r.get("pyshacl_results")
        p2 = r.get("pyrudof_results")
        if p1 is not None and p2 is not None:
            if p1 == p2:
                agreements += 1
            else:
                disagreements += 1

    if agreements + disagreements > 0:
        print(
            f"\nResult count agreement: {agreements} / {agreements + disagreements} graphs matched"
        )

    # Detailed violation comparison (from --compare-reports)
    if compare_reports:
        has_comparison_data = any(r.get("common_results") is not None for r in results)

        if not has_comparison_data:
            print("\n--- Detailed Violation Comparison (--compare-reports) ---")
            print("  No comparison data available.")
            print("  This usually happens when one of the engines (PySHACL or pyrudof)")
            print("  could not be initialized (see messages above).")
        else:
            match_count = 0
            mismatch_count = 0
            total_common = 0
            total_only_pyshacl = 0
            total_only_pyrudof = 0

            for r in results:
                if r.get("reports_match") is True:
                    match_count += 1
                elif r.get("reports_match") is False:
                    mismatch_count += 1

                if r.get("common_results") is not None:
                    total_common += r.get("common_results", 0)
                    total_only_pyshacl += r.get("only_pyshacl", 0)
                    total_only_pyrudof += r.get("only_pyrudof", 0)

            print("\n--- Detailed Violation Comparison (--compare-reports) ---")
            print(f"  Graphs with identical violation sets: {match_count}")
            print(f"  Graphs with differences:              {mismatch_count}")
            if match_count + mismatch_count > 0:
                print(
                    f"  Match rate: {match_count / (match_count + mismatch_count) * 100:.1f}%"
                )

            print(f"\n  Total common violations across all graphs:     {total_common}")
            print(
                f"  Total violations only in PySHACL:              {total_only_pyshacl}"
            )
            print(
                f"  Total violations only in pyrudof (Rust):       {total_only_pyrudof}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark PySHACL vs pyrudof (Rust) SHACL validation performance."
    )
    parser.add_argument("endpoint", help="SPARQL endpoint URL")
    parser.add_argument("shapefile", help="SHACL shapes file (Turtle)")
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of graphs to test (0 = all). Also pushes LIMIT into the initial SPARQL discovery query when > 0.",
    )
    parser.add_argument("--output", "-o", help="Write detailed results to CSV file")
    parser.add_argument("--warmup", type=int, default=2, help="Number of warmup graphs")
    parser.add_argument(
        "--compare-reports",
        action="store_true",
        help="Also compare the actual set of violations between engines (slower, adds overlap columns)",
    )
    parser.add_argument(
        "--diff-dir",
        metavar="DIR",
        help="Write detailed per-graph diff artifacts (raw reports + structured violations) into this directory. "
        "Very useful for understanding why the two engines disagree.",
    )
    args = parser.parse_args()

    results = run_benchmark(
        endpoint=args.endpoint,
        shapes_path=args.shapefile,
        limit=args.limit,
        warmup=args.warmup,
        compare_reports=args.compare_reports,
        diff_dir=args.diff_dir,
    )

    print_summary(results, compare_reports=args.compare_reports)

    if args.output:
        fieldnames = [
            "graph_uri",
            "pyshacl_time_s",
            "pyshacl_results",
            "pyshacl_error",
            "pyrudof_time_s",
            "pyrudof_results",
            "pyrudof_error",
            "error",
        ]
        if args.compare_reports:
            fieldnames += [
                "common_results",
                "only_pyshacl",
                "only_pyrudof",
                "reports_match",
            ]

        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nDetailed results written to {args.output}")

    if args.diff_dir:
        print(f"\nDetailed per-graph diff artifacts written to: {args.diff_dir}/")

    # Final advice
    if not HAS_PYRUDOF:
        print(
            "\nTip: Install pyrudof with `pip install pyrudof` to enable the Rust comparison."
        )


if __name__ == "__main__":
    main()
