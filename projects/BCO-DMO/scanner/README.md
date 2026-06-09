# BCO-DMO Scanner

Tools for discovering and inventorying BCO-DMO data and metadata access routes,
oriented toward the DOOS harvest → transform-to-RDF → SHACL-validate pipeline.

See [`bco-dmo-access-review.md`](bco-dmo-access-review.md) for the full review of
BCO-DMO's programmatic access options.

## Contents

| File | Purpose |
|---|---|
| `scan_erddap.py` | Seed/search ERDDAP's catalog and probe each dataset's access routes |
| `scan_iso_measurements.py` | Read a `scan_erddap.py` result, scan ISO 19115 for depth/pressure variables, emit ODIS-pattern schema.org JSON-LD |
| `bco-dmo-access-review.md` | Review of BCO-DMO APIs / ERDDAP / metadata routes |
| `scan_datasets.py` | **Deprecated** — Playwright crawl of the JS-rendered site search; superseded by `scan_erddap.py --search` |

## Key findings

BCO-DMO exposes **three** routes for machine access. ERDDAP is the most useful
seed for harvesting.

### 1. ERDDAP — primary programmatic interface ⭐

- **Server:** `https://erddap.bco-dmo.org/erddap`
- **Catalog size:** **2,505 active datasets** (live count, see run below).
- Dataset IDs follow `bcodmo_dataset_<NUMBER>` (sometimes with a `_vN` suffix).
- Pure RESTful service — swap the file extension to change format.

A single request enumerates the whole catalog with bounding box, time range, and
ERDDAP-provided info/ISO URLs:

```
https://erddap.bco-dmo.org/erddap/tabledap/allDatasets.json?datasetID,title,institution,summary,dataStructure,minLongitude,maxLongitude,minLatitude,maxLatitude,minTime,maxTime,infoUrl,iso19115
```

> Note: `allDatasets` has **no `license` column** — license lives in each
> dataset's `info/<id>/index.json`.

Per-dataset access routes (all verified reachable in probing):

| Route | URL pattern |
|---|---|
| Metadata JSON | `…/info/<datasetID>/index.json` |
| OPeNDAP attrs/structure | `…/tabledap/<datasetID>.das` / `.dds` |
| Data download | `…/tabledap/<datasetID>.<ext>` (tabular) or `…/griddap/…` (gridded) |
| Raw file browser | `…/files/<datasetID>/` |
| Full-text search | `…/search/index.json?searchFor=<term>` |

Output formats: `.json`, `.jsonlCSV`, `.csv`, `.tsv`, `.nc`, `.mat`, `.nccsv`, `.xhtml`.

### 2. Dataset landing pages + structured metadata

Per-dataset pages at `https://www.bco-dmo.org/dataset/<id>` provide:

- **ISO 19115-2 (NOAA profile)** XML at `…/dataset/<id>/iso`
- **DataCite DOIs** (`10.26008/1912/bco-dmo.<id>.<v>`) → content negotiation for
  DataCite JSON/RDF
- Increasingly, **schema.org JSON-LD** markup for Google Dataset Search

### 3. "BCO-DMO API"

Referenced at `/how-to/access-and-reuse/bco-dmo-api` but JS-rendered; endpoint
spec unverified. Historically a GraphQL/LOD service — confirm in a browser.

## Usage

### `scan_erddap.py` — ERDDAP access inventory

Seeds from `allDatasets`, derives every access route per dataset, and (with
`--probe`) verifies reachability via a ranged GET (first byte only, so large data
files are not downloaded).

```bash
# Fast: enumerate catalog only (candidate routes, no network probing)
python scan_erddap.py --output erddap_inventory.json

# Enumerate + verify access routes for the first 25 datasets
python scan_erddap.py --probe --limit 25 --output erddap_inventory.json

# Probe everything (slow — several requests per dataset)
python scan_erddap.py --probe --output erddap_inventory.json

# Full-text search instead of enumerating the whole catalog
python scan_erddap.py --search "dissolved oxygen depth" --probe --output oxygen.json
```

Options: `--output` (default `erddap_inventory.json`), `--search KEYWORD`,
`--probe`, `--limit N`.

#### `--search` — ERDDAP full-text search

Hits ERDDAP's `search/index.json?searchFor=<keyword>` endpoint, which searches
across all dataset metadata (title, summary, institution, variable names,
attributes) rather than enumerating the full catalog. Results are normalized to
the same record shape as the catalog path, so `--probe` / `--limit` / `--output`
all apply unchanged.

Query syntax is Google-like:

- Multiple words → implicit **AND** (`--search "oxygen depth"`)
- `"quoted phrase"` → exact phrase match
- `-word` → exclude

The search table omits spatial/temporal extents (those keys are emitted as
`null`); `dataStructure` is inferred from whether the hit exposes a tabledap or
griddap endpoint. A search with no matches writes an empty inventory rather than
failing. This mode makes the Playwright-based `scan_datasets.py` largely
redundant for keyword discovery — no browser, and you get full metadata plus
access URLs in one JSON response.

Output JSON shape:

