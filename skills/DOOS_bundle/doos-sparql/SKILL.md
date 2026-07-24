---
name: doos-sparql
description: >
  Query DOOS schema.org RDF graphs via SPARQL. Use when the user wants to run
  SPARQL, inspect a triplestore, list datasets, inventory variableMeasured or
  depth (DepBelowSurf), explore named graphs, or build schema.org SPARQL against
  an endpoint URL. Triggers: SPARQL, Oxigraph, QLever, /query, /doos-sparql,
  triplestore, schema.org graph, depth assay, variableMeasured, list graphs/types.
  Not for: SHACL validation, loading RDF, FAIR interviews, free-text Blazegraph search.
license: Apache-2.0
metadata:
  project: DOOS
  version: "1.0"
  author: DOOS / GoFAIR US
---

# SPARQL Query

Run **portable SPARQL 1.1** against a user-supplied endpoint. Prefer curated
templates in `queries/`; when none fit, author new SPARQL from the **schema.org
cookbook** below and execute with `query` or `file`.

## Required: endpoint URL

Every network command needs:

```text
--endpoint <SPARQL_URL>
```

**Local test (Oxigraph):** `http://localhost:7878/query`

Other examples:

- Federated QLever (if available): see monorepo `README.md` / `scripts/README.md`
- Always use the full **query** path (`/query`), not the store base URL alone

If the user does not give an endpoint, ask once, then default the suggestion to
`http://localhost:7878/query` for local work.

## Agent workflow

1. **Confirm endpoint** — required; do not invent live URLs.
2. **Match a template** — run `list`, pick the best `id`, then `run`.
3. **If no template fits** — write SPARQL from the cookbook → `query` or `file`.
4. **Show the SPARQL** — use `--show-query` (or paste the query in the reply).
5. **Report results honestly** — row counts and sample rows only; never invent bindings.
6. **Empty results** — try `probe_triples` / `list_graphs`; check http vs https schema.org; check named graphs vs default graph.

### Prefer templates over inventing SPARQL

| User intent | Template id |
|---|---|
| Is the store alive / has data? | `probe_triples` |
| What types exist? | `list_types` |
| What named graphs? | `list_graphs` |
| Sample datasets | `datasets_sample` |
| Find datasets by name | `dataset_by_name` (`--name`) |
| List measured variables | `variable_measured` |
| Depth variables inventory | `depth_assay` |
| DepBelowSurf ranges | `depth_minmax` |
| Spatial coverage count | `count_spatial` |
| Provider slugs from graph IRIs | `providers_from_graphs` |

## CLI

From the **DOOS repo root** (or any cwd; paths below are relative to this skill):

```bash
# List templates (no network)
python skills/DOOS_bundle/doos-sparql/scripts/sparql_query.py list

# Run a named template
python skills/DOOS_bundle/doos-sparql/scripts/sparql_query.py run \
  --endpoint http://localhost:7878/query \
  --query depth_assay \
  --limit 50 \
  --format table \
  --show-query

# Optional filters
#   --name <fragment>           # required for dataset_by_name
#   --graph-contains <substr>   # FILTER on named graph IRI (variable_measured, depth_minmax)

# Ad-hoc SPARQL string
python skills/DOOS_bundle/doos-sparql/scripts/sparql_query.py query \
  --endpoint http://localhost:7878/query \
  --sparql 'PREFIX schema: <https://schema.org/>
SELECT ?s ?name WHERE {
  GRAPH ?g { ?s a schema:Dataset ; schema:name ?name . }
} LIMIT 10' \
  --format json

# Any .rq file (including monorepo SPARQL/)
python skills/DOOS_bundle/doos-sparql/scripts/sparql_query.py file \
  --endpoint http://localhost:7878/query \
  --query-file SPARQL/get100.rq
```

| Subcommand | Network? | Purpose |
|---|---|---|
| `list` | no | Catalog of template ids |
| `run` | yes | Curated `queries/<id>.rq` |
| `query` | yes | Inline SPARQL string |
| `file` | yes | Path to `.rq` file |

**Output:** `--format table|json|csv` (default `table`).

**Deps:** `SPARQLWrapper` (monorepo `.venv` / `pyproject.toml`). Optional pandas is **not** required.

```bash
source .venv/bin/activate   # from repo root
python skills/DOOS_bundle/doos-sparql/scripts/sparql_query.py --help
```

