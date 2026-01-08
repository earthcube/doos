# GeoParquet2RDF 

## About

## TODO

Integrate the RML approach in /home/fils/src/Projects/CODATA/INSPIRE/gaiaCatalog/mappings



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
