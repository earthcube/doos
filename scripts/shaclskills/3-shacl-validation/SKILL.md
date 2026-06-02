---
name: shacl-validation
description: Stage 3 of the SHACL-for-AI-outputs flow. Validate an RDF knowledge graph against SHACL shapes (constraints) to check semantic validity, not just format. Use when you have an RDF graph and a set of SHACL shapes to enforce.
metadata:
  stage: 3
  flow: shacl-for-ai-outputs
---

# Stage 3 — SHACL Validation

Validate the RDF graph against SHACL shapes (constraints).

## Goal

Check the knowledge graph for *semantic* validity by running it against SHACL
shapes. Unlike JSON Schema (which checks shape/format), SHACL checks meaning:
required links, valid relationships, datatypes, cardinality, and vocabulary use.

## Inputs

- An RDF graph ([[rdf-knowledge-graph]]).
- SHACL shapes defining the constraints.

## Outputs

- A SHACL validation result (conforms / does not conform + violations).

## What SHACL catches

- Missing required links
- Orphan nodes
- Invalid relationships
- Datatype issues
- Cardinality errors (1..*)
- Vocabulary mismatches

## Next stage

[[violation-report]] — produce a detailed report of any constraint violations.

## To expand later

- Choice of validation engine (pySHACL, rudof, TopBraid, etc.).
- Writing and organizing SHACL shape files.
- SHACL-AF (advanced features) and SPARQL constraints.
