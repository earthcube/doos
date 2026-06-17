# Scripts

Command-line utilities for querying, loading, validating, and exploring DOOS RDF
graphs. Query templates live in [`../SPARQL/`](../SPARQL/).

**Default federated endpoint:**  
https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans

**Search UI:**  
https://qlever-test.geocodes-aws-dev.earthcube.org/

---

## Quickstart

```bash
cd scripts
source ../.venv/bin/activate

# Run a SPARQL query file against the deepoceans endpoint
python3 sparqlQueryl.py

# SHACL-validate named graphs from an endpoint (single-threaded baseline)
python3 shapeValidator/validateToOxigraph.py \
  https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans \
  ../SHACL/depth_one.ttl \
  --output results.nq
```

---

## `sparqlQueryl.py`

Run a `.rq` query file against any SPARQL endpoint and print results as a
pandas DataFrame.

### Usage

```bash
python3 sparqlQueryl.py
python3 sparqlQueryl.py <endpoint>
python3 sparqlQueryl.py <endpoint> --query ../SPARQL/depthAssay.rq
python3 sparqlQueryl.py --help
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `endpoint` | deepoceans QLever URL | SPARQL endpoint (positional, optional) |
| `--query` | `../SPARQL/varMes_bodc.rq` | Path to a SPARQL query file |

### Examples

```bash
# BODC DepBelowSurf min/max on the federated graph
python3 sparqlQueryl.py

# Cross-provider depth variable inventory
python3 sparqlQueryl.py \
  https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans \
  --query ../SPARQL/depthAssay.rq

# Count datasets with spatial coverage
python3 sparqlQueryl.py <endpoint> --query ../SPARQL/countBySpatial.rq
```

Query files are in [`../SPARQL/`](../SPARQL/). See that directory for available
templates (`varMes_bodc.rq`, `valuesList.rq`, `depthAssay.rq`, spatial search
templates, etc.).

---

## `shapeValidator/`

SHACL validation suite — batch-validates named graphs from a SPARQL endpoint
against OIH shape files in [`../SHACL/`](../SHACL/).

| Script | When to use |
|--------|-------------|
| `validateToOxigraph.py` | Single-threaded baseline; safe default |
| `validateToParquet.py` | Large runs — parallel workers, streams to Parquet |
| `validateToRudof.py` | Rust/pyrudof engine; use `ERDDAP_simple.ttl` not `ERDDAP.ttl` |
| `validateToParquetRudof.py` | pyrudof + parallel Parquet harness |
| `benchmark_shacl_engines.py` | Compare pyshacl vs pyrudof vs pyoxigraph on the same input |

```bash
# Baseline (single-threaded)
python3 shapeValidator/validateToOxigraph.py <endpoint> <shapefile.ttl> \
  --output results.nq

# Production (parallel, recommended for large endpoints)
python3 shapeValidator/validateToParquet.py <endpoint> <shapefile.ttl> \
  --workers 8 --output-dir shacl_results

# Test on first N graphs only
python3 shapeValidator/validateToOxigraph.py <endpoint> <shapefile.ttl> --limit 50
```

Shared utilities are in `shapeValidator/defs/` (`getGraphs.py`, `getConstruct.py`,
`shaclValidator.py`, `parquet_streaming.py`).

See [shapeValidator/README.md](shapeValidator/README.md) for engine notes and
recent changes.

---

## `SPARQLupdate/`

Load N-Quads or N-Triples into a SPARQL update endpoint (e.g. after exporting
validated graphs from a provider subproject).

```bash
python3 SPARQLupdate/insertUpdates.py \
  --token <TOKEN> \
  --endpoint <UPDATE_ENDPOINT> \
  --file ../projects/BODC/output/bodc_validated.nq \
  --format nquads
```

See [SPARQLupdate/README.md](SPARQLupdate/README.md) for curl examples and
QLever index rebuild references.

---

## `text2query/`

Natural language → SPARQL using DSPy. Requires full `pyproject.toml` deps
(`dspy`, `langchain-openai`, etc.) — not in minimal `requirements.txt`.

```bash
python3 text2query/text2SPARQL.py \
  -q "datasets with depth below 1000m" \
  --sparql-url https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans
```

Other files in this directory extract triple patterns from query results
(`triplePatternsJSON.py`, `triplePatternsCSV.py`).

---

## Directory layout

```
scripts/
├── sparqlQueryl.py          # Run .rq files → pandas DataFrame
├── shapeValidator/          # SHACL batch validation
├── SPARQLupdate/            # Load RDF into SPARQL endpoints
└── text2query/              # DSPy natural language → SPARQL
```

Provider-specific pipelines (harvest, inventory, export) live under
[`../projects/`](../projects/) — e.g. `projects/BODC/scripts/`.