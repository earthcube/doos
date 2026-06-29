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

**Outputs per record:**

| File | Description |
|---|---|
| `{uuid}_source.xml` | Fetched ISO 19115-3 XML (fetch mode only) |
| `{id}_iso19139.xml` | Intermediate ISO 19139 |
| `{id}.jsonld` | schema.org JSON-LD |
| `{id}.nt` | N-Triples (unless `--no-nt`) |
| `run.json` | Run manifest with paths and summary stats |

### convert_script.py

Step 1 only: transforms XML using XSLT 2.0/3.0 via Saxon.

**Arguments:**

- `-input` / `--input-file`: Source XML file (required)
- `-xslt` / `--xslt-file`: XSLT stylesheet (required)
- `-output` / `--output-file`: Output file path (required)

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