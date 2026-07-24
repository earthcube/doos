---
name: decoder-lift-rdf
description: Stage 2 of the decoder pipeline. Deterministically convert the Stage 1 metadata record (url, name, description, keywords) into a schema:Dataset RDF graph (Turtle) using the canonical https://schema.org/ vocabulary, with a stable minted IRI. Use to turn structured AI output into triples ready for SHACL validation.
metadata:
  stage: 2
  flow: decoder
---

# Stage 2 — decoder-lift-rdf

Convert `01_extracted.json` into a `schema:Dataset` RDF graph.

## What it does

`assets/lift.py` is a **pure, deterministic** mapping — no LLM. It builds a
JSON-LD document from `assets/jsonld_context.json` (`@vocab:
https://schema.org/`) and lifts it to triples with rdflib, so every type and
property lands in the canonical `https://schema.org/` namespace that the Stage 3
shape targets. The same input always yields the same graph.

Mapping (minimal set → schema.org): `name → schema:name`,
`description → schema:description`, `url → schema:url` (as an IRI), each
`keywords[]` item → `schema:keywords`. Only non-null/non-empty values produce
triples.

## Run it

```bash
python assets/lift.py 01_extracted.json --out-dir <run-dir> [--iri-base BASE]
```
```python
from lift import run_lift
run_lift("01_extracted.json", out_dir="runs/<id>")
```

## Inputs / Outputs

- **Input:** `01_extracted.json` (Stage 1).
- **Output:** `02_graph.ttl` (Turtle).

## Key behavior

- **IRI policy (PLAN.md §4.2):** the Dataset IRI is `<BASE>/<slug>` where `BASE`
  defaults to `https://doos.earthcube.org/id/dataset` (override with
  `$DOOS_IRI_BASE` or `--iri-base`) and `slug` = first 16 hex of
  `sha256(normalized_url)` — stable and collision-resistant.
- Blank nodes are skolemized here (authority `http://gleaner.io`, matching Stage
  3) so validation reports are stable across runs.
- Examples in `assets/examples/`.

## Next stage

[[decoder-validate-shacl]] — validate `02_graph.ttl` against the Dataset SHACL shape.
