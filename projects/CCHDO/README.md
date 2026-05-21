# CCHDO NetCDF → JSON-LD Pipelines

Extracts metadata from CCHDO [NetCDF](https://www.unidata.ucar.edu/software/netcdf/) bottle files and transforms it into JSON-LD using [SHACL Advanced Features (SHACL-AF)](https://www.w3.org/TR/shacl-af/) SPARQL rules. Two output formats are supported:

- **schema.org Dataset** — `variableMeasured` as `PropertyValue` nodes with units, CF names, WHP codes, and reference scales
- **MLCommons Croissant 1.1** — `cr:RecordSet` / `cr:Field` structure for ML dataset cataloguing

## Overview

Both pipelines share the same first step:

```
33RR20220430_bottle.nc
        │
        │ nc_metadata.py
        │
        ▼
33RR20220430_bottle.metadata.json
        │
        ├─ nc_to_jsonld.py  +  SHACL_AF/nc_metadata_to_schema.ttl
        │         ▼
        │  33RR20220430_bottle.schema.shacl.jsonld
        │
        └─ nc_to_croissant.py  +  SHACL_AF/nc_metadata_to_croissant.ttl
                  ▼
         33RR20220430_bottle.croissant.jsonld
```

**Step 1 — Extract metadata** (`nc_metadata.py`): reads a `.nc` file and writes a structured JSON file containing the file's global attributes, dimensions, and all variable descriptors (name, shape, dtype, variable-level attributes).

**Step 2 — Transform to JSON-LD** (`nc_to_jsonld.py`): loads the metadata JSON, converts it to an intermediate RDF graph, applies SHACL-AF SPARQL rules to generate schema.org triples, then frames and serializes to JSON-LD.

## Requirements

Python 3.13+ with the project virtual environment:

```bash
uv sync   # from /home/fils/src/Projects/earthcube/doos/
```

Key packages: `netCDF4`, `rdflib`, `pyshacl`, `pyld`.

## Usage

### Step 1 — Extract NetCDF metadata

```bash
.venv/bin/python nc_metadata.py [path/to/file.nc]
```

Defaults to `33RR20220430_bottle.nc` in the current directory. Writes `<stem>.metadata.json`.

**Output structure:**

```json
{
  "source_file": "33RR20220430_bottle.nc",
  "global_attributes": {
    "Conventions": "CF-1.8 CCHDO-1.0",
    "featureType": "profile",
    ...
  },
  "dimensions": {
    "N_PROF": 149,
    "N_LEVELS": 36,
    ...
  },
  "variables": {
    "temperature": {
      "dimensions": ["N_PROF", "N_LEVELS"],
      "shape": [149, 36],
      "dtype": "float64",
      "attributes": { "whp_name": "CTDTMP", "standard_name": "sea_water_temperature", ... }
    },
    ...
  }
}
```

### Step 2 — Transform to schema.org JSON-LD

```bash
.venv/bin/python nc_to_jsonld.py [metadata.json] [--shapes SHAPES_TTL] [--output OUT]
```

| Argument | Default |
|---|---|
| `metadata.json` | `33RR20220430_bottle.metadata.json` |
| `--shapes` | `SHACL_AF/nc_metadata_to_schema.ttl` |
| `--output` | `<stem>.schema.shacl.jsonld` |

**Output structure:**

```json
{
  "@context": { "@vocab": "https://schema.org/" },
  "@id": "urn:cchdo:dataset:33RR20220430_bottle",
  "@type": "Dataset",
  "name": "33RR20220430_bottle.nc",
  "variableMeasured": [
    {
      "@id": "urn:cchdo:var:33RR20220430_bottle:time_pv",
      "@type": "PropertyValue",
      "name": "time",
      "additionalType": "float64"
    },
    ...
  ]
}
```

## SHACL-AF Shapes — schema.org (`SHACL_AF/nc_metadata_to_schema.ttl`)

The shapes file defines two `sh:SPARQLRule` rules that operate on an intermediate RDF graph built from the metadata JSON.

### Intermediate vocabulary

A temporary `cchdo:` namespace (`https://cchdo.ucsd.edu/vocab#`) is used to represent the JSON structure as RDF before the rules fire. These triples are ephemeral — they do not appear in the output.

| Intermediate term | Source JSON field |
|---|---|
| `cchdo:NCDataset` | top-level object |
| `cchdo:sourceFile` | `source_file` |
| `cchdo:hasVariable` | link from dataset to each variable |
| `cchdo:NCVariable` | each entry in `variables` |
| `cchdo:varName` | variable key name |
| `cchdo:varDtype` | `variables[name].dtype` |

### Rule 1 — Dataset shape (`sh:order 1`)

Targets `cchdo:NCDataset`. Generates:

```sparql
CONSTRUCT {
    $this a schema:Dataset .
    $this schema:name ?srcFile .
}
```

### Rule 2 — Variable shape (`sh:order 2`)

Targets `cchdo:NCVariable`. Generates a `schema:PropertyValue` node for each variable and links it to the parent dataset:

```sparql
CONSTRUCT {
    ?pvNode a schema:PropertyValue .
    ?pvNode schema:name ?vname .
    ?pvNode schema:additionalType ?vdtype .
    ?ds schema:variableMeasured ?pvNode .
}
```

`PropertyValue` IRIs are minted deterministically as `{variable_IRI}_pv`.

---

## Step 2b — Transform to MLCommons Croissant JSON-LD

```bash
.venv/bin/python nc_to_croissant.py [metadata.json] [--shapes SHAPES_TTL] [--output OUT]
```

| Argument | Default |
|---|---|
| `metadata.json` | `33RR20220430_bottle.metadata.json` |
| `--shapes` | `SHACL_AF/nc_metadata_to_croissant.ttl` |
| `--output` | `<stem>.croissant.jsonld` |

Produces a [Croissant 1.1](https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html)-compliant JSON-LD document describing the dataset for ML tooling.

**Output structure:**

```json
{
  "@context": { "@vocab": "http://schema.org/", "cr": "http://mlcommons.org/croissant/", ... },
  "@type": "Dataset",
  "conformsTo": "http://mlcommons.org/croissant/1.1",
  "name": "33RR20220430_bottle.nc",
  "distribution": [
    {
      "@type": "cr:FileObject",
      "name": "33RR20220430_bottle.nc",
      "encodingFormat": "application/netcdf"
    }
  ],
  "recordSet": [
    {
      "@type": "cr:RecordSet",
      "name": "variables",
      "field": [
        {
          "@type": "cr:Field",
          "name": "ctd_temperature",
          "description": "sea_water_temperature",
          "dataType": "Float",
          "isArray": true,
          "arrayShape": "(149, 36)",
          "source": {
            "fileObject": { "@id": "urn:cchdo:dataset:.../fileobject" },
            "extract": { "column": "CTDTMP" }
          }
        },
        ...
      ]
    }
  ]
}
```

## SHACL-AF Shapes — Croissant (`SHACL_AF/nc_metadata_to_croissant.ttl`)

### Intermediate vocabulary (Croissant-specific predicates)

The Croissant pipeline extends the shared `cchdo:` intermediate vocabulary with three additional predicates pre-computed in Python before the rules fire:

| Intermediate term | Source | Notes |
|---|---|---|
| `cchdo:varSchemaType` | `variables[name].dtype` | Mapped to `sc:Float`, `sc:Integer`, or `sc:Text` IRI |
| `cchdo:varIsArray` | `len(variables[name].shape) > 0` | `xsd:boolean` |
| `cchdo:varArrayShape` | `variables[name].shape` | Formatted string, e.g. `"(149, 36)"` |

**dtype → `cr:dataType` mapping:**

| NetCDF dtype | Croissant `cr:dataType` |
|---|---|
| `float64`, `float32` | `sc:Float` |
| `int32`, `int8`, `int16` | `sc:Integer` |
| `\|S1`, `\|S2`, `U*` | `sc:Text` |

### Rule 1 — Dataset shape (`sh:order 1`)

Targets `cchdo:NCDataset`. Generates the dataset wrapper, a `cr:FileObject` node linked via `sc:distribution`, and a `cr:RecordSet` node linked via `cr:recordSet`.

### Rule 2 — Variable shape (`sh:order 2`)

Targets `cchdo:NCVariable`. For each variable generates a `cr:Field` and a two-node extraction chain:

```sparql
CONSTRUCT {
    ?fieldNode a cr:Field .
    ?fieldNode cr:dataType ?dataTypeIRI .
    ?fieldNode cr:isArray ?isArr .
    ?fieldNode cr:arrayShape ?arrShape .
    ?fieldNode cr:source ?sourceNode .
    ?sourceNode cr:fileObject ?foNode .
    ?sourceNode cr:extract ?extractNode .
    ?extractNode cr:column ?colName .
    ?rsNode cr:field ?fieldNode .
}
```

`source`, `extract`, and `field` IRIs are minted deterministically as `{variable_IRI}_source`, `_extract`, and `_field`. The `cr:column` value is `whp_name` when present, otherwise the variable key name.

## File Reference

```
CCHDO/
├── nc_metadata.py                           # Step 1: .nc → metadata JSON
├── nc_to_jsonld.py                          # Step 2a: metadata JSON → schema.org JSON-LD
├── nc_to_croissant.py                       # Step 2b: metadata JSON → Croissant JSON-LD
├── SHACL_AF/
│   ├── nc_metadata_to_schema.ttl            # SHACL-AF shapes for schema.org output
│   └── nc_metadata_to_croissant.ttl         # SHACL-AF shapes for Croissant output
├── 33RR20220430_bottle.nc                   # Sample NetCDF file
├── 33RR20220430_bottle.metadata.json        # Extracted metadata (Step 1 output)
├── 33RR20220430_bottle.schema.shacl.jsonld  # schema.org JSON-LD (Step 2a output)
└── 33RR20220430_bottle.croissant.jsonld     # Croissant JSON-LD (Step 2b output)
```
