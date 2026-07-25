# AGENTS.md

> Kept in sync with `CLAUDE.md` — that file is the canonical source of project
> guidance. Update both together if either changes.

## Purpose

Instructions for agentic coding agents working in the DOOS (Deep Ocean Observation
System) EarthCube monorepo: harvesting, converting, validating, and federating ocean
observation metadata as RDF/JSON-LD (Schema.org + GeoSPARQL), validated against OIH
depth profile SHACL shapes. The end goal is a federated SPARQL graph exposing a
consistent **depth profile** (`DepBelowSurf` / related depth variables) across
providers.

**Never commit unless the user explicitly asks.**

### Live endpoints

- Search UI: https://deepoceans.geocodes-aws.earthcube.org/#/landing
- SPARQL (QLever): https://qlever-ui.geocodes-aws-dev.earthcube.org/deepoceans/GxLMVz
- Dev graph endpoint (scripts default):
  https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans

### Providers

| Path | Provider | Role |
|---|---|---|
| `projects/ARGO/` | Argo GDAC floats | GeoParquet → RDF (JSON-LD templates; optional RML) |
| `projects/OBIS/` | Ocean Biodiversity Information System | Auxiliary depth graph from occurrence parquet |
| `projects/BODC/` | British Oceanographic Data Centre | Harvest + SHACL-validate existing schema.org JSON-LD |
| `projects/AODN/` | Australian Ocean Data Network | ISO 19115-3/19139 → schema.org XSLT pipeline |
| `projects/CCHDO/` | CCHDO bottle NetCDF | Intermediate RDF + SHACL-AF rules → schema.org / Croissant |
| `projects/CIOOS/` | Canadian Integrated Ocean Observing System | Early CKAN → schema.org (exploratory) |
| `projects/ERDDAP/` | NOAA OSMC / ERDDAP | Notes and harvested JSON-LD examples only — not a transform pipeline |
| `skills/DOOS_bundle/doos-bco-dmo-index/` | BCO-DMO | ERDDAP search + ISO depth scan → merged N-Triples |

Candidate sources not yet subprojects (see `docs/sources.md`): EMODNET, OceanSITES,
marine-regions, Australian Antarctic Data Group.

When working inside a subproject, prefer that directory's own `README.md` (and
`CLAUDE.md` where present, e.g. `projects/OBIS/CLAUDE.md`).

### Key directories

- `projects/` — per-provider subprojects; see `projects/README.md`
- `projects/dataLocations.md` — canonical provider output paths for loaders
- `skills/DOOS_bundle/doos-bco-dmo-index/` — BCO-DMO ERDDAP + ISO depth → N-Triples
  (`assets/run_pipeline.py`; published `output/output.nt`)
- `mapping/SSSOM/` — SSSOM-driven flat-JSON → schema.org JSON-LD (`kobo/` = GAIA Kobo)
- `mapping/Croissant/` — MLCommons Croissant / GeoCroissant samples and notes
- `scripts/shapeValidator/` — SHACL validation suite (pyshacl, pyrudof, parallel Parquet)
- `scripts/shapeValidator/defs/` — `getGraphs.py`, `getConstruct.py`, `getShape.py`,
  `shaclValidator.py`, `parquet_streaming.py`
- `scripts/loadToOxigraph/` — YAML-driven load of provider outputs into Oxigraph
- `scripts/SPARQLupdate/` — `insertUpdates.py` SPARQL UPDATE inserts
- `scripts/text2query/` — DSPy natural language → SPARQL (`text2SPARQL.py`)
- `scripts/sparqlQueryl.py` — run a `.rq` file against an endpoint → pandas DataFrame
- `build/Dockerfile` — in-memory Oxigraph 0.5.x image (`doos-oxigraph`, port 7878)
- `SHACL/` — OIH depth / Google Dataset shape files (`.ttl`)
- `SPARQL/` — reusable SPARQL queries (`.rq`) and update scripts
- `skills/DOOS_bundle/` — AI skills (`doos-bco-dmo-index`, `doos-sparql`,
  `doos-fair-interview`, `doos-graph-inspect`, `doos-rocrate-from-url`)
