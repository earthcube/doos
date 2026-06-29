# AODN

This toolkit transforms Australian Ocean Data Network (AODN) metadata records into web-friendly, machine-readable formats. It provides a two-step XSLT pipeline that first converts ISO 19115-3 metadata to ISO 19139 XML, then transforms that output into JSON-LD using schema.org vocabulary. A top-level orchestrator can fetch records live from the IMOS GeoNetwork catalogue, export N-Triples, and produce a run manifest.

The resulting JSON-LD is suitable for discovery by search engines, data aggregators, and DOOS federation (including OIH depth-profile fields such as `DepBelowSurf` in `variableMeasured`).

## About

Pipeline stages:

1. **Fetch** (optional): Download ISO 19115-3 XML from GeoNetwork (`catalogue-imos.aodn.org.au`)
2. **ISO 19115-3 → ISO 19139**: Convert to standard ISO 19139 XML (preserves `metadataLinkage` as `gmd:dataSetURI`)
3. **ISO 19139 → JSON-LD**: Transform to schema.org vocabulary (`https://schema.org/`)
4. **JSON-LD → N-Triples** (optional): Normalize and serialize RDF for graph endpoints

AODN-specific mapping highlights:

- `mdb:metadataLinkage` → dataset `@id`, `url`, and `identifier`
- `gmd:contentInfo/gmd:MD_SampleDimension` → `variableMeasured` (`depth` → `DepBelowSurf`)
- `principalInvestigator` → `creator`; `resourceProvider` → `publisher`
- `includedInDataCatalog` → Australian Ocean Data Network (AODN)

See [DEMO-AODN.md](DEMO-AODN.md) for a full end-to-end walkthrough using a live catalogue fetch.

## JSON-LD output

Each record is a schema.org `Dataset` with `@context.@vocab` set to `https://schema.org/`. Measured variables (from `gmd:MD_SampleDimension`) are `PropertyValue` objects in the `variableMeasured` array — not top-level Dataset properties. The CF standard name `depth` is mapped to `DepBelowSurf` for OIH depth-profile compatibility.

```json
{
  "@context": { "@vocab": "https://schema.org/" },
  "@id": "https://catalogue-imos.aodn.org.au:443/geonetwork/srv/api/records/<uuid>",
  "@type": "Dataset",
  "name": "...",
  "url": "https://catalogue-imos.aodn.org.au:443/geonetwork/srv/api/records/<uuid>",
  "variableMeasured": [
    {
      "@type": "PropertyValue",
      "name": "DepBelowSurf",
      "alternateName": "depth"
    }
  ]
}
```

## Dependencies

From the monorepo root (Python ≥ 3.13):

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv sync   # saxonche, lxml, pyld, pyoxigraph
```

| Package | Used by |
|---|---|
| **saxonche** | `convert_script.py` — XSLT 3.0 (ISO 19115-3 → 19139) |
| **lxml** | `aodnTransform.py` — XSLT 1.0 (ISO 19139 → JSON-LD) |
| **pyld** | `run_pipeline.py` — JSON-LD normalization |
| **pyoxigraph** | `run_pipeline.py` — N-Triples export |
| **openpyxl**, **xlrd** | `depth_from_distribution.py` — Excel `.xlsx` / `.xls` support |
| **polars** (optional) | `depth_from_distribution.py` — faster csv/tsv/parquet loading (`--engine polars`) |

For depth probing on Excel distributions:

```bash
uv pip install openpyxl xlrd
```

Optional polars engine for csv/tsv/parquet:

```bash
uv pip install polars
```

## Scripts

### run_pipeline.py (recommended)

End-to-end orchestrator: fetch → ISO 19139 → JSON-LD → N-Triples.

```bash
# Live fetch from catalogue-imos.aodn.org.au
python run_pipeline.py --uuid 528f280c-b151-45c4-9526-e0746510a617

# Local ISO 19115-3 XML (skip fetch)
python run_pipeline.py --input-xml ./AODN_GN4_depth_metadata.xml --output-dir ./output

# Batch: one UUID per line in a text file
python run_pipeline.py --uuid-file uuids.txt --output-dir ./runs/batch

# JSON-LD only (skip N-Triples)
python run_pipeline.py --uuid <uuid> --no-nt

