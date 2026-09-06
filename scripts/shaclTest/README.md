# shaclTest

Fetch `schema:Dataset` records from a SPARQL endpoint and validate them with
[pwin/SHACL_Engine](https://github.com/pwin/SHACL_Engine) (Python package `shacl`).

This directory is a small engine test. It is not the production validator.
For batch named-graph validation use [`../shapeValidator/`](../shapeValidator/).

## What it does

`validate_datasets.py` runs four steps:

1. Load a SHACL shapes graph from an HTTP(S) URL or a local Turtle file (default: Google Dataset recommended fields).
2. `CONSTRUCT` the 1-hop neighborhood of N `schema:Dataset` resources from the SPARQL endpoint.
3. Compile the shapes with `shacl.Shapes.from_turtle(...)` and validate the N-Triples graph.
4. Write the data graph, shapes, SPARQL query, and reports under `shacl_results/`.

The default endpoint is the DOOS QLever graph:
https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans

The default shapes file is:
https://raw.githubusercontent.com/OHDSI/gaiaCatalog/refs/heads/main/shapeGraphs/googleRecommended.ttl

The remote default is a copy of the gaiaCatalog shapes. Use the corrected local
file with `--shapes scripts/shaclTest/shapes/googleRecommended.ttl`.

## Contents

| File | Purpose |
|------|---------|
| `validate_datasets.py` | CLI: fetch Datasets, validate, write reports |
| `shapes/googleRecommended.ttl` | Corrected local Google Dataset shapes |
| `notes.md` | Lab notes from the first run (100 Datasets) |
| `shacl_results/` | Default output directory (overwritten on each run) |

## Quickstart

Run these commands from the repository root.

1. Create the venv and install `pyproject.toml` deps (includes `shacl>=0.1.10`):

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv sync
```

2. Run the validator with defaults (100 Datasets against the QLever endpoint):

```bash
python scripts/shaclTest/validate_datasets.py
```

3. Inspect the reports in `scripts/shaclTest/shacl_results/`.

A smaller smoke test:

```bash
python scripts/shaclTest/validate_datasets.py --limit 10
```

Show CLI flags:

```bash
python scripts/shaclTest/validate_datasets.py --help
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--endpoint` | QLever deepoceans URL | SPARQL endpoint that accepts POST `application/sparql-query` |
| `--shapes` | gaiaCatalog `googleRecommended.ttl` | HTTP(S) URL or local path to a Turtle SHACL shapes graph |
| `--limit` | `100` | Number of distinct `schema:Dataset` IRIs to `CONSTRUCT`. `0` or `ALL` omits `LIMIT` |
| `--out` | `shacl_results/` next to the script | Output directory |

Examples:

```bash
# Fewer Datasets
python scripts/shaclTest/validate_datasets.py --limit 50

# Every Dataset (no SPARQL LIMIT)
python scripts/shaclTest/validate_datasets.py --limit 0
python scripts/shaclTest/validate_datasets.py --limit ALL

# Local Oxigraph
python scripts/shaclTest/validate_datasets.py \
  --endpoint http://localhost:7878/query \
  --limit 20

# Local shapes file
python scripts/shaclTest/validate_datasets.py \
  --shapes SHACL/depth_one.ttl

# Remote shapes file
python scripts/shaclTest/validate_datasets.py \
  --shapes https://example.org/shapes.ttl
```

The SPARQL request uses `Accept: application/n-triples`. The endpoint must return N-Triples.

## How the SPARQL CONSTRUCT works

The query selects distinct `?s a schema:Dataset` up to `--limit`. With `--limit 0`
or `--limit ALL` the query has no `LIMIT` clause, so the endpoint returns every
matching Dataset. It then pulls every triple on `?s` and one hop of triples on
each object `?o`.

SPARQL `LIMIT 0` would return no rows, so the script omits the clause instead.
An unbounded pull can be large and may hit the 180 second SPARQL timeout.

The extra hop covers nested `schema:PropertyValue`, `schema:Place`, and similar objects
that the shapes inspect.

The script writes the query as `shacl_results/construct.rq`.

## Output files

Each run overwrites files in `--out` (default `shacl_results/`):

| File | Contents |
|------|----------|
| `datasets.nt` | CONSTRUCTed N-Triples data graph |
| `<shapes basename>.ttl` | Copy of the shapes graph (name from the URL or local file) |
| `construct.rq` | SPARQL CONSTRUCT used for this run |
| `validation_report.ttl` | Official `sh:ValidationReport` |
| `validation_results.csv` | One row per SHACL result |
| `validation_summary.json` | Counts, per-dataset tallies, run metadata |

CSV columns: `severity`, `component`, `focus_node`, `path`, `value`, `source_shape`,
`message`.

The process prints a short summary: `conforms`, result count, counts by constraint
component, and counts by property path.

## Sample run

First run (2026-08-26) against the default QLever endpoint with `--limit 100`:

| | |
|---|---|
| Datasets pulled | 100 |
| Triples in data graph | 29,054 |
| Conforms | false |
| SHACL results | 869 (all `Violation`) |
| Results per dataset | 8 to 11. No dataset passed cleanly. |

By constraint component:

| Count | Component |
|------:|-----------|
| 833 | `MinCountConstraintComponent` |
| 31 | `NodeKindConstraintComponent` |
| 5 | `MaxCountConstraintComponent` |

By property path:

| Count | Path |
|------:|------|
| 126 | `schema:keywords` |
| 100 | `schema:alternateName` |
| 100 | `schema:citation` |
| 100 | `schema:sameAs` |
| 95 | `schema:identifier` |
| 95 | `schema:license` |
| 95 | `schema:version` |
| 95 | `schema:url` |
| 56 | `schema:variableMeasured` |
| 6 | `schema:spatialCoverage` |
| 1 | `schema:temporalCoverage` |

Most results report a missing recommended field. `schema:keywords` also fails
`sh:nodeKind sh:Literal` when the value is an IRI (for example NERC vocabulary terms
on BODC records). Five BODC records have more than one `schema:spatialCoverage`.

See `notes.md` for the same numbers.

## Shape caveats

`shapes/googleRecommended.ttl` is a corrected local copy of the gaiaCatalog
shapes. It is not the same file as
`skills/SHACL_bundle/decoder-validate-shacl/assets/googleRecommended.ttl`.

Corrections relative to the remote gaiaCatalog file:

- `ex:CreatorShape` targets `schema:Dataset` (the remote file used `schema:DataSet`).
- `ex:CitationShape` requires at least one citation, not exactly 11.
- Identifier, license, and version no longer use `sh:class` on `schema:URL` or `schema:Number`. Those terms are datatypes. URL values use `sh:nodeKind sh:IRI`. Version values use `sh:nodeKind sh:Literal`.
- `ex:AltNameShape` no longer has a redundant `sh:not [ sh:nodeKind sh:IRI ]`.
- `ex:URLShape` message matches the `sh:IRIOrLiteral` constraint.

Several properties still require exactly one value (`identifier`, `license`,
`sameAs`, `spatialCoverage`, `temporalCoverage`, `version`, `url`). A missing or
extra value is a Violation.

The default remote URL still has the uncorrected gaiaCatalog shapes.

## Relation to `shapeValidator/`

| | `shaclTest/` | `shapeValidator/` |
|---|---|---|
| Role | Engine test | Production batch validator |
| Engine | pwin/SHACL_Engine (`import shacl`) | pyshacl or pyrudof |
| Unit of work | One CONSTRUCT of N Datasets | One named graph at a time |
| Default shapes | gaiaCatalog Google recommended | OIH `SHACL/*.ttl` (for example `depth_one.ttl`) |
| Output | Turtle report + CSV + JSON | N-Quads or Parquet |

Use this directory to try the Rust `shacl` Python bindings on a SPARQL CONSTRUCT
result. Use `shapeValidator/` for OIH depth-profile checks and large runs.

## Requirements

- Python `>=3.13`
- Package `shacl>=0.1.10` (declared in the repo `pyproject.toml`)
- Network access to the SPARQL endpoint. Shapes also need network access when `--shapes` is a URL.

The script uses the standard library for HTTP (`urllib.request`). It sets
`User-Agent: dataset-shacl-validate/1.0`. SPARQL timeout is 180 seconds. Shapes
download timeout is 60 seconds.

If the SPARQL request fails or the shapes source is unreadable, the script
exits with code 1.
If the CONSTRUCT returns no `schema:Dataset` type triples, it exits with code 2.
