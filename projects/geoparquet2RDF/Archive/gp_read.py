import polars as pl

# Specify the path to your GeoParquet file
file_path = 'argo_profiles_features_nmdis.parquet'

# Read the first 100 rows into a Polars DataFrame
df = pl.read_parquet(file_path, n_rows=100)

# Print the first 10 rows
print(df.head(10))
