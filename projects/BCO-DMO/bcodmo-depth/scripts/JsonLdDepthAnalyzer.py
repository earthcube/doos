#!/usr/bin/env python3
"""
Main script to fetch JSON-LD, download distributions, and analyze depth data.
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from bs4 import BeautifulSoup

# Import the existing assay module
from assay import analyze_depth_columns


def fetch_jsonld(url):
    """
    Fetch HTML from the given URL and extract embedded JSON-LD.
    Looks for <script type="application/ld+json"> tags and validates
    it's a schema.org Dataset.

    Args:
        url: URL to the HTML page containing embedded JSON-LD

    Returns:
        dict: Parsed JSON-LD data

    Raises:
        Exception: If URL is invalid or no valid JSON-LD Dataset is found
    """
    try:
        req = Request(url, headers={"User-Agent": "BCO-DMO-Depth-Analyzer/1.0"})

        with urlopen(req, timeout=30) as response:
            html_content = response.read().decode("utf-8", errors="replace")

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")

            # Find all JSON-LD script tags
            jsonld_scripts = soup.find_all("script", type="application/ld+json")

            if not jsonld_scripts:
                raise Exception("No JSON-LD found in the HTML page")

            # Look for a Dataset type in the JSON-LD blocks
            dataset_jsonld = None

            for script in jsonld_scripts:
                try:
                    jsonld = json.loads(script.string)

                    # Handle @graph arrays
                    if isinstance(jsonld, dict) and "@graph" in jsonld:
                        for item in jsonld["@graph"]:
                            if (
                                isinstance(item, dict)
                                and item.get("@type") == "Dataset"
                            ):
                                dataset_jsonld = item
                                break
                    # Handle direct Dataset object
                    elif isinstance(jsonld, dict) and jsonld.get("@type") == "Dataset":
                        dataset_jsonld = jsonld
                        break
                    # Handle array of objects
                    elif isinstance(jsonld, list):
                        for item in jsonld:
                            if (
                                isinstance(item, dict)
                                and item.get("@type") == "Dataset"
                            ):
                                dataset_jsonld = item
                                break

                    if dataset_jsonld:
                        break

                except json.JSONDecodeError:
                    continue  # Skip malformed JSON-LD blocks

            if not dataset_jsonld:
                # If no Dataset found, return the first valid JSON-LD with a warning
                for script in jsonld_scripts:
                    try:
                        jsonld = json.loads(script.string)
                        if isinstance(jsonld, dict):
                            print(
                                f"Warning: @type is '{jsonld.get('@type', 'unknown')}', expected 'Dataset'",
                                file=sys.stderr,
                            )
                            return jsonld
                    except json.JSONDecodeError:
                        continue
                raise Exception("No valid JSON-LD object found in the HTML page")

            return dataset_jsonld

    except HTTPError as e:
        raise Exception(f"HTTP Error {e.code}: {e.reason}")
    except URLError as e:
        raise Exception(f"URL Error: {e.reason}")


def extract_distributions(jsonld):
    """
    Extract distribution information from JSON-LD.

    Args:
        jsonld: Parsed JSON-LD data

    Returns:
        list: List of distribution objects
    """
    distributions = jsonld.get("distribution", [])

    # Handle single distribution (not in array)
    if isinstance(distributions, dict):
        distributions = [distributions]

    # Filter for CSV and Parquet files
    supported_formats = [
        "text/csv",
        "application/csv",
        "application/x-parquet",
        "application/parquet",
    ]

    filtered = []
    for dist in distributions:
        encoding_format = dist.get("encodingFormat", "").lower()
        content_url = dist.get("contentUrl", "")

        # Check by MIME type or file extension
        is_supported = (
            encoding_format in [f.lower() for f in supported_formats]
            or content_url.lower().endswith(".csv")
            or content_url.lower().endswith(".parquet")
        )

        if is_supported and content_url:
            filtered.append(
                {
                    "url": content_url,
                    "format": encoding_format or "unknown",
                    "name": dist.get("name", "Unnamed"),
                    "description": dist.get("description", ""),
                }
            )

    return filtered


def download_file(url, output_dir=None):
    """
    Download file from URL to output directory.

    Args:
        url: URL to download
        output_dir: Directory to save file (uses temp dir if None)

    Returns:
        tuple: (path to downloaded file, file size in bytes)
    """
    try:
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="bcodmo_depth_")
        else:
            os.makedirs(output_dir, exist_ok=True)

        # Extract filename from URL
        filename = os.path.basename(url.split("?")[0])
        if not filename:
            filename = "downloaded_data"

        # Ensure proper extension
        if not (filename.endswith(".csv") or filename.endswith(".parquet")):
            if "csv" in url.lower():
                filename += ".csv"
            elif "parquet" in url.lower():
                filename += ".parquet"

        output_path = os.path.join(output_dir, filename)

        req = Request(url, headers={"User-Agent": "BCO-DMO-Depth-Analyzer/1.0"})

        print(f"Downloading from {url}...", file=sys.stderr)

        with urlopen(req, timeout=120) as response:
            total_size = response.headers.get("Content-Length")

            if total_size:
                total_size = int(total_size)
                size_mb = total_size / (1024 * 1024)

                if size_mb > 100:
                    print(f"Warning: Large file ({size_mb:.1f} MB)", file=sys.stderr)

            # Download file
            with open(output_path, "wb") as f:
                chunk_size = 8192
                downloaded = 0

                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size:
                        progress = (downloaded / total_size) * 100
                        print(f"\rProgress: {progress:.1f}%", end="", file=sys.stderr)

        print(f"\nDownloaded to: {output_path}", file=sys.stderr)
        return output_path, downloaded

    except Exception as e:
        raise Exception(f"Error downloading file: {e}")


def save_results(output_file, metadata, distribution, depth_analysis, notes=None):
    """
    Save complete analysis results to JSON file.

    Args:
        output_file: Path to output JSON file
        metadata: Dataset metadata dict
        distribution: Distribution info dict
        depth_analysis: Depth analysis results dict
        notes: Optional list of observation strings
    """

    # Convert numpy types to native Python types for JSON serialization
    def convert_to_native(obj):
        if isinstance(obj, dict):
            return {k: convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(item) for item in obj]
        elif hasattr(obj, "item"):  # numpy scalar types have .item() method
            return obj.item()
        return obj

    result = {
        "metadata": {
            "dataset_id": metadata.get("id", ""),
            "dataset_name": metadata.get("name", ""),
            "dataset_url": metadata.get("url", ""),
            "analysis_date": datetime.now(timezone.utc).isoformat(),
        },
        "distribution": distribution,
        "depth_analysis": convert_to_native(depth_analysis),
        "notes": notes or [],
    }

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nResults saved to {output_path}", file=sys.stderr)


def generate_observations(depth_analysis):
    """
    Generate human-readable observations from depth analysis.

    Args:
        depth_analysis: Dict of depth statistics

    Returns:
        list: List of observation strings
    """
    observations = []

    for col_name, stats in depth_analysis.items():
        depth_range = stats["max"] - stats["min"]

        if depth_range > 1000:
            observations.append(
                f"Wide depth range ({stats['min']:.1f} - {stats['max']:.1f}m) "
                "indicates diverse sampling zones"
            )

        if stats["std_dev"] > stats["mean"] * 0.5:
            observations.append(
                f"High standard deviation ({stats['std_dev']:.1f}m) "
                "suggests variable depth coverage"
            )

        if stats["min"] < 10:
            observations.append("Includes near-surface samples")

        if stats["max"] > 1000:
            observations.append("Includes deep ocean samples (>1000m)")

    return observations


def main():
    parser = argparse.ArgumentParser(
        description="Analyze depth data from schema.org Dataset JSON-LD"
    )
    parser.add_argument("--url", required=True, help="URL to JSON-LD file")
    parser.add_argument("--output", default="reviewed.json", help="Output file path")
    parser.add_argument("--temp-dir", help="Temporary directory for downloads")

    args = parser.parse_args()

    try:
        # Step 1: Fetch JSON-LD
        print("Fetching JSON-LD metadata...", file=sys.stderr)
        jsonld = fetch_jsonld(args.url)

        metadata = {
            "id": jsonld.get("@id", ""),
            "name": jsonld.get("name", ""),
            "description": jsonld.get("description", ""),
            "url": jsonld.get("url", ""),
        }

        print(f"✓ Found dataset: '{metadata['name']}'", file=sys.stderr)

        # Step 2: Extract distributions
        print("\nChecking for data distributions...", file=sys.stderr)
        distributions = extract_distributions(jsonld)

        if not distributions:
            print("No CSV or Parquet distributions found.", file=sys.stderr)
            return 1

        print(f"✓ Found {len(distributions)} distribution(s):", file=sys.stderr)
        for i, dist in enumerate(distributions, 1):
            print(f"  {i}. {dist['name']} ({dist['format']})", file=sys.stderr)

        # Step 3: Download first distribution (or allow selection)
        dist = distributions[0]
        print(f"\nDownloading: {dist['name']}", file=sys.stderr)

        file_path, file_size = download_file(dist["url"], args.temp_dir)

        distribution_info = {
            "file_url": dist["url"],
            "file_format": dist["format"],
            "file_size_bytes": file_size,
        }

        # Step 4: Analyze depth columns
        print("\nAnalyzing depth columns...", file=sys.stderr)
        depth_results = analyze_depth_columns(file_path)

        if not depth_results:
            print("No depth columns found in the data.", file=sys.stderr)
            return 1

        print(f"✓ Found {len(depth_results)} depth column(s)", file=sys.stderr)

        # Display results
        print("\n" + "=" * 60, file=sys.stderr)
        print("DEPTH ANALYSIS RESULTS", file=sys.stderr)
        print("=" * 60, file=sys.stderr)

        for col_name, stats in depth_results.items():
            print(f"\nColumn: {col_name}", file=sys.stderr)
            print(f"  Minimum depth: {stats['min']:.2f} meters", file=sys.stderr)
            print(f"  Maximum depth: {stats['max']:.2f} meters", file=sys.stderr)
            print(f"  Average depth: {stats['mean']:.2f} meters", file=sys.stderr)
            print(f"  Median depth: {stats['median']:.2f} meters", file=sys.stderr)
            if stats["mode"] is not None:
                print(f"  Mode: {stats['mode']:.2f} meters", file=sys.stderr)
            print(
                f"  Standard deviation: {stats['std_dev']:.2f} meters", file=sys.stderr
            )

        # Generate observations
        observations = generate_observations(depth_results)

        if observations:
            print("\nObservations:", file=sys.stderr)
            for obs in observations:
                print(f"  • {obs}", file=sys.stderr)

        # Step 5: Save results
        save_results(
            args.output, metadata, distribution_info, depth_results, observations
        )

        # Cleanup temp file
        try:
            os.remove(file_path)
        except:
            pass

        return 0

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
