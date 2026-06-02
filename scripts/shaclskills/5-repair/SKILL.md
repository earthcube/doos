---
name: repair
description: Stage 5 of the SHACL-for-AI-outputs flow. Repair an RDF graph using the Stage 4 report — add values from the source record, coerce/remove mechanically, and LLM-reword text — then hand back to Stage 3 for re-validation. Never fabricates factual fields. Use when a violation report identifies constraint failures to correct.
metadata:
  stage: 5
  flow: shacl-for-ai-outputs
---

# Stage 5 — Repair

Fix the graph based on the report, then loop back to re-validation.

## What it does

`assets/repair.py` is a single stateless pass (the driver owns the loop). It
reads the latest graph + `04_report.json` (+ `01_extracted.json` for source
values) and writes a repaired `05_graph.ttl`, appending an audit trail to
`run.log`.

**Repair policy — never fabricate facts:**

- `add` → add the value **from `01_extracted.json`** when present. For
  summarizable text (`description`) with no source value, the LLM may *generate*
  it from the record's own fields. Factual fields with no source value
  (creator/license/identifier/…) are **left unfixed, never invented**.
- `coerce` → transform the node in place (Literal ⇄ IRI for nodeKind).
- `remove` → drop extra values, keep one (MaxCount).
- `reword` → LLM rewrites the existing literal to satisfy the constraint.
- `manual` / LLM-needed-but-no-key → left unfixed, logged.

LLM-backed repairs (`generate`, `reword`) need `OPENROUTER_API_KEY`; without it
those findings are skipped and the loop's no-progress / max-iteration exit takes
over.

## Run it

```bash
python assets/repair.py <graph.ttl> 04_report.json \
    --extracted 01_extracted.json --out-dir <run-dir> [--no-llm]
```
```python
from repair import run_repair
run_repair("02_graph.ttl", "04_report.json", out_dir="runs/<id>",
           extracted_path="runs/<id>/01_extracted.json")
```

## Inputs / Outputs

- **Input:** latest graph TTL + `04_report.json` (+ `01_extracted.json`).
- **Output:** `05_graph.ttl`; audit lines appended to `run.log`.

## Loop control (owned by the driver)

After repair, re-enter [[shacl-validation]] on `05_graph.ttl`. The driver
proceeds to [[trusted-output]] when **any** holds: conforms; no auto-fixable
violations remain; the violation signature is unchanged (no progress); or
max iterations (default 3) reached — unresolved violations recorded as caveats.
Prompts live in `assets/reprompt_template.md`.

## Next stage

Re-run [[shacl-validation]]; once it conforms (or the loop stops), proceed to
[[trusted-output]].
