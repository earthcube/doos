# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Kept in sync with `AGENTS.md`. Update both together if either changes. This file is the canonical source of project guidance.

## Project

DOOS (Deep Ocean Observation System) is an EarthCube monorepo for harvesting, converting, validating, and federating ocean observation metadata. Data is transformed to RDF/JSON-LD conforming to Schema.org + GeoSPARQL, validated against OIH depth profile SHACL shapes.

The end goal is a federated SPARQL graph that exposes a consistent **depth profile** (`DepBelowSurf` / related depth variables) across providers.

**Never commit unless the user explicitly asks.**

### Live endpoints

- Search UI: https://deepoceans.geocodes-aws.earthcube.org/#/landing
- SPARQL (QLever): https://qlever-ui.geocodes-aws-dev.earthcube.org/deepoceans/GxLMVz
- Dev graph endpoint (scripts default): https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans

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

Candidate sources not yet subprojects (see `docs/sources.md`): EMODNET, OceanSITES, marine-regions, Australian Antarctic Data Group.

When working inside a subproject, prefer that directory's own `README.md` (and `CLAUDE.md` where present, e.g. `projects/OBIS/CLAUDE.md`).

## Environment

`pyproject.toml` requires Python `>=3.13`. Two dependency manifests coexist and intentionally differ:

- `requirements.txt` — minimal RDF/validation core (`geopandas pandas rdflib pyshacl morph_kgc pyld pyarrow`). Enough for the validators and most `projects/` transforms.
- `pyproject.toml` — fuller set: `dspy`, `langchain-openai`, `langchain-experimental`, `langgraph`, `playwright`, `pyrudof`, `pyshacl`, `rdflib`, `pyld`, `saxonche` (XSLT), `sparqlwrapper`, `tavily`, `netcdf4`, `ipykernel`, etc. Needed for `text2query/`, the pyrudof validator, AODN XSLT, CCHDO NetCDF, and `skills/SHACL_bundle/` orchestration.

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt   # core only
uv sync                              # full pyproject deps
```

Subprojects may carry their own `pyproject.toml` / `.venv` and extra deps not in the root manifests:

- `projects/ARGO/` — `geopandas`, `morph-kgc`, `pyarrow`, `qlever` (local `uv sync`)
- `projects/OBIS/` — `duckdb`, `pyoxigraph`, `python-dwca-reader`, …
- `skills/DOOS_bundle/doos-bco-dmo-index/assets/requirements.txt` — `requests`, `tqdm`, `pyld`, `pyoxigraph`
- `scripts/text2query/` also needs `rich`, `diskcache`, `aiohttp` (not always declared in root manifests)
- SSSOM transform needs `pyyaml`, `jsonpath-ng`, `ply`

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

**SHACL validation (manual CLI; primary test path for graphs):**
```bash
# Single-threaded baseline
python scripts/shapeValidator/validateToOxigraph.py <endpoint> <shapefile.ttl> --output results.nq

# Parallel, high-throughput (recommended for large runs)
python scripts/shapeValidator/validateToParquet.py <endpoint> <shapefile.ttl> --workers 8 --output-dir shacl_results
```

**Query / load helpers:**
```bash
# Run a .rq file against a SPARQL endpoint (default: deepoceans QLever)
python scripts/sparqlQueryl.py
python scripts/sparqlQueryl.py <endpoint> --query SPARQL/depthAssay.rq

# Local in-memory Oxigraph: build image, start server, load configured provider outputs
docker build -t doos-oxigraph build/
docker run --rm --network host doos-oxigraph   # or -p 7878:7878
python scripts/loadToOxigraph/loadToOxigraph.py --wait
python scripts/loadToOxigraph/loadToOxigraph.py --wait --export output/doos.nq
```

**Pytest** (dev dep; only a real suite under the SHACL decoder bundle today):
```bash
uv run pytest -c skills/SHACL_bundle/pytest.ini skills/SHACL_bundle/tests
# Generic form if more suites appear:
pytest tests/ -v
pytest tests/test_foo.py::test_bar
```

**Verify any CLI change:**
```bash
python path/to/script.py --help
```

**Discovery MCP** (default **HTTP** streamable-http at `http://127.0.0.1:8765/mcp`; SPARQL backend `http://localhost:7878/query`):
```bash
docker compose -f deployment/docker-compose.yml up --build   # Oxigraph + load + MCP
export PYTHONPATH=src && python -m mcp_server                # local HTTP
python -m mcp_server --transport stdio                       # desktop process hosts
```
See `src/mcp_server/README.md` and `deployment/README.md`.

## Architecture

### Data pipeline

1. **Ingest** — fetch metadata from HTTP APIs, sitemaps, files (NetCDF, GeoParquet, XML, JSON-LD, ERDDAP)
2. **Transform** — map to Schema.org + GeoSPARQL RDF (approach is per provider; see table below)
3. **Validate** — SHACL against `SHACL/` shapes (especially `depth_one.ttl` for the depth profile)
4. **Export** — N-Triples / N-Quads / Turtle for SPARQL endpoints
5. **Load / query** — load into Oxigraph or federated QLever; query via `SPARQL/`, `doos-sparql`, or `text2query/`

