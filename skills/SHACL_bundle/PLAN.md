# PLAN — Build-out of the Decoder Skill Bundle

> Working spec. Each stage below has a **Directive** (what to build) and a
> **Build mode** (code / SHACL / LLM-only). Stages share data through a run
> directory of temporary files (see §3). A LangGraph driver (see §7) sequences
> the stages and implements the validate→report→repair loop.

## 0. What this bundle is

A six-stage chain that turns a **dataset URL** into **validated, trustworthy
RDF** by routing extracted metadata through an RDF + SHACL pipeline. Flow
(see `shaclWorkflowImage.jpg`):

```
1 decoder-extract-metadata → 2 decoder-lift-rdf → 3 decoder-validate-shacl
   → 4 decoder-report-findings → 5 decoder-repair-graph ─┐
                                    ├─(loop back to 3 until conforms)→ 6 decoder-emit-provenance
        3 decoder-validate-shacl ◄───────────────────────┘
```

Tagline: *validate meaning, not just format.* JSON Schema proves data is
well-formed; SHACL proves it is meaningful.

Each stage is an **independent, atomic skill** (a `SKILL.md` + an `assets/`
dir). They are *composed* by the LangGraph driver, but each must be runnable on
its own given its input file(s).

## 0a. Decisions (locked 2026-06-02)

These resolve the prior open blockers. The rest of the doc reflects them.

1. **Execution model = Hybrid.** Stages **2 (RDF) and 3 (validation) are pure,
   deterministic Python — no LLM.** Stages **1, 4, 5, 6 use an LLM.** Every
   stage is a Python module under its `assets/` (importable *and* CLI-runnable);
   `SKILL.md` documents the stage and lets it run standalone in Claude Code. The
   LangGraph driver imports and calls these modules — it does not invoke skills
   agentically.
2. **LLM access = any OpenAI-compatible API via LangChain.** LLM stages call
   `langchain_openai.ChatOpenAI(base_url=$LLM_BASE_URL, api_key=$LLM_API_KEY,
   model=$LLM_MODEL)`. Provider/model is fully env-driven and swappable —
   OpenRouter (the default `LLM_BASE_URL`), native OpenAI, a hosted provider, or
   a local server, with no code change. Legacy `OPENROUTER_*` vars are honoured
   as fallbacks. One shared helper (`orchestration/llm.py`) constructs the
   client; stages import it.
3. **Stage 1 input = reuse-embedded-else-extract.** Fetch the URL; if it carries
   embedded `schema.org` JSON-LD (or other structured metadata), parse and reuse
   it; otherwise fall back to LLM extraction from page text.
4. **Canonical namespace = `https://schema.org/`** (with trailing slash),
   applied identically to the generated RDF (Stage 2) and the SHACL shape
   (Stage 3). The existing `googleRequiredOrg.ttl` mixes `http`/`https` — it
   gets normalized to `https://schema.org/` when adapted.

## 1. Current state

| Stage | Dir | SKILL.md | assets/ | Build mode |
|------|-----|----------|---------|-----------|
| 1 | `decoder-extract-metadata/` | **done** | **built**: `extract.py` + `schema.json` + `extract_prompt.md` | **LLM + code** (URL → reuse JSON-LD / extract structured metadata) |
| 2 | `decoder-lift-rdf/` | **done** | **built**: `lift.py` + `jsonld_context.json` + examples | **code only** (JSON → schema.org RDF, deterministic) |
| 3 | `decoder-validate-shacl/` | **done** | **built**: `validate.py` + `googleRecommended.ttl` | **code only** (pySHACL + shape) |
| 4 | `decoder-report-findings/` | **done** | **built**: `parse_report.py` + `violation_schema.json` | **code + LLM** (results → fix-oriented report) |
| 5 | `decoder-repair-graph/` | **done** | **built**: `repair.py` + `reprompt_template.md` | **code + LLM** (rule fixes + LLM reword, loop) |
| 6 | `decoder-emit-provenance/` | **done** | **built**: `render_record.py` + `raid_template.json` + `narrative_prompt.md` | **code + LLM** (RAiD-style provenance record) |

