# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repo builds an **auxiliary depth graph** for OBIS (Ocean Biogeographic Information System) datasets. OBIS's API and harvested JSON-LD do not expose per-dataset depth statistics, so this project derives `minimumDepthInMeters`/`maximumDepthInMeters` ranges per dataset from the OBIS parquet export and emits new schema.org JSON-LD that can be loaded into a triplestore (Blazegraph/Oxigraph) and shared back with OBIS. See `README.md` for the original problem context and the target JSON-LD shape (`book/thematics/depth` ODIS pattern).

## Environment

- Python `>=3.13`, managed with **uv** (`uv.lock`, `pyproject.toml`). Run with `uv run <script.py>`. Sync a fresh checkout with `uv sync`.
- Dependencies declared in `pyproject.toml`: `duckdb`, `pandas`, `pyarrow`, `pyld`, `pyoxigraph`, `python-dwca-reader`, `requests`, `visidata`.

## The pipeline — `build_depth_graph.py`

The entire workflow lives in one script with one function per stage. Each stage consumes the previous stage's output.

```
uv run python build_depth_graph.py             # run all 3 stages
uv run python build_depth_graph.py --stage 2 3 # run a subset
uv run python build_depth_graph.py --source obis_20240625.parquet --help
```

1. **`aggregate_depth`** — DuckDB group-by on the OBIS export `obis_20240625.parquet` (the full occurrence export from https://obis.org/data/access/; depth is OBIS's interpretation of the Darwin Core min/max depth fields — large, **not committed**). Writes `idMinMaxDepth.parquet` with columns `dataset_id`, `Min(minimumDepthInMeters)`, `Max(maximumDepthInMeters)` (the parenthesised names are pinned via SQL aliases because stage 2 references them by name — see `COL_MIN`/`COL_MAX`).
2. **`generate_jsonld`** — reads `idMinMaxDepth.parquet`, resolves each dataset's canonical `@id` by substring-matching `dataset_id` against the `url` field of `./jsonld/obis_source/*.jsonld` (all urls read once), then fills `DEPTH_TEMPLATE` (a schema.org `Dataset` → `variableMeasured` "depth" `PropertyValue`). Writes `<dataset_id>_depth.jsonld` to `./jsonld/output_raw/` (all) and `./jsonld/output_raw_strict/` (non-null min AND max). Both dirs are cleared of prior `*_depth.jsonld` files first, so each run regenerates them from scratch.
3. **`build_nquads`** — `pyld` URDNA2015-normalizes each JSON-LD file and loads it into a per-file **named graph** (`http://oceaninfohub.org/graph/obisdepth/<filename>`) in a `pyoxigraph.Store`, then dumps `output.nq`. Defaults to the **strict** dir (clean depth values); override with `--nq-from` (e.g. `./jsonld/output_raw`).

## Loading into a triplestore (separate, alternative sink)

Stage 3 and the shell loaders are **alternatives**, not sequential — both consume stage 2's JSON-LD dirs independently. Use stage 3 for a local `output.nq`; use the loaders to push into a live SPARQL store:

- `scripts/jsonldDirLoader.sh <dir> <sparql-endpoint>` — POSTs every file in a dir (via `jsonld format -q`) to a SPARQL update endpoint.
- `scripts/jsonldLoader.sh <minio-bucket> <sparql-endpoint>` — same, streaming source files from a Minio bucket (`mc`).
- Both require external CLIs: `jsonld` (digitalbazaar jsonld.js), `mc` (Minio client), `curl`.

## `jsonld/` directory layout

- `obis_source/` — harvested OBIS dataset JSON-LD (lookup source for resolving `@id` by `dataset_id`). **Provenance:** crawled by the gleaner.io / Ocean InfoHub (OIH) pipeline from OBIS's published schema.org JSON-LD (same family as `obis_release.ttl`); the 40-hex filenames are gleaner content hashes. Stage 2 reads only the `url` field. Coverage is bounded by this crawl — datasets absent here get no `@id` and are skipped, so a stale crawl silently shrinks output.
- `output_raw/`, `output_raw_strict/` — generated depth JSON-LD (stage 2 output; strict drops null depths).

## Side scripts (not part of the pipeline)

`dwca/dwcaReader.py`, `dwca/dwcaPandas.py` are exploratory: they read Darwin Core Archive (`.zip`) files with `python-dwca-reader`, from a local `./archive/` file or an IPT endpoint, to inspect depth fields.

## Conventions

- `DEPTH_TEMPLATE` in `build_depth_graph.py` is the single source of truth for the emitted JSON-LD shape. `README.md` also shows the pattern as documentation — keep it consistent if you change units/`propertyID`/`minValue`/`maxValue`.
- Data artifacts (`*.parquet`, `output.nq`, `obis_release.ttl`, `jsonld/`, `store/`) are gitignored working data — regenerate via the script rather than hand-editing or committing them.
