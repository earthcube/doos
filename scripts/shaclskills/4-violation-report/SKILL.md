---
name: violation-report
description: Stage 4 of the SHACL-for-AI-outputs flow. Produce a detailed, actionable report of SHACL constraint violations from a validation result. Use when a SHACL validation run reports non-conformance and the failures need to be understood.
metadata:
  stage: 4
  flow: shacl-for-ai-outputs
---

# Stage 4 — Violation Report

Produce a detailed report of constraint violations.

## Goal

Turn the raw SHACL validation result into a clear, detailed report of what
failed and why, so the issues can be fixed in the repair stage.

## Inputs

- A SHACL validation result ([[shacl-validation]]).

## Outputs

- A human- and machine-readable report of violations: focus node, failing
  constraint, message, severity, and expected vs. actual values.

## Next stage

[[repair]] — fix the data based on the reported violations.

## To expand later

- Parsing the SHACL validation report graph (sh:ValidationReport).
- Grouping / prioritizing violations by severity and focus node.
- Output formats (Markdown, JSON, dashboards).