## 2. Existing tooling to reuse

`../shapeValidator/` has working validators — Stage 3 should wrap one rather
than write a new engine:

- **`defs/shaclValidator.py:validate_with_shacl_results(rdf_graph_text,
  shacl_shape_text, ...)`** — **this is the reuse target for Stage 3.** It takes
  the graph and shape as **text** and runs pySHACL, returning structured
  results. Stage 3's wrapper reads the local TTL files → text → calls this.
- `googleRequiredOrg.ttl` — existing SHACL shape, but it **targets
  `schema:Organization`** and mixes `http`/`https`. We need a normalized
  **`schema:Dataset`** shape (see Stage 3 / §5).
- (Context only — **not** Stage 3 targets) `validateToOxigraph.py`,
  `validateToParquet.py`, `validateToRudof.py` are **SPARQL-endpoint-oriented**
  (they pull graphs from an endpoint via `getGraphs`/`getConstruct`). They do
  not validate a local file, so do not wrap them here. Keep them as references
  for scale/engine choice and `benchmark_shacl_engines.py` for comparisons.

> NOTE (as built): Stage 3's `assets/validate.py` makes **one** pySHACL call
> directly (same config as the shared module: `inference="rdfs"`, skolemize
> `gleaner.io`) and reuses `defs/shaclValidator.py`'s `SH` namespace + `_get_obj`
> extractor so the result-row schema stays identical. It does **not** call
> `validate_with_shacl_results` — that helper discards the report graph, and
> Stage 3 needs `03_report.ttl`. Same engine/config, no forked validator logic.

## 3. Shared run state (how stages pass data)

Stages are atomic but sequential, so they exchange data through a **per-run
working directory** created by the driver:

```
runs/<run-id>/
  00_input.json        # { "url": "<dataset url>" }
  01_extracted.json    # Stage 1 output (structured metadata)
  02_graph.ttl         # Stage 2 output (schema.org RDF, Turtle)
  03_report.ttl        # Stage 3 output (sh:ValidationReport graph; provenance)
  03_results.json      # Stage 3 output (normalized result rows; primary Stage 4 input)
  03_conforms.json     # { conforms, raw_conforms, n_violations, n_warnings, n_info }
  04_report.json       # Stage 4 normalized, fix-oriented violation report
  04_report.md         # Stage 4 human-readable report
  05_graph.ttl         # Stage 5 repaired RDF (overwrites the validation input each loop)
  06_raid.json         # Stage 6 RAiD-style provenance record
  run.log              # append-only event log across all stages
```

Conventions:
- Each skill reads named input file(s), writes named output file(s), exits
  non-zero on hard failure. **No stage holds state in memory across runs.**
- The driver owns `<run-id>` and the loop counter; skills are stateless w.r.t.
  iteration (Stage 5 just reads the latest report + graph and writes a new graph).
- Filenames are the contract. If a better store than flat files is wanted later
  (SQLite, an oxigraph store, LangGraph checkpointer), swap it behind the same
  logical keys — but flat temp files are the v1.

> ALTERNATIVE to explore: hold the run state as the LangGraph `State` object
> (a TypedDict) and only spill large artifacts (TTL, report graph) to disk,
> passing file paths in state. Recommended once the flat-file v1 works.

## 4. Per-stage directives

### Stage 1 — `decoder-extract-metadata/`  (LLM + code) — **BUILT 2026-06-02**
**Directive:** Given a dataset **URL**, produce a consistent set of dataset
metadata fields. **Reuse-embedded-else-extract:** fetch the page; if it carries
embedded structured metadata, reuse it; otherwise extract with the LLM.

