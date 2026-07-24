#!/usr/bin/env python
"""
Stage 6 — decoder-emit-provenance (decoder pipeline).

Reads a finished run directory and emits a provenance record of what happened:

  * ``06_raid.json`` — a best-effort RAiD v1.6-style record (PLAN.md §4.6).
                       RAiD models research activities, so the fit is
                       approximate: standard block names are used, vocab IRIs are
                       PLACEHOLDERs, and the authoritative facts live under the
                       ``x_pipeline`` extension block.
  * ``06_record.md`` — a short human-readable narrative (LLM-written when a key
                       is configured, deterministic template otherwise).

This stage only reads existing run artifacts; it is robust to missing files.

Usage (CLI):
    python render_record.py RUN_DIR [--run-id ID] [--out-dir DIR]
                            [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--no-llm]

Usage (import):
    from render_record import run_record
    summary = run_record("runs/<id>")
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph, RDF, URIRef

_BUNDLE_ROOT = Path(__file__).resolve().parents[2]
if str(_BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BUNDLE_ROOT))

TEMPLATE_PATH = Path(__file__).resolve().parent / "raid_template.json"
SCHEMA_DATASET = URIRef("https://schema.org/Dataset")
RAID_ID_BASE = "https://doos.earthcube.org/raid"

_NARRATIVE_SYSTEM = (
    "You write a short, factual provenance note (3-6 sentences) describing what "
    "a metadata validation pipeline did to a dataset record. Use ONLY the "
    "supplied facts; do not invent steps, numbers, or outcomes. Plain prose, no "
    "headings, no preamble."
)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _isodate(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def _graph_facts(graph_path: Path) -> tuple[str | None, int | None]:
    """Return (dataset_iri, n_triples) for the latest graph, or (None, None)."""
    if not graph_path.exists():
        return None, None
    g = Graph()
    try:
        g.parse(str(graph_path), format="turtle")
    except Exception:  # noqa: BLE001
        return None, None
    iri = next((str(s) for s in g.subjects(RDF.type, SCHEMA_DATASET)), None)
    return iri, len(g)


def gather_facts(run_dir: Path) -> dict:
    """Assemble the authoritative pipeline facts from the run directory."""
    input_json = _read_json(run_dir / "00_input.json") or {}
    extracted = _read_json(run_dir / "01_extracted.json") or {}
    conforms = _read_json(run_dir / "03_conforms.json") or {}
    report = _read_json(run_dir / "04_report.json") or {}

    latest_graph = run_dir / "05_graph.ttl"
    if not latest_graph.exists():
        latest_graph = run_dir / "02_graph.ttl"
    dataset_iri, n_triples = _graph_facts(latest_graph)

    # Repair passes / fixes from the audit log.
    repair_passes, n_fixes = 0, 0
    log_path = run_dir / "run.log"
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("[stage5]"):
                repair_passes += 1
                m = re.search(r"fixed=(\d+)", line)
                if m:
                    n_fixes += int(m.group(1))

    extracted_fields = [
        k for k in ("name", "description", "url", "keywords")
        if extracted.get(k) not in (None, "", [])
    ]

    summary = report.get("summary", {})
    return {
        "flow": "decoder",
        "source_url": input_json.get("url") or extracted.get("url"),
        "dataset_iri": dataset_iri,
        "extraction_source": extracted.get("source"),
        "extracted_fields": extracted_fields,
        "shape": "googleRecommended.ttl",
        "n_triples": n_triples,
        "repair_passes": repair_passes,
        "n_fixes_applied": n_fixes,
        "final_conforms": conforms.get("conforms"),
        "final_violations": conforms.get("n_violations", summary.get("n_violations")),
        "final_warnings": conforms.get("n_warnings", summary.get("n_warnings")),
    }


def _deterministic_narrative(facts: dict) -> str:
    src = facts["source_url"] or "an unknown URL"
    how = {
        "embedded-jsonld": "by reusing embedded schema.org JSON-LD",
        "llm-extracted": "by LLM extraction from the page text",
        "none": "but no metadata could be obtained",
    }.get(facts.get("extraction_source"), "from the page")
    parts = [
        f"The dataset at {src} was processed by the decoder pipeline."
    ]
    parts.append(
        f"Metadata was obtained {how}"
        + (f" (fields: {', '.join(facts['extracted_fields'])})"
           if facts["extracted_fields"] else "")
        + "."
    )
    if facts["dataset_iri"]:
        parts.append(
            f"It was lifted to a schema:Dataset graph of {facts['n_triples']} "
            f"triples (IRI {facts['dataset_iri']}) and validated against "
            f"{facts['shape']}."
        )
    if facts["repair_passes"]:
        parts.append(
            f"{facts['repair_passes']} repair pass(es) applied "
            f"{facts['n_fixes_applied']} fix(es)."
        )
    conforms = facts["final_conforms"]
    if conforms is True:
        parts.append(
            f"The final graph conforms (0 blocking violations, "
            f"{facts['final_warnings']} recommendation warning(s))."
        )
    elif conforms is False:
        parts.append(
            f"The final graph still has {facts['final_violations']} blocking "
            f"violation(s) recorded as caveats."
        )
    return " ".join(parts)


def _narrative(facts: dict, use_llm: bool) -> str:
    if use_llm:
        try:
            from orchestration.llm import complete, llm_available

            if llm_available():
                text = complete(_NARRATIVE_SYSTEM, json.dumps(facts)).strip()
                if text:
                    return text
        except Exception:  # noqa: BLE001
            pass
    return _deterministic_narrative(facts)


def build_raid(facts: dict, run_id: str, start: str, end: str) -> dict:
    raid = copy.deepcopy(_read_json(TEMPLATE_PATH))

    raid["identifier"]["id"] = f"{RAID_ID_BASE}/{run_id}"
    raid["date"] = {"startDate": start, "endDate": end}

    title = facts["source_url"] or "dataset"
    name_hint = next((f for f in facts["extracted_fields"] if f == "name"), None)
    raid["title"][0]["text"] = (
        f"SHACL validation of {title}" if not name_hint
        else f"SHACL validation run for: {title}"
    )
    raid["title"][0]["startDate"] = start
    raid["title"][0]["endDate"] = end

    raid["description"][0]["text"] = _deterministic_narrative(facts)

    raid["alternateIdentifier"] = [
        {"id": run_id, "type": "run-id"},
    ]
    if facts["dataset_iri"]:
        raid["alternateIdentifier"].append(
            {"id": facts["dataset_iri"], "type": "dataset-iri"}
        )

    related = []
    if facts["source_url"]:
        related.append({
            "id": facts["source_url"],
            "schemaUri": "",
            "type": {"id": "PLACEHOLDER", "schemaUri": "https://vocabulary.raid.org/relatedObject.type.schema/"},
            "category": [{"id": "input", "schemaUri": ""}],
        })
    if facts["dataset_iri"]:
        related.append({
            "id": facts["dataset_iri"],
            "schemaUri": "",
            "type": {"id": "PLACEHOLDER", "schemaUri": "https://vocabulary.raid.org/relatedObject.type.schema/"},
            "category": [{"id": "output", "schemaUri": ""}],
        })
    raid["relatedObject"] = related

    raid["contributor"][0]["_note"] = (
        "Automated pipeline agent: DOOS decoder."
    )

    xp = raid["x_pipeline"]
    xp.update(facts)
    xp["run_id"] = run_id
    return raid


def run_record(
    run_dir: str | Path,
    run_id: str | None = None,
    out_dir: str | Path | None = None,
    start: str | None = None,
    end: str | None = None,
    use_llm: bool = True,
) -> dict:
    """Build 06_raid.json + 06_record.md from a run directory."""
    run_dir = Path(run_dir)
    out_dir = Path(out_dir) if out_dir else run_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_id or run_dir.name

    # Dates: prefer explicit; else derive from artifact mtimes.
    artifacts = sorted(run_dir.glob("0*"), key=lambda p: p.stat().st_mtime)
    if artifacts:
        start = start or _isodate(artifacts[0].stat().st_mtime)
        end = end or _isodate(artifacts[-1].stat().st_mtime)
    else:
        start = start or ""
        end = end or start

    facts = gather_facts(run_dir)
    raid = build_raid(facts, run_id, start, end)
    narrative = _narrative(facts, use_llm)
    raid["description"][0]["text"] = narrative

    raid_json = out_dir / "06_raid.json"
    record_md = out_dir / "06_record.md"
    raid_json.write_text(json.dumps(raid, indent=2), encoding="utf-8")

    md = [
        "# Trusted Output — Run Record",
        "",
        narrative,
        "",
        "## Facts",
        f"- **Source URL:** {facts['source_url']}",
        f"- **Dataset IRI:** {facts['dataset_iri']}",
        f"- **Extraction:** {facts['extraction_source']} "
        f"(fields: {', '.join(facts['extracted_fields']) or 'none'})",
        f"- **Validated against:** {facts['shape']}",
        f"- **Triples:** {facts['n_triples']}",
        f"- **Repair passes / fixes:** {facts['repair_passes']} / "
        f"{facts['n_fixes_applied']}",
        f"- **Final conforms:** {facts['final_conforms']} "
        f"(violations={facts['final_violations']}, warnings={facts['final_warnings']})",
        f"- **RAiD record:** `{raid_json.name}`",
        "",
    ]
    record_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    return {
        "raid_json": str(raid_json),
        "record_md": str(record_md),
        "facts": facts,
        "final_conforms": facts["final_conforms"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 6: write a RAiD-style provenance record for a run.",
    )
    parser.add_argument("run_dir", help="The run directory (runs/<id>)")
    parser.add_argument("--run-id", default=None, help="Run id (default: dir name)")
    parser.add_argument("--out-dir", default=None, help="Output dir (default: run_dir)")
    parser.add_argument("--start", default=None, help="Run start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="Run end date YYYY-MM-DD")
    parser.add_argument("--no-llm", action="store_true", help="No LLM narrative.")
    args = parser.parse_args(argv)

    r = run_record(args.run_dir, args.run_id, args.out_dir, args.start, args.end,
                   use_llm=not args.no_llm)
    print(f"conforms={r['final_conforms']} -> {r['raid_json']}")
    print(f"  narrative: {r['record_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
