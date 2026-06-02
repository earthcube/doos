#!/usr/bin/env python
"""
Stage 5 — Repair (SHACL-for-AI-outputs flow).

Reads the latest RDF graph (``02_graph.ttl`` on the first pass, ``05_graph.ttl``
on later loop iterations) plus Stage 4's ``04_report.json`` and produces a
repaired ``05_graph.ttl`` to be re-validated by Stage 3. The driver owns the
loop; this stage is a single stateless pass (PLAN.md §4.5).

Repair policy (deliberately conservative — never fabricate facts):

  * fixType ``add``    → add the value **from the source** ``01_extracted.json``
                         when present. For text the dataset can summarize
                         (``description``) with no source value, the LLM may
                         GENERATE it from the record's own fields. Factual
                         fields with no source value (creator/license/…) are
                         left unfixed — never invented.
  * fixType ``coerce`` → transform the existing node in place
                         (Literal ⇄ IRI for nodeKind mismatches).
  * fixType ``remove`` → drop extra values, keep one (MaxCount).
  * fixType ``reword`` → LLM rewrites the existing literal to satisfy the
                         constraint (e.g. MinLength), preserving meaning.
  * ``manual`` / not autoFixable → untouched, logged.

LLM-backed repairs (`generate`, `reword`) require ``OPENROUTER_API_KEY`` via
``orchestration/llm.py``; without it those findings are skipped (left for the
loop's no-progress / max-iteration exit). Rule-based repairs always run.

Usage (CLI):
    python repair.py GRAPH.ttl REPORT.json [--extracted 01_extracted.json]
                     [--out-dir DIR] [--no-llm]

Usage (import):
    from repair import run_repair
    summary = run_repair("02_graph.ttl", "04_report.json", out_dir="runs/<id>")
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rdflib import Graph, Literal, URIRef

# --- Shared OpenRouter LLM helper (orchestration/llm.py) ---------------------
_SHACLSKILLS_ROOT = Path(__file__).resolve().parents[2]
if str(_SHACLSKILLS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHACLSKILLS_ROOT))

SCHEMA = "https://schema.org/"

# schema.org property local name -> key in 01_extracted.json (minimal set).
SOURCE_KEYS = {"name": "name", "description": "description", "url": "url",
               "keywords": "keywords"}
# Properties whose object is an IRI (everything else is a literal).
IRI_PROPS = {"url"}
# Properties the LLM may SYNTHESIZE from the record itself when no source value
# exists (summaries, not facts).
GENERATABLE = {"description"}

_GEN_SYSTEM = (
    "You write a concise, factual description for a dataset. Use ONLY the "
    "provided fields (name, keywords, url). Do not invent facts, methods, "
    "coverage, or provenance not implied by those fields. Return plain text "
    "between 50 and 300 characters, no quotes, no preamble."
)
_REWORD_SYSTEM = (
    "You rewrite a dataset text field to satisfy a SHACL constraint while "
    "preserving its meaning. Use only information already present; do not add "
    "new facts. Return only the rewritten value as plain text, no preamble."
)


def _local_name(iri: str | None) -> str:
    if not iri:
        return ""
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _obj_node(prop_local: str, value: str):
    """Build the right RDF node for a property's value."""
    return URIRef(value) if prop_local in IRI_PROPS else Literal(value)


def _llm_generate_description(extracted: dict) -> str | None:
    from orchestration.llm import complete

    payload = {
        "name": extracted.get("name"),
        "keywords": extracted.get("keywords") or [],
        "url": extracted.get("url"),
    }
    text = complete(_GEN_SYSTEM, json.dumps(payload)).strip().strip('"')
    return text or None


def _llm_reword(prop_local: str, current_value: str, message: str,
                extracted: dict) -> str | None:
    from orchestration.llm import complete

    payload = {
        "property": prop_local,
        "current_value": current_value,
        "constraint_message": message,
        "name": extracted.get("name"),
        "keywords": extracted.get("keywords") or [],
    }
    text = complete(_REWORD_SYSTEM, json.dumps(payload)).strip().strip('"')
    return text or None


