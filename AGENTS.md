# AGENTS.md

> Kept in sync with `CLAUDE.md` — that file is the canonical source of project
> guidance. Update both together if either changes.

## Purpose
Instructions for agentic coding agents working in the DOOS (Deep Ocean Observation
System) EarthCube monorepo: harvesting, converting, validating, and federating ocean
observation metadata as RDF/JSON-LD (Schema.org + GeoSPARQL), validated against OIH
depth profile SHACL shapes. The end goal is a federated SPARQL graph exposing a
consistent **depth profile** across providers.

**Never commit unless the user explicitly asks.**

Key dirs:
- `projects/`: Per-provider subprojects (ARGO, OBIS, ERDDAP, BCO-DMO, CCHDO, AODN, BODC, CIOOS)
- `mapping/SSSOM/`: SSSOM-driven flat-JSON → schema.org JSON-LD transform (`kobo/` holds a GAIA Kobo metadata-form mapping)
- `mapping/Croissant/`: MLCommons Croissant JSON-LD outputs
- `scripts/shapeValidator/`: SHACL validation tools (validateToOxigraph.py, validateToParquet.py, validateToRudof.py, validateToParquetRudof.py, benchmark_shacl_engines.py)
- `scripts/shapeValidator/defs/`: Shared utilities (getGraphs.py, shaclValidator.py, getConstruct.py, parquet_streaming.py)
- `scripts/text2query/`: DSPy natural language → SPARQL (`text2SPARQL.py`)
- `scripts/SPARQLupdate/`: `insertUpdates.py` — apply SPARQL UPDATE inserts to a graph
- `SHACL/`: Shapes files (.ttl)
- `SPARQL/`: Reusable queries (.rq) and update scripts
- `.opencode/skills/`: AI skills (`fair-assessment`, `oih-graph`)
- `skills/`: Standalone skills (`crateskill` RO-Crate, `shaclskills` SHACL workflow)
- `docs/`: Notes (sources.md tracks provider status)

## Environment Setup
`pyproject.toml` requires Python `>=3.13`. Two dependency manifests coexist and
intentionally differ:
- `requirements.txt` — minimal RDF/validation core (`geopandas pandas rdflib pyshacl morph_kgc pyld pyarrow`); enough for the validators and most `projects/` transforms.
- `pyproject.toml` — the full set, adding `dspy`, `langchain-openai`, `langgraph`, `playwright`, `pyrudof`, `saxonche` (XSLT), `sparqlwrapper`, `tavily`; needed for `text2query`, the pyrudof validator, and the AODN XSLT path.

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt   # core only
uv sync                              # full pyproject deps (text2query, XSLT, pyrudof)
```

Some subprojects carry their own `.venv` (e.g. `projects/ARGO/.venv`) and extra deps
not in either manifest (`text2query` also needs `rich diskcache aiohttp`).

Git repo: yes. NEVER commit unless user asks explicitly.

## Build, Lint, Test Commands
**Build:** `uv build` (wheel/sdist)

**Lint/format/typecheck:**
```bash
ruff check . && ruff check --fix .  # Lint
black .                             # Format
mypy .                              # Typecheck
```

**Tests:** No pytest suite. Manual scripts only:
```bash
# Single-threaded (safe baseline)
python scripts/shapeValidator/validateToOxigraph.py <endpoint> <shapefile.ttl> --output results.nq

