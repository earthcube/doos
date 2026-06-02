---
name: rdf-knowledge-graph
description: Stage 2 of the SHACL-for-AI-outputs flow. Convert structured LLM output into an RDF / knowledge-graph representation so it can be validated against SHACL shapes. Use when you have structured AI output that needs to become triples.
metadata:
  stage: 2
  flow: shacl-for-ai-outputs
---

# Stage 2 — RDF / Knowledge Graph

Convert the LLM output to an RDF representation.

## Goal

Turn the structured information from Stage 1 into RDF triples (a knowledge
graph) so that SHACL constraints can be applied. This step gives the data
explicit semantics: nodes, edges, and typed relationships.

## Inputs

- Structured LLM output ([[llm-output]]).

## Outputs

- An RDF graph (e.g. Turtle, N-Triples, JSON-LD) representing the data.

## Next stage

[[shacl-validation]] — validate the graph against SHACL shapes.

## To expand later

- Mapping rules from JSON/JSON-LD to RDF.
- Vocabulary / ontology selection (schema.org, domain ontologies).
- Handling blank nodes, IRIs, and datatypes.