### Per-provider transform approaches

| Provider | Approach | Entry point |
|---|---|---|
| **ARGO** | GeoParquet rows filled into schema.org JSON-LD templates → N-Triples; optional morph-kgc RML | `projects/ARGO/geopan.py` (`tordf` / `rml`) |
| **OBIS** | DuckDB aggregate occurrence parquet → depth PropertyValue JSON-LD → named-graph N-Quads (auxiliary graph; not a full re-description) | `projects/OBIS/build_depth_graph.py` |
| **BODC** | No field transform — Linked Systems UK already publishes schema.org JSON-LD with `DepBelowSurf`; inventory, harvest, SHACL, export | `projects/BODC/scripts/Bodc*.py` |
| **AODN** | ISO 19115-3 → ISO 19139 (Saxon) → schema.org JSON-LD (lxml XSLT) → optional N-Triples; optional depth min/max from tabular distributions | `projects/AODN/run_pipeline.py`, `depth_from_distribution.py` |
| **CCHDO** | NetCDF attrs → intermediate `cchdo:` RDF → `pyshacl.shacl_rules()` SHACL-AF SPARQL CONSTRUCT → schema.org or MLCommons Croissant | `projects/CCHDO/nc_to_jsonld.py`, `nc_to_croissant.py` |
| **BCO-DMO** | ERDDAP catalog/search inventory + ISO 19115 depth/pressure scan → in-memory schema.org JSON-LD → merged N-Triples | `skills/DOOS_bundle/doos-bco-dmo-index/assets/run_pipeline.py` |
| **CIOOS** | CKAN `package_show` → schema.org Dataset (exploratory; depth incomplete) | `projects/CIOOS/convert.py` |
| **SSSOM (generic)** | `.sssom.tsv` with `source_jsonpath`/`target_jsonpath` drives flat-JSON → schema.org JSON-LD (no field names hard-coded) | `mapping/SSSOM/sssom_to_jsonld.py` |

Typical published outputs (see `projects/README.md`, `projects/dataLocations.md`):

| Provider | Output |
|---|---|
| ARGO | `projects/ARGO/data/output/*.nt` |
| OBIS | `projects/OBIS/output.nq` |
| BODC | `projects/BODC/output/bodc_harvest.nq`, `bodc_validated.nq` |
| AODN | `projects/AODN/output/`, `demo-output/` |
| BCO-DMO | `skills/DOOS_bundle/doos-bco-dmo-index/output/output.nt` (publish from `runs/<ts>/output.nt`) |
| CCHDO | per-file `*.schema.shacl.jsonld`, `*.croissant.jsonld` |

### Key directories

| Path | Purpose |
|---|---|
| `projects/` | Per-provider subprojects (ARGO, OBIS, CCHDO, ERDDAP, AODN, BODC, CIOOS); see `projects/README.md` |
| `projects/dataLocations.md` | Canonical provider output paths for loaders |
| `skills/DOOS_bundle/doos-bco-dmo-index/` | BCO-DMO ERDDAP + ISO depth → N-Triples (`assets/run_pipeline.py`) |
| `mapping/SSSOM/` | SSSOM-driven flat-JSON → schema.org JSON-LD (`kobo/` = GAIA Kobo form mapping) |
| `mapping/Croissant/` | MLCommons Croissant / GeoCroissant JSON-LD samples and notes |
| `scripts/shapeValidator/` | SHACL validation suite (pyshacl, pyrudof, parallel Parquet) |
| `scripts/shapeValidator/defs/` | Shared utilities: `getGraphs.py`, `getConstruct.py`, `getShape.py`, `shaclValidator.py`, `parquet_streaming.py` |
| `scripts/loadToOxigraph/` | YAML-driven load of provider outputs into Oxigraph (`oxigraph_load.yaml`) |
| `scripts/SPARQLupdate/` | `insertUpdates.py` — SPARQL UPDATE inserts into a graph endpoint |
| `scripts/text2query/` | DSPy natural language → SPARQL (`text2SPARQL.py`) |
| `scripts/sparqlQueryl.py` | Run a `.rq` file against an endpoint → pandas DataFrame |
| `build/Dockerfile` | In-memory Oxigraph 0.5.x image (`doos-oxigraph`, port 7878, union default graph) |
| `SHACL/` | OIH depth / Google Dataset shape files (`.ttl`) |
| `SPARQL/` | Reusable SPARQL queries (`.rq`) and update scripts |
| `skills/DOOS_bundle/` | AI skills: `doos-bco-dmo-index`, `doos-sparql`, `doos-fair-interview`, `doos-graph-inspect`, `doos-rocrate-from-url` |
| `skills/SHACL_bundle/` | Six-stage decoder pipeline (`decoder-*`) + LangGraph `orchestration/` |
| `src/mcp_server/` | DOOS Discovery MCP — SPARQL tools, graph context resources, prompts (see README there) |
| `build/Dockerfile.mcp` | Slim MCP image |
| `build/Dockerfile.load` | One-shot Oxigraph loader image |
| `deployment/docker-compose.yml` | Oxigraph + load + MCP stack |
| `prompts/` | Host-facing conversation prompts (FAIR/Blueprint); also served via MCP |
| `docs/` | Notes — `sources.md` provider status; `bco-dmo-access-review.md`; `reports/` |

