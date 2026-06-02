# Stage 6 — narrative prompt

Used to write the short human-readable write-up of the run. The model is given
the assembled facts as JSON and must summarize **only** those facts.

**System:**
> You write a short, factual provenance note (3-6 sentences) describing what a
> metadata validation pipeline did to a dataset record. Use ONLY the supplied
> facts; do not invent steps, numbers, or outcomes. Plain prose, no headings, no
> preamble.

**User:** JSON of the gathered run facts (`x_pipeline` block).

---

`render_record.py` carries an inline copy of this prompt. Without an
`OPENROUTER_API_KEY` it falls back to a deterministic template narrative.
