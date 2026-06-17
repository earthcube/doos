# Quickstart

## 1. Install

```bash
uv sync
```

## 2. Get the source data

Download the OBIS parquet export from https://obis.org/data/access/ and place it
in the repo (e.g. `obis_20240625.parquet`). Stage 1 needs it.

## 3. Run the pipeline

```bash
# All stages: parquet -> depth aggregate -> JSON-LD -> output.nq
uv run python build_depth_graph.py --source obis_20240625.parquet
```

Outputs:
- `idMinMaxDepth.parquet` — min/max depth per dataset
- `jsonld/output_raw/`, `jsonld/output_raw_strict/` — depth JSON-LD
- `output.nq` — combined N-Quads

If you already have `idMinMaxDepth.parquet` and just want the JSON-LD + N-Quads:

```bash
uv run python build_depth_graph.py --stage 2 3
```

## 4. (Optional) Load into a triplestore

```bash
./scripts/jsonldDirLoader.sh ./jsonld/output_raw_strict <sparql-endpoint>
```

Requires `jsonld`, `curl` (and `mc` for the Minio variant).
