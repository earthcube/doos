---
name: llm-output
description: Stage 1 of the SHACL-for-AI-outputs flow. Capture and structure raw LLM output so it can be converted into an RDF knowledge graph downstream. Use when an AI generates structured information that needs to be made machine-validatable.
metadata:
  stage: 1
  flow: shacl-for-ai-outputs
---

# Stage 1 — LLM Output

The AI generates structured information (the raw model response).

## Goal

Capture LLM output in a form that is ready to be converted to RDF. This is the
entry point of the validation pipeline: everything downstream depends on the
output being structured and parseable.

## Inputs

- A prompt / task given to the LLM.

## Outputs

- Structured information from the LLM (e.g. JSON, JSON-LD, key/value records).

## Next stage

[[rdf-knowledge-graph]] — convert this output to an RDF representation.

## To expand later

- Prompting patterns that produce reliably structured output.
- Schema/contract the model is asked to fill.
- Handling malformed or partial responses.
