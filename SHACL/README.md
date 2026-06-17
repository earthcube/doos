# SHACL

SHACL shape files for validating ocean metadata graphs conforming to schema.org `Dataset`.
All shapes use the `oihval:` namespace (`https://oceans.collaborium.io/voc/validation/1.0.1/shacl#`)
and target `schema:Dataset` nodes unless noted.

## Shape files

### `ERDDAP.ttl`

Primary OIH (Ocean Information Hub) validation shapes. Intended for use with PySHACL.

- **`oihval:IDShape`** — warns if the Dataset node has no IRI (`@id`)
- **`oihval:OIHCoreShape`** — enforces required fields (`name`, `description`, `license`) as Violations and recommended fields (`contacts`, `citation`, `variableMeasured`, `measurementMethod`) as Warnings; also checks that `variableMeasured` contains `PropertyValue` nodes named `latitude` and `longitude`
- **`oihval:OIHSpatialShape`** — validates `schema:GeoShape` polygon strings: space-separated numbers, polygon closed (first coordinate equals last) via regex backreference

### `ERDDAP_simple.ttl`

Drop-in replacement for `ERDDAP.ttl` compatible with the Rust-based **pyrudof** engine. Identical in all shapes except `oihval:polygonCloseProperty`, where the backreference (`\1`) in the polygon-close regex is replaced with a simplified pattern (requires ≥4 space-separated numbers). The first-equals-last constraint is relaxed as a result. Use this file when running `validateToRudof.py` or `validateToParquetRudof.py`.

### `ERDDAP_test.ttl`

Minimal single-shape file used for targeted testing. Checks only that `variableMeasured` contains at least one `PropertyValue` with `name = "latitude"`. Useful for quick sanity checks of the qualified value shape pattern without running the full OIH suite.

### `googleRequired.ttl`

Checks the three fields required by Google Dataset Search for dataset indexing:

- `schema:url` — exactly one, IRI or literal
- `schema:description` — exactly one literal, 50–5000 characters
- `schema:name` — at least one literal

### `depth_one.ttl`

OIH depth profile presence check. Validates that a Dataset has exactly one `name`, one `description`, and at least one `variableMeasured` whose `name` value is `"DepBelowSurf"` (depth below surface). Used to confirm the core OIH depth variable is present in a graph.

## Usage

```bash
# Validate against Google required fields (JSON-LD input, table output)
pyshacl -s ./googleRequired.ttl -sf turtle -df json-ld -f table ../docs/examples/edmoExample.json

# Validate against full OIH shapes (N-Quads input)
pyshacl -s ./ERDDAP.ttl -sf turtle -df nquads -f table data.nq

# Validate with pyrudof-compatible shapes
pyshacl -s ./ERDDAP_simple.ttl -sf turtle -df nquads -f table data.nq
```

See `scripts/shapeValidator/` for the full parallel validation harness.
