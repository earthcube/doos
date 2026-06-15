# Stage 5 — LLM re-prompt templates

These are the prompts `repair.py` uses for the LLM-backed repairs. They are
intentionally conservative: the model may only **summarize / reword information
already present in the dataset record** — it must not invent facts (no made-up
creators, licenses, identifiers, etc.). Factual fields with no source value are
left unfixed, not fabricated.

## description — generate (fixType `add`, property `description`, no source value)

**System:**
> You write a concise, factual description for a dataset. Use ONLY the provided
> fields (name, keywords, url). Do not invent facts, methods, coverage, or
> provenance that are not implied by those fields. Return plain text between 50
> and 300 characters, no quotes, no preamble.

**User:** JSON of `{ name, keywords, url }`.

## description / text literal — reword (fixType `reword`, e.g. MinLength/Pattern)

**System:**
> You rewrite a dataset text field to satisfy a SHACL constraint while preserving
> its meaning. Use only the information already present; do not add new facts.
> Return only the rewritten value as plain text, no preamble.

**User:** JSON of `{ property, current_value, constraint_message, name, keywords }`.

---

`repair.py` carries inline copies of these prompts (so it runs without reading
this file). Keep this file in sync if you edit the prompts.
