# loadToOxigraph

Load DOOS provider outputs into an in-memory [Oxigraph](https://github.com/oxigraph/oxigraph)
SPARQL server for ad-hoc querying and federation testing.

The output locations are taken from [`projects/README.md`](../../projects/README.md).
Each provider's RDF is pushed to the running server over the SPARQL
[Graph Store HTTP Protocol](https://www.w3.org/TR/sparql11-http-rdf-update/).

## Contents

| File | Purpose |
|---|---|
| `loadToOxigraph.py` | Reads the YAML config and POSTs each source into a running Oxigraph server. |
| `oxigraph_load.yaml` | Declares the provider sources to load (paths, formats, target graphs). |
| `../../build/Dockerfile` | Builds an in-memory Oxigraph server image used as the load target. |

## What gets loaded

| Provider | Source | Format | Target graph |
|---|---|---|---|
| ARGO | `projects/ARGO/data/output/*.nt` | N-Triples | `urn:doos:argo` |
| OBIS | `projects/OBIS/output.nq` | N-Quads | embedded graph names |
| AODN | `projects/AODN/output/output.json` | JSON-LD | `urn:doos:aodn` |
| BODC | `projects/BODC/output/bodc_harvest.nq` | N-Quads | embedded graph names |
| BCO-DMO | `skills/bco-dmo-scan/output/output.nt` | N-Triples | `urn:doos:bcodmo` |

Triple formats (`nt`, `ttl`, `jsonld`) are loaded into the named graph declared by
`graph:` in the config. Quad formats (`nq`, `trig`) already carry their own graph
names, so the `graph:` field is omitted for them.

> **JSON-LD note:** Oxigraph 0.5.x parses JSON-LD natively
> (`application/ld+json`), so JSON-LD sources are loaded as-is — there is **no**
> pre-conversion step.

## Quickstart

Run all commands from the repository root.

```bash
# 1. Build and start the in-memory Oxigraph server (data is lost on stop)
docker build -t doos-oxigraph build/
docker run --rm -p 7878:7878 doos-oxigraph

# 2. In another terminal, load the configured sources
python scripts/loadToOxigraph/loadToOxigraph.py --wait
```

`--wait` polls the endpoint until the server is ready before loading. On success
the script prints a summary like:

```
Done: loaded 2471 file(s) into http://localhost:7878

Loaded store summary:
  default-graph (union) triples: 110923
  named graphs: 4884 (top 15 by triple count):
    urn:doos:argo,46702
    urn:doos:bcodmo,169
    urn:doos:aodn,159
    ...
```

The server is started with `--union-default-graph`, so the default graph is the
union of every named graph — a bare `{ ?s ?p ?o }` query sees all loaded data.

### Options

```bash
python scripts/loadToOxigraph/loadToOxigraph.py --help
```

| Flag | Description |
|---|---|
| `--config PATH` | YAML source config (default: `oxigraph_load.yaml` next to the script). |
| `--endpoint URL` | Override the endpoint from the config (e.g. `http://localhost:7878`). |
| `--wait` | Wait for the server to come up before loading. |

## Test query against the running container

Use the repo's [`sparqlQueryl.py`](../sparqlQueryl.py) with the simple
[`get100.rq`](../../SPARQL/get100.rq) query (`SELECT * WHERE { ?s ?p ?o } LIMIT 100`):

```bash
python scripts/sparqlQueryl.py http://localhost:7878/query --query SPARQL/get100.rq
```

Expected output is a 100-row DataFrame:

```
                                                    o  ...                                       s
0              https://www.bco-dmo.org/dataset/986596  ...  https://www.bco-dmo.org/dataset/986596
..                                                ...  ...                                     ...
[100 rows x 3 columns]
```

You can also query the endpoint directly with `curl`:

```bash
# Total triples in the (union) default graph
curl -s http://localhost:7878/query \
  --data-urlencode 'query=SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }' \
  -H 'Accept: text/csv'

# List the named graphs
curl -s http://localhost:7878/query \
  --data-urlencode 'query=SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } } LIMIT 20' \
  -H 'Accept: text/csv'
```

## Adding a provider

Append an entry to `oxigraph_load.yaml`:

```yaml
  - name: myprovider
    path: projects/MyProvider/output      # file OR directory, relative to repo root
    format: jsonld                         # nt | nq | ttl | trig | jsonld
    graph: urn:doos:myprovider             # required for triple formats; omit for nq/trig
```

A directory `path` loads every matching file in it (`*.nt`, `*.jsonld`/`*.json`,
etc.). Line-based formats (`nt`, `nq`, `ttl`, `trig`) in a directory are
concatenated into a single request; JSON-LD files are posted one per request.

## Dependencies

`requests`, `pyyaml`, and `tqdm` (all in the project venv). The server side needs
only Docker.
