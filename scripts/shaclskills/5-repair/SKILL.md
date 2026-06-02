---
name: repair
description: Stage 5 of the SHACL-for-AI-outputs flow. Fix data that failed SHACL validation, either automatically or with a human in the loop. Use when a violation report identifies constraint failures that need correcting.
metadata:
  stage: 5
  flow: shacl-for-ai-outputs
---

# Stage 5 — Repair

Fix data automatically or with a human in the loop.

## Goal

Correct the violations identified in the report so the data conforms to the
SHACL shapes. Repairs can be automated (rule-based fixes, re-prompting the LLM)
or reviewed by a human for ambiguous cases.

## Inputs

- A violation report ([[violation-report]]).
- The original RDF graph ([[rdf-knowledge-graph]]).

## Outputs

- A corrected RDF graph, ready for re-validation.

## Next stage

Re-run [[shacl-validation]]; once it conforms, proceed to [[trusted-output]].

## To expand later

- Automatic repair strategies (default values, type coercion, link insertion).
- Re-prompting the LLM with violation feedback.
- Human-in-the-loop review workflows and audit trails.
