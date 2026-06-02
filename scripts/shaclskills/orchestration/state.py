"""LangGraph state for the SHACL-for-AI-outputs pipeline (PLAN.md §7).

A single TypedDict threaded through all nodes. Large artifacts (TTL, reports)
live on disk in the run directory; the state carries paths + small scalars.
"""

from __future__ import annotations

from typing import TypedDict


class PipelineState(TypedDict, total=False):
    # --- identity / config (set by the driver) ---
    run_id: str
    run_dir: str
    url: str
    max_iterations: int
    use_llm: bool
    progress: bool             # print live stage checkpoints to stderr

    # --- artifact paths (set by stage nodes) ---
    extracted_json: str        # 01_extracted.json   (Stage 1)
    current_graph: str         # 02_graph.ttl, then 05_graph.ttl (Stages 2/5)
    results_json: str          # 03_results.json     (Stage 3)
    report_ttl: str            # 03_report.ttl       (Stage 3)
    report_json: str           # 04_report.json      (Stage 4)
    raid_json: str             # 06_raid.json        (Stage 6)

    # --- loop control / verdicts ---
    conforms: bool             # Stage 3: zero Violation-severity results
    n_violations: int
    n_warnings: int
    has_autofixable_violations: bool   # Stage 4
    current_violation_sig: str         # Stage 4: signature of current violations
    prev_violation_sig: str | None     # Stage 5: sig of the prior pass (no-progress check)
    iteration: int             # repair passes completed

    # --- audit ---
    events: list
