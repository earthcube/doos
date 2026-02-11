import pandas as pd
from scipy import stats  # For mode, if needed (pandas also has mode)


def analyze_depth_columns(file_path):
    # Load the file based on extension
    if file_path.lower().endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.lower().endswith('.parquet'):
        df = pd.read_parquet(file_path)
    else:
        raise ValueError("Unsupported file format. Please provide a CSV or Parquet file.")

    # Identify potential depth columns (case-insensitive search for 'depth' in column name)
    depth_columns = [col for col in df.columns if 'depth' in col.lower()]

    if not depth_columns:
        print("No columns found related to 'depth'.")
        return

    results = {}
    for col in depth_columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            # Compute statistics
            col_stats = {
                'min': df[col].min(),
                'max': df[col].max(),
                'mean': df[col].mean(),
                'median': df[col].median(),
                'mode': df[col].mode().values[0] if not df[col].mode().empty else None,
                'std_dev': df[col].std()
            }
            results[col] = col_stats
            print(f"\nStatistics for column '{col}':")
            for stat, value in col_stats.items():
                print(f"{stat}: {value}")
        else:
            print(f"Column '{col}' is not numeric, skipping statistics.")

    return results

# Example usage
# analyze_depth_columns('your_file.csv')