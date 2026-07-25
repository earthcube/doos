# DOOS Discovery MCP

MCP server that exposes **graph discovery** against a local (or remote) SPARQL
endpoint, plus **prompts** and a thin **skill catalog**.

v1 focus:

- Curated SPARQL templates (from `skills/DOOS_bundle/doos-sparql/`)
- Ad-hoc SPARQL execution
- **Host-side** text→SPARQL: resources (`patterns`, `cookbook`) + `ask_graph` prompt;
  the host LLM writes SPARQL; this server only executes
- Prompts from `prompts/` (FAIR / Blueprint interview)
- Skill catalog as MCP resources (not the main product surface)

**Default MCP transport: HTTP** (`streamable-http`) at  
`http://127.0.0.1:8765/mcp`

SPARQL backend default: **`http://localhost:7878/query`** (Oxigraph via
`build/Dockerfile` + `scripts/loadToOxigraph/`).

## Setup

### Docker (recommended)

Full stack (Oxigraph + load monorepo RDF + MCP) from the monorepo root:

```bash
docker compose -f deployment/docker-compose.yml up --build
```

- MCP: `http://127.0.0.1:8765/mcp`
- SPARQL: `http://127.0.0.1:7878/query`

See [`deployment/README.md`](../../deployment/README.md). Images: `build/Dockerfile.mcp`, `build/Dockerfile.load`.

### Local venv

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements-mcp.txt
# or: uv sync  (full monorepo)
```

Ensure Oxigraph is running and loaded:

```bash
docker build -t doos-oxigraph build/
docker run --rm --network host doos-oxigraph
# other terminal:
python scripts/loadToOxigraph/loadToOxigraph.py --wait
```

## Run (HTTP default)

```bash
cd /path/to/doos
source .venv/bin/activate
export PYTHONPATH=src
python -m mcp_server
# → streamable-http on http://127.0.0.1:8765/mcp
#
# Docker / published ports: bind all interfaces
python -m mcp_server --host 0.0.0.0 --port 8765
```

### Transport options

| Flag | Transport | When to use |
|---|---|---|
| *(default)* | `streamable-http` | Remote / multi-client HTTP MCP |
| `--transport sse` | SSE | Older HTTP+SSE clients |
| `--transport stdio` | stdio | Claude Desktop / process-spawned hosts |

```bash
# Explicit HTTP bind
python -m mcp_server --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp

# Legacy SSE
python -m mcp_server --transport sse --port 8765

# Stdio (desktop hosts)
python -m mcp_server --transport stdio
```

### Environment

| Variable | Default | Meaning |
|---|---|---|
| `DOOS_ROOT` | auto (repo root) | Monorepo root for skills/prompts/templates |
| `DOOS_MCP_TRANSPORT` | `streamable-http` | `streamable-http` \| `sse` \| `stdio` |
| `DOOS_MCP_HOST` | `127.0.0.1` | HTTP/SSE bind host |
| `DOOS_MCP_PORT` | `8765` | HTTP/SSE bind port |
| `DOOS_MCP_PATH` | `/mcp` | Streamable HTTP path |
| `DOOS_SPARQL_ENDPOINT` | `http://localhost:7878/query` | Default SPARQL URL |
| `DOOS_SPARQL_TIMEOUT` | `30` | HTTP timeout seconds |
| `DOOS_SPARQL_DEFAULT_LIMIT` | `100` | Auto LIMIT when missing |
| `DOOS_SPARQL_MAX_LIMIT` | `1000` | Hard cap on LIMIT |
| `DOOS_SPARQL_MAX_ROWS` | `500` | Max rows returned to the host |

## Client configuration

### HTTP (streamable-http) — default

Hosts that support remote MCP URLs (works for local `python -m mcp_server` or
`docker compose -f deployment/docker-compose.yml up`):

```json
{
  "mcpServers": {
    "doos-discovery": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

Exact JSON shape varies by host (Cursor, Claude, custom). The important part is
the **URL** `http://127.0.0.1:8765/mcp` while the server is running.

### Stdio (optional)

```json
{
  "mcpServers": {
    "doos-discovery": {
      "command": "/path/to/doos/.venv/bin/python",
      "args": ["-m", "mcp_server", "--transport", "stdio"],
      "env": {
        "PYTHONPATH": "/path/to/doos/src",
        "DOOS_ROOT": "/path/to/doos",
        "DOOS_SPARQL_ENDPOINT": "http://localhost:7878/query"
      }
    }
  }
}
```

## Tools

| Tool | Purpose |
|---|---|
| `list_capabilities` | Self-description + default endpoint + MCP URL |
| `sparql_list_templates` | Catalog of curated query ids |
| `sparql_run_template` | Run a template (`depth_assay`, `probe_triples`, …) |
| `sparql_query` | Ad-hoc SPARQL (auto-LIMIT for SELECT) |
| `graph_probe` | Quick store health sample |

## Resources

| URI | Content |
|---|---|
| `doos://config` | Defaults and paths |
| `doos://graph/patterns` | `scripts/text2query/patterns.txt` |
| `doos://graph/cookbook` | Schema.org SPARQL cookbook |
| `doos://sparql/templates` | Template index JSON |
| `doos://sparql/templates/{id}` | Raw `.rq` body |
| `doos://prompts` / `doos://prompts/{name}` | Files under `prompts/` |
| `doos://skills` / `doos://skills/{name}` | Skill catalog / `SKILL.md` |

## Prompts

| Prompt | Source |
|---|---|
| `ask_graph` | Host-side NL→SPARQL workflow |
| `fair_blueprint_interview` | `prompts/fairAssessmentInterview.md` |
| `blueprint_context` | `prompts/contextPromptShort.md` |

## Example host workflow (text → SPARQL)

1. Load prompt **`ask_graph`**
2. Read resources **`doos://graph/cookbook`** and **`doos://graph/patterns`**
3. Optionally `sparql_list_templates` / `sparql_run_template` for known intents
4. Otherwise draft SPARQL → **`sparql_query`**
5. Report only real bindings from the tool result

## Smoke test (library, no MCP host)

```bash
export PYTHONPATH=src
python - <<'PY'
from mcp_server.server import list_capabilities, graph_probe, sparql_list_templates
print(list_capabilities()[:500])
print(graph_probe(limit=5)[:400])
PY
```

## Smoke test (HTTP server)

```bash
export PYTHONPATH=src
python -m mcp_server --port 8765 &
# MCP endpoint (streamable HTTP; clients use the full MCP protocol):
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/mcp
```

## Out of scope (v1)

- Server-side LLM / DSPy text→SPARQL (see `scripts/text2query/`)
- SHACL validation, Oxigraph load, BCO-DMO index tools
- SPARQL UPDATE
- Authentication on the MCP HTTP port (bind to localhost by default)
