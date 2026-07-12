# BODC — Implementation Plan

British Oceanographic Data Centre subproject within DOOS. BODC already publishes
schema.org JSON-LD via the Linked Systems UK API; this plan covers harvesting that
metadata, classifying depth-profile presence, validating against OIH SHACL shapes,
and exporting to the federated SPARQL graph.

**Status:** Indexing  
**Provider:** [BODC](https://www.bodc.ac.uk/)  
**JSON-LD API:** `https://api.linked-systems.uk/api/schema-org/dataset/{series_id}`

---

## Goal

Deliver a full DOOS pipeline slice for BODC:

```
Ingest → Analyze → Validate → Export → Federated SPARQL
```

No transform layer is required — BODC metadata is already schema.org JSON-LD. Work
focuses on discovery, depth classification, SHACL validation, and N-Quads export.

Primary DOOS alignment: expose depth-below-surface measurements as queryable
`DepBelowSurf` in `variableMeasured`, while also tracking all depth-related P01
terms for coverage reporting.

---

## Artifacts

| File | Description |
|------|-------------|
| `bodc_release.nq` | Gleaner/OIH harvest dump — N-Quads with named graphs `urn:gleaner.io:oih:bodc:data:*` |
| `docs/exampleData/edmoExample.json` | Reference JSON-LD shape (series 1927880) |
| `SPARQL/varMes_bodc.rq` | Federated query template for BODC depth `variableMeasured` stats |
| `SHACL/depth_one.ttl` | OIH depth-profile shape — requires `DepBelowSurf` in `variableMeasured` |

### Release snapshot baseline (`bodc_release.nq`)

Harvested via Gleaner/OIH on **2026-01-18**.

| Metric | Value |
|--------|-------|
| N-Quads lines | ~415k |
| Unique dataset IDs | 743 |
| Named graphs | 4,345 (multiple harvest versions per series) |
| Graphs with `DepBelowSurf` | ~1,910 (~44%) |
| Graphs without `DepBelowSurf` | ~2,435 |

Depth-related `variableMeasured` names observed in the release (non-exhaustive):

| Name | Count | P01 `propertyID` |
|------|-------|------------------|
| `DepBelowSurf` | 3,820 | `ADEPZZ01` |
| `BinDep` | 109 | `DBINAA01` |
| `Start_depth` | 97 | `DEPHPRST` |
| `BathyDepES_ISL` | 10 | — |
| `SwathCBBathyDep` | 6 | — |
| `DEPHFP01` | 36 | `DEPHFP01` |

Instrument-description strings containing "at depth" also appear (e.g. moored CTD
series) and should be classified separately from P01-coded depth variables.

---

## Depth detection rules

### Tier 1 — OIH depth profile (SHACL `depth_one.ttl`)

A dataset passes the OIH depth-profile shape when `variableMeasured` contains a
`schema:PropertyValue` with:

```json
{
  "@type": "PropertyValue",
  "name": "DepBelowSurf",
  "propertyID": "https://vocab.nerc.ac.uk/collection/P01/current/ADEPZZ01/",
  "minValue": <number>,
  "maxValue": <number>
}
```

### Tier 2 — Other depth-related P01 terms (broad coverage)

Also track any `variableMeasured` entry whose `name` or `propertyID` indicates
depth. Known alternates from the release and investigation notes:

- `DepBelowSurf` / `ADEPZZ01`
- `BinDep` / `DBINAA01`
- `Start_depth` / `DEPHPRST`
- `DEPHFP01`
- Any P01 URI under `vocab.nerc.ac.uk/collection/P01/current/` matching depth
  parameter codes (prefixes `ADEP`, `DEPH`, `DBIN`, bathymetry codes)

Report Tier 1 and Tier 2 separately. A dataset may satisfy Tier 2 without
passing `depth_one.ttl`.

---

## Dataset discovery

### Primary: BODC sitemap

BODC publishes an 11-part sitemap index at `https://www.bodc.ac.uk/sitemap.xml`
(referenced in `robots.txt`). Series landing pages follow:

```
https://www.bodc.ac.uk/data/documents/series/{series_id}/
```

Map each series ID to the JSON-LD API:

```
https://api.linked-systems.uk/api/schema-org/dataset/{series_id}
```

Fetch with `Accept: application/ld+json`, `User-Agent: DOOS-BODC-Depth-Analyzer/1.0`,
`timeout=30`.

### Fallback: `bodc_release.nq`

If sitemap parsing is unavailable, incomplete, or blocked, extract unique dataset
IDs from the Gleaner/OIH release:

```
https://api.linked-systems.uk/api/schema-org/dataset/{id}
```

The release currently contains 743 known IDs.

### Future

Per `docs/sources.md`, consider asking BODC for a dataset-only sitemap to simplify
discovery and reduce noise from non-series pages in the general sitemap.

---

## Phases

### Phase 1 — Inventory (local release)

1. Parse `bodc_release.nq` for unique dataset IDs and named graphs.
2. Classify each graph: Tier 1 (`DepBelowSurf`), Tier 2 (other depth P01), none.
3. Produce `output/depth_inventory.json` and `output/depth_inventory.csv` with
   per-dataset fields: `series_id`, `graph_uri`, `tier`, `depth_names`,
   `property_ids`, `min_value`, `max_value`, `has_dep_below_surf`.
4. Summarize coverage percentages against the 743-dataset baseline.

### Phase 2 — Live harvest (sitemap-driven)

1. Crawl BODC sitemaps; extract series IDs from `/data/documents/series/` URLs.
2. Fetch JSON-LD from `api.linked-systems.uk` for each ID (rate-limited).
3. Run the same depth classification as Phase 1.
4. Diff live corpus against `bodc_release.nq` — new series, missing series,
   changed `minValue`/`maxValue`.
5. Serialize harvested JSON-LD to N-Quads (`output/bodc_harvest.nq`).

### Phase 3 — SHACL validation

1. Validate harvested or release graphs against `SHACL/depth_one.ttl` using
   `scripts/shapeValidator/validateToOxigraph.py` (baseline) or
   `validateToParquet.py` (large runs).
2. Record pass/fail per dataset; write `output/shacl_results.json`.
3. Report Tier 1 pass rate separately from Tier 2 breadth.

### Phase 4 — Export and federated query

1. Export validated N-Quads for loading to the federated endpoint.
2. Confirm `SPARQL/varMes_bodc.rq` returns `DepBelowSurf` min/max for BODC graphs.
3. Verify records appear in the Geocodes search UI
   (`deepoceans.geocodes-aws.earthcube.org`).

---

## Deliverables

| Deliverable | Path | Description |
|-------------|------|-------------|
| Depth inventory CLI | `scripts/BodcDepthInventory.py` | Parse release or fetch live JSON-LD; classify depth tiers |
| Harvest CLI | `scripts/BodcHarvest.py` | Sitemap-driven fetch → N-Quads |
| Coverage report | `output/depth_inventory.json` | Per-dataset depth classification + summary stats |
| SHACL report | `output/shacl_results.json` | Pass/fail against `depth_one.ttl` |
| N-Quads export | `output/bodc_harvest.nq` | Federated-graph-ready serialization |

Reference implementation: `skills/bco-dmo-scan/assets/defs/iso_measurements.py`
(ISO 19115 + ERDDAP info → ODIS depth JSON-LD). BODC differs in that depth ranges
are already present in metadata `variableMeasured` — distribution download is
optional, not required.

---

## Success criteria

All of the following:

1. **Coverage report** — % of datasets with Tier 1 (`DepBelowSurf`) and Tier 2
   (any depth P01 term), with min/max depth range stats.
2. **SHACL validation** — pass/fail report against `SHACL/depth_one.ttl` per dataset.
3. **Working CLI** — scripts runnable via `python scripts/BodcDepthInventory.py --help`
   and `python scripts/BodcHarvest.py --help`.
4. **Federated query** — `SPARQL/varMes_bodc.rq` returns BODC depth results from
   the live endpoint.

---

## Example dataset

Series 1928999 (from original investigation notes):

- Landing page: `https://www.bodc.ac.uk/data/documents/series/1928999/`
- JSON-LD: `https://api.linked-systems.uk/api/schema-org/dataset/1928999`
- Depth: `DepBelowSurf`, `minValue: 8.8`, `maxValue: 4819.4`
- Distributions: ODV (`text/x-odv`), NetCDF (`application/netcdf`)

---

## Open items

- [x] Record harvest date for `bodc_release.nq` — Gleaner/OIH export **2026-01-18**
- [ ] Confirm rate limits / crawl policy for BODC sitemap + API (robots.txt
      specifies `Crawl-delay: 5`)
- [ ] Decide whether to request a dataset-only sitemap from BODC
- [ ] Evaluate whether Tier 2-only datasets (no `DepBelowSurf`) need upstream
      feedback to BODC or are acceptable as partial depth coverage