- `skills/SHACL_bundle/` — six-stage decoder pipeline (`decoder-*`) + LangGraph
  `orchestration/`
- `src/mcp_server/` — DOOS Discovery MCP (SPARQL tools, graph resources, prompts)
- `prompts/` — FAIR/Blueprint conversation prompts (also served via MCP)
- `docs/` — notes (`sources.md` provider status; `bco-dmo-access-review.md`; `reports/`)

## Environment Setup

`pyproject.toml` requires Python `>=3.13`. Two dependency manifests coexist and
intentionally differ:

- `requirements.txt` — minimal RDF/validation core
  (`geopandas pandas rdflib pyshacl morph_kgc pyld pyarrow`); enough for the
  validators and most `projects/` transforms.
- `pyproject.toml` — fuller set: `dspy`, `langchain-openai`, `langchain-experimental`,
  `langgraph`, `playwright`, `pyrudof`, `pyshacl`, `rdflib`, `pyld`, `saxonche` (XSLT),
  `sparqlwrapper`, `tavily`, `netcdf4`, `ipykernel`, etc. Needed for `text2query/`,
  the pyrudof validator, AODN XSLT, CCHDO NetCDF, and `skills/SHACL_bundle/`
  orchestration.

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt   # core only
uv sync                              # full pyproject deps
```

Subprojects may carry their own `pyproject.toml` / `.venv` and extra deps not in the
root manifests:

- `projects/ARGO/` — `geopandas`, `morph-kgc`, `pyarrow`, `qlever` (local `uv sync`)
- `projects/OBIS/` — `duckdb`, `pyoxigraph`, `python-dwca-reader`, …
- `skills/DOOS_bundle/doos-bco-dmo-index/assets/requirements.txt` — `requests`,
  `tqdm`, `pyld`, `pyoxigraph`
- `scripts/text2query/` also needs `rich`, `diskcache`, `aiohttp`
- SSSOM transform needs `pyyaml`, `jsonpath-ng`, `ply`

Git repo: yes. NEVER commit unless user asks explicitly.

## Build, Lint, Test Commands

**Build:** `uv build` (wheel/sdist)

**Lint/format/typecheck:**
```bash
ruff check . && ruff check --fix .  # Lint
black .                             # Format
mypy .                              # Typecheck
```

**SHACL validation** (manual CLI; primary test path for graphs):
```bash
# Single-threaded (safe baseline)
python scripts/shapeValidator/validateToOxigraph.py <endpoint> <shapefile.ttl> --output results.nq

# Recommended for large runs (parallel, streams to Parquet)
python scripts/shapeValidator/validateToParquet.py <endpoint> <shapefile.ttl> --workers 8 --output-dir shacl_results
```

**Query / load helpers:**
```bash
python scripts/sparqlQueryl.py
python scripts/sparqlQueryl.py <endpoint> --query SPARQL/depthAssay.rq

docker build -t doos-oxigraph build/
docker run --rm --network host doos-oxigraph
python scripts/loadToOxigraph/loadToOxigraph.py --wait
python scripts/loadToOxigraph/loadToOxigraph.py --wait --export output/doos.nq
```

**Pytest** (dev dep; only a real suite under the SHACL decoder bundle today):
```bash
uv run pytest -c skills/SHACL_bundle/pytest.ini skills/SHACL_bundle/tests
pytest tests/ -v                    # if a root suite is added later
pytest tests/test_foo.py::test_bar  # single test
```

**Verify any CLI change:** `python path/to/script.py --help`

**Discovery MCP** (default **HTTP** at `http://127.0.0.1:8765/mcp`; SPARQL
`http://localhost:7878/query`):
```bash
# Docker stack (Oxigraph + load + MCP) — preferred for demos
docker compose -f deployment/docker-compose.yml up --build

# Local process
export PYTHONPATH=src
python -m mcp_server                          # streamable-http (default)
python -m mcp_server --transport stdio        # Claude Desktop-style hosts
# Tools: list_capabilities, sparql_list_templates, sparql_run_template,
#        sparql_query, graph_probe
# See src/mcp_server/README.md and deployment/README.md
```

