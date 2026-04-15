# ARGO GeoParquet2RDF

This tool transforms ARGO ocean profiling float data from GeoParquet format into semantic web-ready RDF representations. ARGO floats are autonomous instruments that drift through the world's oceans collecting vertical profiles of temperature, salinity, and other oceanographic variables. The data arrives as GeoParquet files containing profile metadata, depth measurements, and spatial geometries. This CLI enables researchers to inspect the dataset structure, export records to CSV for traditional analysis workflows, or convert profiles to RDF N-Triples using JSON-LD templates that map fields to Schema.org and GeoSPARQL vocabularies. The resulting linked data can then be integrated with other semantic web resources, enabling federated queries across distributed ocean observation datasets.

## About

A CLI tool for processing ARGO ocean profiling data from GeoParquet format. It provides utilities to inspect parquet files, export to CSV, and convert records to RDF using JSON-LD templates.

## Installation

Requires Python >= 3.11. Using `uv`:

```bash
uv sync
```

Or with pip:

```bash
pip install geopandas morph-kgc pyarrow pyld
```

## Usage

```bash
python geopan.py <command> [options]
```

### Commands

#### `info` - Inspect parquet file metadata

Displays record count, column names, and sample data from the parquet file.

```bash
python geopan.py info -parquet argo_profiles_features_nmdis.parquet
```

**Output includes:**
- Total number of records
- List of all columns
- First 10 rows of selected columns (id, title, depth_max_in_meters, description, geometry, mission, themes)

#### `tocsv` - Convert parquet to CSV

Exports the GeoParquet file to CSV format with geometry converted to WKT (Well-Known Text).

```bash
python geopan.py tocsv -parquet argo_profiles_features_nmdis.parquet
```

**Output:** Creates `output.csv` in the current directory.

#### `tordf` - Convert to RDF using JSON-LD template

Converts parquet records to RDF N-Triples format using a JSON-LD template.

```bash
python geopan.py tordf -parquet argo_profiles_features_nmdis.parquet -mapping ./template/argo1.json
```

The `-mapping` argument specifies the JSON-LD template file used for RDF conversion.

**Output:** Creates N-Triples files named `{id}.nt` in `data/output/` directory. Blank nodes are skolemized for semantic web compatibility.

#### `rml` - Convert to RDF using RML mapping

Converts parquet records to RDF N-Triples format using morph-kgc with an RML (RDF Mapping Language) mapping file.

```bash
python geopan.py rml -parquet argo_profiles_features_nmdis.parquet -mapping ./RML/test.ttl
```

The `-mapping` argument specifies the RML mapping file (Turtle format) used for RDF conversion.

**Output:** Prints N-Triples to stdout. Requires that the RML mapping file references columns that exist in the parquet file.

## File Structure

```
ARGO/
├── geopan.py                              # Main CLI tool
├── argo_profiles_features_nmdis.parquet   # Sample ARGO data
├── template/
│   └── argo1.json                         # JSON-LD template for RDF conversion
├── RML/
│   ├── test.ttl                           # RML mapping files
│   └── argo.ttl
└── data/
    └── output/                            # Generated N-Triples files
```

## JSON-LD Template

The `tordf` command uses a JSON-LD template (`template/argo1.json`) that maps ARGO profile fields to Schema.org and GeoSPARQL vocabularies:

- `name`, `title`, `description` - Basic metadata
- `variableMeasured[0].maxValue` - Maximum depth in meters
- `geosparql:hasGeometry` - Spatial geometry as WKT

## Dependencies

- `geopandas` - Geospatial data handling
- `morph-kgc` - RML mapping engine (used by `rml` command)
- `pyarrow` - Parquet file support
- `pyld` - JSON-LD processing
- `rdflib` - RDF serialization
