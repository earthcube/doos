# BODC

British Oceanographic Data Centre subproject within [DOOS](https://github.com/earthcubeprojects/doos).
BODC already publishes schema.org JSON-LD via the Linked Systems UK API — no transform
layer is required. This subproject inventories depth-profile presence, validates against
OIH SHACL shapes, and prepares N-Quads for federated SPARQL.

**Provider:** [BODC](https://www.bodc.ac.uk/)  
**JSON-LD API:** `https://api.linked-systems.uk/api/schema-org/dataset/{series_id}`  
**Status:** Indexing

See [PLAN.md](PLAN.md) for the full implementation plan and design decisions.

---

## What this does

BODC series metadata includes depth ranges as schema.org `PropertyValue` entries on
`variableMeasured`, typically:

```json
{
  "@type": "PropertyValue",
  "name": "DepBelowSurf",
  "propertyID": "https://vocab.nerc.ac.uk/collection/P01/current/ADEPZZ01/",
  "minValue": 8.8,
  "maxValue": 4819.4
}
```

The pipeline:

```
Ingest → Analyze → Validate → Export → Federated SPARQL
```

| Phase | Script | What it does |
|-------|--------|--------------|
| 1 | `BodcDepthInventory.py` | Classify depth tiers from local Gleaner/OIH release |
| 2 | `BodcHarvest.py` | Discover series via sitemap, fetch live JSON-LD, diff vs release |
| 3 | `BodcShaclValidate.py` | Validate graphs against `SHACL/depth_one.ttl` |
| 4 | `BodcExport.py` + `BodcVerifyFederation.py` | Export SHACL-passing graphs; verify SPARQL queries |

Depth is reported at two levels:

- **Tier 1 (OIH depth profile):** `DepBelowSurf` / P01 `ADEPZZ01` — required by `depth_one.ttl`
- **Tier 2 (broad):** other depth-related P01 terms (`BinDep`, `Start_depth`, etc.)

Unlike OBIS, BODC does not need a separate depth-only auxiliary graph — min/max values
are already embedded in the dataset metadata graphs.

---

## Prerequisites

From the DOOS repo root:

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt
```

Dependencies used by this subproject: `rdflib`, `pyshacl`, `pyld`, `pyoxigraph`,
`SPARQLWrapper`, `tqdm`.

---

## Quickstart

```bash
cd projects/BODC/scripts

# Phase 1: classify depth from the Gleaner/OIH release
python3 BodcDepthInventory.py

# Phase 3: SHACL validation (uses Phase 1 inventory for tier cross-reference)
python3 BodcShaclValidate.py

# Phase 4: export validated graphs and verify SPARQL locally
python3 BodcExport.py
python3 BodcVerifyFederation.py --skip-remote
```

Expected Phase 1 results (2026-01-18 Gleaner/OIH harvest, 743 series):

- **442 series (59.5%)** — Tier 1 (`DepBelowSurf`)
- **86 series (11.6%)** — Tier 2 only (other depth P01 terms)
- **70 series** — instrument-description depth signals only
- **145 series** — no depth detected

---

## Running the pipeline

All scripts live in `scripts/` and write outputs to `output/` by default.

### Phase 1 — Depth inventory (local release)

Parse `bodc_release.nq` and classify each named graph by depth tier.

```bash
python3 BodcDepthInventory.py
python3 BodcDepthInventory.py --input ../bodc_release.nq --output-dir ../output
```

### Phase 2 — Live harvest (sitemap-driven)

Discover series IDs from [BODC sitemaps](https://www.bodc.ac.uk/sitemap.xml), fetch
JSON-LD from the API (5 s delay per `robots.txt`), classify depth, and diff against
the release inventory.

```bash
# Test with a small subset
python3 BodcHarvest.py --limit 50

# Harvest the 743 known release series (useful for release diff)
python3 BodcHarvest.py --use-release-ids

# Full sitemap harvest (~130k series — takes days at default delay)
python3 BodcHarvest.py
```

Cached JSON-LD is stored in `output/jsonld_cache/`. Re-runs skip cached files unless
`--no-resume` is passed.

### Phase 3 — SHACL validation

Validate each named graph against [`SHACL/depth_one.ttl`](../../SHACL/depth_one.ttl).

```bash
python3 BodcShaclValidate.py
python3 BodcShaclValidate.py --input ../output/bodc_harvest.nq   # validate live harvest
python3 BodcShaclValidate.py --limit 50                         # test subset
```

Tier 1 series pass SHACL at 100% (at least one graph per series conforms). Graph-level
pass rate is lower (~32%) because multiple harvest versions exist per series.

### Phase 4 — Export and federation verify

Export one SHACL-passing graph per series, then verify depth queries.

```bash
python3 BodcExport.py
python3 BodcVerifyFederation.py                  # local + federated endpoint
python3 BodcVerifyFederation.py --skip-remote      # local only
```

To load into a federated endpoint after export:

```bash
python ../../scripts/SPARQLupdate/insertUpdates.py \
  --token <TOKEN> \
  --endpoint <UPDATE_ENDPOINT> \
  --file ../output/bodc_validated.nq \
  --format nquads
```

Then re-run `BodcVerifyFederation.py` and search for `bodc` in the
[Geocodes UI](https://qlever-test.geocodes-aws-dev.earthcube.org/).

Query depth values with [`SPARQL/varMes_bodc.rq`](../../SPARQL/varMes_bodc.rq) against
the [deepoceans QLever endpoint](https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans).

---

## Inputs

| File | Description |
|------|-------------|
| `bodc_release.nq` | Gleaner/OIH harvest dump (2026-01-18). Named graphs: `urn:gleaner.io:oih:bodc:data:*` |
| `docs/exampleData/edmoExample.json` | Reference JSON-LD shape (repo root) |
| `SHACL/depth_one.ttl` | OIH depth-profile shape — requires `DepBelowSurf` in `variableMeasured` |
| `SPARQL/varMes_bodc.rq` | Federated query for `DepBelowSurf` min/max values |

---

## Outputs

All generated files go to `output/` unless overridden with `--output-dir`.

### Inventory and classification

| File | Description |
|------|-------------|
| `depth_inventory.json` | Per-graph depth classification + summary stats (Phase 1) |
| `depth_inventory.csv` | Same data in flat tabular form |
| `live_depth_inventory.json` | Live harvest classification (Phase 2) |
| `live_depth_inventory.csv` | Same, tabular |
| `harvest_diff.json` | New/missing/changed series vs release (Phase 2) |

Key fields per record: `series_id`, `tier`, `min_value`, `max_value`,
`has_dep_below_surf`, `depth_names`, `property_ids`.

The inventory files are the easiest way to get min/max depth ranges per series as
plain JSON or CSV. Example:

| series_id | tier | min_value | max_value |
|-----------|------|-----------|-----------|
| 1928999 | tier1 | 8.8 | 4819.4 |
| 2148897 | tier1 | 5.8 | 151.2 |

### SHACL validation

| File | Description |
|------|-------------|
| `shacl_results.json` | Per-graph pass/fail against `depth_one.ttl` + tier cross-reference |

### RDF graphs (N-Quads)

| File | Description |
|------|-------------|
| `bodc_release.nq` | Input — full Gleaner/OIH harvest (743 series, ~4.3k named graphs) |
| `bodc_harvest.nq` | Live-harvested JSON-LD as N-Quads (`urn:doos:bodc:harvest:{id}`) |
| `bodc_validated.nq` | **Export-ready** — 442 SHACL-passing series, 53,911 quads |

`bodc_validated.nq` contains full schema.org Dataset graphs with `DepBelowSurf`
`minValue`/`maxValue` embedded in `variableMeasured` — this is the file to load into
a federated SPARQL endpoint.

| File | Description |
|------|-------------|
| `export_manifest.json` | Maps each exported `series_id` to its `graph_uri` |
| `federation_verify.json` | Local and remote SPARQL verification report |

### Cache

| Directory | Description |
|-----------|-------------|
| `jsonld_cache/` | Cached API responses from `BodcHarvest.py` (`{series_id}.jsonld`) |

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/BodcDepthInventory.py` | Phase 1 — parse release, classify depth tiers |
| `scripts/BodcHarvest.py` | Phase 2 — sitemap discovery, live fetch, diff |
| `scripts/BodcShaclValidate.py` | Phase 3 — SHACL validation per named graph |
| `scripts/BodcExport.py` | Phase 4 — export SHACL-passing graphs |
| `scripts/BodcVerifyFederation.py` | Phase 4 — verify SPARQL queries local + remote |
| `scripts/bodc_depth.py` | Shared depth classification library (not run directly) |

---

## Example dataset

Series **1928999**:

- Landing page: https://www.bodc.ac.uk/data/documents/series/1928999/
- JSON-LD: https://api.linked-systems.uk/api/schema-org/dataset/1928999
- Depth: `DepBelowSurf`, min **8.8**, max **4819.4**

---

## Federation status

As of the last verification run:

- **Local** (`bodc_validated.nq`): `varMes_bodc.rq` returns `DepBelowSurf` min/max values
- **Federated endpoint**: BODC graphs not yet loaded — run `insertUpdates.py` then re-verify
- **Search UI**: https://qlever-test.geocodes-aws-dev.earthcube.org/ (reachable)