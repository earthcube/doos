# BCO-DMO Programmatic Access Review

A review of [bco-dmo.org](https://www.bco-dmo.org) for APIs, ERDDAP interfaces, and
other machine-accessible routes to data and metadata — oriented toward the DOOS
harvest → transform-to-RDF → SHACL-validate pipeline.

_Reviewed: 2026-06-03_

## Summary

BCO-DMO offers **three** routes for machine access. For DOOS harvesting/RDF work,
ERDDAP and the per-dataset metadata views are the most useful.

---

## 1. ERDDAP (primary programmatic interface) ⭐

**Server base URL:** `https://erddap.bco-dmo.org/erddap`

- ~470+ active datasets.
- Dataset IDs follow `bcodmo_dataset_<NUMBER>` (sometimes with a `_vN` version suffix).
- Pure RESTful service: every human web form has a machine equivalent — just swap the
  file extension.

### Key URL patterns

| Goal | URL pattern |
|---|---|
| **List all datasets** | `…/tabledap/allDatasets.json?datasetID,title,institution,summary,license,minLongitude,maxLongitude,minLatitude,maxLatitude` |
| **Dataset metadata** | `…/info/<datasetID>/index.json` (also `.csv`, `.nccsv`, `.xhtml`) |
| **OPeNDAP structure / attrs** | `…/tabledap/<datasetID>.das` and `.dds` |
| **Full-text search** | `…/search/index.json?searchFor=<term>` |
| **Advanced search** | `…/search/advanced.json?searchFor=<term>` |
| **Download data (tabular)** | `…/tabledap/<datasetID>.<ext>?<vars>&<constraints>` |
| **Download data (gridded)** | `…/griddap/<datasetID>.<ext>?<vars>&<constraints>` |
| **Browse raw files** | `…/files/<datasetID>/` |
| **Change notifications** | RSS + email/URL subscriptions per dataset |

### Output formats

`.json`, `.jsonlCSV`, `.jsonlCSV1`, `.jsonlKVP`, `.csv`, `.tsv`, `.nc` (NetCDF),
`.mat` (MATLAB), `.nccsv`, `.itx`, `.htmlTable`, `.xhtml`.

> `allDatasets` is the natural harvest seed — one call enumerates every dataset with
> bounding box, license, and the data-access-form URL.

---

## 2. Dataset landing pages + structured metadata

Per-dataset pages at `https://www.bco-dmo.org/dataset/<id>` expose:

- **ISO 19115-2 (NOAA profile)** XML: `https://www.bco-dmo.org/dataset/<id>/iso` —
  clean machine-readable metadata.
- **DataCite DOIs** — BCO-DMO became a DataCite minting agent in Dec 2025; DOI form
  `10.26008/1912/bco-dmo.<id>.<v>`. DOI content negotiation yields DataCite JSON/RDF.
- HTML and PDF descriptions, plus a JSON data-viewer endpoint.
- As of late 2025, landing pages are being enriched with **schema.org markup** for
  Google Dataset Search — so JSON-LD harvesting (the standard DOOS pattern) should
  increasingly work directly off these pages.

---

## 3. "BCO-DMO API"

Referenced in their navigation (`/how-to/access-and-reuse/bco-dmo-api`), but the doc
pages are JS-rendered and the endpoint spec could not be extracted via simple fetch.
Historically this has been a GraphQL/LOD service.

> **Action needed:** open that page in a browser to confirm the current base URL and
> schema — its live status is unverified.

---

## Recommendation for the DOOS scanner

For the harvest → transform-to-RDF → SHACL-validate pipeline, anchor on **ERDDAP**:

1. Seed from `allDatasets.json` → full dataset inventory + spatial extents + license in
   one request.
2. Per dataset, pull `…/info/<id>/index.json` (or the ISO XML from the landing page) for
   rich metadata to map to Schema.org/GeoSPARQL.
3. Use DOI content negotiation as a cross-check and for `sameAs` / citation triples.
4. Watch for schema.org JSON-LD appearing directly on landing pages — the lowest-friction
   path and consistent with the rest of the DOOS provider ingest.

---

## Sources

- [ERDDAP home](https://erddap.bco-dmo.org/erddap/index.html)
- [RESTful Web Services](https://erddap.bco-dmo.org/erddap/rest.html)
- [tabledap documentation](https://erddap.bco-dmo.org/erddap/tabledap/documentation.html)
- [allDatasets form](https://erddap.bco-dmo.org/erddap/tabledap/allDatasets.html)
- [Accessing Data at BCO-DMO](https://www.bco-dmo.org/data)
- [BCO-DMO API page](https://www.bco-dmo.org/how-to/access-and-reuse/bco-dmo-api)
- [DOI rationale blog (DataCite minting)](https://blog.bco-dmo.org/2026/05/04/dataset-doi-rationale)
- [BCODMO GitHub](https://github.com/BCODMO)
