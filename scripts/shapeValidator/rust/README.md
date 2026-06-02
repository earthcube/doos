# shacl-validate-oxi (Rust)

Rust implementation of a SHACL validator, intended as a high-performance replacement for the Python `validateToOxigraph.py`.

## Goals

- Same CLI interface as the Python version:
  - `endpoint` (SPARQL endpoint)
  - `shapefile` (SHACL shapes — local file **or** HTTP URL)
  - `--output` / `-o` (N-Quads, default `results.nq`)
  - `--limit`

- Fetch graphs via **SPARQL CONSTRUCT** (matching current Python behavior).
- Use **rudof** for SHACL validation (excellent performance in our benchmarks).
- Store results in **Oxigraph** (on-disk by default to handle large result sets).
- Always skolemize `sh:ValidationReport` and `sh:ValidationResult` subjects with authority `http://gleaner.io` (for consistency with the existing Python pipeline).
- Support parallel fetching + validation using **tokio**, with configurable **rate limiting** to be polite to data providers.
- Final output as N-Quads.

## Architecture (v0.1 target)

- **SHACL validation**: `rudof_lib`
- **RDF store**: `oxigraph` (opened on disk via `Store::open()`)
- **Async runtime + concurrency**: `tokio`
- **Rate limiting**: `governor` (token bucket, applied to SPARQL fetches)
- **HTTP client**: `reqwest` (async)
- **CLI**: `clap` (derive)
- **Error handling**: `anyhow` + `thiserror`

## Directory

This lives in `scripts/shapeValidator/rust/` so it can live alongside the Python tools and benchmarks during the transition.

## Current Status (as of latest build)

The project now has a **substantially complete first-pass pipeline**:

- Full CLI (same style as `validateToOxigraph.py` + rate limiting controls).
- Rate-limited concurrent fetching via SPARQL CONSTRUCT (using `governor` + tokio).
- Shapes loading from file or URL.
- Concurrent task structure that does: fetch → rudof validation → (placeholder for skolemization) → insert into on-disk Oxigraph store.
- Skolemization module ready.
- On-disk Oxigraph store creation and final N-Quads dump.

`cargo check` currently has some type inference issues around the exact `rudof_lib` return types (very common on first integration). These are quick to resolve once we lock the precise API calls.

The architecture is now very close to what a working first version will look like.

The project is ready for the core pipeline implementation.

## Building & Running (once implemented)

```bash
cargo run --release -- \
    http://ghost.lan:7007 \
    ../../SHACL/ERDDAP_simple.ttl \
    --limit 100 \
    --output results.nq \
    --max-concurrent 8 \
    --requests-per-second 2
```

## Open Design Notes

### On-Disk vs In-Memory Oxigraph

Because validation reports for thousands of graphs can become large, we are defaulting to on-disk storage (`oxigraph::Store::open(path)`). This is safer for production-scale runs than keeping everything in RAM.

### Rate Limiting

We will expose CLI options such as:
- `--max-concurrent N` (how many graphs to process in parallel)
- `--requests-per-second N` (or `--rate-limit`)

This protects upstream SPARQL endpoints.

See the parent `shapeValidator/` directory (especially `validateToOxigraph.py`, `benchmark_shacl_engines.py`, and `ERDDAP_simple.ttl`) for context and reference implementation.