> STATUS: `assets/extract.py` (+ `assets/schema.json`, `assets/extract_prompt.md`)
> implemented and tested (CLI + importable `run_extract(url, out_dir, use_llm)`;
> `file://` URLs work for fixtures). Fetch (UA/timeout/size-cap) + JSON-LD
> detection are deterministic; LLM is fallback only (gated on
> `llm_available()`). Emits `01_extracted.json` (validates against
> `schema.json`) with `source ∈ {embedded-jsonld, llm-extracted, none}`.
> Verified: embedded `@graph` Dataset picked correctly → full 1→2→3 CONFORMS;
> comma-separated keywords split; no-data+no-LLM → honest `source=none` with
> keys preserved.

- **Fetch + detect (code):** HTTP GET the URL (set a UA, cap response size,
  respect timeouts; on non-HTML/binary, record content-type and skip parsing).
  Look for embedded `schema.org` metadata in priority order: JSON-LD
  (`<script type="application/ld+json">` with `@type` Dataset/DataCatalog),
  then Microdata/RDFa. If found → normalize directly into the field contract.
- **Fallback (LLM):** if no usable embedded metadata, pass cleaned page
  text/`<head>` to the LLM (via `orchestration/llm.py`) to fill the **same fixed
  field set**. Record `source: "embedded-jsonld" | "llm-extracted"` in the output.
- **Input:** `00_input.json` → `{ "url": "..." }`
- **Output:** `01_extracted.json` — a fixed schema, always the same keys so
  downstream stages are deterministic. **Field set = MINIMAL (locked):**
  - `url` (string), `name` (string), `description` (string),
    `keywords` (array of strings).
  - Use `null`/`[]` for absent fields — **never drop keys** (consistency is the
    point of this stage).
  - Additional schema.org fields (creator, publisher, license, identifier,
    spatial/temporalCoverage, variableMeasured, distribution, …) are **deferred**
    — the shape emits `sh:Warning`s for them, which is acceptable. Add them to
    this contract later when extraction is reliable.
- **Assets to create:** `assets/extract_prompt.md` (the extraction prompt with
  the fixed field list + "emit null when unknown" rule), `assets/schema.json`
  (JSON Schema for `01_extracted.json` so the output is checkable), 1–2 example
  outputs in `assets/examples/`.
- **SKILL.md additions:** the fetch/inspect approach, the fixed field contract,
  malformed/partial-response handling.

### Stage 2 — `decoder-lift-rdf/`  (code only, deterministic) — **BUILT 2026-06-02**
**Directive:** Convert `01_extracted.json` to RDF using **schema.org**
vocabulary, typed as `schema:Dataset`. Pure deterministic mapping — **no LLM**
(per §0a.1); same input always yields the same graph. Use the canonical
namespace **`https://schema.org/`** (per §0a.4) for every type and property.
Primary reference: https://schema.org/Dataset.

> STATUS: `assets/lift.py` (+ `assets/jsonld_context.json`, `assets/examples/`)
> implemented and tested (CLI + importable `run_lift(input_path, out_dir,
> iri_base)`). Builds a JSON-LD doc from the context (`@vocab =
> https://schema.org/`) and lifts via rdflib; `url` emitted as an IRI. Verified:
> 2→3 segment end-to-end (good input → Stage 3 CONFORMS/0 violations; missing
> `description` → 1 violation/exit 1); output is byte-identical on repeat
> (deterministic).

- **Input:** `01_extracted.json`  → **Output:** `02_graph.ttl` (Turtle).
- **Mapping (minimal set → schema.org):**
  - node `a schema:Dataset`, IRI minted per the IRI policy below.
  - `name`→`schema:name`, `description`→`schema:description`,
    `url`→`schema:url`, each item of `keywords[]`→`schema:keywords`.
  - Emit only keys that are non-null/non-empty (absent ⇒ no triple; the shape
    will warn). The mapping table extends naturally as the field contract grows.
