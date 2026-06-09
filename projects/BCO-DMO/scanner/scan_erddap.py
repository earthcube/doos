#!/usr/bin/env python3
"""
Scan BCO-DMO's ERDDAP server to build a dataset access inventory.

Seeds from ERDDAP's ``allDatasets`` table (one request enumerates every active
dataset with bounding box and license), then optionally probes each dataset's
access routes — ERDDAP metadata JSON, the www.bco-dmo.org ISO 19115-2 record,
and the DataCite DOI — recording which are reachable.

The output is a JSON inventory suitable for seeding the DOOS harvest →
transform-to-RDF → SHACL-validate pipeline.

Usage:
    # Just enumerate the catalog (one fast request, no per-dataset probing)
    python scan_erddap.py --output erddap_inventory.json

    # Enumerate and probe access routes for the first 25 datasets
    python scan_erddap.py --probe --limit 25 --output erddap_inventory.json

    # Probe every dataset (slow — one request per route per dataset)
    python scan_erddap.py --probe --output erddap_inventory.json

    # Full-text search the catalog instead of enumerating everything
    python scan_erddap.py --search depth --probe --output depth_datasets.json
"""

import argparse
import json
import sys
from pathlib import Path

import requests
from tqdm import tqdm
from urllib.parse import quote

ERDDAP_BASE = "https://erddap.bco-dmo.org/erddap"
WWW_BASE = "https://www.bco-dmo.org"
USER_AGENT = "BCO-DMO-Scanner/1.0 (DOOS; dfils@ucsd.edu)"
TIMEOUT = 30

# Columns requested from the allDatasets table. ERDDAP exposes these for every
# dataset, so a single tabledap request yields the whole catalog with extents.
ALLDATASETS_COLUMNS = [
    "datasetID",
    "title",
    "institution",
    "summary",
    "dataStructure",
    "minLongitude",
    "maxLongitude",
    "minLatitude",
    "maxLatitude",
    "minTime",
    "maxTime",
    "infoUrl",
    "iso19115",
]


