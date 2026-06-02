# README for Validator

## Notes

* `validateToOxigraph.py` — Recommended single-threaded baseline. Clean, correct, uses pyoxigraph.
* `validateToParquet.py` — Recommended for large-scale runs. Uses ProcessPoolExecutor + streaming Parquet output (structured SHACL results, one row per ValidationResult).
* `benchmark_shacl_engines.py` — Tool to compare PySHACL vs pyrudof (Rust bindings) performance on your real data.
* `validateToRudof.py` — pyrudof (rudof) version of the single-threaded validator. Use with `ERDDAP_simple.ttl`. Supports `--no-skolemize`.
* `conccurrent/streamToParquet.py` — Reusable high-throughput streaming pattern (not SHACL-specific).

* Or use pyoxigraph from the start?
* A table format for use in KuzuDB?   nice for analytics and path analysis

## Rust option

Lincoln institute, Internet of Water, is using:

https://github.com/rudof-project/rudof?tab=readme-ov-file

This is work checking out.  May need https://lib.rs/crates/rdftk_core to provide
Skolemization.  Though I don't see it in there nor in rudof.   Without that,
it's a bit hard to move over, though it's not an impossible bit of logic
to do in Rust.

## Recent improvements (2026)

* `validateToOxigraph.py`
  * Now uses argparse with `--output` and `--limit`.
  * Endpoint from CLI is actually respected for both graph listing and CONSTRUCT (was previously ignored due to globals in defs/).
  * Per-URI error resilience; better output control.
  * Updated for current pyoxigraph API (mime_type strings instead of RdfFormat).

* `defs/getGraphs.py` + `defs/getConstruct.py`
  * Removed dangerous module-level global SPARQLWrapper singletons for new callers.
  * Functions now accept explicit `endpoint=` (with backward-compatible defaults).
  * Fixed return types, docstrings, and header accumulation bug in CONSTRUCT calls.

* `conccurrent/streamToParquet.py`
  * Replaced slow `Manager().Queue` with fast `spawn` context Queue.
  * Cleaner shutdown (sentinel + as_completed progress).
  * argparse, reusable StreamingParquetWriter, improved docs for adapting to SHACL result streaming.
  * Removed global writer anti-pattern.

* **NEW: `validateToParquet.py`** (recommended for large-scale work)
  * Combines the high-throughput streaming Parquet pattern with real SHACL validation.
  * Uses ProcessPoolExecutor (true parallelism, no GIL issues).
  * Emits **one row per SHACL ValidationResult** (plus synthetic rows for clean graphs).
  * Produces analytics-friendly Parquet (zstd compressed) ready for polars/duckdb.
  * New helper `validate_with_shacl_results()` added to `defs/shaclValidator.py`.
  * Example: `python validateToParquet.py http://... shapes.ttl --workers 8 --output-dir results`

* **NEW: `validateToRudof.py`**
  * pyrudof (rudof) equivalent of the single-threaded `validateToOxigraph.py`.
  * Uses the fast Rust-based SHACL engine via Python bindings.
  * Still stores results in pyoxigraph as N-Quads.
  * Supports `--no-skolemize` flag to disable report skolemization.
  * Must be used with `ERDDAP_simple.ttl` (or equivalent) because the original `ERDDAP.ttl` contains regex backreferences that rudof cannot parse.
  * **Known limitation**: On Linux, some datasets with very long graph URIs can cause "File name too long" (os error 36) inside rudof's internal storage. These graphs are skipped with a warning. The data is loaded into the default graph (no named graph) to reduce this risk.