- **IRI policy (locked):** **base namespace + slug.** Dataset IRI =
  `<BASE>/<slug>` where `BASE` defaults to `https://doos.earthcube.org/id/dataset`
  (env-overridable, e.g. `DOOS_IRI_BASE`) and `slug` = a stable URL-safe token
  derived from the normalized source URL — use the first 16 hex chars of
  `sha256(normalized_url)` for collision-resistant stability. Skolemize any blank
  nodes in Stage 2 (not Stage 3) so the validation report is stable across runs.
- **Build mode:** deterministic mapping only — `assets/jsonld_context.json`
  (with `"@vocab": "https://schema.org/"`) + `assets/lift.py` using
  `rdflib`/`pyld`. Unmappable/ambiguous fields are dropped or logged, never
  LLM-guessed (ambiguity is resolved upstream in Stage 1).
- **Assets to create:** `assets/jsonld_context.json`, `assets/lift.py`,
  `assets/examples/02_graph.ttl`.

### Stage 3 — `decoder-validate-shacl/`  (code) — **BUILT 2026-06-02**
**Directive:** Validate `02_graph.ttl` (or `05_graph.ttl` on loop iterations)
with **pySHACL** against the shape **`assets/googleRecommended.ttl`**.

> STATUS: `assets/validate.py` is implemented and tested (CLI + importable
> `run_validation(data_path, shape_path=DEFAULT_SHAPE, out_dir)`). It writes
> `03_report.ttl`, `03_results.json`, `03_conforms.json`; exit 0 iff zero
> violations. One pySHACL call (`inference="rdfs"`, skolemize `gleaner.io`),
> reusing `defs/shaclValidator.py`'s `SH`/`_get_obj` for the row schema.
> Verified: bad Dataset → 1 violation/14 warnings/exit 1; good → 0 violations/
> exit 0 with `conforms=True` despite `raw_conforms=False`.

- **Input:** latest graph TTL (`02_graph.ttl`, or `05_graph.ttl` on loop
  iterations) + `assets/googleRecommended.ttl`.
- **Output (as built):** `03_report.ttl` (the `sh:ValidationReport` graph),
  `03_results.json` (normalized rows — primary Stage 4 input), and
  `03_conforms.json`: `{ conforms, raw_conforms, n_violations, n_warnings, n_info }`.
- **CRITICAL — define "conforms" by severity, not pyshacl's boolean.** pyshacl
  returns `conforms == False` whenever *any* result exists, **including
  `sh:Warning`s**. The Dataset shape emits warnings for every missing recommended
  field, so a perfectly fine Dataset (valid name + description) yields
  `conforms=False` + ~14 warnings. The loop must therefore set
  `03_conforms.json.conforms = (count of results with
  sh:resultSeverity == sh:Violation == 0)` — **ignore warnings for conformance.**
  Keying the loop off pyshacl's raw boolean would loop forever. (Verified
  2026-06-02 against the drafted shape.)
- **Asset (DRAFTED):** `assets/googleRecommended.ttl` exists and parses
  (17 NodeShapes, normalized to `https://schema.org/`, `sh:targetClass
  schema:Dataset`). Split: **REQUIRED (`sh:Violation`)** = `name`,
  `description` (50–5000 chars), plus `contentUrl` *within* any distribution;
  **RECOMMENDED (`sh:Warning`)** = `url`, `identifier`, `keywords`, `license`,
  `creator`, `publisher`, `citation`, `variableMeasured`, `temporalCoverage`,
  `spatialCoverage`, `sameAs`, `alternateName`, `version`, `distribution`
  (+`encodingFormat`). Open: confirm the required/recommended split is right for
  the DOOS use case (§5/§8).
- **Build mode (done):** `assets/validate.py` — see the STATUS box above for the
  as-built engine call. Do **not** wrap the endpoint-oriented scripts (see §2).
- **SKILL.md additions (TODO):** engine = pySHACL, shape location, conformance =
  zero-violations semantics, exit codes, link to rudof/parquet variants for scale.

### Stage 4 — `decoder-report-findings/`  (code + LLM) — **BUILT 2026-06-02**
**Directive:** Turn `03_report.ttl` into a report that **explains each issue and
proposes a potential fix**, structured so Stage 5 can act on it programmatically.