## Architecture

### Data pipeline

1. **Ingest** — fetch metadata from HTTP APIs, sitemaps, files (NetCDF, GeoParquet,
   XML, JSON-LD, ERDDAP)
2. **Transform** — map to Schema.org + GeoSPARQL RDF (approach is per provider)
3. **Validate** — SHACL against `SHACL/` shapes (especially `depth_one.ttl`)
4. **Export** — N-Triples / N-Quads / Turtle for SPARQL endpoints
5. **Load / query** — Oxigraph or federated QLever; `SPARQL/`, `doos-sparql`, or
   `text2query/`

### Per-provider transform approaches

| Provider | Approach | Entry point |
|---|---|---|
| **ARGO** | GeoParquet rows filled into schema.org JSON-LD templates → N-Triples; optional morph-kgc RML | `projects/ARGO/geopan.py` (`tordf` / `rml`) |
| **OBIS** | DuckDB aggregate occurrence parquet → depth PropertyValue JSON-LD → named-graph N-Quads (auxiliary graph) | `projects/OBIS/build_depth_graph.py` |
| **BODC** | No field transform — Linked Systems UK publishes schema.org JSON-LD with `DepBelowSurf`; inventory, harvest, SHACL, export | `projects/BODC/scripts/Bodc*.py` |
| **AODN** | ISO 19115-3 → ISO 19139 (Saxon) → schema.org JSON-LD (lxml XSLT) → optional N-Triples; optional depth from tabular distributions | `projects/AODN/run_pipeline.py`, `depth_from_distribution.py` |
| **CCHDO** | NetCDF attrs → intermediate `cchdo:` RDF → `pyshacl.shacl_rules()` SHACL-AF SPARQL CONSTRUCT → schema.org or Croissant | `projects/CCHDO/nc_to_jsonld.py`, `nc_to_croissant.py` |
| **BCO-DMO** | ERDDAP catalog/search inventory + ISO 19115 depth/pressure scan → in-memory schema.org JSON-LD → merged N-Triples | `skills/DOOS_bundle/doos-bco-dmo-index/assets/run_pipeline.py` |
| **CIOOS** | CKAN `package_show` → schema.org Dataset (exploratory; depth incomplete) | `projects/CIOOS/convert.py` |
| **SSSOM (generic)** | `.sssom.tsv` with `source_jsonpath`/`target_jsonpath` drives flat-JSON → schema.org JSON-LD | `mapping/SSSOM/sssom_to_jsonld.py` |

Typical published outputs (see `projects/README.md`, `projects/dataLocations.md`):

| Provider | Output |
|---|---|
| ARGO | `projects/ARGO/data/output/*.nt` |
| OBIS | `projects/OBIS/output.nq` |
| BODC | `projects/BODC/output/bodc_harvest.nq`, `bodc_validated.nq` |
| AODN | `projects/AODN/output/`, `demo-output/` |
| BCO-DMO | `skills/DOOS_bundle/doos-bco-dmo-index/output/output.nt` (publish from `runs/<ts>/output.nt`) |
| CCHDO | per-file `*.schema.shacl.jsonld`, `*.croissant.jsonld` |

### Validation engines

- **`validateToOxigraph.py`** — single-threaded, pyshacl backend, safe baseline
- **`validateToParquet.py`** — `ProcessPoolExecutor` parallelism, streams results to
  Parquet (zstd), recommended for production
