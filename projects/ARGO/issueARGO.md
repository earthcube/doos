# ARGO GeoParquet to RDF: Status and Next Steps

## Overview

This issue tracks the current status and proposed next steps for the ARGO ocean profiling data transformation pipeline. The goal is to convert ARGO float profile data from GeoParquet format into semantic web-ready RDF representations aligned with ODIS and Schema.org patterns.

## Current Status

### What's Working

We have a functional CLI tool (`geopan.py`) with the following capabilities:

| Command | Status | Description |
|---------|--------|-------------|
| `info` | Working | Inspect parquet file metadata (record count, columns, sample data) |
| `tocsv` | Working | Export to CSV with WKT geometry |
| `tordf` | Working | Convert to RDF using JSON-LD templates, outputs N-Triples files |
| `rml` | Wired up | RML mapping via morph-kgc (needs ARGO-specific mapping files) |

### Data Assets

- **Sample data**: `argo_profiles_features_nmdis.parquet` - ARGO profile data from NMDIS
- **JSON-LD template**: `template/argo1.json` - Maps to Schema.org Dataset + GeoSPARQL
- **RML mappings**: `RML/test.ttl`, `RML/argo.ttl` - Need refinement for ARGO columns
- **Generated output**: ~100+ N-Triples files in `data/output/`

### Current Semantic Model

The `tordf` command currently maps ARGO profiles to:
- `schema:Dataset` for each profile
- `schema:name`, `schema:title`, `schema:description` for metadata
- `schema:variableMeasured` with `schema:PropertyValue` for depth measurements
- `geosparql:hasGeometry` with WKT literals for spatial location

## Known Gaps

1. **RML mappings need ARGO-specific columns**: The existing RML files reference columns from a different dataset (GDSC). Need to create mappings that target actual ARGO parquet columns.

2. **Limited variable coverage**: Currently only mapping `depth_max_in_meters`. ARGO profiles contain additional oceanographic variables (temperature, salinity, etc.) that could be represented.

3. **Profile-to-float relationships**: No current linking between individual profiles and their parent ARGO float platform.

4. **Temporal coverage**: Profile timestamps not yet mapped to `schema:temporalCoverage`.

5. **ODIS alignment verification**: Need to verify output conforms to ODIS Ocean InfoHub patterns.

## Proposed Next Steps

### Phase 1: Core Improvements

- [ ] **Create ARGO-specific RML mapping** - Build `RML/argo_profiles.ttl` that maps all relevant ARGO parquet columns
- [ ] **Add temporal mapping** - Include profile date/time in the RDF output
- [ ] **Expand variable coverage** - Map additional oceanographic measurements (temperature, salinity, conductivity)

### Phase 2: ODIS Alignment

- [ ] **Review ODIS patterns** - Ensure output aligns with [ODIS-Arch guidelines](https://book.odis.org/)
- [ ] **Add provenance metadata** - Include data source attribution and licensing
- [ ] **Platform linking** - Connect profiles to ARGO float identifiers using appropriate vocabularies

### Phase 3: Integration & Testing

- [ ] **Test with additional ARGO sources** - Validate against data from other DACs (AOML, Coriolis, etc.)
- [ ] **SPARQL endpoint integration** - Load output into triplestore and test federated queries
- [ ] **Documentation** - Create examples showing how to query the resulting linked data

## Questions for the Group

1. What additional ARGO variables are highest priority to include in the semantic model?
2. Are there specific ODIS patterns or vocabularies we should prioritize aligning with?
3. Should we link to external vocabularies like NERC/BODC for oceanographic terms?
4. What downstream use cases should we design the RDF output to support?

## Resources

- **Repository**: https://github.com/earthcube/doos
- **ARGO project directory**: `projects/ARGO/`
- **ODIS Book**: https://book.odis.org/
- **ARGO Program**: https://argo.ucsd.edu/

## How to Test Locally

```bash
cd projects/ARGO

# Create virtual environment
uv sync

# Inspect the sample data
python geopan.py info -parquet argo_profiles_features_nmdis.parquet

# Generate RDF using JSON-LD template
python geopan.py tordf -parquet argo_profiles_features_nmdis.parquet -mapping ./template/argo1.json

# Output files created in data/output/
```

---

Looking forward to your input on priorities and next steps!