> STATUS: `assets/parse_report.py` (+ `assets/violation_schema.json`)
> implemented and tested (CLI + importable `run_report(results_path, out_dir,
> use_llm)`). Deterministic `fixType`/`autoFixable` from a constraint table;
> LLM enriches `issue`/`suggestedFix` prose via `orchestration/llm.py`, with a
> deterministic template fallback when no `LLM_API_KEY` (so it always
> runs). Emits `04_report.json` (validates against `violation_schema.json`) +
> `04_report.md` grouped by severity. Verified on the 2→3→4 segment: violation
> case → 1 violation/13 warnings, conforming case → 0 violations.
> **Output key is `findings` (includes warnings), not `violations`.**

- **Input:** `03_results.json` (the normalized rows Stage 3 already produced —
  each has `severity`, `focus_node`, `result_path`, `source_constraint`,
  `message`, `value`); `03_report.ttl` available for extra context if needed.
- **Output:** `04_report.json` (normalized, machine-actionable) and
  `04_report.md` (human-readable).
- **Normalized violation schema (per result):** carry through Stage 3's
  `03_results.json` keys verbatim (snake_case: `severity`, `focus_node`,
  `result_path`, `source_shape`, `source_constraint`, `message`, `value`,
  `result_id`) — do **not** rename them — then add the repair fields:
  `issue` (plain-language explanation), `suggestedFix` (concrete action, e.g.
  "add `schema:description` ≥ 50 chars"), `fixType`
  (`add` | `coerce` | `remove` | `reword` | `manual`), `autoFixable` (bool).
- **Build mode:** code parses `sh:ValidationResult` triples → normalized records
  (deterministic). **`autoFixable`/`fixType` are set by code from a
  `constraintComponent → fixability` table** (e.g. `MinCountConstraint`→`add`,
  `DatatypeConstraint`→`coerce`, `MaxCountConstraint`→`remove`,
  `MinLength`/`PatternConstraint`→`reword`), because these gate the driver's
  loop and must be deterministic. The LLM only enriches the human-facing
  `issue`/`suggestedFix` prose — it does not decide control flow. Group/sort by
  severity then focus node.
- **Assets to create:** `assets/parse_report.py`, `assets/report_template.md`,
  `assets/violation_schema.json`.

### Stage 5 — `decoder-repair-graph/`  (LLM + code; loops) — **BUILT 2026-06-02**
**Directive:** Use `04_report.json` to **repair the RDF**, then hand back to
Stage 3 for re-validation. The driver loops 3→4→5 until Stage 3/4 report nothing
fixable, then proceeds to Stage 6.

> STATUS: `assets/repair.py` (+ `assets/reprompt_template.md`) implemented and
> tested (CLI + importable `run_repair(graph_path, report_path, out_dir,
> extracted_path, use_llm)`). Single stateless pass; reads latest graph +
> `04_report.json` (+ `01_extracted.json` for source values), writes
> `05_graph.ttl`, appends an audit trail to `run.log`. Verified: full 3→4→5→3
> loop closes (missing description added from source → re-validate CONFORMS);
> `remove-extra` keeps 1 of N; no-source/no-LLM findings left unfixed (not
> fabricated).

- **Input:** latest graph TTL + `04_report.json` (+ `01_extracted.json`)  →
  **Output:** `05_graph.ttl`.
- **Repair policy (as built — never fabricate facts):**
  - `add` → add the value **from `01_extracted.json`** when present (rule-based).
    For summarizable text (`description`) with no source value, the LLM may
    *generate* it from the record's own fields. Factual fields with no source
    value (creator/license/identifier/…) are **left unfixed, never invented**.
  - `coerce` → transform the node in place (Literal ⇄ IRI for nodeKind).
  - `remove` → drop extra values, keep one (MaxCount).
  - `reword` → LLM rewrites the existing literal to satisfy the constraint.
  - `manual` / LLM-needed-but-no-key → leave unfixed, logged to `run.log`.