```json
{
  "source": "erddap.bco-dmo.org",
  "erddap_base": "https://erddap.bco-dmo.org/erddap",
  "search": null,
  "probed": true,
  "count": 2505,
  "datasets": [
    {
      "datasetID": "bcodmo_dataset_700773",
      "title": "[13C incubation cell counts] - ...",
      "institution": "BCO-DMO",
      "dataStructure": "table",
      "minLongitude": null, "maxLongitude": null,
      "infoUrl": "...", "iso19115": "...",
      "access": {
        "erddap_info":        {"url": "…/info/bcodmo_dataset_700773/index.json", "ok": true, "status": 200, "error": null},
        "erddap_metadata_das":{"url": "…/tabledap/bcodmo_dataset_700773.das",     "ok": true, "status": 206, "error": null},
        "erddap_data_csv":    {"url": "…/tabledap/bcodmo_dataset_700773.csv",     "ok": true, "status": 200, "error": null},
        "erddap_files":       {"url": "…/files/bcodmo_dataset_700773/",           "ok": true, "status": 200, "error": null},
        "landing_page":       {"url": "https://www.bco-dmo.org/dataset/700773",    "ok": true, "status": 200, "error": null},
        "iso_19115":          {"url": "https://www.bco-dmo.org/dataset/700773/iso","ok": true, "status": 200, "error": null}
      }
    }
  ]
}
```

### `scan_iso_measurements.py` — depth/pressure measurements → JSON-LD

Reads a `scan_erddap.py` result file, fetches each dataset's ISO 19115-2 record
from `www.bco-dmo.org`, finds variables related to depth or pressure, and
expresses them as a schema.org `Dataset` with `variableMeasured` PropertyValue
entries following the [ODIS depth pattern](https://book.odis.org/thematics/depth/index.html).

```bash
# Scan every dataset in the input and print findings + JSON-LD
python scan_iso_measurements.py --input scan_results.json

# Limit to the first 5 datasets while testing
python scan_iso_measurements.py --input scan_results.json --limit 5

# Plain-text findings only, no JSON-LD
python scan_iso_measurements.py --input scan_results.json --no-jsonld

# Write one <datasetID>.jsonld file per match into a directory
python scan_iso_measurements.py --input scan_results.json --save-dir jsonld_out
```

Options: `--input` (default `scan_results.json`), `--limit N`,
`--jsonld` / `--no-jsonld` (default on), `--save-dir DIR`.

With `--save-dir`, each matched record's JSON-LD is written to
`<DIR>/<datasetID>.jsonld` (the directory is created if needed). This is
independent of `--jsonld`, which only controls console printing — so you can
save files without echoing them by combining `--save-dir DIR --no-jsonld`.

**How variables are found.** BCO-DMO ISO records describe variables in two
index-aligned keyword blocks: `type="theme"` (the dataset's own column names →
`dataset-parameter` LOD URIs) and `type="featureType"` ("BCO-DMO Standard
Parameters" → canonical `parameter` LOD URIs). Each column is paired with its
standardized parameter; a variable matches if either name contains `depth`,
`press`, `bathy`, or `dbar`.

**Numeric enrichment.** ISO records carry **no numeric measurement values** (only
the lat/lon bounding box and file size). So each matched variable is enriched
from the dataset's ERDDAP `info` JSON:

- `actual_range` → `minValue` / `maxValue`
- `units` → `unitText` (+ `unitCode` URIs for unambiguous units: m, dbar)
- `long_name` → `description`

ERDDAP sometimes renames a source column (e.g. `MaxDepth` → the `depth` axis), so
matching falls back from the exact name to a normalized match on the variable
name and then its `long_name`. Datasets whose ERDDAP data is access-restricted
return HTTP 401/403 on the `info` endpoint; these are reported as a `[note]` and
fall back to ISO-only output (semantic identity without numeric ranges).

Example `variableMeasured` entry:

```json
{
  "@type": "PropertyValue",
  "name": "MaxDepth",
  "alternateName": "depth_max",
  "propertyID": "http://lod.bco-dmo.org/id/parameter/1690",
  "description": "Max Depth",
  "minValue": 0.0,
  "maxValue": 1220.0,
  "unitText": "m",
  "unitCode": [
    "https://qudt.org/vocab/unit/M",
    "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/"
  ]
}
```

### `scan_datasets.py` — DEPRECATED

Playwright crawl of the JS-rendered site search. It is **superseded by
`scan_erddap.py --search`**, which hits BCO-DMO's documented server-side search,
needs no browser, and returns full metadata plus access URLs in one JSON
response. Kept only for reference; prefer the ERDDAP search for keyword
discovery.

## Recommendation for the DOOS pipeline

Anchor on ERDDAP:

1. Seed/search via `scan_erddap.py` → full inventory + per-dataset access routes.
2. Per dataset, combine the two complementary sources (as `scan_iso_measurements.py`
   does): the **ISO 19115** record for semantic identity (LOD `propertyID`,
   standardized parameter names) and the **ERDDAP `info` JSON** for numeric ranges
   and units. Map to Schema.org / GeoSPARQL.
3. Use DOI content negotiation for `sameAs` / citation triples.
4. Watch for schema.org JSON-LD on landing pages — the lowest-friction path and
   consistent with the rest of the DOOS provider ingest.

## Dependencies

- `scan_erddap.py`: `requests`, `tqdm`
- `scan_iso_measurements.py`: `requests` (ISO parsing uses the stdlib `xml.etree`)
- `scan_datasets.py` (deprecated): `playwright` (run `playwright install chromium` once)
