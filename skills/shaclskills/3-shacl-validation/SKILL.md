---
name: shacl-validation
description: Stage 3 of the SHACL-for-AI-outputs flow. Validate a schema:Dataset RDF graph against the Google Dataset SHACL shape (googleRecommended.ttl) with pySHACL, emitting structured results and a severity-aware conformance verdict. Use to check semantic validity (required links, datatypes, cardinality) — not just format.
metadata:
  stage: 3
  flow: shacl-for-ai-outputs
---

# Stage 3 — SHACL Validation

Validate the RDF graph against the Google Dataset SHACL shape.

## What it does

`assets/validate.py` runs **pySHACL** (one call: `inference="rdfs"`, skolemize
`gleaner.io`) over the graph against `assets/googleRecommended.ttl`, reusing the
shared validator's `SH`/`_get_obj` helpers so result rows match the rest of the
codebase. It validates `02_graph.ttl` on the first pass and `05_graph.ttl` on
repair-loop iterations.

## Run it

```bash
python assets/validate.py <graph.ttl> [--shape SHAPE.ttl] [--out-dir <run-dir>]
```
```python
from validate import run_validation
run_validation("02_graph.ttl", out_dir="runs/<id>")   # shape defaults to bundled
```

## Inputs / Outputs

- **Input:** the latest graph TTL + `assets/googleRecommended.ttl`.
- **Outputs:**
  - `03_report.ttl` — the `sh:ValidationReport` graph (provenance).
  - `03_results.json` — one normalized row per result (`severity`, `focus_node`,
    `result_path`, `source_constraint`, `message`, `value`, …) — the primary
    Stage 4 input.
  - `03_conforms.json` — `{ conforms, raw_conforms, n_violations, n_warnings,
    n_info }`.
- Exit 0 iff zero violations.

## Key behavior — conformance is by severity, not pySHACL's boolean

pySHACL returns `conforms == False` whenever **any** result exists, **including
`sh:Warning`s**. The Dataset shape warns on every missing *recommended* field,
so a valid Dataset (good name + description) has `raw_conforms=False` with ~12
warnings. Therefore **`conforms` here = zero `sh:Violation` results** (warnings
ignored). Keying the repair loop off the raw boolean would loop forever.

## The shape (`googleRecommended.ttl`)

Targets `schema:Dataset`, all IRIs normalized to `https://schema.org/`.
**Required (`sh:Violation`):** `name`, `description` (50–5000 chars), and
`contentUrl` within any `distribution`. **Recommended (`sh:Warning`):** `url`,
`identifier`, `keywords`, `license`, `creator`, `publisher`, `citation`,
`variableMeasured`, temporal/`spatialCoverage`, `sameAs`, `alternateName`,
`version`, `distribution`. Flip a `sh:severity` to change the required set.
For scale, see the endpoint/Parquet/rudof variants in `../../shapeValidator/`.

## Next stage

[[violation-report]] — turn `03_results.json` into a fix-oriented report.
