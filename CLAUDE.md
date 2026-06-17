# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DOOS (Deep Ocean Observation System) is an EarthCube monorepo for harvesting, converting, validating, and federating ocean observation metadata. Each provider with a subproject lives under `projects/`: ARGO, OBIS, ERDDAP, BCO-DMO, CCHDO, AODN, BODC, CIOOS. (EMODNET, OceanSITES, and marine-regions are candidate sources tracked in `README.md`/`docs/sources.md`, not yet subprojects.) Data is transformed to RDF/JSON-LD conforming to Schema.org + GeoSPARQL, validated against OIH depth profile SHACL shapes.

The end goal is a federated SPARQL graph (live endpoints linked from `README.md`) that exposes a consistent **depth profile** across providers.

**Never commit unless the user explicitly asks.**

## Environment

`pyproject.toml` requires Python `>=3.13`. Two dependency manifests coexist and intentionally differ:

- `requirements.txt` — minimal RDF/validation core (`geopandas pandas rdflib pyshacl morph_kgc pyld pyarrow`). Enough for the validators and most `projects/` transforms.
- `pyproject.toml` — the full set, adding `dspy`, `langchain-openai`, `langgraph`, `playwright`, `pyrudof`, `saxonche` (XSLT), `sparqlwrapper`, `tavily`. Needed for `text2query/`, the pyrudof validator, and the AODN XSLT path.

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt   # core only
uv sync                              # full pyproject deps (text2query, XSLT, pyrudof)
```

Some subprojects carry their own `.venv` (e.g. `projects/ARGO/.venv`) and extra deps not in either manifest (`text2query` also needs `rich diskcache aiohttp`).

## Commands

**Build:**
```bash
uv build
```

**Lint / format / typecheck:**
```bash
ruff check . && ruff check --fix .
black .
mypy .
```

**Tests:** No pytest suite — testing is manual via CLI scripts:
```bash
# Single-threaded baseline
python scripts/shapeValidator/validateToOxigraph.py <endpoint> <shapefile.ttl> --output results.nq

# Parallel, high-throughput (recommended for large runs)
python scripts/shapeValidator/validateToParquet.py <endpoint> <shapefile.ttl> --workers 8 --output-dir shacl_results
```

**If pytest is needed** (it's in dev deps):
```bash
pytest tests/ -v
pytest tests/test_foo.py::test_bar   # single test
```

**Verify any CLI change:**
```bash
python path/to/script.py --help
```

## Architecture

### Data pipeline

1. **Ingest** — fetch metadata from HTTP APIs, sitemaps, files (NetCDF, GeoParquet, XML, JSON-LD)
2. **Transform** — map to Schema.org + GeoSPARQL RDF via one of five approaches, chosen per provider:
   - JSON-LD templates (BCO-DMO, OBIS)
   - RML rules run through `morph-kgc` (ARGO, geoparquet)
   - XSLT via `saxonche` for ISO-19139/19115 XML sources (AODN — see `projects/AODN/transformations/`)
   - SSSOM-driven mapping (`mapping/SSSOM/sssom_to_jsonld.py`): a `.sssom.tsv` file declares flat-JSON→schema.org field correspondences with `source_jsonpath`/`target_jsonpath` extension slots, and the script drives the transform entirely from that file — no field names hard-coded
   - **SHACL-AF SPARQL rules** (CCHDO): Python builds an intermediate `cchdo:` namespace RDF graph, then `pyshacl.shacl_rules()` fires `sh:SPARQLRule` CONSTRUCT rules to produce schema.org or MLCommons Croissant JSON-LD — see `projects/CCHDO/`
3. **Validate** — run SHACL validation against `SHACL/` shapes
4. **Export** — serialize to N-Triples/N-Quads/Turtle for SPARQL endpoints
5. **Query** — federated SPARQL across providers; `text2query/text2SPARQL.py` is a DSPy program converting natural language → SPARQL against any OpenAI-compatible LLM provider

### Key directories

| Path | Purpose |
|---|---|
| `projects/` | Per-provider subprojects (ARGO, OBIS, BCO-DMO, CCHDO, ERDDAP, AODN, BODC, CIOOS) |
| `mapping/SSSOM/` | SSSOM-driven flat-JSON → schema.org JSON-LD transform (currently untracked) |
| `scripts/shapeValidator/` | SHACL validation suite — three engines (pyshacl, pyrudof, pyoxigraph) |
| `scripts/shapeValidator/defs/` | Shared utilities: `getGraphs.py`, `shaclValidator.py`, `getConstruct.py`, `parquet_streaming.py` |
| `SHACL/` | OIH depth profile shape files (`.ttl`) |
| `SPARQL/` | Reusable SPARQL queries (`.rq`) and update scripts |
| `text2query/` | DSPy natural language → SPARQL |
| `.opencode/skills/` | AI skills: `fair-assessment`, `oih-graph` |
| `docs/` | Project notes — `sources.md` tracks provider status |

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

## Code conventions

**Naming:** `snake_case` for functions/vars/files; `PascalCase` for classes (rare).

**Import order:**
1. stdlib (`sys`, `os`, `json`, `argparse`, `pathlib`)
2. third-party (`geopandas`, `rdflib`, `pyoxigraph`)
3. local (`from defs.shaclValidator import validate_with_shacl`)

**Formatting:** 4-space indent, black-compatible (line length ~88–100), Unix LF, 2 blank lines before/after top-level functions.

**Docstrings:** Google/PEP257 style for public functions and CLI entry points.

**Error handling:**
```python
try:
    ...
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
```

**CLI pattern** — every script uses `argparse` + `if __name__ == "__main__":`. Progress via `tqdm`. File I/O with `Path(...).mkdir(parents=True, exist_ok=True)`.

**RDF/SHACL patterns:**
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

**SHACL-AF PREFIX gotcha:** pyshacl does not auto-propagate Turtle `@prefix` declarations into the SPARQL strings inside `sh:construct`. Standard prefixes (like `schema:`) may work incidentally, but any non-standard prefix (`cr:`, `dct:`, custom vocabs) will raise `Unknown namespace prefix`. Fix: embed explicit `PREFIX` declarations at the top of every `sh:construct` SPARQL string, even when they are already declared as Turtle prefixes in the same file.

**JSON-LD `@language` gotcha:** setting `"@language": "en"` in a framing context causes all plain string literals to serialize as `{"@value": "...", "@language": "en"}` objects instead of bare strings. Omit `@language` from the context unless the spec requires it.

Output formats: N-Triples (`.nt`), N-Quads (`.nq`), Turtle (`.ttl`).

**User-Agent and timeouts:** always set `User-Agent` and `timeout=30` on HTTP calls.

## OpenCode skills

Use the `skill` tool when relevant:
- `fair-assessment` — evaluate FAIR compliance of a dataset/metadata record
- `oih-graph` — execute SPARQL queries against OIH metadata graphs
