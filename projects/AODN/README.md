# AODN

This toolkit transforms Australian Ocean Data Network (AODN) metadata records into web-friendly, machine-readable formats. It provides a two-step XSLT pipeline that first converts ISO 19115-3 metadata to ISO 19139 XML, then transforms that output into JSON-LD using schema.org vocabulary. The resulting JSON-LD can be embedded in web pages for discovery by search engines and data aggregators, enabling FAIR (Findable, Accessible, Interoperable, Reusable) data practices.

## About

This directory contains tools for transforming AODN (Australian Ocean Data Network) metadata records through a two-step pipeline:

1. **ISO 19115-3 → ISO 19139**: Convert ISO 19115-3:2014 XML metadata to standard ISO 19139 XML
2. **ISO 19139 → JSON-LD**: Transform ISO 19139 to schema.org vocabulary as JSON-LD

## Dependencies

Install required packages:

```bash
uv add saxonche lxml
```

- **saxonche**: Saxon XSLT 3.0 processor (used by `convert_script.py`)
- **lxml**: Python XML library with XSLT 1.0 support (used by `aodnTransform.py`)

## Scripts

### convert_script.py

Transforms XML using XSLT 2.0/3.0 stylesheets via Saxon. Writes output to a file.

**Arguments:**
- `-input` / `--input-file`: Source XML file (required)
- `-xslt` / `--xslt-file`: XSLT stylesheet (required)
- `-output` / `--output-file`: Output file path (required)

### aodnTransform.py

Transforms XML using XSLT 1.0 stylesheets via lxml. Prints output to stdout.

**Arguments:**
- `-xml` / `--xml-file`: Source XML file (required)
- `-xslt` / `--xslt-file`: XSLT stylesheet (required)

## Workflow

The typical workflow transforms metadata from ISO 19115-3 → ISO 19139 → JSON-LD (schema.org):

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
  -xslt ./ISO19139mapping/ISO19139ToSDODatasetStandalone1.0.xslt
```

To save the JSON-LD output to a file:

```bash
python aodnTransform.py \
  -xml metadata_19139_output.xml \
  -xslt ./ISO19139mapping/ISO19139ToSDODatasetStandalone1.0.xslt > output.jsonld
```

## Directory Structure

- `transformations/` - XSLT stylesheets for ISO format conversions
- `ISO19139mapping/` - XSLT stylesheets for ISO 19139 to schema.org JSON-LD