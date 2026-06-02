---
name: llm-output
description: Stage 1 of the SHACL-for-AI-outputs flow. Given a dataset URL, produce a consistent minimal metadata record (url, name, description, keywords) by reusing embedded schema.org JSON-LD when present, else extracting with an LLM. Use as the entry point that turns a dataset URL into structured, machine-validatable input.
metadata:
  stage: 1
  flow: shacl-for-ai-outputs
---

# Stage 1 — LLM Output

Turn a **dataset URL** into a fixed, structured metadata record ready to be
lifted to RDF.

## What it does

`assets/extract.py` fetches the URL and applies **reuse-embedded-else-extract**:

1. **Fetch** the page (browser UA, timeout, 5 MB size cap).
2. **Reuse embedded metadata (deterministic, no LLM):** scan for
   `<script type="application/ld+json">` blocks, flatten `@graph`/arrays, and
   pick the first node typed `Dataset` (then `DataCatalog`). Normalize it into
   the fixed field set.
3. **LLM fallback:** if no usable embedded metadata, send the page's visible
   text to the LLM (`orchestration/llm.py`) to fill the **same** fields. Gated
   on `llm_available()` — skipped when no `OPENROUTER_API_KEY`.

The output always carries the same keys (the minimal contract, PLAN.md §4.1) so
every downstream stage is deterministic.

## Run it

```bash
# CLI (file:// works for local fixtures)
python assets/extract.py <dataset-url> --out-dir <run-dir> [--no-llm]
```
```python
# Import (used by the orchestration node)
from extract import run_extract
run_extract(url, out_dir="runs/<id>", use_llm=True)
```

## Inputs / Outputs

- **Input:** a dataset URL (the driver also writes `00_input.json` = `{ "url": … }`).
- **Output:** `01_extracted.json` — `{ url, name, description, keywords[], source }`.
  Absent fields are `null` / `[]` (keys are never dropped). `source ∈
  {embedded-jsonld, llm-extracted, none}`. Validates against `assets/schema.json`.

## Key behavior

- **No fabrication.** The LLM prompt (`assets/extract_prompt.md`) forbids
  inventing fields; unknowns stay `null`/`[]`. With no metadata and no LLM the
  result is `source="none"` with empty fields — honest, not guessed.
- JSON-LD normalization tolerates `@type` as string/list/IRI/prefixed, language
  maps, `keywords` as a comma-string or list of `DefinedTerm`, and `url` falling
  back to `@id` then the input URL.

## Next stage

[[rdf-knowledge-graph]] — lift `01_extracted.json` to a `schema:Dataset` graph.
