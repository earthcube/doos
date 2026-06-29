# AODN live-fetch demo

This walkthrough fetches a real metadata record from the IMOS GeoNetwork catalogue at [catalogue-imos.aodn.org.au](https://catalogue-imos.aodn.org.au), runs the full AODN transform pipeline, and inspects the outputs.

**Record used:** SAIMOS biological and flow-cytometry data (April 2015, South Australia)

- **UUID:** `528f280c-b151-45c4-9526-e0746510a617`
- **Catalogue page:** https://catalogue-imos.aodn.org.au/geonetwork/srv/eng/catalog.search#/metadata/528f280c-b151-45c4-9526-e0746510a617

## Prerequisites

From the DOOS monorepo root:

```bash
cd /path/to/doos
uv venv .venv --python 3.13
source .venv/bin/activate
uv sync
cd projects/AODN
```

## Step 1 — Run the pipeline

Fetch the record XML from GeoNetwork, convert to ISO 19139, emit JSON-LD, and export N-Triples:

```bash
python run_pipeline.py \
  --uuid 528f280c-b151-45c4-9526-e0746510a617 \
  --output-dir ./demo-output
```

The pipeline:

1. **Fetches** ISO 19115-3 XML from  
   `https://catalogue-imos.aodn.org.au/geonetwork/srv/api/records/528f280c-b151-45c4-9526-e0746510a617/formatters/xml`
2. **Converts** ISO 19115-3 → ISO 19139 via Saxon (`transformations/ISO19139/toISO19139.xsl`)
3. **Transforms** ISO 19139 → schema.org JSON-LD via lxml (`ISO19139mapping/ISO19139ToSDODatasetStandalone1.0.xslt`)
4. **Exports** N-Triples via pyld + pyoxigraph
5. **Writes** `demo-output/run.json` manifest

## Step 2 — Inspect the run manifest

```bash
cat demo-output/run.json
```

Expected structure (values will match your run timestamp):

```json
{
  "started_at": "2026-06-29T00:17:33.932418+00:00",
  "output_dir": "/path/to/projects/AODN/demo-output",
  "records": [
    {
      "record_id": "528f280c-b151-45c4-9526-e0746510a617",
      "source_xml": ".../528f280c-b151-45c4-9526-e0746510a617_source.xml",
      "iso19139_xml": ".../528f280c-b151-45c4-9526-e0746510a617_iso19139.xml",
      "jsonld": ".../528f280c-b151-45c4-9526-e0746510a617.jsonld",
      "dataset_id": "https://catalogue-imos.aodn.org.au:443/geonetwork/srv/api/records/528f280c-b151-45c4-9526-e0746510a617",
      "variable_measured_count": 18,
      "has_dep_below_surf": true,
      "nt": ".../528f280c-b151-45c4-9526-e0746510a617.nt",
      "triple_count": 273
    }
  ]
}
```

Key checks:

- `dataset_id` is the GeoNetwork metadata URL (not a bare UUID URN)
- JSON-LD root has `"@type": "Dataset"` (schema.org Dataset)
- `has_dep_below_surf` is `true` — `DepBelowSurf` is inside `variableMeasured`, not a top-level key
- `variable_measured_count` reflects variables from `gmd:MD_SampleDimension`

## Step 3 — Inspect JSON-LD highlights

```bash
python3 -c "
import json
from pathlib import Path

doc = json.loads(Path('demo-output/528f280c-b151-45c4-9526-e0746510a617.jsonld').read_text())

assert doc['@type'] == 'Dataset'
assert 'DepBelowSurf' not in doc
dep = next(v for v in doc['variableMeasured'] if v['name'] == 'DepBelowSurf')

print(json.dumps({
    '@context': doc['@context'],
    '@id': doc['@id'],
    '@type': doc['@type'],
    'name': doc['name'],
    'url': doc['url'],
    'creator': doc.get('creator'),
    'publisher': doc.get('publisher'),
    'includedInDataCatalog': doc.get('includedInDataCatalog'),
    'variableMeasured': [dep],
}, indent=2))
"
```

Example output:

```json
{
  "@context": {
    "@vocab": "https://schema.org/",
    "datacite": "http://purl.org/spar/datacite/",
    "earthcollab": "https://library.ucar.edu/earthcollab/schema#",
    "geolink": "http://schema.geolink.org/1.0/base/main#",
    "vivo": "http://vivoweb.org/ontology/core#",
    "dcat": "http://www.w3.org/ns/dcat#"
  },
  "@id": "https://catalogue-imos.aodn.org.au:443/geonetwork/srv/api/records/528f280c-b151-45c4-9526-e0746510a617",
  "@type": "Dataset",
  "name": "SAIMOS - Biological and Flow Cytometry data collected from CTD stations in South Australia, in April 2015",
  "url": "https://catalogue-imos.aodn.org.au:443/geonetwork/srv/api/records/528f280c-b151-45c4-9526-e0746510a617",
  "creator": [
    {
      "@type": "Role",
      "roleName": "SAIMOS Biological Leader; principalInvestigator",
      "creator": {
        "@type": "Person",
        "name": "van Ruth, Paul",
        "email": ["Paul.vanruth@sa.gov.au"],
        "affiliation": {
          "@type": "Organization",
          "name": "SARDI Aquatic Sciences"
        }
      }
    }
  ],
  "publisher": [
    {
      "@type": "Role",
      "roleName": "resourceProvider",
      "publisher": {
        "@type": "Organization",
        "name": "Integrated Marine Observing System (IMOS)",
        "email": ["imos@imos.org.au"]
      }
    }
  ],
  "includedInDataCatalog": {
    "@type": "DataCatalog",
    "name": "Australian Ocean Data Network (AODN)",
    "url": "https://portal.aodn.org.au/"
  },
  "variableMeasured": [
    {
      "@type": "PropertyValue",
      "additionalType": "earthcollab:Parameter",
      "name": "DepBelowSurf",
      "alternateName": "depth",
      "propertyID": "http://cf-pcmdi.llnl.gov/documents/cf-standard-names",
      "url": "http://cf-pcmdi.llnl.gov/documents/cf-standard-names/depth",
      "description": "Maximum and sampling depth both recorded."
    }
  ]
}
```

Depth variables are schema.org `PropertyValue` entries inside `variableMeasured`, not top-level Dataset properties. The full record contains additional `variableMeasured` entries (latitude, sea_surface_temperature, etc.); the example above shows only the OIH depth-profile entry.

## Step 4 — Verify ISO 19139 intermediate (optional)

Confirm that the catalogue metadata URL was preserved as `gmd:dataSetURI`:

```bash
grep -A2 'dataSetURI' demo-output/528f280c-b151-45c4-9526-e0746510a617_iso19139.xml
```

You should see:

```xml
<gmd:dataSetURI>
   <gco:CharacterString>https://catalogue-imos.aodn.org.au:443/geonetwork/srv/api/records/528f280c-b151-45c4-9526-e0746510a617</gco:CharacterString>
</gmd:dataSetURI>
```

## Step 5 — Validate against DOOS SHACL shapes (optional)

From the monorepo root (after Step 1 has written `projects/AODN/demo-output/`):

```bash
python3 -c "
import json
from pathlib import Path
from pyld import jsonld
from pyshacl import validate
from rdflib import Graph

doc = json.loads(Path('projects/AODN/demo-output/528f280c-b151-45c4-9526-e0746510a617.jsonld').read_text())
assert doc['@type'] == 'Dataset'
assert any(v.get('name') == 'DepBelowSurf' for v in doc.get('variableMeasured', []))
nq = jsonld.to_rdf(doc, {'format': 'application/n-quads'})
data = Graph().parse(data=nq, format='nquads')

for shape in ['SHACL/depth_one.ttl', 'SHACL/googleRequired.ttl']:
    shapes = Graph().parse(shape, format='turtle')
    conforms, _, report = validate(data, shacl_graph=shapes, inference='rdfs')
    print(shape, '→', 'PASS' if conforms else 'FAIL')
    if not conforms:
        print(report)
"
```

Both shapes should report **PASS** for this record.

## Step 6 — Inspect N-Triples (optional)

```bash
grep 'schema.org/Dataset' demo-output/528f280c-b151-45c4-9526-e0746510a617.nt
wc -l demo-output/528f280c-b151-45c4-9526-e0746510a617.nt
```

The `grep` should show the dataset typed as `https://schema.org/Dataset`. `wc -l` should report 273 lines for this record (matching `triple_count` in `run.json`).

## Step 7 — Probe depth columns in a distribution (optional)

Download a tabular `distribution` from the JSON-LD metadata and compute
min/max for depth-related columns. Requires `openpyxl` and `xlrd` for Excel.

```bash
uv pip install openpyxl xlrd

python depth_from_distribution.py \
  --jsonld demo-output/528f280c-b151-45c4-9526-e0746510a617.jsonld \
  --output demo-output/depth_report.json
```

Probe every tabular distribution and cross-check against the ISO 19139 vertical extent sibling file:

```bash
python depth_from_distribution.py \
  --jsonld demo-output/528f280c-b151-45c4-9526-e0746510a617.jsonld \
  --try-all \
  --verbose \
  --output demo-output/depth_report_all.json
```

Expected highlights in `best`:

| Column | min | max |
|---|---|---|
| `Sampling depth` | 5 | 75 |
| `Max Depth (m)` | 49 | 104 |

`metadata_comparison` uses `528f280c-..._iso19139.xml` (0–75 m vertical extent). `Sampling depth` (5–75) should be `within_metadata_extent: true`; `Max Depth (m)` (up to 104) may fall outside and flag `consistent: false`.

## Step 8 — Pipeline depth probe and JSON-LD enrichment (optional)

Run depth probing as part of the pipeline and write observed min/max into
`DepBelowSurf` inside `variableMeasured`:

```bash
python run_pipeline.py \
  --input-xml ./AODN_GN4_depth_metadata.xml \
  --output-dir ./demo-output \
  --no-nt \
  --probe-depth \
  --enrich-jsonld \
  --depth-verbose
```

Or enrich an existing JSON-LD file in place:

```bash
python depth_from_distribution.py \
  --jsonld demo-output/528f280c-b151-45c4-9526-e0746510a617.jsonld \
  --enrich-jsonld \
  --output demo-output/depth_report.json
```

After enrichment, the `DepBelowSurf` entry should include `minValue`, `maxValue`,
and a human-readable `value` string (e.g. `5.0–104.0 m`).

Prefix-listing distributions (`?prefix=...` on `data.aodn.org.au`) are expanded
via the public `imos-data` S3 ListObjects API. Directories that contain only
non-tabular files (e.g. `.fcs`, `.zip`) are skipped with `no_tabular_objects`.

## Output files

After a successful run, `demo-output/` contains:

| File | Description |
|---|---|
| `528f280c-..._source.xml` | Raw ISO 19115-3 XML fetched from GeoNetwork |
| `528f280c-..._iso19139.xml` | Intermediate ISO 19139 |
| `528f280c-....jsonld` | Final schema.org JSON-LD |
| `528f280c-....nt` | N-Triples RDF export |
| `run.json` | Pipeline manifest |
| `depth_report.json` | Depth min/max from best tabular distribution (Step 7) |
| `{id}_depth_report.json` | Depth probe report from pipeline `--probe-depth` (Step 8) |

## Variations

**JSON-LD only (no RDF export):**

```bash
python run_pipeline.py --uuid 528f280c-b151-45c4-9526-e0746510a617 --no-nt
```

**Offline replay** using the bundled sample (no network):

```bash
python run_pipeline.py \
  --input-xml ./AODN_GN4_depth_metadata.xml \
  --output-dir ./demo-output-offline
```

Output files use the XML stem as the record id (e.g. `AODN_GN4_depth_metadata.jsonld`, not the GeoNetwork UUID filename).

**Different catalogue base URL:**

```bash
python run_pipeline.py \
  --uuid 528f280c-b151-45c4-9526-e0746510a617 \
  --catalog-api https://catalogue-imos.aodn.org.au/geonetwork/srv/api \
  --output-dir ./demo-output
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| HTTP error on fetch | Network/firewall; confirm UUID exists in the catalogue |
| `saxonche` import error | Run `uv sync` from monorepo root |
| Empty `variableMeasured` | Source record lacks `gmd:contentInfo/gmd:MD_SampleDimension` |
| SHACL FAIL on `depth_one` | Record has no `depth` sample dimension (no `DepBelowSurf` mapping) |
| Depth probe finds no columns | Distribution may lack depth fields; try `--try-all --verbose` |
| Excel import error | Run `uv pip install openpyxl xlrd` |