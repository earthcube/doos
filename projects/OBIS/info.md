# OBIS Python Scripts

This directory contains four Python scripts for processing OBIS (Ocean Biodiversity Information System) data, primarily focused on depth statistics from Parquet/DwC-A files and generating JSON-LD metadata.

## Scripts Overview

**ibis_test1.py**
- Computes minimum and maximum depth per `dataset_id` from a large OBIS Parquet file using Ibis and DuckDB.
- Outputs aggregated results to `idMinMaxDepth.parquet`.
- No command line parameters (hardcoded paths).
- Example: `python ibis_test1.py`

**depthTriples.py**
- Reads `idMinMaxDepth.parquet`, queries matching JSON-LD files via DuckDB to resolve dataset URLs.
- Generates schema.org JSON-LD files with `variableMeasured` depth properties (using min/max).
- Writes separate outputs for all records and strict (non-null) records.
- No command line parameters (hardcoded paths and directories).
- Example: `python depthTriples.py`

**dwcaPandas.py**
- Demonstrates loading a Darwin Core Archive (DwC-A) ZIP using `dwca.read` and converting the core occurrence file to a Pandas DataFrame.
- Prints info, head, and depth statistics for the example archive.
- No command line parameters (hardcoded ZIP path).
- Example: `python dwcaPandas.py`

**dwcaReader.py**
- Example/tutorial script demonstrating the `dwca.read` library features: metadata access, descriptor inspection, term querying, row iteration, and utility functions for Darwin Core terms.
- Uses a sample DwC-A archive to explore structure and data.
- No command line parameters (hardcoded ZIP path).
- Example: `python dwcaReader.py`

None of the scripts accept CLI arguments or flags (use `argparse` or `sys.argv` for future enhancements). They are currently demonstration/exploratory tools with hardcoded file paths.