- **Loop control (owned by the driver, see §7):** max N iterations
  (recommend **3**). Stop and proceed to Stage 6 when **any** holds:
  (a) `03_conforms.json.conforms == true`;
  (b) no `autoFixable` violations remain (only `manual` left);
  (c) **no progress** — the violation count/signature is unchanged from the
  previous iteration (prevents burning iterations re-failing the same reword);
  (d) iteration count hits N.
  In cases (b)–(d), go to Stage 6 with the unresolved violations recorded as
  caveats. Re-validation always re-enters Stage 3 on `05_graph.ttl`.
- **Assets to create:** `assets/repair.py` (rule-based fixes + re-prompt
  orchestration), `assets/reprompt_template.md`, audit entries appended to
  `run.log`.

### Stage 6 — `decoder-emit-provenance/`  (LLM + code) — **BUILT 2026-06-02**
**Directive:** The RDF is generated + validated. Produce a **short write-up of
what happened** to get here, as a **RAiD-style structured record**.
Reference: https://metadata.raid.org/en/v1.6/. RAiD is an imperfect fit — map
what's reasonable, leave the rest, the user will revisit.

> STATUS: `assets/render_record.py` (+ `assets/raid_template.json`,
> `assets/narrative_prompt.md`) implemented and tested (CLI + importable
> `run_record(run_dir, run_id, out_dir, start, end, use_llm)`). Reads the whole
> run dir (robust to missing files), emits `06_raid.json` + `06_record.md`.
> RAiD block names are used with PLACEHOLDER vocab IRIs (not fabricated); the
> authoritative facts live under an `x_pipeline` extension. Narrative is LLM-
> written when a key is set, deterministic otherwise. Verified on happy path
> (conforms) and repair path (parses `run.log` for passes/fixes). **Revisit the
> RAiD mapping later (user).**

- **Input:** the run dir (graphs, reports, `run.log`) → **Output:**
  `06_raid.json` (RAiD-shaped record) + a short Markdown narrative.
- **RAiD mapping (best-effort):** use RAiD blocks like `title`, `description`,
  `date` (start/end of run), `contributor` (the pipeline/agents), `organisation`,
  `relatedObject` (the source dataset URL + the produced RDF), `access`,
  `alternateIdentifier` (run-id). Record: input URL, fields extracted, shape
  validated against, iterations run, violations found/fixed, final conformance.
- **Assets to create:** `assets/raid_template.json`, `assets/render_record.py`,
  `assets/narrative_prompt.md`.
- **SKILL.md additions:** persistence target for the final TTL + RAiD record
  (file v1; triple store later), provenance fields, versioning.

## 5. SHACL shape (gating asset — DRAFTED 2026-06-02)

`decoder-validate-shacl/assets/googleRecommended.ttl` exists, parses, and validates
correctly (see Stage 3). Required = `name`, `description`, distribution
`contentUrl`; everything else is `sh:Warning`. It supersedes an earlier draft
that used `http://schema.org/` (wrong namespace), lacked `name`/`description`,
and marked every field required.

> TO CONFIRM (you): _Is the required/recommended split right for DOOS?_ E.g.
> should `url`, `keywords`, or `license` be promoted to required (`sh:Violation`)?
> Edit severities in the `.ttl` directly — that is the single knob.

## 6. Suggested build order

1. ~~Run-dir layout (§3).~~ **DONE.**
2. ~~`googleRecommended.ttl` (§5) + Stage 3 wrapper.~~ **DONE & verified.**
3. **NEXT:** Lock the Stage 1 field contract (§4.1) + IRI policy (§4.2) — Stage 2
   depends on the exact keys. Then build Stage 2 mapping (produces the
   `02_graph.ttl` the validator already consumes).
