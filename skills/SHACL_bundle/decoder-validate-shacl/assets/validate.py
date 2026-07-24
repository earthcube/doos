#!/usr/bin/env python
"""
Stage 3 — decoder-validate-shacl (decoder pipeline).

Validates a schema:Dataset RDF graph (Stage 2 / Stage 5 output) against the
bundled ``googleRecommended.ttl`` shape using pySHACL, and writes three
artifacts into the run directory:

  * ``03_report.ttl``   — the SHACL ValidationReport graph (provenance / human)
  * ``03_results.json`` — one normalized record per sh:ValidationResult
                          (the primary input for Stage 4)
  * ``03_conforms.json``— ``{conforms, n_violations, n_warnings, n_info,
                          raw_conforms}``

IMPORTANT (PLAN.md §4.3 / Stage 3): pySHACL's raw ``conforms`` boolean is
``False`` whenever *any* result exists — **including sh:Warning**. The Dataset
shape emits a warning for every missing recommended field, so a perfectly valid
Dataset (valid name + description) is ``raw_conforms == False`` with many
warnings. The repair loop must therefore key off ``conforms`` defined here as
"**zero sh:Violation-severity results**", ignoring warnings. Using the raw
boolean would loop forever.

Engine reuse: this performs the same single pySHACL call the shared validator
uses (``inference="rdfs"``, skolemize authority ``http://gleaner.io``) and
reuses ``defs/shaclValidator.py``'s ``SH`` namespace + ``_get_obj`` extractor so
the result-row schema stays identical to the rest of the codebase. (It calls
pySHACL directly rather than ``validate_with_shacl_results`` only because it
also needs the report graph, which that helper discards.)

Usage (CLI):
    python validate.py DATA.ttl [--shape SHAPE.ttl] [--out-dir DIR]

Usage (import, e.g. from a LangGraph node):
    from validate import run_validation
    summary = run_validation("02_graph.ttl", out_dir="runs/<id>")
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pyshacl import validate

# --- Reuse the shared validator's helpers (single source of truth) -----------
# defs/shaclValidator.py lives at <repo>/scripts/shapeValidator/defs/.
# This skill is at skills/SHACL_bundle/decoder-validate-shacl/assets/.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_SHAPE_VALIDATOR_ROOT = _REPO_ROOT / "scripts" / "shapeValidator"
if str(_SHAPE_VALIDATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHAPE_VALIDATOR_ROOT))

from defs.shaclValidator import SH, _get_obj  # noqa: E402  (path set above)

from rdflib.namespace import RDF  # noqa: E402

# Default shape ships alongside this script.
DEFAULT_SHAPE = Path(__file__).resolve().parent / "googleRecommended.ttl"

# Skolemization authority — match the shared validator for stable IRIs.
_SKOLEM_AUTHORITY = "http://gleaner.io"


def _severity_bucket(severity_iri: str | None) -> str:
    """Map a sh:resultSeverity IRI to 'violation' | 'warning' | 'info'."""
    if not severity_iri:
        # SHACL default severity is sh:Violation when none is stated.
        return "violation"
    s = severity_iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1].lower()
    if s.startswith("viol"):
        return "violation"
    if s.startswith("warn"):
        return "warning"
    if s.startswith("info"):
        return "info"
    return "violation"  # unknown severities are treated as blocking


def run_validation(
    data_path: str | Path,
    shape_path: str | Path = DEFAULT_SHAPE,
    out_dir: str | Path = ".",
) -> dict:
    """Validate ``data_path`` against ``shape_path``; write the three Stage 3
    artifacts into ``out_dir`` and return a summary dict.

    Returns:
        {
          "conforms": bool,          # True iff zero Violation-severity results
          "raw_conforms": bool,      # pySHACL's boolean (False if ANY result)
          "n_violations": int,
          "n_warnings": int,
          "n_info": int,
          "results": [ {result_id, severity, focus_node, result_path,
                        message, source_shape, source_constraint, value}, ... ],
          "report_ttl": str,         # path to 03_report.ttl
          "results_json": str,       # path to 03_results.json
          "conforms_json": str,      # path to 03_conforms.json
        }
    """
    data_path = Path(data_path)
    shape_path = Path(shape_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data_text = data_path.read_text(encoding="utf-8")
    shape_text = shape_path.read_text(encoding="utf-8")

    try:
        raw_conforms, report_graph, _ = validate(
            data_text,
            data_graph_format="ttl",
            shacl_graph=shape_text,
            shacl_graph_format="ttl",
            inference="rdfs",
            serialize_report_graph=False,
        )
    except Exception as e:  # surface a clean error to the caller / driver
        raise RuntimeError(f"SHACL validation failed for {data_path}: {e}") from e

    # Skolemize blank nodes for stable result identifiers (matches shared validator).
    report_graph = report_graph.skolemize(authority=_SKOLEM_AUTHORITY)

    results: list[dict] = []
    for res in report_graph.subjects(RDF.type, SH.ValidationResult):
        results.append(
            {
                "result_id": str(res),
                "severity": _get_obj(report_graph, res, SH.resultSeverity),
                "focus_node": _get_obj(report_graph, res, SH.focusNode),
                "result_path": _get_obj(report_graph, res, SH.resultPath),
                "message": _get_obj(report_graph, res, SH.resultMessage),
                "source_shape": _get_obj(report_graph, res, SH.sourceShape),
                "source_constraint": _get_obj(
                    report_graph, res, SH.sourceConstraintComponent
                ),
                "value": _get_obj(report_graph, res, SH.value),
            }
        )

    buckets = [_severity_bucket(r["severity"]) for r in results]
    n_violations = buckets.count("violation")
    n_warnings = buckets.count("warning")
    n_info = buckets.count("info")

    # Conformance for the repair loop = no blocking (Violation) results.
    conforms = n_violations == 0

    report_ttl = out_dir / "03_report.ttl"
    results_json = out_dir / "03_results.json"
    conforms_json = out_dir / "03_conforms.json"

    report_ttl.write_text(report_graph.serialize(format="turtle"), encoding="utf-8")
    results_json.write_text(json.dumps(results, indent=2), encoding="utf-8")

    summary = {
        "conforms": conforms,
        "raw_conforms": bool(raw_conforms),
        "n_violations": n_violations,
        "n_warnings": n_warnings,
        "n_info": n_info,
    }
    conforms_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    summary["results"] = results
    summary["report_ttl"] = str(report_ttl)
    summary["results_json"] = str(results_json)
    summary["conforms_json"] = str(conforms_json)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 3: validate a schema:Dataset RDF graph against the "
        "Google Dataset SHACL shape (pySHACL).",
    )
    parser.add_argument("data", help="RDF data graph (Turtle), e.g. 02_graph.ttl")
    parser.add_argument(
        "--shape",
        default=str(DEFAULT_SHAPE),
        help=f"SHACL shapes file (default: bundled {DEFAULT_SHAPE.name})",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Directory to write 03_report.ttl / 03_results.json / "
        "03_conforms.json (default: current dir)",
    )
    args = parser.parse_args(argv)

    summary = run_validation(args.data, args.shape, args.out_dir)

    status = "CONFORMS" if summary["conforms"] else "NON-CONFORMING"
    print(
        f"{status}: {summary['n_violations']} violation(s), "
        f"{summary['n_warnings']} warning(s), {summary['n_info']} info "
        f"(pySHACL raw conforms={summary['raw_conforms']})"
    )
    print(f"  report:   {summary['report_ttl']}")
    print(f"  results:  {summary['results_json']}")
    print(f"  conforms: {summary['conforms_json']}")

    # Exit 0 when there are no blocking violations, 1 otherwise — handy for the
    # driver / shell, but the loop should read 03_conforms.json, not just $?.
    return 0 if summary["conforms"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
