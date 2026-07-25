# DOOS deployment — discovery stack

Docker Compose stack for the **Discovery MCP** and a local **Oxigraph**
triplestore, with an optional one-shot **RDF load** from monorepo provider
outputs.

## Architecture

```text
Host
  :8765  →  mcp (doos-mcp)  ──SPARQL──►  oxigraph :7878
  :7878  →  oxigraph (persisted volume)
               ▲
               │ one-shot
             load (mounts monorepo)
```

| Service | Image | Role |
|---|---|---|
| `oxigraph` | `ghcr.io/oxigraph/oxigraph:0.5.5` | SPARQL endpoint, union default graph, data volume |
| `load` | `build/Dockerfile.load` | Push paths from `scripts/loadToOxigraph/oxigraph_load.yaml` |
| `mcp` | `build/Dockerfile.mcp` | MCP streamable-http (`/mcp`) |

## Prerequisites

- Docker Compose v2
- From a **clone of this monorepo** (load bind-mounts the repo root)
- Provider RDF outputs present where the load config expects them (missing paths are skipped with a warning):

  | Source | Path |
  |---|---|
  | ARGO | `projects/ARGO/data/output/*.nt` |
  | OBIS | `projects/OBIS/output.nq` |
  | AODN | `projects/AODN/output/output.json` |
  | BODC | `projects/BODC/output/bodc_harvest.nq` |
  | BCO-DMO | `skills/DOOS_bundle/doos-bco-dmo-index/output/output.nt` |

## Quickstart

```bash
# From monorepo root
docker compose -f deployment/docker-compose.yml up --build
```

Then:

- **MCP:** `http://127.0.0.1:8765/mcp`
- **SPARQL:** `http://127.0.0.1:7878/query`

If those host ports are already in use:

```bash
DOOS_OXIGRAPH_PORT=17878 DOOS_MCP_PORT=18765 \
  docker compose -f deployment/docker-compose.yml up --build
```
Example MCP client config:

```json
{
  "mcpServers": {
    "doos-discovery": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

Smoke SPARQL (host):

```bash
curl -sG 'http://127.0.0.1:7878/query' \
  --data-urlencode 'query=SELECT * WHERE { ?s ?p ?o } LIMIT 5' \
  -H 'Accept: application/sparql-results+json' | head
```

## Common commands

```bash
# Full stack (build + load + MCP)
docker compose -f deployment/docker-compose.yml up --build

# Detached
docker compose -f deployment/docker-compose.yml up --build -d

# Oxigraph only, then MCP without waiting for load (empty or existing volume)
docker compose -f deployment/docker-compose.yml up -d oxigraph
docker compose -f deployment/docker-compose.yml up --build --no-deps mcp

# Re-run load only (against running oxigraph)
docker compose -f deployment/docker-compose.yml run --rm load

# Logs
docker compose -f deployment/docker-compose.yml logs -f mcp

# Tear down (keeps volume)
docker compose -f deployment/docker-compose.yml down

# Tear down and wipe the graph volume
docker compose -f deployment/docker-compose.yml down -v
```

## Build images alone

```bash
docker build -f build/Dockerfile.mcp -t doos-mcp .
docker build -f build/Dockerfile.load -t doos-load .
docker build -t doos-oxigraph build/   # optional in-memory variant (no volume)
```

## Environment (MCP service)

| Variable | Compose default | Meaning |
|---|---|---|
| `DOOS_SPARQL_ENDPOINT` | `http://oxigraph:7878/query` | SPARQL URL inside the Docker network |
| `DOOS_MCP_HOST` | `0.0.0.0` | Must be all-interfaces in containers |
| `DOOS_MCP_PORT` | `8765` | Published as host `8765` |
| `DOOS_MCP_PATH` | `/mcp` | Streamable HTTP path |

## Data notes

- **Persisted graph:** volume `oxigraph-data`. Re-running `load` **appends** (does not clear). Use `down -v` for a clean store, or clear the volume manually.
- **ARGO data** is often gitignored (`projects/ARGO/data/`). Load will warn and skip if absent; other sources still load.
- The MCP image is **slim** (no full monorepo deps). Index/transform pipelines (BCO-DMO harvest, AODN XSLT, SHACL workers) are **not** in this stack.

## Troubleshooting

| Symptom | Check |
|---|---|
| MCP can't reach SPARQL | `DOOS_SPARQL_ENDPOINT=http://oxigraph:7878/query` (not `localhost` from inside the container) |
| Port publish but connection refused | MCP must bind `0.0.0.0` (compose sets this) |
| Load exits before oxigraph is ready | Increase `--wait-retries` / `--wait-delay` on the load service |
| Empty query results | Run load; confirm host files exist; try `down -v` then full `up --build` |
| Stale MCP code | `docker compose -f deployment/docker-compose.yml up --build mcp` |