## Schema.org cookbook (DOOS graph)

DOOS metadata is primarily **schema.org** + **GeoSPARQL**, often in **named graphs**.

### Prefixes (portable)

```sparql
PREFIX schema: <https://schema.org/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
PREFIX geo:    <http://www.opengis.net/ont/geosparql#>
```

Prefer `https://schema.org/`. Some older loads use `http://schema.org/` — if counts look low, UNION both or probe with `list_types`.

### Named graphs

Most Oxigraph loads in this project put triples in **named graphs**. Prefer:

```sparql
SELECT ... WHERE {
  GRAPH ?g {
    ?dataset a schema:Dataset ;
             schema:name ?name .
  }
}
```

If empty, also try the default graph (no `GRAPH` clause) or run `list_graphs`.

### Core types and properties

| Concept | Pattern |
|---|---|
| Dataset | `?d a schema:Dataset` |
| Name / description / URL | `schema:name`, `schema:description`, `schema:url` |
| License / keywords | `schema:license`, `schema:keywords` |
| Temporal | `schema:temporalCoverage` |
| Variables | `?d schema:variableMeasured ?vm . ?vm a schema:PropertyValue` |
| Variable fields | `schema:name`, `schema:minValue`, `schema:maxValue`, `schema:propertyID`, `schema:unitCode`, `schema:unitText` |
| Depth profile (OIH) | `?vm schema:name "DepBelowSurf"` |
| Spatial | `schema:spatialCoverage` and/or `geo:hasGeometry` / `geo:asWKT` |

### Copy-paste patterns

**Datasets with a variable name fragment:**

```sparql
PREFIX schema: <https://schema.org/>
SELECT DISTINCT ?dataset ?dsName ?varName ?minValue ?maxValue ?g
WHERE {
  GRAPH ?g {
    ?dataset a schema:Dataset ;
             schema:name ?dsName ;
             schema:variableMeasured ?vm .
    ?vm a schema:PropertyValue ;
        schema:name ?varName .
    OPTIONAL { ?vm schema:minValue ?minValue . }
    OPTIONAL { ?vm schema:maxValue ?maxValue . }
    FILTER(CONTAINS(LCASE(STR(?varName)), "temp"))
  }
}
LIMIT 50
```

**Count datasets per named graph:**

```sparql
PREFIX schema: <https://schema.org/>
SELECT ?g (COUNT(DISTINCT ?d) AS ?n)
WHERE {
  GRAPH ?g {
    ?d a schema:Dataset .
  }
}
GROUP BY ?g
ORDER BY DESC(?n)
LIMIT 50
```

### Parameter placeholders in templates

| Placeholder | CLI flag | Notes |
|---|---|---|
| `{{LIMIT}}` | `--limit` | Default 100 if omitted |
| `{{NAME_FRAGMENT}}` | `--name` | Required for `dataset_by_name` |
| `{{GRAPH_FILTER}}` | `--graph-contains` | Injects `FILTER(CONTAINS(STR(?g), "..."))` or empty |

## Failure handling

| Situation | Action |
|---|---|
| Connection refused | Endpoint down; confirm Oxigraph/`--endpoint` URL and `/query` path |
| HTTP 404 | Wrong path (base URL without `/query`) |
| Empty results | `probe_triples`, `list_graphs`; check schema http/https; named vs default graph |
| Syntax error | Show SPARQL; fix PREFIX/braces; re-run with `--show-query` |
| Vendor query fails | Blazegraph `bds:` / QLever spatial not in this skill; rewrite portable SPARQL |
| Missing SPARQLWrapper | `source .venv/bin/activate` or `uv pip install SPARQLWrapper` |

## Do not

- Invent result rows or graph statistics
- Use Blazegraph free-text (`bds:`) or QLever `spatialSearch:` in skill templates
- Call production endpoints without the user providing/confirming the URL
- Commit query dumps or large result files unless the user asks
- Confuse this skill with SHACL validation (`scripts/shapeValidator/`)

## Layout

```text
doos-sparql/
├── SKILL.md
├── queries/
│   ├── catalog.json
│   └── *.rq
└── scripts/
    └── sparql_query.py
```

Source inspiration for templates: monorepo `SPARQL/` (adapted for portable SPARQL 1.1).
For one-off monorepo scripting without the skill, `scripts/sparqlQueryl.py` remains available.
