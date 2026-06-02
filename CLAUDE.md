# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

DOOS (Deep Ocean Observation System) is an EarthCube monorepo for harvesting, converting, validating, and federating ocean observation metadata. It ingests from providers (ARGO, OBIS, ERDDAP, BCO-DMO, CCHDO, AODN, BODC, CIOOS, EMODNET) and transforms data to RDF/JSON-LD conforming to Schema.org + GeoSPARQL, validated against OIH depth profile SHACL shapes.

**Never commit unless the user explicitly asks.**

## Environment

```bash
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
```

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
2. **Transform** — map to Schema.org + GeoSPARQL RDF using JSON-LD templates, RML rules (morph-kgc), or XSLT
3. **Validate** — run SHACL validation against `SHACL/` shapes
4. **Export** — serialize to N-Triples/N-Quads/Turtle for SPARQL endpoints
5. **Query** — federated SPARQL across providers; `text2query/` adds LLM-to-SPARQL conversion

### Key directories

| Path | Purpose |
|---|---|
| `projects/` | Per-provider subprojects (ARGO, OBIS, BCO-DMO, CCHDO, ERDDAP, AODN, BODC, CIOOS, geoparquet2RDF) |
| `scripts/shapeValidator/` | SHACL validation suite — three engines (pyshacl, pyrudof, pyoxigraph) |
| `scripts/shapeValidator/defs/` | Shared utilities: `getGraphs.py`, `shaclValidator.py`, `getConstruct.py`, `parquet_streaming.py` |
| `SHACL/` | OIH depth profile shape files (`.ttl`) |
| `SPARQL/` | Reusable SPARQL queries (`.rq`) and update scripts |
| `text2query/` | LLM-based natural language → SPARQL |
| `.opencode/skills/` | AI skills: `fair-assessment`, `oih-graph` |
| `docs/` | Project notes — `sources.md` tracks provider status |

### Validation engines

- **`validateToOxigraph.py`** — single-threaded, pyshacl backend, safe baseline
- **`validateToParquet.py`** — `ProcessPoolExecutor` parallelism, streams results to Parquet (zstd), recommended for production
- **`validateToRudof.py`** — Rust-based pyrudof engine; faster but no regex backreferences → use `SHACL/ERDDAP_simple.ttl` not `ERDDAP.ttl`

### SHACL shape files

- `SHACL/ERDDAP.ttl` — full shapes, PySHACL-compatible
- `SHACL/ERDDAP_simple.ttl` — pyrudof-compatible subset (no regex backreferences)

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
# pyshacl (via wrapper)
validate_with_shacl(report_graph, shapes_file)
# morph-kgc
morph_kgc.materialize(config, data_dict)
# pyld JSON-LD → RDF
jsonld.to_rdf(doc, {'format': 'application/n-quads'})
```

Output formats: N-Triples (`.nt`), N-Quads (`.nq`), Turtle (`.ttl`).

**User-Agent and timeouts:** always set `User-Agent` and `timeout=30` on HTTP calls.

## OpenCode skills

Use the `skill` tool when relevant:
- `fair-assessment` — evaluate FAIR compliance of a dataset/metadata record
- `oih-graph` — execute SPARQL queries against OIH metadata graphs
