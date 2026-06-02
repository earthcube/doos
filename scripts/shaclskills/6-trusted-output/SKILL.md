---
name: trusted-output
description: Stage 6 of the SHACL-for-AI-outputs flow. Emit validated, consistent, and trustworthy knowledge as the final pipeline output. Use when data has passed SHACL validation (or repair + re-validation) and is ready to be published or consumed.
metadata:
  stage: 6
  flow: shacl-for-ai-outputs
---

# Stage 6 — Trusted Output

Validated, consistent, and trustworthy knowledge.

## Goal

Deliver the final, conforming RDF as trustworthy knowledge that downstream
systems can rely on. This is the output of the pipeline: data that is not just
well-formed but semantically meaningful and validated.

## Inputs

- A conforming RDF graph (passed [[shacl-validation]], possibly after
  [[repair]]).

## Outputs

- Published / consumable validated knowledge graph.

## To expand later

- Persistence and publishing targets (triple stores, files, APIs).
- Provenance and validation metadata attached to the output.
- Versioning and downstream consumption contracts.
