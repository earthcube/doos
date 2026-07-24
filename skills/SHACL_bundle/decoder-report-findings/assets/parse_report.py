#!/usr/bin/env python
"""
Stage 4 — decoder-report-findings (decoder pipeline).

Turns Stage 3's ``03_results.json`` into a fix-oriented report that Stage 5 can
act on programmatically:

  * ``04_report.json`` — machine-actionable findings (see violation_schema.json)
  * ``04_report.md``   — human-readable, grouped by severity then focus node

Build mode (PLAN.md §4.4): the control-flow fields — ``fixType`` and
``autoFixable`` — are set **deterministically by code** from a
``constraintComponent → fixType`` table, because the repair loop gates on them.
The LLM only enriches the human-facing prose (``issue`` / ``suggestedFix``);
it never decides control flow. When no LLM is configured (no
``LLM_API_KEY``), the prose falls back to deterministic templates, so this
stage always runs.

Field names from ``03_results.json`` are carried through verbatim (snake_case)
and never renamed (PLAN.md §4.4).

Usage (CLI):
    python parse_report.py 03_results.json [--out-dir DIR] [--no-llm]

Usage (import, e.g. from a LangGraph node):
    from parse_report import run_report
    summary = run_report("03_results.json", out_dir="runs/<id>")
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# --- Reuse the shared OpenRouter LLM helper (orchestration/llm.py) -----------
# orchestration/ lives two levels up from this assets/ dir.
_BUNDLE_ROOT = Path(__file__).resolve().parents[2]
if str(_BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BUNDLE_ROOT))

# fixType by SHACL constraint component (local name). autoFixable = fixType != "manual".
FIXTYPE_BY_CONSTRAINT = {
    "MinCountConstraintComponent": "add",
    "MaxCountConstraintComponent": "remove",
    "DatatypeConstraintComponent": "coerce",
    "NodeKindConstraintComponent": "coerce",
    "MinLengthConstraintComponent": "reword",
    "MaxLengthConstraintComponent": "reword",
    "PatternConstraintComponent": "reword",
    "ClassConstraintComponent": "manual",
    "InConstraintComponent": "manual",
    "OrConstraintComponent": "manual",
    "AndConstraintComponent": "manual",
    "NotConstraintComponent": "manual",
}
DEFAULT_FIXTYPE = "manual"

# Sort order for severities (violations first).
_SEVERITY_ORDER = {"violation": 0, "warning": 1, "info": 2}


def _local_name(iri: str | None) -> str:
    """Local name of an IRI (after the last '#' or '/'); '' for None."""
    if not iri:
        return ""
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _severity_bucket(severity_iri: str | None) -> str:
    """Map sh:resultSeverity IRI to 'violation' | 'warning' | 'info'.

    SHACL's default severity (when unstated) is sh:Violation.
    """
    name = _local_name(severity_iri).lower()
    if name.startswith("warn"):
        return "warning"
    if name.startswith("info"):
        return "info"
    return "violation"


def _fix_type(constraint_iri: str | None) -> str:
    return FIXTYPE_BY_CONSTRAINT.get(_local_name(constraint_iri), DEFAULT_FIXTYPE)


def _deterministic_prose(row: dict) -> tuple[str, str]:
    """(issue, suggestedFix) templated from the row — the LLM-free fallback."""
    path = _local_name(row.get("result_path")) or "the value"
    msg = row.get("message") or ""
    fix = row["fixType"]

    issue = msg or f"The constraint on '{path}' was not satisfied."

    if fix == "add":
        need = "required" if row["severity_bucket"] == "violation" else "recommended"
        suggested = f"Add a value for schema:{path} ({need}, currently missing)."
    elif fix == "coerce":
        suggested = f"Convert the value of schema:{path} to the required form ({msg})."
    elif fix == "remove":
        suggested = f"Remove the extra value(s) of schema:{path} (too many present)."
    elif fix == "reword":
        suggested = f"Rewrite the value of schema:{path} to satisfy: {msg}"
    else:  # manual
        suggested = f"Manual review needed for schema:{path}: {msg}"
    return issue, suggested


def _enrich_with_llm(findings: list[dict]) -> bool:
    """Try to set issue/suggestedFix from the LLM in one batched call.

    Returns True if enrichment succeeded (findings mutated in place), False to
    fall back to deterministic prose. Never raises.
    """
    try:
        from orchestration.llm import complete, llm_available

        if not llm_available() or not findings:
            return False

        compact = [
            {
                "result_id": f["result_id"],
                "property": _local_name(f.get("result_path")),
                "constraint": _local_name(f.get("source_constraint")),
                "severity": f["severity_bucket"],
                "fixType": f["fixType"],
                "shacl_message": f.get("message"),
                "offending_value": f.get("value"),
            }
            for f in findings
        ]
        system = (
            "You explain SHACL validation findings for a schema.org Dataset and "
            "propose concrete fixes. Return ONLY a JSON array; one object per "
            "input finding with keys: result_id, issue (1-2 sentence plain-English "
            "explanation), suggestedFix (a concrete, actionable instruction). Do "
            "not change which fields are fixable; just explain and advise."
        )
        user = json.dumps(compact, indent=2)
        raw = complete(system, user).strip()

        # Tolerate code fences / leading prose: extract the JSON array.
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end == -1:
            return False
        enriched = json.loads(raw[start : end + 1])
        by_id = {e.get("result_id"): e for e in enriched if isinstance(e, dict)}

        applied = False
        for f in findings:
            e = by_id.get(f["result_id"])
            if e and e.get("issue") and e.get("suggestedFix"):
                f["issue"] = str(e["issue"]).strip()
                f["suggestedFix"] = str(e["suggestedFix"]).strip()
                applied = True
        return applied
    except Exception:
        return False


def _to_finding(row: dict) -> dict:
    """Normalize one 03_results.json row into a Stage 4 finding (prose TBD)."""
    fix_type = _fix_type(row.get("source_constraint"))
    issue, suggested = "", ""
    finding = {
        # carried through verbatim from Stage 3
        "result_id": row.get("result_id"),
        "severity": row.get("severity"),
        "focus_node": row.get("focus_node"),
        "result_path": row.get("result_path"),
        "source_shape": row.get("source_shape"),
        "source_constraint": row.get("source_constraint"),
        "value": row.get("value"),
        "message": row.get("message"),
        # added by Stage 4
        "severity_bucket": _severity_bucket(row.get("severity")),
        "fixType": fix_type,
        "autoFixable": fix_type != "manual",
        "issue": issue,
        "suggestedFix": suggested,
    }
    finding["issue"], finding["suggestedFix"] = _deterministic_prose(finding)
    return finding


def _render_markdown(summary: dict, findings: list[dict]) -> str:
    lines = ["# SHACL Violation Report", ""]
    lines.append(
        f"**Conforms:** {summary['conforms']} "
        f"(violations={summary['n_violations']}, "
        f"warnings={summary['n_warnings']}, info={summary['n_info']}, "
        f"auto-fixable={summary['n_autofixable']})"
    )
    lines.append(f"_Prose enrichment: {summary['enrichment']}._")
    lines.append("")

    if not findings:
        lines.append("No findings — the graph conforms with no warnings. ✅")
        return "\n".join(lines) + "\n"

    for bucket, heading in (
        ("violation", "## Violations (blocking)"),
        ("warning", "## Warnings (recommended)"),
        ("info", "## Info"),
    ):
        group = [f for f in findings if f["severity_bucket"] == bucket]
        if not group:
            continue
        lines.append(heading)
        lines.append("")
        for f in group:
            prop = _local_name(f.get("result_path")) or "(node)"
            lines.append(f"### `{prop}` — {f['fixType']}"
                         + ("" if f["autoFixable"] else " · _manual_"))
            lines.append(f"- **Focus node:** `{f.get('focus_node')}`")
            if f.get("value"):
                lines.append(f"- **Offending value:** `{f['value']}`")
            lines.append(f"- **Issue:** {f['issue']}")
            lines.append(f"- **Suggested fix:** {f['suggestedFix']}")
            lines.append("")
    return "\n".join(lines) + "\n"


def run_report(
    results_path: str | Path,
    out_dir: str | Path = ".",
    use_llm: bool = True,
) -> dict:
    """Build 04_report.json + 04_report.md from 03_results.json.

    Returns the report dict (also written to 04_report.json), augmented with
    ``report_json`` / ``report_md`` paths.
    """
    results_path = Path(results_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = json.loads(results_path.read_text(encoding="utf-8"))
    findings = [_to_finding(r) for r in rows]

    enrichment = "deterministic"
    if use_llm and _enrich_with_llm(findings):
        enrichment = "llm"

    # Sort: violations first, then by focus node, then property.
    findings.sort(
        key=lambda f: (
            _SEVERITY_ORDER.get(f["severity_bucket"], 9),
            f.get("focus_node") or "",
            f.get("result_path") or "",
        )
    )

    n_violations = sum(1 for f in findings if f["severity_bucket"] == "violation")
    n_warnings = sum(1 for f in findings if f["severity_bucket"] == "warning")
    n_info = sum(1 for f in findings if f["severity_bucket"] == "info")
    summary = {
        "n_total": len(findings),
        "n_violations": n_violations,
        "n_warnings": n_warnings,
        "n_info": n_info,
        "n_autofixable": sum(1 for f in findings if f["autoFixable"]),
        "conforms": n_violations == 0,
        "enrichment": enrichment,
    }
    report = {"summary": summary, "findings": findings}

    report_json = out_dir / "04_report.json"
    report_md = out_dir / "04_report.md"
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report_md.write_text(_render_markdown(summary, findings), encoding="utf-8")

    report["report_json"] = str(report_json)
    report["report_md"] = str(report_md)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 4: build a fix-oriented violation report from "
        "03_results.json.",
    )
    parser.add_argument("results", help="Stage 3 output, e.g. 03_results.json")
    parser.add_argument(
        "--out-dir", default=".", help="Directory for 04_report.{json,md} (default: cwd)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM prose enrichment (use deterministic templates only).",
    )
    args = parser.parse_args(argv)

    report = run_report(args.results, args.out_dir, use_llm=not args.no_llm)
    s = report["summary"]
    print(
        f"{s['n_violations']} violation(s), {s['n_warnings']} warning(s), "
        f"{s['n_autofixable']} auto-fixable — enrichment: {s['enrichment']}"
    )
    print(f"  json: {report['report_json']}")
    print(f"  md:   {report['report_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