### Discovery MCP (`src/mcp_server/`)

MCP server for graph discovery against local Oxigraph. **Default transport is HTTP** (`streamable-http` on `http://127.0.0.1:8765/mcp`). SPARQL backend default: `http://localhost:7878/query`. **Host-side** text→SPARQL: resources `doos://graph/cookbook` + `doos://graph/patterns` and the `ask_graph` prompt; the host LLM writes SPARQL; tools only execute.

```bash
export PYTHONPATH=src
python -m mcp_server                              # HTTP
python -m mcp_server --transport stdio            # stdio
python -m mcp_server --transport sse --port 8765  # SSE
```

Tools: `list_capabilities`, `sparql_list_templates`, `sparql_run_template`, `sparql_query`, `graph_probe`.  
Prompts: `ask_graph`, `fair_blueprint_interview`, `blueprint_context`.  
Deps: `mcp[cli]`, `SPARQLWrapper` (in `pyproject.toml`). See `src/mcp_server/README.md`.

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

Decoder shape (under skills):

- `skills/SHACL_bundle/decoder-validate-shacl/assets/googleRecommended.ttl` — Google required + recommended Dataset fields for the decoder pipeline

### Local Oxigraph load

`scripts/loadToOxigraph/oxigraph_load.yaml` maps provider outputs to named graphs (e.g. `urn:doos:argo`, `urn:doos:obis`, `urn:doos:aodn`, `urn:doos:bodc`, `urn:doos:bcodmo`). Triple formats require a `graph:`; quad formats may keep embedded graph names or collapse into one provider graph. Prefer `--network host` when Docker port mapping stalls HTTP responses.

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
# pyld URDNA2015 normalize (common before N-Triples dump via pyoxigraph)
jsonld.normalize(doc, {'algorithm': 'URDNA2015', 'format': 'application/n-quads'})
```

**SHACL-AF PREFIX gotcha:** pyshacl does not auto-propagate Turtle `@prefix` declarations into the SPARQL strings inside `sh:construct`. Standard prefixes (like `schema:`) may work incidentally, but any non-standard prefix (`cr:`, `dct:`, custom vocabs) will raise `Unknown namespace prefix`. Fix: embed explicit `PREFIX` declarations at the top of every `sh:construct` SPARQL string, even when they are already declared as Turtle prefixes in the same file.

**JSON-LD `@language` gotcha:** setting `"@language": "en"` in a framing context causes all plain string literals to serialize as `{"@value": "...", "@language": "en"}` objects instead of bare strings. Omit `@language` from the context unless the spec requires it.

Output formats: N-Triples (`.nt`), N-Quads (`.nq`), Turtle (`.ttl`).

**User-Agent and timeouts:** always set `User-Agent` and `timeout=30` on HTTP calls. No secrets in code. Use `tempfile.mkdtemp(prefix='...')` for temp dirs.

## Skills

Skills under `skills/DOOS_bundle/` — use when relevant:

- `doos-bco-dmo-index` — BCO-DMO ERDDAP search + ISO depth scan → merged `output.nt` (prefer `assets/run_pipeline.py`)
- `doos-sparql` — curated schema.org SPARQL templates or ad-hoc SPARQL against an endpoint
- `doos-fair-interview` — guided FAIR practices interview (person/repository), not automated scoring
- `doos-graph-inspect` — experimental MCP/graph inspection (prefer `doos-sparql` for SPARQL)
- `doos-rocrate-from-url` — download a file URL into an Attached RO-Crate 1.2

Also: `skills/SHACL_bundle/` — decoder pipeline (URL → extract → lift RDF → SHACL validate → report → repair loop → RAiD provenance). Stages: `decoder-extract-metadata`, `decoder-lift-rdf`, `decoder-validate-shacl`, `decoder-report-findings`, `decoder-repair-graph`, `decoder-emit-provenance`. Orchestrator: `uv run python -m orchestration.run "<dataset-url>"` from `skills/SHACL_bundle/`. LLM optional via `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` (OpenAI-compatible; defaults degrade to deterministic).

## Verification after changes

1. Lint/format/typecheck (`ruff`, `black`, `mypy`) where applicable
2. Run affected scripts: `python path/to/script.py --help`
3. Manual test RDF/SHACL output (or SHACL_bundle pytest for decoder changes)
4. `git diff` + `git status` before any commit (only commit when the user asks)