def _session():
    """Return a requests Session with the project's standard User-Agent."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def fetch_all_datasets(session):
    """
    Enumerate every active dataset via ERDDAP's allDatasets table.

    Args:
        session: A configured requests.Session

    Returns:
        list[dict]: One dict per dataset keyed by ALLDATASETS_COLUMNS. The
        synthetic "allDatasets" summary row that ERDDAP includes is dropped.
    """
    # ERDDAP tabledap takes the variable list as a raw query string (no key=),
    # so it is appended directly rather than via requests' params encoding.
    query = quote(",".join(ALLDATASETS_COLUMNS), safe=",")
    url = f"{ERDDAP_BASE}/tabledap/allDatasets.json?{query}"

    resp = session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()

    table = resp.json()["table"]
    columns = table["columnNames"]
    rows = table["rows"]

    datasets = [dict(zip(columns, row)) for row in rows]
    # ERDDAP lists itself as a meta-dataset; it is not a real data resource.
    return [d for d in datasets if d.get("datasetID") != "allDatasets"]


# ERDDAP's search endpoint uses human-readable column labels; map the ones we
# keep onto the machine-name keys that fetch_all_datasets produces so both code
# paths yield identically shaped records.
SEARCH_COLUMN_MAP = {
    "Dataset ID": "datasetID",
    "Title": "title",
    "Institution": "institution",
    "Summary": "summary",
    "Info": "infoUrl",
    "ISO 19115": "iso19115",
}

# ERDDAP rejects out-of-range itemsPerPage with a 404, so request a bounded page
# size and paginate rather than asking for everything at once.
SEARCH_PAGE_SIZE = 1000


def _normalize_search_rows(table):
    """Map an ERDDAP search result table onto fetch_all_datasets()-shaped records."""
    columns = table["columnNames"]
    datasets = []
    for row in table["rows"]:
        raw = dict(zip(columns, row))
        record = {
            machine: raw.get(label) for label, machine in SEARCH_COLUMN_MAP.items()
        }
        # The search table omits extents; keep keys present but null so the
        # output schema matches the allDatasets path.
        for key in (
            "minLongitude",
            "maxLongitude",
            "minLatitude",
            "maxLatitude",
            "minTime",
            "maxTime",
        ):
            record[key] = None
        record["dataStructure"] = "grid" if raw.get("griddap") else "table"
        datasets.append(record)
    return [d for d in datasets if d.get("datasetID") != "allDatasets"]


def search_datasets(session, keyword):
    """
    Full-text search ERDDAP metadata and return matching dataset records.

    Hits ``/search/index.json?searchFor=<keyword>`` (Google-like syntax: words
    AND together, "quoted phrases" match exactly, -word excludes), paging
    through results in SEARCH_PAGE_SIZE chunks. Records are normalized to the
    same shape as fetch_all_datasets(); dataStructure is inferred from whether
    the hit exposes a tabledap or griddap endpoint. The search endpoint does
    not return spatial/temporal extents, so those keys are set to None.

    ERDDAP signals an empty result set with a 404 whose body says "no matching
    results"; that case returns an empty list. Any other 404 (or error) is
    raised rather than silently treated as zero matches.

    Args:
        session: A configured requests.Session
        keyword: Search term(s)

    Returns:
        list[dict]: Matching dataset records (empty list if nothing matches).
    """
    url = f"{ERDDAP_BASE}/search/index.json"
    datasets = []
    page = 1

    while True:
        params = {
            "searchFor": keyword,
            "page": page,
            "itemsPerPage": SEARCH_PAGE_SIZE,
        }
        resp = session.get(url, params=params, timeout=TIMEOUT)

        # ERDDAP returns 404 for an empty result set (only ever on page 1),
        # distinguished from real errors by the message in the body. Anything
        # else — bad query, server error masquerading as 404 — must surface
        # rather than be silently treated as zero matches.
        if (
            resp.status_code == 404
            and page == 1
            and "no matching results" in resp.text.lower()
        ):
            return []
        resp.raise_for_status()

        table = resp.json()["table"]
        raw_count = len(table["rows"])
        datasets.extend(_normalize_search_rows(table))

        # A short page means we've reached the last one; stop before requesting
        # a past-the-end page (which would itself 404). Compare the raw row
        # count, not the filtered list, so dropping the allDatasets meta-row
        # never looks like the end of results.
        if raw_count < SEARCH_PAGE_SIZE:
            break
        page += 1

    return datasets


def _numeric_id(dataset_id):
    """
    Extract the numeric BCO-DMO id from an ERDDAP datasetID.

    "bcodmo_dataset_3773_v3" -> "3773". Returns None if no numeric id is found
    (e.g. non-BCO-DMO datasets mirrored on the server).
    """
    parts = dataset_id.split("_")
    for part in parts:
        if part.isdigit():
            return part
    return None


def build_access_routes(dataset_id):
    """
    Return the candidate access URLs for a dataset across all known routes.

    Args:
        dataset_id: ERDDAP datasetID (e.g. "bcodmo_dataset_3773_v3")

    Returns:
        dict[str, str]: route name -> URL. Routes tied to the numeric landing
        page (ISO, landing) are omitted when no numeric id can be derived.
    """
    routes = {
        "erddap_info": f"{ERDDAP_BASE}/info/{dataset_id}/index.json",
        "erddap_metadata_das": f"{ERDDAP_BASE}/tabledap/{dataset_id}.das",
        "erddap_data_csv": f"{ERDDAP_BASE}/tabledap/{dataset_id}.csv",
        "erddap_files": f"{ERDDAP_BASE}/files/{dataset_id}/",
    }

    num_id = _numeric_id(dataset_id)
    if num_id:
        routes["landing_page"] = f"{WWW_BASE}/dataset/{num_id}"
        routes["iso_19115"] = f"{WWW_BASE}/dataset/{num_id}/iso"

    return routes


def probe_route(session, url):
    """
    Issue a lightweight request and report whether a route is reachable.

    Uses a ranged GET (first byte only) so we confirm availability without
    downloading large data files. Falls back gracefully on any error.

    Returns:
        dict: {"ok": bool, "status": int|None, "error": str|None}
    """
    try:
        resp = session.get(
            url,
            timeout=TIMEOUT,
            headers={"Range": "bytes=0-0"},
            stream=True,
        )
        # 200 (full) and 206 (partial) both mean the resource exists.
        ok = resp.status_code in (200, 206)
        resp.close()
        return {"ok": ok, "status": resp.status_code, "error": None}
    except requests.RequestException as e:
        return {"ok": False, "status": None, "error": str(e)}


def probe_dataset(session, dataset):
    """
    Attach access routes (and probe results) to a single dataset record.

    Args:
        session: A configured requests.Session
        dataset: A dataset dict from fetch_all_datasets()

    Returns:
        dict: the dataset record with an added "access" mapping of
        route -> {url, ok, status, error}.
    """
    routes = build_access_routes(dataset["datasetID"])
    access = {}
    for name, url in routes.items():
        result = probe_route(session, url)
        access[name] = {"url": url, **result}
    dataset = dict(dataset)
    dataset["access"] = access
    return dataset


def main():
    parser = argparse.ArgumentParser(
        description="Build a BCO-DMO ERDDAP dataset access inventory"
    )
    parser.add_argument(
        "--output",
        default="erddap_inventory.json",
        help="Output JSON file path (default: erddap_inventory.json)",
    )
    parser.add_argument(
        "--search",
        default=None,
        metavar="KEYWORD",
        help=(
            "Full-text search ERDDAP metadata instead of fetching the whole "
            'catalog. Google-like syntax: words AND together, "quoted '
            'phrases" match exactly, -word excludes.'
        ),
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Probe each dataset's access routes for reachability",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N datasets (useful with --probe)",
    )

    args = parser.parse_args()

    session = _session()

    try:
        if args.search:
            print(f"Searching ERDDAP metadata for: '{args.search}'", file=sys.stderr)
            datasets = search_datasets(session, args.search)
            print(f"  {len(datasets)} matching datasets.", file=sys.stderr)
        else:
            print("Fetching ERDDAP allDatasets catalog...", file=sys.stderr)
            datasets = fetch_all_datasets(session)
            print(f"  {len(datasets)} datasets in catalog.", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.limit is not None:
        datasets = datasets[: args.limit]
        print(f"  Limiting to first {len(datasets)}.", file=sys.stderr)

    if args.probe:
        print("Probing access routes per dataset...", file=sys.stderr)
        try:
            datasets = [
                probe_dataset(session, d)
                for d in tqdm(datasets, desc="Probing", unit="dataset")
            ]
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Still record the candidate routes, just without reachability checks.
        for d in datasets:
            d["access"] = {
                name: {"url": url}
                for name, url in build_access_routes(d["datasetID"]).items()
            }

    result = {
        "source": "erddap.bco-dmo.org",
        "erddap_base": ERDDAP_BASE,
        "search": args.search,
        "probed": args.probe,
        "count": len(datasets),
        "datasets": datasets,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(
        f"\nDone. {len(datasets)} datasets written to {output_path}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