# Probe depth from tabular distributions and enrich DepBelowSurf min/max
python run_pipeline.py --uuid <uuid> --probe-depth --enrich-jsonld --output-dir ./demo-output
```

**Arguments:**

| Flag | Description |
|---|---|
| `--uuid` | GeoNetwork record UUID |
| `--uuid-file` | Text file with one UUID per line (`#` comments allowed) |
| `--input-xml` | Local source XML; skips fetch |
| `--catalog-api` | GeoNetwork API base (default: `https://catalogue-imos.aodn.org.au/geonetwork/srv/api`) |
| `--output-dir` | Output directory (default: `./runs/<timestamp>`) |
| `--no-nt` | Skip N-Triples export |
| `--probe-depth` | Download tabular distributions and compute depth min/max |
| `--depth-try-all` | Probe every tabular/prefix distribution (not just the first match) |
| `--depth-verbose` | Log skipped/failed distributions during depth probe |
| `--depth-engine` | `pandas` (default) or `polars` for csv/tsv/parquet |
| `--no-crawl-prefix` | Skip expanding `?prefix=` S3 listing URLs |
| `--enrich-jsonld` | Write observed `minValue`/`maxValue` into `DepBelowSurf` (implies `--probe-depth`) |

**Outputs per record:**

| File | Description |
|---|---|
| `{uuid}_source.xml` | Fetched ISO 19115-3 XML (fetch mode only) |
| `{id}_iso19139.xml` | Intermediate ISO 19139 |
| `{id}.jsonld` | schema.org JSON-LD |
| `{id}.nt` | N-Triples (unless `--no-nt`) |
| `{id}_depth_report.json` | Depth probe report (with `--probe-depth`) |
| `run.json` | Run manifest with paths and summary stats |

### convert_script.py

Step 1 only: transforms XML using XSLT 2.0/3.0 via Saxon.

**Arguments:**

- `-input` / `--input-file`: Source XML file (required)
- `-xslt` / `--xslt-file`: XSLT stylesheet (required)
- `-output` / `--output-file`: Output file path (required)

### depth_from_distribution.py

Download a tabular `distribution` from a JSON-LD metadata file and compute
min/max for depth-related columns (`.csv`, `.tsv`, `.parquet`, `.xls`, `.xlsx`).

```bash
python depth_from_distribution.py \
  --jsonld demo-output/528f280c-b151-45c4-9526-e0746510a617.jsonld \
  --output depth_report.json

# Probe every tabular distribution and cross-check against ISO vertical extent
python depth_from_distribution.py \
  --jsonld demo-output/528f280c-b151-45c4-9526-e0746510a617.jsonld \
  --try-all --verbose
```

**Arguments:**

| Flag | Description |
|---|---|
| `--jsonld` | schema.org Dataset JSON-LD file (required) |
| `--output` | Optional JSON report path (default: stdout) |
| `--distribution-url` | Force a specific distribution URL |
| `--try-all` | Probe all tabular distributions; include `attempts` in report |
| `--iso19139` | ISO 19139 XML for vertical extent check (default: `{stem}_iso19139.xml` sibling) |
| `--verbose` | Log skipped/failed distributions to stderr |
| `--engine` | `pandas` (default) or `polars` for csv/tsv/parquet |
| `--no-crawl-prefix` | Skip expanding `?prefix=` S3 listing distributions |
| `--enrich-jsonld` | Write observed min/max into `DepBelowSurf` in the JSON-LD file |

### aodnTransform.py

Step 2 only: transforms XML using XSLT 1.0 via lxml.

**Arguments:**

- `-xml` / `--xml-file`: Source XML file (required)
- `-xslt` / `--xslt-file`: XSLT stylesheet (required)
- `-output` / `--output-file`: Output JSON-LD file (optional; default stdout)

## Manual two-step workflow

If you prefer to run each stage separately:

### Step 1: Convert ISO 19115-3 to ISO 19139

```bash
python convert_script.py \
  -input ./AODN_GN4_depth_metadata.xml \
  -xslt ./transformations/ISO19139/toISO19139.xsl \
  -output metadata_19139_output.xml
```

### Step 2: Convert ISO 19139 to JSON-LD

```bash
python aodnTransform.py \
  -xml metadata_19139_output.xml \
  -xslt ./ISO19139mapping/ISO19139ToSDODatasetStandalone1.0.xslt \
  -output output.jsonld
```

## Directory structure

| Path | Purpose |
|---|---|
| `transformations/` | XSLT stylesheets for ISO format conversions |
| `ISO19139mapping/` | XSLT stylesheets for ISO 19139 → schema.org JSON-LD |
| `runs/` | Default output location for `run_pipeline.py` (created on demand) |
| `AODN_GN4_depth_metadata.xml` | Sample ISO 19115-3 record for offline testing |
| `DEMO-AODN.md` | End-to-end live-fetch walkthrough |
| `defs/depth_columns.py` | Depth column matching, metadata compare, JSON-LD enrichment |
| `defs/prefix_listing.py` | Resolve tabular files from AODN `?prefix=` S3 listings |
| `depth_from_distribution.py` | Download distribution and probe depth min/max |