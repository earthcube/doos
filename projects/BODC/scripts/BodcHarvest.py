#!/usr/bin/env python3
"""
Harvest BODC dataset JSON-LD from the Linked Systems UK API.

Discovers series IDs from BODC sitemaps (fallback: bodc_release.nq), fetches
JSON-LD with rate limiting, classifies depth tiers, diffs against the Phase 1
release inventory, and writes N-Quads.

Usage:
  python BodcHarvest.py --limit 50
  python BodcHarvest.py --use-release-ids
  python BodcHarvest.py
"""

import argparse
import io
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pyoxigraph
from pyld import jsonld
from pyoxigraph import NamedNode
from tqdm import tqdm

from bodc_depth import (
    API_DATASET_URL,
    SERIES_LANDING_RE,
    USER_AGENT,
    best_record_per_series,
    build_harvest_diff,
    classify_jsonld,
    load_graph_records,
    load_release_series_index,
    summarize_records,
    write_inventory_csv,
)


SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
GRAPH_BASE = "urn:doos:bodc:harvest"


def parse_args():
    """Parse command-line arguments."""
    project_root = Path(__file__).resolve().parent.parent
    default_output = project_root / "output"

    parser = argparse.ArgumentParser(
        description="Harvest BODC JSON-LD, classify depth, diff against release."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help="Output directory (default: ../output)",
    )
    parser.add_argument(
        "--release-inventory",
        type=Path,
        default=default_output / "depth_inventory.json",
        help="Phase 1 inventory JSON for diffing",
    )
    parser.add_argument(
        "--release-nq",
        type=Path,
        default=project_root / "bodc_release.nq",
        help="Fallback source for series IDs",
    )
    parser.add_argument(
        "--sitemap-url",
        default="https://www.bodc.ac.uk/sitemap.xml",
        help="BODC sitemap index URL",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Seconds between API requests (robots.txt Crawl-delay: 5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of series IDs to fetch (for testing)",
    )
    parser.add_argument(
        "--use-release-ids",
        action="store_true",
        help="Harvest only series IDs found in bodc_release.nq",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Re-fetch JSON-LD even when cache files exist",
    )
    return parser.parse_args()


def fetch_bytes(url, accept=None):
    """Fetch a URL and return response bytes."""
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as response:
        return response.read()


def discover_series_ids_from_sitemap(sitemap_url):
    """
    Crawl the BODC sitemap index and extract series IDs.

    Returns:
        tuple: (sorted series IDs, metadata dict)
    """
    root = ET.fromstring(fetch_bytes(sitemap_url))
    submaps = [
        loc.text
        for loc in root.findall("sm:sitemap/sm:loc", SITEMAP_NS)
        if loc.text
    ]

    series_ids = set()
    for submap_url in submaps:
        content = fetch_bytes(submap_url).decode("utf-8", errors="replace")
        for match in SERIES_LANDING_RE.finditer(content):
            series_ids.add(match.group(1))

    return sorted(series_ids, key=int), {
        "source": "sitemap",
        "sitemap_url": sitemap_url,
        "sitemap_parts": len(submaps),
        "series_count": len(series_ids),
    }


def discover_series_ids_from_release(release_nq):
    """
    Extract unique series IDs from a Gleaner/OIH N-Quads release.

    Returns:
        tuple: (sorted series IDs, metadata dict)
    """
    records, stats = load_graph_records(release_nq)
    series_ids = sorted(
        {
            record["series_id"]
            for record in records
            if record.get("series_id")
        },
        key=int,
    )
    return series_ids, {
        "source": "release_nq",
        "release_nq": str(release_nq),
        "series_count": len(series_ids),
        "load": stats,
    }


def resolve_series_ids(args):
    """
    Resolve the series ID list using sitemap discovery with release fallback.
    """
    if args.use_release_ids:
        if not args.release_nq.exists():
            print(f"Error: release file not found: {args.release_nq}", file=sys.stderr)
            sys.exit(1)
        return discover_series_ids_from_release(args.release_nq)

    try:
        return discover_series_ids_from_sitemap(args.sitemap_url)
    except Exception as exc:
        print(f"Sitemap discovery failed: {exc}", file=sys.stderr)
        if not args.release_nq.exists():
            print(f"Error: release fallback not found: {args.release_nq}", file=sys.stderr)
            sys.exit(1)
        print(f"Falling back to {args.release_nq}", file=sys.stderr)
        return discover_series_ids_from_release(args.release_nq)


def fetch_dataset_jsonld(series_id):
    """Fetch schema.org JSON-LD for one BODC series."""
    url = API_DATASET_URL.format(series_id=series_id)
    payload = fetch_bytes(url, accept="application/ld+json")
    return json.loads(payload.decode("utf-8"))


def cache_path(cache_dir, series_id):
    """Return the JSON-LD cache path for a series."""
    return cache_dir / f"{series_id}.jsonld"


def jsonld_to_nquads(doc, graph_name):
    """Normalize JSON-LD and return N-Quads text for one named graph."""
    return jsonld.normalize(
        doc,
        {"algorithm": "URDNA2015", "format": "application/n-quads"},
    )


def append_to_store(store, ntriples_text, graph_name):
    """Load normalized N-Triples into a pyoxigraph store under a named graph."""
    store.load(
        io.StringIO(ntriples_text),
        "application/n-triples",
        base_iri=None,
        to_graph=NamedNode(graph_name),
    )


def harvest_series(series_ids, args):
    """
    Fetch JSON-LD for each series ID, classify depth, and build N-Quads.

    Returns:
        tuple: (records list, errors list, pyoxigraph Store)
    """
    cache_dir = args.output_dir / "jsonld_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    store = pyoxigraph.Store()
    records = []
    errors = []

    for index, series_id in enumerate(
        tqdm(series_ids, desc="Harvesting", unit="series")
    ):
        cache_file = cache_path(cache_dir, series_id)

        try:
            if cache_file.exists() and not args.no_resume:
                doc = json.loads(cache_file.read_text(encoding="utf-8"))
            else:
                if index > 0 and args.delay > 0:
                    time.sleep(args.delay)
                doc = fetch_dataset_jsonld(series_id)
                cache_file.write_text(
                    json.dumps(doc, indent=2),
                    encoding="utf-8",
                )

            graph_name = f"{GRAPH_BASE}:{series_id}"
            ntriples = jsonld_to_nquads(doc, graph_name)
            append_to_store(store, ntriples, graph_name)

            record = classify_jsonld(doc)
            record["graph_uri"] = graph_name
            records.append(record)
        except (HTTPError, URLError, json.JSONDecodeError, Exception) as exc:
            errors.append({"series_id": series_id, "error": str(exc)})

    return records, errors, store


def write_outputs(args, records, errors, store, discovery_meta, diff):
    """Write harvest artifacts to the output directory."""
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize_records(records)
    summary["discovery"] = discovery_meta
    summary["errors"] = {
        "count": len(errors),
        "items": errors,
    }

    inventory_payload = {
        "source": "live_api",
        "api_base": "https://api.linked-systems.uk/api/schema-org/dataset/",
        "summary": summary,
        "records": records,
    }
    json_path = args.output_dir / "live_depth_inventory.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(inventory_payload, handle, indent=2)

    csv_path = write_inventory_csv(
        args.output_dir, records, "live_depth_inventory.csv"
    )

    diff_path = args.output_dir / "harvest_diff.json"
    with diff_path.open("w", encoding="utf-8") as handle:
        json.dump(diff, handle, indent=2)

    nq_path = args.output_dir / "bodc_harvest.nq"
    store.dump(nq_path, "application/n-quads")

    return json_path, csv_path, diff_path, nq_path


def print_diff_summary(diff):
    """Print harvest diff summary to stderr."""
    print("Diff vs release inventory:", file=sys.stderr)
    print(f"  release series: {diff['release_series_count']}", file=sys.stderr)
    print(f"  live harvested: {diff['live_series_count']}", file=sys.stderr)
    print(f"  new in live: {diff['new_series_count']}", file=sys.stderr)
    print(f"  missing from live: {diff['missing_series_count']}", file=sys.stderr)
    print(f"  changed tier/depth: {diff['changed_count']}", file=sys.stderr)


def main():
    """Discover series IDs, harvest JSON-LD, diff against release, export N-Quads."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        series_ids, discovery_meta = resolve_series_ids(args)
        print(
            f"Discovered {len(series_ids)} series IDs via {discovery_meta['source']}",
            file=sys.stderr,
        )

        if args.limit is not None:
            series_ids = series_ids[: args.limit]
            print(f"Limited harvest to {len(series_ids)} series", file=sys.stderr)

        records, errors, store = harvest_series(series_ids, args)

        release_index = {}
        if args.release_inventory.exists():
            release_index = load_release_series_index(args.release_inventory)
        else:
            print(
                f"Warning: release inventory not found: {args.release_inventory}",
                file=sys.stderr,
            )

        live_index = best_record_per_series(records)
        diff = build_harvest_diff(release_index, live_index)

        json_path, csv_path, diff_path, nq_path = write_outputs(
            args, records, errors, store, discovery_meta, diff
        )

        summary = summarize_records(records)
        print(
            f"Harvested {summary['series']['unique_count']} series; "
            f"errors: {len(errors)}",
            file=sys.stderr,
        )
        print_diff_summary(diff)
        print(f"Wrote {json_path}", file=sys.stderr)
        print(f"Wrote {csv_path}", file=sys.stderr)
        print(f"Wrote {diff_path}", file=sys.stderr)
        print(f"Wrote {nq_path}", file=sys.stderr)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()