# ARGO GeoParquet2RDF 

## About

This CLI tool processes ARGO ocean profiling data from GeoParquet format. It provides three main commands: info to inspect dataset metadata including record count, available columns, and sample data; tocsv to export data to CSV format with geometry converted to Well-Known Text; and rml to convert GeoParquet records to RDF using template-based JSON-LD transformations. 

The RML mapping command reads a JSON-LD template, iterates through ARGO profile features to populate fields like title, description, depth measurements, and spatial geometries, then outputs N-Triples with skolemized blank nodes to enable integration with semantic web applications and ontologies.

## geopan.py

This Python script uses the `geopandas` library to read a GeoParquet file named `argo_profiles_features_nmdis.parquet`.

### Functionality

1.  **Reads Data**: It loads the specified GeoParquet file into a GeoDataFrame.
2.  **Prints Metadata**:
    *   It prints the total number of rows (records) in the GeoDataFrame.
    *   It prints a list of all column names available in the dataset.
3.  **Subsets and Displays Data**:
    *   It attempts to select a predefined list of columns: `['title', 'depth_max_in_meters', 'description', 'geometry']`.
    *   If all specified columns exist, it prints the first 10 rows of this subset.
    *   If any of the specified columns are missing, it prints an error message listing the missing columns.

### To Run the Script

1.  **Install dependencies**:
    ```bash
    pip install geopandas
    ```
2.  **Execute the script**:
    ```bash
    python geopan.py
    ```