# Recommended for large runs (parallel, streams to Parquet)
python scripts/shapeValidator/validateToParquet.py <endpoint> <shapefile.ttl> --workers 8 --output-dir shacl_results
```

**If pytest is needed** (it's in dev deps):
```bash
pytest tests/ -v                    # All tests
pytest tests/test_foo.py::test_bar  # Single test
```

**Verify any CLI change:** `python path/to/script.py --help`

## Architecture

### Data pipeline
1. **Ingest** — fetch metadata from HTTP APIs, sitemaps, files (NetCDF, GeoParquet, XML, JSON-LD)
2. **Transform** — map to Schema.org + GeoSPARQL RDF via one of five approaches, chosen per provider:
   - JSON-LD templates (BCO-DMO, OBIS)
   - RML rules run through `morph-kgc` (ARGO, geoparquet)
   - XSLT via `saxonche` for ISO-19139/19115 XML sources (AODN — see `projects/AODN/transformations/`)
   - SSSOM-driven mapping (`mapping/SSSOM/sssom_to_jsonld.py`): a `.sssom.tsv` file declares flat-JSON→schema.org field correspondences; the script drives the transform entirely from that file — no field names hard-coded
   - **SHACL-AF SPARQL rules** (CCHDO): Python builds an intermediate `cchdo:` namespace RDF graph, then `pyshacl.shacl_rules()` fires `sh:SPARQLRule` CONSTRUCT rules to produce schema.org or MLCommons Croissant JSON-LD — see `projects/CCHDO/`
3. **Validate** — run SHACL validation against `SHACL/` shapes
4. **Export** — serialize to N-Triples/N-Quads/Turtle for SPARQL endpoints
5. **Query** — federated SPARQL; `scripts/text2query/text2SPARQL.py` is a DSPy program converting natural language → SPARQL against any OpenAI-compatible LLM provider

### Validation engines
- **`validateToOxigraph.py`** — single-threaded, pyshacl backend, safe baseline
- **`validateToParquet.py`** — `ProcessPoolExecutor` parallelism, streams results to Parquet (zstd), recommended for production
- **`validateToRudof.py`** — Rust-based pyrudof engine; faster but no regex backreferences → use `SHACL/ERDDAP_simple.ttl` not `ERDDAP.ttl`
- **`validateToParquetRudof.py`** — pyrudof engine with the parallel/Parquet harness (same `ERDDAP_simple.ttl` caveat)
- **`benchmark_shacl_engines.py`** — compares the three engines on the same input

All take `<endpoint> <shapefile.ttl>`; the endpoint is queried for named graphs which are each validated against the shapes.

### SHACL shape files
Validation shapes (in `SHACL/`):
- `ERDDAP.ttl` — full OIH shapes (ID, core fields, spatial polygon); PySHACL only
- `ERDDAP_simple.ttl` — pyrudof-compatible drop-in; relaxes the polygon closed-ring regex backreference
- `ERDDAP_test.ttl` — minimal single-shape sanity check for `variableMeasured`/`latitude`
- `googleRequired.ttl` — checks the three fields required by Google Dataset Search (`url`, `description`, `name`)
- `depth_one.ttl` — OIH depth profile presence check: requires `DepBelowSurf` in `variableMeasured`

Transform shapes (per-provider, under `projects/`):
- `projects/CCHDO/SHACL_AF/nc_metadata_to_schema.ttl` — SHACL-AF rules: NetCDF metadata → schema.org `Dataset`
- `projects/CCHDO/SHACL_AF/nc_metadata_to_croissant.ttl` — SHACL-AF rules: NetCDF metadata → MLCommons Croissant 1.1

## Code Conventions
### Naming
- **snake_case**: functions, vars, files (`construct_graph`, `validate_with_shacl`)
- **PascalCase**: Classes (rare)

### Imports
**Order:**
1. stdlib: `import sys, os, json, argparse`, `from pathlib import Path`
2. 3rd party: `import geopandas as gpd`, `from rdflib import Graph`, `import pyoxigraph`
3. Local: `from defs.shaclValidator import validate_with_shacl`

### Formatting
4-space indent (PEP8), black-compatible: line-length ~88-100, Unix LF. 2 blank lines
before/after top-level functions.

### Docstrings
Google/PEP257 style for public functions and CLI entry points.

### Error Handling
```python
try:
    ...
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
```

### CLI Scripts
All scripts use `argparse` + `if __name__ == "__main__":`. Progress via `tqdm`.
File I/O with `Path(...).mkdir(parents=True, exist_ok=True)`.

### RDF/SHACL Patterns
```python
# rdflib
Graph().parse(data=ntriples, format='nt')
# pyoxigraph
store.load(src, RdfFormat.TURTLE)
# pyshacl validation (via wrapper)
validate_with_shacl(report_graph, shapes_file)
# pyshacl SHACL-AF rule expansion (returns expanded graph, not a report)
from pyshacl import shacl_rules
expanded_graph = shacl_rules(data_graph, shacl_graph=str(shapes_path), shacl_graph_format="ttl")
# morph-kgc
morph_kgc.materialize(config, data_dict)
# pyld JSON-LD → RDF
jsonld.to_rdf(doc, {'format': 'application/n-quads'})
# pyld framing (structure flat JSON-LD into nested tree)
jsonld.frame(raw_jsonld, frame_dict)
```

Output formats: N-Triples (`.nt`), N-Quads (`.nq`), Turtle (`.ttl`).

**SHACL-AF PREFIX gotcha:** pyshacl does not auto-propagate Turtle `@prefix`
declarations into the SPARQL strings inside `sh:construct`. Standard prefixes (like
`schema:`) may work incidentally, but any non-standard prefix (`cr:`, `dct:`, custom
vocabs) will raise `Unknown namespace prefix`. Fix: embed explicit `PREFIX`
declarations at the top of every `sh:construct` SPARQL string, even when already
declared as Turtle prefixes in the same file.

**JSON-LD `@language` gotcha:** setting `"@language": "en"` in a framing context
causes all plain string literals to serialize as `{"@value": "...", "@language":
"en"}` objects instead of bare strings. Omit `@language` from the context unless the
spec requires it.

### Security Best Practices
No secrets in code. Always set `User-Agent` and `timeout=30` on HTTP calls. Validate
inputs. Use `tempfile.mkdtemp(prefix='...')` for temp dirs.

## Skills
OpenCode skills (`.opencode/skills/`) — use the `skill` tool when relevant:
- `fair-assessment` — evaluate FAIR compliance of a dataset/metadata record
- `oih-graph` — execute SPARQL queries against OIH metadata graphs

Standalone skills (`skills/`): `crateskill` (RO-Crate), `shaclskills` (SHACL workflow).

## Verification After Changes
1. Lint/format/typecheck (`ruff`, `black`, `mypy`)
2. Run affected scripts: `python path/to/script.py --help`
3. Manual test RDF/SHACL output
4. `git diff` + `git status` before any commit (only commit when the user asks)
