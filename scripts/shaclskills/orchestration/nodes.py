"""LangGraph nodes — thin shells that import & call each stage's module and
update state (PLAN.md §7 / §0a.1). The stage modules do the work.

Stage modules live in sibling dirs whose names start with digits and contain
hyphens, so they are not importable as normal packages — they are loaded by
file path with importlib.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from .state import PipelineState

_BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def _load(rel_path: str, mod_name: str):
    path = _BUNDLE_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load each stage module once.
_extract = _load("1-llm-output/assets/extract.py", "stage1_extract")
_lift = _load("2-rdf-knowledge-graph/assets/lift.py", "stage2_lift")
_validate = _load("3-shacl-validation/assets/validate.py", "stage3_validate")
_report = _load("4-violation-report/assets/parse_report.py", "stage4_report")
_repair = _load("5-repair/assets/repair.py", "stage5_repair")
_record = _load("6-trusted-output/assets/render_record.py", "stage6_record")


def _violation_sig(report_json_path: str) -> tuple[str, bool]:
    """Return (signature, has_autofixable_violations) for Violation findings."""
    report = json.loads(Path(report_json_path).read_text(encoding="utf-8"))
    viols = [f for f in report.get("findings", [])
             if f.get("severity_bucket") == "violation"]
    sig = json.dumps(
        sorted((f.get("focus_node"), f.get("result_path"), f.get("source_constraint"))
               for f in viols)
    )
    has_autofixable = any(f.get("autoFixable") for f in viols)
    return sig, has_autofixable


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #
def stage1(state: PipelineState) -> dict:
    r = _extract.run_extract(state["url"], state["run_dir"], use_llm=state["use_llm"])
    return {
        "extracted_json": r["extracted_json"],
        "events": state.get("events", []) + [f"stage1: source={r['source']}"],
    }


def stage2(state: PipelineState) -> dict:
    r = _lift.run_lift(state["extracted_json"], state["run_dir"])
    return {
        "current_graph": r["graph_ttl"],
        "events": state.get("events", []) + [f"stage2: {r['n_triples']} triples"],
    }


def stage3(state: PipelineState) -> dict:
    r = _validate.run_validation(state["current_graph"], out_dir=state["run_dir"])
    return {
        "results_json": r["results_json"],
        "report_ttl": r["report_ttl"],
        "conforms": r["conforms"],
        "n_violations": r["n_violations"],
        "n_warnings": r["n_warnings"],
        "events": state.get("events", [])
        + [f"stage3: conforms={r['conforms']} violations={r['n_violations']}"],
    }


def stage4(state: PipelineState) -> dict:
    r = _report.run_report(state["results_json"], state["run_dir"],
                           use_llm=state["use_llm"])
    sig, has_autofixable = _violation_sig(r["report_json"])
    return {
        "report_json": r["report_json"],
        "current_violation_sig": sig,
        "has_autofixable_violations": has_autofixable,
        "events": state.get("events", [])
        + [f"stage4: autofixable_violations={has_autofixable}"],
    }


def stage5(state: PipelineState) -> dict:
    r = _repair.run_repair(
        state["current_graph"],
        state["report_json"],
        out_dir=state["run_dir"],
        extracted_path=state["extracted_json"],
        use_llm=state["use_llm"],
    )
    return {
        "current_graph": r["graph_ttl"],
        "iteration": state.get("iteration", 0) + 1,
        # Remember the sig we just tried to fix, for the next decide().
        "prev_violation_sig": state.get("current_violation_sig"),
        "events": state.get("events", [])
        + [f"stage5: iter={state.get('iteration', 0) + 1} fixed={r['n_fixed']}"],
    }


def stage6(state: PipelineState) -> dict:
    r = _record.run_record(state["run_dir"], run_id=state["run_id"],
                          use_llm=state["use_llm"])
    return {
        "raid_json": r["raid_json"],
        "events": state.get("events", [])
        + [f"stage6: conforms={r['final_conforms']} -> {Path(r['raid_json']).name}"],
    }


# --------------------------------------------------------------------------- #
# Conditional routing after stage4 (PLAN.md §4.5 stop conditions)
# --------------------------------------------------------------------------- #
def decide(state: PipelineState) -> str:
    """Route to 'stage5' (repair + loop) or 'stage6' (finish)."""
    if state.get("conforms"):
        return "stage6"                                   # (a) conforms
    if not state.get("has_autofixable_violations"):
        return "stage6"                                   # (b) only manual left
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        return "stage6"                                   # (d) max iterations
    if (state.get("prev_violation_sig") is not None
            and state.get("prev_violation_sig") == state.get("current_violation_sig")):
        return "stage6"                                   # (c) no progress
    return "stage5"