4. Stage 4 parser/report, then Stage 5 repair — closes the loop.
5. Stage 1 extractor (feeds the chain) + Stage 6 RAiD record.
6. LangGraph driver (§7) + an end-to-end golden run; update `README.md`.

## 7. Orchestration — LangGraph driver — **BUILT 2026-06-02**

> STATUS: `orchestration/` (`state.py`, `nodes.py`, `graph.py`, `run.py`,
> `llm.py`, `__init__.py`) implemented and tested. Nodes import each stage
> module by file path and call its `run_*` function. Entry point:
> `uv run python -m orchestration.run <url> [--max-iterations N] [--run-id ID]
> [--no-llm] [--no-probe]` (plus `--check-llm` to probe the LLM and exit).
> Creates `runs/<run-id>/`, writes `00_input.json`, runs 1→6 with
> the conditional 3→4→5 loop and all four §4.5 stop conditions. `runs/` is
> gitignored. Deps `langgraph`/`pyshacl`/`rdflib` declared direct.
> **Verified end-to-end (no LLM):** happy path → `1→2→3→4→6` CONFORMS; short
> description → `3→4→5→3→4→6`, one repair pass then no-progress stop, exit 1
> with a RAiD caveat record.

Build a LangGraph app that sequences the six skills and implements the repair
loop. This is a deliverable of this plan.

- **Location:** `orchestration/` (new dir) — `graph.py`, `state.py`, `nodes.py`,
  `llm.py`, `run.py`.
- **Dependencies:** `langchain-openai` **added** (direct dep, 2026-06-02).
  Still to add when building the driver: `langgraph`; and declare the transitive
  RDF deps directly — `pyshacl`, `rdflib`.
- **LLM helper (`llm.py`): BUILT** — `orchestration/llm.py` constructs
  `ChatOpenAI(base_url=$LLM_BASE_URL, api_key=$LLM_API_KEY, model=$LLM_MODEL)`
  (provider-agnostic OpenAI-compatible; `LLM_BASE_URL` defaults to OpenRouter;
  legacy `OPENROUTER_*` vars honoured as fallbacks) and exposes
  `llm_available()` + `complete()`. Stages 1/4/5/6 import it and gate on
  `llm_available()` so they degrade gracefully with no key. Stage 4 already uses it.
  Also exposes `check_llm()` (one-shot connectivity probe) + `describe_config()`;
  the driver runs the probe as a **preflight** (skip with `--no-probe`, or use
  `--check-llm` to probe and exit) so a configured-but-unreachable LLM is
  reported (`final["llm_status"]`) and the run continues deterministically
  instead of silently degrading.
- **State (`state.py`):** a `TypedDict` carrying `run_id`, `run_dir`, `url`,
  paths to each artifact (`extracted`, `graph`, `report`, `results_json`,
  `report_json`, `raid`), `conforms: bool`, `iteration: int`,
  `max_iterations: int`, `prev_violation_sig: str|None` (for the no-progress
  stop condition §4.5c), `events: list`.
- **Nodes (`nodes.py`):** one node per stage, each a thin shell that **imports
  and calls** the stage's `assets/` module with the right run-dir paths and
  updates state (per §0a.1 — not agentic skill invocation). Nodes stay dumb; the
  stage modules do the work.
- **Edges / control flow (`graph.py`):**
  ```
  stage1 → stage2 → stage3 → stage4 → decide
  decide --(conforms OR only-manual-left OR no-progress OR iteration==max)--> stage6 → END
  decide --(else)--> stage5 → stage3   # loop, iteration += 1
  ```
  Implement `decide` as a LangGraph **conditional edge** reading
  `03_conforms.json` / `04_report.json` (the four stop conditions from §4.5).
- **Run dir & run-id:** the driver creates `runs/<run-id>/` (`run_id` = `uuid4`
  hex, or a UTC timestamp + short token) and writes `00_input.json`. Optionally
  use a LangGraph checkpointer for resume; v1 may keep flat files only.
- **Entry point:** `python orchestration/run.py <dataset-url>` → prints final
  `06_raid.json` path + conformance summary.

