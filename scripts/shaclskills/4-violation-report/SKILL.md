---
name: violation-report
description: Stage 4 of the SHACL-for-AI-outputs flow. Turn Stage 3's structured validation results into a fix-oriented report — deterministic fixType/autoFixable tags plus LLM-enriched (or templated) issue/suggestedFix prose — so the repair stage can act on it programmatically. Use when validation reports non-conformance and the failures need to be understood and fixed.
metadata:
  stage: 4
  flow: shacl-for-ai-outputs
---

# Stage 4 — Violation Report

Turn validation results into an actionable, fix-oriented report.

## What it does

`assets/parse_report.py` reads `03_results.json` and produces a report where:

- **Control-flow fields are deterministic (code).** `fixType` comes from a
  `constraintComponent → fixType` table (`MinCount→add`,
  `Datatype/NodeKind→coerce`, `MaxCount→remove`, `MinLength/Pattern→reword`,
  else `manual`); `autoFixable = fixType != "manual"`. These gate the repair
  loop, so the LLM never decides them.
- **Prose is LLM-enriched, optional.** One batched call writes the human-facing
  `issue` / `suggestedFix`. With no `OPENROUTER_API_KEY` it falls back to
  deterministic templates, so the stage always runs.

## Run it

```bash
python assets/parse_report.py 03_results.json --out-dir <run-dir> [--no-llm]
```
```python
from parse_report import run_report
run_report("03_results.json", out_dir="runs/<id>", use_llm=True)
```

## Inputs / Outputs

- **Input:** `03_results.json` (Stage 3); `03_report.ttl` available for context.
- **Outputs:**
  - `04_report.json` — `{ summary, findings[] }`. Validates against
    `assets/violation_schema.json`. Carries Stage 3's snake_case keys verbatim
    and adds `severity_bucket`, `fixType`, `autoFixable`, `issue`,
    `suggestedFix`. The array is `findings` (includes warnings), violations
    sorted first.
  - `04_report.md` — human-readable, grouped by severity then focus node.

## Key behavior

- `summary.conforms` = no `sh:Violation` findings; `n_autofixable` counts
  fixable findings. The orchestration node derives the violation signature and
  the "has auto-fixable violations" flag from `findings`.

## Next stage

[[repair]] — apply fixes from `04_report.json`, then re-validate.
