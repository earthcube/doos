#!/usr/bin/env python
"""
Entry point for the SHACL-for-AI-outputs pipeline (PLAN.md §7).

Creates a run directory, writes 00_input.json, and drives the six stages
(1→6) through the LangGraph graph with the 3→4→5 repair loop. Stages run
deterministically; LLM-backed steps (1 fallback, 4/5/6 prose) activate when
OPENROUTER_API_KEY is set, otherwise they degrade gracefully.

Usage:
    python orchestration/run.py <dataset-url> [--max-iterations N]
                                [--run-id ID] [--runs-dir DIR] [--no-llm]

Run as a module so the package-relative imports resolve:
    uv run python -m orchestration.run <url>           (from the bundle root)
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

# Allow `python orchestration/run.py ...` (script form) as well as `-m`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from orchestration.graph import build_graph  # type: ignore
    from orchestration.llm import llm_available  # type: ignore
else:
    from .graph import build_graph
    from .llm import llm_available

_BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def run_pipeline(
    url: str,
    max_iterations: int = 3,
    run_id: str | None = None,
    runs_dir: str | Path | None = None,
    use_llm: bool = True,
) -> dict:
    """Run the full pipeline for one dataset URL; return the final state."""
    run_id = run_id or uuid.uuid4().hex[:12]
    runs_dir = Path(runs_dir) if runs_dir else _BUNDLE_ROOT / "runs"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "00_input.json").write_text(
        json.dumps({"url": url}, indent=2), encoding="utf-8"
    )

    init: dict = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "url": url,
        "max_iterations": max_iterations,
        "use_llm": use_llm and llm_available(),
        "iteration": 0,
        "prev_violation_sig": None,
        "events": [],
    }

    app = build_graph()
    # Recursion budget covers stage1,2 + (3,4,5)*max + 3,4 + 6, with headroom.
    final = app.invoke(init, config={"recursion_limit": 4 * max_iterations + 25})
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the SHACL-for-AI-outputs pipeline on a dataset URL."
    )
    parser.add_argument("url", help="Dataset URL (file:// works for fixtures)")
    parser.add_argument("--max-iterations", type=int, default=3,
                        help="Max repair passes before finishing (default: 3)")
    parser.add_argument("--run-id", default=None, help="Run id (default: random)")
    parser.add_argument("--runs-dir", default=None,
                        help="Parent dir for run folders (default: <bundle>/runs)")
    parser.add_argument("--no-llm", action="store_true",
                        help="Disable all LLM-backed steps.")
    args = parser.parse_args(argv)

    final = run_pipeline(
        args.url,
        max_iterations=args.max_iterations,
        run_id=args.run_id,
        runs_dir=args.runs_dir,
        use_llm=not args.no_llm,
    )

    print("\n=== pipeline trace ===")
    for ev in final.get("events", []):
        print(f"  {ev}")
    print("\n=== result ===")
    print(f"  run dir:     {final['run_dir']}")
    print(f"  conforms:    {final.get('conforms')} "
          f"(violations={final.get('n_violations')}, "
          f"warnings={final.get('n_warnings')}, "
          f"repair passes={final.get('iteration', 0)})")
    print(f"  RAiD record: {final.get('raid_json')}")
    return 0 if final.get("conforms") else 1


if __name__ == "__main__":
    raise SystemExit(main())
