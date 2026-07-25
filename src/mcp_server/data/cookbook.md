# DOOS schema.org SPARQL cookbook

Use this with triple patterns (`doos://graph/patterns`) to write **portable SPARQL 1.1**
against DOOS graphs (Oxigraph, QLever). Prefer curated templates when they fit
(`sparql_list_templates` / `sparql_run_template`).

## Prefixes

```sparql
PREFIX schema: <https://schema.org/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
PREFIX geo:    <http://www.opengis.net/ont/geosparql#>
```

Prefer `https://schema.org/`. Some older loads use `http://schema.org/` — if counts
look low, UNION both or probe with template `list_types`.

## Named graphs

Most loads put triples in **named graphs**. Prefer:

```sparql
SELECT ... WHERE {
  GRAPH ?g {
    ?dataset a schema:Dataset ;
             schema:name ?name .
  }
}
```

Local Oxigraph may be started with `--union-default-graph` (see `build/Dockerfile`),
so bare `{ ?s ?p ?o }` can also see named-graph data. If empty, try both styles and
run template `list_graphs`.

## Core patterns

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

## Examples

**DepBelowSurf ranges:**

```sparql
PREFIX schema: <https://schema.org/>
SELECT ?dataset ?dsName ?minValue ?maxValue ?g
WHERE {
  GRAPH ?g {
    ?dataset a schema:Dataset ;
             schema:name ?dsName ;
             schema:variableMeasured ?vm .
    ?vm a schema:PropertyValue ;
        schema:name "DepBelowSurf" .
    OPTIONAL { ?vm schema:minValue ?minValue . }
    OPTIONAL { ?vm schema:maxValue ?maxValue . }
  }
}
LIMIT 50
```

**Variable name fragment:**

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
    FILTER(CONTAINS(LCASE(STR(?varName)), "depth"))
  }
}
LIMIT 50
```

## Rules for agents

1. Always include a `LIMIT` (default ≤ 100 unless the user asks for more).
2. Prefer template ids from `sparql_list_templates` when they match the intent.
3. Call `sparql_query` or `sparql_run_template` to execute — **never invent result rows**.
4. On empty results: `graph_probe`, then `list_graphs` / `list_types`; check https vs http schema.org.
5. Portable SPARQL only — no Blazegraph `bds:` or QLever-only spatial extensions in generated queries.
