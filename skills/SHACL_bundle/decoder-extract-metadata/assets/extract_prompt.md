# Stage 1 — LLM extraction prompt (fallback)

Used only when a page carries **no** embedded schema.org Dataset metadata.

**System:**
> You extract dataset metadata from a web page's text. Return ONLY a JSON object
> with EXACTLY these keys: `url` (string), `name` (string or null),
> `description` (string or null), `keywords` (array of strings). Use the given
> page URL for `url`. Use null / [] when a field is not clearly present — do NOT
> invent names, descriptions, or keywords that are not supported by the text.
> No preamble, no code fences, JSON only.

**User:** JSON of `{ "url": <page url>, "page_text": <cleaned visible text> }`.

---

`extract.py` carries an inline copy of this prompt so it runs without reading
this file. Keep this file in sync if you edit the prompt.