- **`validateToRudof.py`** — Rust-based pyrudof engine; faster but no regex
  backreferences → use `SHACL/ERDDAP_simple.ttl` not `ERDDAP.ttl`
- **`validateToParquetRudof.py`** — pyrudof engine with the parallel/Parquet harness
  (same `ERDDAP_simple.ttl` caveat)
- **`benchmark_shacl_engines.py`** — compares the three engines on the same input

All take `<endpoint> <shapefile.ttl>`; the endpoint is queried for named graphs which
are each validated against the shapes.

### SHACL shape files

Validation shapes (in `SHACL/`):

- `ERDDAP.ttl` — full OIH shapes (ID, core fields, spatial polygon); PySHACL only
- `ERDDAP_simple.ttl` — pyrudof-compatible drop-in; relaxes the polygon closed-ring
  regex backreference
- `ERDDAP_test.ttl` — minimal single-shape sanity check for `variableMeasured`/`latitude`
- `googleRequired.ttl` — checks the three fields required by Google Dataset Search
  (`url`, `description`, `name`)
- `depth_one.ttl` — OIH depth profile presence check: requires `DepBelowSurf` in
  `variableMeasured`

Transform shapes (per-provider, under `projects/`):

- `projects/CCHDO/SHACL_AF/nc_metadata_to_schema.ttl` — NetCDF metadata → schema.org
- `projects/CCHDO/SHACL_AF/nc_metadata_to_croissant.ttl` — NetCDF metadata → Croissant 1.1

Decoder shape:

- `skills/SHACL_bundle/decoder-validate-shacl/assets/googleRecommended.ttl` — Google
  required + recommended Dataset fields for the decoder pipeline

### Local Oxigraph load

`scripts/loadToOxigraph/oxigraph_load.yaml` maps provider outputs to named graphs
(e.g. `urn:doos:argo`, `urn:doos:obis`, `urn:doos:aodn`, `urn:doos:bodc`,
`urn:doos:bcodmo`). Triple formats require a `graph:`; quad formats may keep embedded
graph names or collapse into one provider graph. Prefer `--network host` when Docker
port mapping stalls HTTP responses.

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
# pyld URDNA2015 normalize (common before N-Triples dump via pyoxigraph)
jsonld.normalize(doc, {'algorithm': 'URDNA2015', 'format': 'application/n-quads'})
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

Skills under `skills/DOOS_bundle/` — use when relevant:

- `doos-bco-dmo-index` — BCO-DMO ERDDAP search + ISO depth scan → merged `output.nt`
  (prefer `assets/run_pipeline.py`)
- `doos-sparql` — curated schema.org SPARQL templates or ad-hoc SPARQL against an
  endpoint
- `doos-fair-interview` — guided FAIR practices interview (person/repository), not
  automated scoring
- `doos-graph-inspect` — experimental MCP/graph inspection (prefer `doos-sparql` for
  SPARQL)
- `doos-rocrate-from-url` — download a file URL into an Attached RO-Crate 1.2

Also: `skills/SHACL_bundle/` — decoder pipeline (URL → extract → lift RDF → SHACL
validate → report → repair loop → RAiD provenance). Stages: `decoder-extract-metadata`,
`decoder-lift-rdf`, `decoder-validate-shacl`, `decoder-report-findings`,
`decoder-repair-graph`, `decoder-emit-provenance`. Orchestrator:
`uv run python -m orchestration.run "<dataset-url>"` from `skills/SHACL_bundle/`.
LLM optional via `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` (OpenAI-compatible;
defaults degrade to deterministic).

## Verification After Changes

1. Lint/format/typecheck (`ruff`, `black`, `mypy`) where applicable
2. Run affected scripts: `python path/to/script.py --help`
3. Manual test RDF/SHACL output (or SHACL_bundle pytest for decoder changes)
4. `git diff` + `git status` before any commit (only commit when the user asks)