def _repair_finding(g: Graph, f: dict, extracted: dict, use_llm: bool) -> dict:
    """Attempt one repair; mutate g in place. Return an audit record."""
    prop_local = _local_name(f.get("result_path"))
    focus = URIRef(f["focus_node"]) if f.get("focus_node") else None
    prop = URIRef(f["result_path"]) if f.get("result_path") else None
    fix = f.get("fixType")
    audit = {"focus": f.get("focus_node"), "property": prop_local,
             "fixType": fix, "action": "skipped", "detail": ""}

    if not f.get("autoFixable") or focus is None or prop is None:
        audit["action"] = "manual" if fix == "manual" else "skipped"
        audit["detail"] = "not auto-fixable" if fix != "manual" else "manual review"
        return audit

    if fix == "add":
        src_key = SOURCE_KEYS.get(prop_local)
        src_val = extracted.get(src_key) if src_key else None
        if src_val:
            values = src_val if isinstance(src_val, list) else [src_val]
            added = 0
            for v in values:
                if v is None or not str(v).strip():
                    continue
                g.add((focus, prop, _obj_node(prop_local, str(v).strip())))
                added += 1
            if added:
                audit.update(action="add-from-source", detail=f"added {added} value(s)")
                return audit
        # No source value: only synthesize summarizable text, never facts.
        if prop_local in GENERATABLE and use_llm:
            try:
                text = _llm_generate_description(extracted)
                if text:
                    g.add((focus, prop, Literal(text)))
                    audit.update(action="llm-generate", detail=f"{len(text)} chars")
                    return audit
            except Exception as e:  # noqa: BLE001
                audit["detail"] = f"llm-generate failed: {e}"
        audit["detail"] = audit["detail"] or "no source value; left unfixed"
        return audit

    if fix == "remove":
        objs = sorted(g.objects(focus, prop), key=lambda o: str(o))
        if len(objs) > 1:
            for extra in objs[1:]:
                g.remove((focus, prop, extra))
            audit.update(action="remove-extra",
                         detail=f"kept 1, removed {len(objs) - 1}")
        else:
            audit["detail"] = "nothing to remove"
        return audit

    if fix == "coerce":
        objs = list(g.objects(focus, prop))
        changed = 0
        for o in objs:
            want_iri = prop_local in IRI_PROPS
            is_iri = isinstance(o, URIRef)
            if want_iri and not is_iri:
                g.remove((focus, prop, o)); g.add((focus, prop, URIRef(str(o))))
                changed += 1
            elif not want_iri and is_iri:
                g.remove((focus, prop, o)); g.add((focus, prop, Literal(str(o))))
                changed += 1
        audit.update(action="coerce" if changed else "skipped",
                     detail=f"coerced {changed} node(s)" if changed
                     else "nothing to coerce")
        return audit

    if fix == "reword":
        objs = list(g.objects(focus, prop))
        if not objs:
            audit["detail"] = "no value to reword"
            return audit
        if not use_llm:
            audit["detail"] = "reword needs LLM (no key); left unfixed"
            return audit
        try:
            current = str(objs[0])
            text = _llm_reword(prop_local, current, f.get("message") or "", extracted)
            if text:
                g.remove((focus, prop, objs[0]))
                g.add((focus, prop, _obj_node(prop_local, text)))
                audit.update(action="llm-reword", detail=f"{len(text)} chars")
            else:
                audit["detail"] = "llm returned empty"
        except Exception as e:  # noqa: BLE001
            audit["detail"] = f"llm-reword failed: {e}"
        return audit

    audit["detail"] = f"unhandled fixType {fix!r}"
    return audit


def run_repair(
    graph_path: str | Path,
    report_path: str | Path,
    out_dir: str | Path = ".",
    extracted_path: str | Path | None = None,
    use_llm: bool = True,
) -> dict:
    """Apply repairs to ``graph_path`` using ``report_path``; write
    ``05_graph.ttl``; append an audit trail to ``run.log``.

    Returns:
        { "graph_ttl", "n_fixed", "n_skipped", "n_manual", "actions": [...] }
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if extracted_path is None:
        cand = out_dir / "01_extracted.json"
        extracted_path = cand if cand.exists() else None
    extracted = (
        json.loads(Path(extracted_path).read_text(encoding="utf-8"))
        if extracted_path
        else {}
    )

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    findings = report.get("findings", [])

    g = Graph()
    g.parse(str(graph_path), format="turtle")

    if use_llm:
        try:
            from orchestration.llm import llm_available

            use_llm = llm_available()
        except Exception:  # noqa: BLE001
            use_llm = False

    actions = [_repair_finding(g, f, extracted, use_llm) for f in findings]

    graph_ttl = out_dir / "05_graph.ttl"
    graph_ttl.write_text(g.serialize(format="turtle"), encoding="utf-8")

    fixed_actions = {"add-from-source", "llm-generate", "coerce", "remove-extra",
                     "llm-reword"}
    n_fixed = sum(1 for a in actions if a["action"] in fixed_actions)
    n_manual = sum(1 for a in actions if a["action"] == "manual")
    n_skipped = sum(1 for a in actions if a["action"] == "skipped")

    with (out_dir / "run.log").open("a", encoding="utf-8") as log:
        log.write(f"[stage5] repaired {graph_path} -> {graph_ttl.name} "
                  f"(llm={'on' if use_llm else 'off'}); "
                  f"fixed={n_fixed} skipped={n_skipped} manual={n_manual}\n")
        for a in actions:
            if a["action"] != "skipped" or a["detail"]:
                log.write(f"  - {a['property']} [{a['fixType']}] -> "
                          f"{a['action']}: {a['detail']}\n")

    return {
        "graph_ttl": str(graph_ttl),
        "n_fixed": n_fixed,
        "n_skipped": n_skipped,
        "n_manual": n_manual,
        "actions": actions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 5: repair an RDF graph using a Stage 4 report; write "
        "05_graph.ttl for re-validation.",
    )
    parser.add_argument("graph", help="Latest graph TTL (02_graph.ttl or 05_graph.ttl)")
    parser.add_argument("report", help="Stage 4 output, 04_report.json")
    parser.add_argument(
        "--extracted",
        default=None,
        help="01_extracted.json (source values for 'add'); defaults to "
        "<out-dir>/01_extracted.json if present",
    )
    parser.add_argument("--out-dir", default=".", help="Directory for 05_graph.ttl")
    parser.add_argument(
        "--no-llm", action="store_true", help="Disable LLM generate/reword repairs."
    )
    args = parser.parse_args(argv)

    s = run_repair(args.graph, args.report, args.out_dir, args.extracted,
                   use_llm=not args.no_llm)
    print(f"Wrote {s['graph_ttl']} — fixed={s['n_fixed']}, "
          f"skipped={s['n_skipped']}, manual={s['n_manual']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
