# Rust SHACL Validator Effort

A high-performance Rust implementation is being developed in `rust/`.

## Current Goals

- Match the CLI and behavior of `validateToOxigraph.py`
- Use **rudof** for fast SHACL validation
- Use **Oxigraph on-disk** for result storage (to handle large result sets)
- Full **tokio** async with **rate limiting** (`governor`) to be respectful to data providers
- Fetch graphs via **SPARQL CONSTRUCT**
- Consistent **skolemization** of report/result subjects using authority `http://gleaner.io`

## Directory

- `rust/` — The Rust project (Cargo workspace)

See `rust/README.md` for detailed status and architecture decisions.