## 8. Status of decisions

**Locked:** execution model (hybrid), LLM access (OpenRouter via LangChain),
Stage 1 reuse-embedded-else-extract, canonical namespace (`https://schema.org/`),
loop stop conditions, deterministic `autoFixable`, run-id scheme,
**Stage 1 field set = minimal (`url`/`name`/`description`/`keywords[]`)**,
**IRI policy = base-ns + sha256 slug, skolemize in Stage 2**.

**Done:**
- [x] `googleRecommended.ttl` (§5) — drafted, parses, validates correctly.
      *Remaining (optional): confirm the required/recommended split fits DOOS.*
- [x] Stage 3 `validate.py` (§4.3) — built & verified.
- [x] Stage 2 `lift.py` + `jsonld_context.json` (§4.2) — built & verified;
      2→3 segment runs end-to-end and is deterministic.
- [x] Stage 4 `parse_report.py` + `violation_schema.json` (§4.4) + shared
      `orchestration/llm.py` — built & verified; 2→3→4 segment runs.
      `langchain-openai` declared as a direct dep.
- [x] Stage 5 `repair.py` + `reprompt_template.md` (§4.5) — built & verified;
      the 3→4→5→3 loop closes deterministically (add-from-source, remove-extra),
      with honest no-fabrication behavior.
- [x] Stage 1 `extract.py` + `schema.json` + `extract_prompt.md` (§4.1) — built
      & verified; reuse-embedded-else-extract; full 1→2→3 chain CONFORMS.
- [x] Stage 6 `render_record.py` + `raid_template.json` + `narrative_prompt.md`
      (§4.6) — built & verified on happy + repair paths. RAiD mapping is
      best-effort (PLACEHOLDER vocab IRIs); user to revisit.
- [x] **LangGraph driver (§7)** — built & verified end-to-end (`orchestration/`).
      `uv run python -m orchestration.run <url>` runs the whole pipeline.

**The bundle is functionally complete.** Remaining work is polish / config, not
core build:
- [x] Fill in the six `SKILL.md` files — done; each documents its as-built
      assets (what it does, run CLI + import, I/O contract, key behavior, next
      stage).
- [ ] Set `LLM_API_KEY` (+ optionally `LLM_BASE_URL` / `LLM_MODEL`) to activate
      LLM steps (Stage 1 fallback, Stage 4/5/6 prose, Stage 5 reword). Then the
      repair loop can close short/missing descriptions to conformance, not just
      stop on them.
- [ ] Pick the golden test URLs (§6) and confirm the `googleRecommended.ttl`
      required/recommended split fits DOOS.
- [ ] Revisit the RAiD mapping (§4.6).
- [x] `README.md` — written: overview, flow table, layout, setup, quickstart,
      single-stage usage, run-dir contract, shape, design principles, roadmap.
- [x] **pytest suite** (`tests/` + `pytest.ini`) — 30 tests over the
      deterministic behaviors of all 6 stages + the driver; LLM forced off.
      `uv run pytest -c skills/SHACL_bundle/pytest.ini skills/SHACL_bundle/tests`.
      `pytest` added as a dev dep.

**Still open — deferrable, do NOT block stages 2–5:**

- [ ] **RAiD field mapping** (§4.6) — best-effort default is fine for v1; user
      will revisit.
- [ ] **Golden test URLs** — pick 2 real dataset URLs (one *with* embedded
      schema.org JSON-LD, one *without*) to verify the chain end-to-end (§6).
- [ ] **`LLM_MODEL` choice** (default in `llm.py` is a placeholder:
      `anthropic/claude-3.5-sonnet`) + set `LLM_API_KEY` (and `LLM_BASE_URL` if
      not using OpenRouter) — needed to activate LLM prose enrichment in Stages
      4/5/6 (they run deterministically without it).

**Verdict:** no remaining blockers for Stages 2→5. The build can proceed down
the §6 order starting with Stage 2.
