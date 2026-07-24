# Projects

Per-provider workspaces under DOOS for turning ocean observation metadata into
schema.org + GeoSPARQL RDF (typically as JSON-LD, N-Triples, or N-Quads) so depth
can be queried consistently in the federated SPARQL graph. Approaches differ by
source format and how much depth information is already present.

**ERDDAP** is excluded below: that directory holds notes and harvested examples
about native ERDDAP JSON-LD, not a DOOS transform pipeline.

---

## AODN

**Australian Ocean Data Network** — XSLT pipeline from ISO metadata, with
optional depth enrichment from distributions.

Records are fetched (or loaded) as ISO 19115-3 XML from the IMOS GeoNetwork
catalogue, converted to ISO 19139, then mapped to schema.org Dataset JSON-LD via
XSLT (`run_pipeline.py` orchestrates Saxon + lxml). Measured variables come from
`gmd:MD_SampleDimension`; the CF name `depth` is remapped to OIH-style
`DepBelowSurf` in `variableMeasured`. When metadata alone lacks numeric ranges,
`depth_from_distribution.py` can download tabular distributions (csv/tsv/parquet/
Excel), compute observed min/max for depth columns, and optionally write those
into the JSON-LD before N-Triples export.

---

## ARGO

**ARGO profiling floats** — GeoParquet → RDF via JSON-LD templates (and optional RML).

Source data is profile-level GeoParquet (`depth_max_in_meters`, geometry, title,
etc.). The `geopan.py` CLI fills a schema.org JSON-LD template
(`template/argo1.json`) per row, setting `variableMeasured` depth
`maxValue` and GeoSPARQL WKT geometry, then serializes to N-Triples under
`data/output/`. An alternate path uses morph-kgc RML mappings under `RML/` (still
maturing for full ARGO column coverage). Depth is taken from the parquet column,
not recomputed from raw profiles.

---

## BODC

**British Oceanographic Data Centre** — harvest and validate existing schema.org
JSON-LD (no field-level transform).

BODC already publishes Dataset JSON-LD via the Linked Systems UK API, including
depth as `DepBelowSurf` (NERC P01 `ADEPZZ01`) with `minValue`/`maxValue` on
`variableMeasured`. This subproject inventories depth tiers from a Gleaner/OIH
release and live sitemap harvest, SHACL-validates against `depth_one.ttl`, and
exports conforming named graphs as N-Quads for federation. Unlike OBIS, no
auxiliary depth graph is built — depth triples are already in the provider
metadata.

---

## CCHDO

**CCHDO bottle NetCDF** — intermediate RDF + SHACL-AF SPARQL rules → JSON-LD.

NetCDF global attributes, dimensions, and variable descriptors are extracted to
JSON (`nc_metadata.py`), loaded into a temporary `cchdo:` RDF graph, then
expanded with SHACL Advanced Features `sh:SPARQLRule` CONSTRUCT rules
(`pyshacl.shacl_rules`) into either schema.org Dataset (`variableMeasured` as
PropertyValue nodes with units, CF/WHP names) or MLCommons Croissant 1.1. Depth
appears as whatever depth-related variables the NetCDF declares (e.g. pressure,
`btm_depth`); the rules materialize those variables into linked data rather than
aggregating occurrence depths from a bulk table.

---

## CIOOS

**Canadian Integrated Ocean Observing System** — early CKAN → schema.org mapping;
depth encoding still exploratory.

Scripts fetch CKAN `package_show` records and map standard fields, spatial/temporal
extent, EOVs, and resources into schema.org Dataset JSON-LD (`convert.py`,
`ckanMeta.py`). CIOOS catalogues also expose framed schema.org JSON-LD on dataset
pages. Depth is not yet a complete transform: ISO `gmd:verticalElement` in sample
records is often nil, while many datasets point at ERDDAP resources that could
supply Z/depth via variable attributes or geometry. Notes consider inferring depth
into the spatial/depth profile (possibly SHACL-AF) once source patterns are fixed
with the CIOOS metadata team.

---

## OBIS

**Ocean Biogeographic Information System** — auxiliary depth graph from occurrence
parquet.

OBIS dataset APIs do not expose per-dataset depth ranges. Stage 1 aggregates
Darwin Core–style `minimumDepthInMeters` / `maximumDepthInMeters` from the bulk
OBIS parquet export (DuckDB) into min/max per `dataset_id`. Stage 2 resolves each
id against harvested source JSON-LD `@id`/`url` values and emits ODIS-pattern
schema.org JSON-LD with a single `depth` PropertyValue (`minValue`/`maxValue`).
Stage 3 normalizes selected JSON-LD into named-graph N-Quads (`output.nq`). The
result is an auxiliary graph meant for federation and feedback to OBIS, not a
full re-description of every dataset field.

---

## Output locations (reference)

| Provider | Typical outputs |
|----------|-----------------|
| AODN | `AODN/output/`, `AODN/demo-output/` (`.jsonld`, `.nt`) |
| ARGO | `ARGO/data/output/` (`.nt`) |
| BODC | `BODC/output/` (`bodc_harvest.nq`, `bodc_validated.nq`, `jsonld_cache/`) |
| CCHDO | per-file `*.schema.shacl.jsonld`, `*.croissant.jsonld` |
| CIOOS | exploratory; sample JSON in-tree |
| OBIS | `OBIS/jsonld/output_raw_strict/`, `OBIS/output.nq` |
| BCO-DMO (outside this dir) | `skills/DOOS_bundle/doos-bco-dmo-index/output/output.nt` |

See each subdirectory’s own `README.md` for install steps, CLI flags, and
detailed file layouts.
