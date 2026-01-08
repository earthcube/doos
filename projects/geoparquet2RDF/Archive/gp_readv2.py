import polars as pl

# Specify the path to your GeoParquet file
file_path = 'argo_profiles_features_nmdis.parquet'

try:
    # Option 1: Quick inspection (via scan_parquet for lazy loading)
    # Prefer scan_parquet over read_parquet for large files to delay full loading
    lazy_df = pl.scan_parquet(file_path)
    
    # Print schema to understand columns (e.g., check for geometry or spatial fields in GeoParquet)
    print("Schema:")
    print(lazy_df.schema)
    
    # Read only specific columns if needed (faster than loading all)
    # Example: If you know the columns, e.g., ['feature_id', 'latitude', 'longitude']
    # Replace with actual column names or remove to read all
    columns_to_read = ['feature_id']  # Adjust based on your file's schema
    df = lazy_df.select(columns_to_read).limit(100).collect()  # Limit to 100 rows
    
    # Optional: Apply filters (example: only rows where a column > value)
    # df = lazy_df.filter(pl.col('latitude') > 0).limit(100).collect()
    
    # Print the first 10 rows
    print("First 10 rows:")
    print(df.head(10))

except Exception as e:
    print(f"Error reading Parquet file: {e}")
    # Additional debug: Check if it's a path issue or Parquet format problem
    import os
    if not os.path.exists(file_path):
        print(f"File not found at {file_path}")
