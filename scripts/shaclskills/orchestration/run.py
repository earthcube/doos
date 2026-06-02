#!/usr/bin/env python
"""
Entry point for the SHACL-for-AI-outputs pipeline (PLAN.md §7).

Creates a run directory, writes 00_input.json, and drives the six stages
(1→6) through the LangGraph graph with the 3→4→5 repair loop. Stages run
deterministically; LLM-backed steps (1 fallback, 4/5/6 prose) activate when
an LLM API key (LLM_API_KEY) is set, otherwise they degrade gracefully.

When LLM steps are enabled and a key is set, a connectivity probe runs first
(skip with --no-probe). If the LLM is configured but unreachable, the run says
so and continues deterministically instead of silently degrading. Use
--check-llm to probe the connection and exit without running the pipeline.

Live per-stage checkpoints (with elapsed time) print to stderr as each stage is
entered, so a slow stage is visible instead of the run appearing to hang;
silence them with --quiet.

Usage:
    python orchestration/run.py <dataset-url> [--max-iterations N]
                                [--run-id ID] [--runs-dir DIR] [--no-llm]
                                [--no-probe] [--quiet]
    python orchestration/run.py --check-llm     # probe LLM connection, then exit

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
    from orchestration.llm import (  # type: ignore
        check_llm,
        describe_config,
        llm_available,
    )
    from orchestration.nodes import reset_clock  # type: ignore
else:
    from .graph import build_graph
    from .llm import check_llm, describe_config, llm_available
    from .nodes import reset_clock

_BUNDLE_ROOT = Path(__file__).resolve().parents[1]


def preflight_llm(use_llm: bool, probe: bool = True) -> tuple[bool, str]:
    """Decide whether LLM steps run, and produce a one-line status.

    Returns ``(effective_use_llm, message)``:

    - LLM not requested ............ ``(False, "LLM: disabled (--no-llm)")``
    - requested, no key ............ ``(False, "LLM: no key set — running deterministically")``
    - requested, probe off ......... ``(True,  "LLM: enabled (<target>, not probed)")``
    - requested, probe OK .......... ``(True,  "LLM: connected (<target>)")``
    - requested, probe FAILED ...... ``(False, "LLM: configured but UNREACHABLE — <error>; continuing deterministically")``

    The failure case is the point of this check: a bad key / base URL / model
    no longer silently degrades to look exactly like an intended ``--no-llm``
    run — it is reported, while the pipeline still completes deterministically.
    """
    if not use_llm:
        return False, "LLM: disabled (--no-llm)"
    if not llm_available():
        return False, "LLM: no key set (LLM_API_KEY) — running deterministically"
    if not probe:
        return True, f"LLM: enabled ({describe_config()}, not probed)"
    ok, detail = check_llm()
    if ok:
        return True, f"LLM: connected ({detail})"
    return False, (
        f"LLM: configured but UNREACHABLE — {detail}; "
        "continuing deterministically"
    )


def run_pipeline(
    url: str,
    max_iterations: int = 3,
    run_id: str | None = None,
    runs_dir: str | Path | None = None,
    use_llm: bool = True,
    probe: bool = True,
    progress: bool = True,
) -> dict:
    """Run the full pipeline for one dataset URL; return the final state.

    When ``use_llm`` and a key is set, a preflight probe verifies the LLM is
    actually reachable (unless ``probe=False``). On failure the run continues
    deterministically and the reason is recorded in ``final["events"]`` and
    ``final["llm_status"]`` rather than being silently swallowed.

    When ``progress`` is true, each stage prints a live checkpoint (with elapsed
    time) to stderr as it is entered/exited, so a long-running stage is visible
    instead of the whole run appearing to hang.
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    runs_dir = Path(runs_dir) if runs_dir else _BUNDLE_ROOT / "runs"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "00_input.json").write_text(
        json.dumps({"url": url}, indent=2), encoding="utf-8"
    )

    effective_use_llm, llm_status = preflight_llm(use_llm, probe=probe)
    if progress:
        # Reset the checkpoint clock so elapsed times are relative to this run,
        # and surface the preflight result before the (possibly slow) stages.
        reset_clock()
        print(f"[   0.0s] {llm_status}", file=sys.stderr, flush=True)

    init: dict = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "url": url,
        "max_iterations": max_iterations,
        "use_llm": effective_use_llm,
        "progress": progress,
        "iteration": 0,
        "prev_violation_sig": None,
        "events": [llm_status],
    }

    app = build_graph()
    # Recursion budget covers stage1,2 + (3,4,5)*max + 3,4 + 6, with headroom.
    final = app.invoke(init, config={"recursion_limit": 4 * max_iterations + 25})
    final["llm_status"] = llm_status
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the SHACL-for-AI-outputs pipeline on a dataset URL."
    )
    parser.add_argument("url", nargs="?",
                        help="Dataset URL (file:// works for fixtures)")
    parser.add_argument("--max-iterations", type=int, default=3,
                        help="Max repair passes before finishing (default: 3)")
    parser.add_argument("--run-id", default=None, help="Run id (default: random)")
    parser.add_argument("--runs-dir", default=None,
                        help="Parent dir for run folders (default: <bundle>/runs)")
    parser.add_argument("--no-llm", action="store_true",
                        help="Disable all LLM-backed steps.")
    parser.add_argument("--no-probe", action="store_true",
                        help="Skip the LLM connectivity probe before running.")
    parser.add_argument("--check-llm", action="store_true",
                        help="Only probe the LLM connection and exit (no pipeline).")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress live per-stage progress checkpoints (stderr).")
    args = parser.parse_args(argv)

    # Preflight-only mode: verify the LLM target and exit with its status.
    if args.check_llm:
        ok, detail = check_llm()
        print("LLM: connected" if ok else "LLM: NOT reachable")
        print(f"  {detail}")
        return 0 if ok else 1

    if not args.url:
        parser.error("the following argument is required: url")

    final = run_pipeline(
        args.url,
        max_iterations=args.max_iterations,
        run_id=args.run_id,
        runs_dir=args.runs_dir,
        use_llm=not args.no_llm,
        probe=not args.no_probe,
        progress=not args.quiet,
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
