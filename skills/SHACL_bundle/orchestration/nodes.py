"""LangGraph nodes — thin shells that import & call each stage's module and
update state (PLAN.md §7 / §0a.1). The stage modules do the work.

Stage modules live in sibling decoder-* dirs (hyphenated), so they are not
importable as normal packages — they are loaded by file path with importlib.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

from .state import PipelineState

_BUNDLE_ROOT = Path(__file__).resolve().parents[1]

# Wall-clock anchor for elapsed-time checkpoints (set on the first _log call).
_clock: dict[str, float] = {}


def reset_clock() -> None:
    """Anchor checkpoint elapsed-times to now (call at the start of a run)."""
    _clock.clear()
    _clock["t0"] = time.perf_counter()


def _log(state: PipelineState, msg: str) -> None:
    """Print a live checkpoint to stderr (gated on state['progress']).

    Checkpoints go to stderr so they don't mingle with the final trace on
    stdout, and are flushed immediately so a slow stage shows where the run is
    before it returns. Elapsed seconds since the first checkpoint prefix each
    line, making it obvious which stage is the slow one.
    """
    if not state.get("progress"):
        return
    now = time.perf_counter()
    t0 = _clock.setdefault("t0", now)
    print(f"[{now - t0:6.1f}s] {msg}", file=sys.stderr, flush=True)


def _load(rel_path: str, mod_name: str):
    path = _BUNDLE_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load each stage module once.
_extract = _load("decoder-extract-metadata/assets/extract.py", "stage1_extract")
_lift = _load("decoder-lift-rdf/assets/lift.py", "stage2_lift")
_validate = _load("decoder-validate-shacl/assets/validate.py", "stage3_validate")
_report = _load("decoder-report-findings/assets/parse_report.py", "stage4_report")
_repair = _load("decoder-repair-graph/assets/repair.py", "stage5_repair")
_record = _load("decoder-emit-provenance/assets/render_record.py", "stage6_record")


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
    _log(state, "→ stage 1/6 decoder-extract-metadata: fetch URL + extract metadata …")
    r = _extract.run_extract(state["url"], state["run_dir"], use_llm=state["use_llm"])
    ev = f"stage1: source={r['source']}"
    if r.get("error"):
        ev += f" (fetch error: {r['error']})"
    _log(state, f"✓ {ev}")
    return {
        "extracted_json": r["extracted_json"],
        "events": state.get("events", []) + [ev],
    }


def stage2(state: PipelineState) -> dict:
    _log(state, "→ stage 2/6 decoder-lift-rdf: lift to RDF …")
    r = _lift.run_lift(state["extracted_json"], state["run_dir"])
    ev = f"stage2: {r['n_triples']} triples"
    _log(state, f"✓ {ev}")
    return {
        "current_graph": r["graph_ttl"],
        "events": state.get("events", []) + [ev],
    }


def stage3(state: PipelineState) -> dict:
    _log(state, "→ stage 3/6 decoder-validate-shacl: run pySHACL (RDFS inference) …")
    r = _validate.run_validation(state["current_graph"], out_dir=state["run_dir"])
    ev = f"stage3: conforms={r['conforms']} violations={r['n_violations']}"
    _log(state, f"✓ {ev}")
    return {
        "results_json": r["results_json"],
        "report_ttl": r["report_ttl"],
        "conforms": r["conforms"],
        "n_violations": r["n_violations"],
        "n_warnings": r["n_warnings"],
        "events": state.get("events", []) + [ev],
    }


def stage4(state: PipelineState) -> dict:
    _log(state, "→ stage 4/6 decoder-report-findings: build fix-oriented report …")
    r = _report.run_report(state["results_json"], state["run_dir"],
                           use_llm=state["use_llm"])
    sig, has_autofixable = _violation_sig(r["report_json"])
    ev = f"stage4: autofixable_violations={has_autofixable}"
    _log(state, f"✓ {ev}")
    return {
        "report_json": r["report_json"],
        "current_violation_sig": sig,
        "has_autofixable_violations": has_autofixable,
        "events": state.get("events", []) + [ev],
    }


def stage5(state: PipelineState) -> dict:
    it = state.get("iteration", 0) + 1
    _log(state, f"→ stage 5/6 decoder-repair-graph (pass {it}): apply fixes …")
    r = _repair.run_repair(
        state["current_graph"],
        state["report_json"],
        out_dir=state["run_dir"],
        extracted_path=state["extracted_json"],
        use_llm=state["use_llm"],
    )
    ev = f"stage5: iter={it} fixed={r['n_fixed']}"
    _log(state, f"✓ {ev} (re-validating …)")
    return {
        "current_graph": r["graph_ttl"],
        "iteration": it,
        # Remember the sig we just tried to fix, for the next decide().
        "prev_violation_sig": state.get("current_violation_sig"),
        "events": state.get("events", []) + [ev],
    }


def stage6(state: PipelineState) -> dict:
    _log(state, "→ stage 6/6 decoder-emit-provenance: write provenance record …")
    r = _record.run_record(state["run_dir"], run_id=state["run_id"],
                          use_llm=state["use_llm"])
    ev = f"stage6: conforms={r['final_conforms']} -> {Path(r['raid_json']).name}"
    _log(state, f"✓ {ev}")
    return {
        "raid_json": r["raid_json"],
        "events": state.get("events", []) + [ev],
    }


# --------------------------------------------------------------------------- #
# Conditional routing after stage4 (PLAN.md §4.5 stop conditions)
# --------------------------------------------------------------------------- #
def decide(state: PipelineState) -> str:
    """Route to 'stage5' (repair + loop) or 'stage6' (finish)."""
    if state.get("conforms"):
        _log(state, "  decide: conforms → finishing")
        return "stage6"                                   # (a) conforms
    if not state.get("has_autofixable_violations"):
        _log(state, "  decide: no auto-fixable violations left → finishing")
        return "stage6"                                   # (b) only manual left
    if state.get("iteration", 0) >= state.get("max_iterations", 3):
        _log(state, "  decide: max iterations reached → finishing")
        return "stage6"                                   # (d) max iterations
    if (state.get("prev_violation_sig") is not None
            and state.get("prev_violation_sig") == state.get("current_violation_sig")):
        _log(state, "  decide: no progress since last pass → finishing")
        return "stage6"                                   # (c) no progress
    _log(state, "  decide: auto-fixable violations remain → repairing")
    return "stage5"
