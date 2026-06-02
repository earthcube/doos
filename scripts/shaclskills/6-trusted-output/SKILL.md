---
name: trusted-output
description: Stage 6 of the SHACL-for-AI-outputs flow. After validation (and any repair), write a provenance record of the run as a best-effort RAiD v1.6-style document plus a short narrative — capturing the source URL, produced RDF, shape, repair passes, and final conformance. Use to emit validated, documented output as the pipeline's final artifact.
metadata:
  stage: 6
  flow: shacl-for-ai-outputs
---

# Stage 6 — Trusted Output

Write the provenance record of what happened to get here.

## What it does

`assets/render_record.py` reads the finished run directory (robust to missing
files) and emits a structured record of the run plus a short write-up. It parses
`run.log` for repair passes/fixes and the latest graph for the dataset IRI and
triple count.

## Run it

```bash
python assets/render_record.py <run-dir> [--run-id ID] [--start YYYY-MM-DD]
                               [--end YYYY-MM-DD] [--no-llm]
```
```python
from render_record import run_record
run_record("runs/<id>", run_id="<id>")
```

## Inputs / Outputs

- **Input:** the run directory (`00_input.json`, `01_extracted.json`,
  `0?_graph.ttl`, `03_conforms.json`, `04_report.json`, `run.log`).
- **Outputs:**
  - `06_raid.json` — RAiD v1.6-style record (see below).
  - `06_record.md` — short narrative + a facts table.

## Key behavior — RAiD is a best-effort fit

RAiD models research *activities*, so the mapping is approximate (PLAN.md §4.6).
Real RAiD **block names** are used (`identifier`, `title`, `date`, `description`,
`access`, `contributor`, `organisation`, `relatedObject`,
`alternateIdentifier`), but **type/vocabulary IRIs are explicit `PLACEHOLDER`s**
— not fabricated controlled-vocab values — and the identifier is marked
`unregistered-local-identifier`. The **authoritative pipeline facts** live under
an `x_pipeline` extension (source URL, extraction source, fields, shape,
triples, repair passes, fixes, final conformance). The narrative is LLM-written
when `LLM_API_KEY` is set, deterministic template otherwise. Template:
`assets/raid_template.json`; prompt: `assets/narrative_prompt.md`.

> The RAiD mapping is intentionally provisional — revisit when a registration
> target and its controlled vocabularies are chosen.

## Inputs from

A conforming RDF graph (passed [[shacl-validation]], possibly after [[repair]]).
This is the end of the pipeline.
