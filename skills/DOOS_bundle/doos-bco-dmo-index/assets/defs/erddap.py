"""ERDDAP catalog enumeration, search, and access-route inventory."""

from pathlib import Path
from urllib.parse import quote

import requests
from tqdm import tqdm

from defs.common import TIMEOUT, log, make_session, write_json

ERDDAP_BASE = "https://erddap.bco-dmo.org/erddap"
WWW_BASE = "https://www.bco-dmo.org"

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

SEARCH_COLUMN_MAP = {
    "Dataset ID": "datasetID",
    "Title": "title",
    "Institution": "institution",
    "Summary": "summary",
    "Info": "infoUrl",
    "ISO 19115": "iso19115",
}

SEARCH_PAGE_SIZE = 1000


def fetch_all_datasets(session: requests.Session) -> list[dict]:
    """
    Enumerate every active dataset via ERDDAP's allDatasets table.

    Returns:
        list[dict]: One dict per dataset keyed by ALLDATASETS_COLUMNS.
    """
    query = quote(",".join(ALLDATASETS_COLUMNS), safe=",")
    url = f"{ERDDAP_BASE}/tabledap/allDatasets.json?{query}"

    resp = session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()

    table = resp.json()["table"]
    columns = table["columnNames"]
    rows = table["rows"]

    datasets = [dict(zip(columns, row)) for row in rows]
    return [d for d in datasets if d.get("datasetID") != "allDatasets"]


def _normalize_search_rows(table: dict) -> list[dict]:
    """Map an ERDDAP search result table onto fetch_all_datasets()-shaped records."""
    columns = table["columnNames"]
    datasets = []
    for row in table["rows"]:
        raw = dict(zip(columns, row))
        record = {
            machine: raw.get(label) for label, machine in SEARCH_COLUMN_MAP.items()
        }
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


def search_datasets(session: requests.Session, keyword: str) -> list[dict]:
    """
    Full-text search ERDDAP metadata and return matching dataset records.
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

        if raw_count < SEARCH_PAGE_SIZE:
            break
        page += 1

    return datasets


def numeric_id(dataset_id: str) -> str | None:
    """Extract the numeric BCO-DMO id from an ERDDAP datasetID."""
    for part in dataset_id.split("_"):
        if part.isdigit():
            return part
    return None


def build_access_routes(dataset_id: str) -> dict[str, str]:
    """Return candidate access URLs for a dataset across all known routes."""
    routes = {
        "erddap_info": f"{ERDDAP_BASE}/info/{dataset_id}/index.json",
        "erddap_metadata_das": f"{ERDDAP_BASE}/tabledap/{dataset_id}.das",
        "erddap_data_csv": f"{ERDDAP_BASE}/tabledap/{dataset_id}.csv",
        "erddap_files": f"{ERDDAP_BASE}/files/{dataset_id}/",
    }

    num_id = numeric_id(dataset_id)
    if num_id:
        routes["landing_page"] = f"{WWW_BASE}/dataset/{num_id}"
        routes["iso_19115"] = f"{WWW_BASE}/dataset/{num_id}/iso"

    return routes


def probe_route(session: requests.Session, url: str) -> dict:
    """
    Issue a lightweight ranged GET and report whether a route is reachable.
    """
    try:
        resp = session.get(
            url,
            timeout=TIMEOUT,
            headers={"Range": "bytes=0-0"},
            stream=True,
        )
        ok = resp.status_code in (200, 206)
        resp.close()
        return {"ok": ok, "status": resp.status_code, "error": None}
    except requests.RequestException as e:
        return {"ok": False, "status": None, "error": str(e)}


def probe_dataset(session: requests.Session, dataset: dict) -> dict:
    """Attach probed access routes to a single dataset record."""
    routes = build_access_routes(dataset["datasetID"])
    access = {}
    for name, url in routes.items():
        result = probe_route(session, url)
        access[name] = {"url": url, **result}
    dataset = dict(dataset)
    dataset["access"] = access
    return dataset


def build_inventory(
    datasets: list[dict],
    *,
    search: str | None,
    probed: bool,
) -> dict:
    """Wrap dataset records in the standard inventory envelope."""
    return {
        "source": "erddap.bco-dmo.org",
        "erddap_base": ERDDAP_BASE,
        "search": search,
        "probed": probed,
        "count": len(datasets),
        "datasets": datasets,
    }


def run_scan_erddap(
    *,
    output: Path,
    search: str | None = None,
    probe: bool = False,
    limit: int | None = None,
) -> dict:
    """
    Build a BCO-DMO ERDDAP dataset access inventory and write it to disk.

    Args:
        output: Path for the inventory JSON file
        search: Optional full-text search keyword (omit to fetch full catalog)
        probe: Probe each dataset's access routes for reachability
        limit: Process only the first N datasets

    Returns:
        dict: Inventory payload written to ``output``
    """
    session = make_session()

    if search:
        log(f"Searching ERDDAP metadata for: '{search}'")
        datasets = search_datasets(session, search)
        log(f"  {len(datasets)} matching datasets.")
    else:
        log("Fetching ERDDAP allDatasets catalog...")
        datasets = fetch_all_datasets(session)
        log(f"  {len(datasets)} datasets in catalog.")

    if limit is not None:
        datasets = datasets[:limit]
        log(f"  Limiting to first {len(datasets)}.")

    if probe:
        log("Probing access routes per dataset...")
        datasets = [
            probe_dataset(session, d)
            for d in tqdm(datasets, desc="Probing", unit="dataset")
        ]
    else:
        for d in datasets:
            d["access"] = {
                name: {"url": url}
                for name, url in build_access_routes(d["datasetID"]).items()
            }

    result = build_inventory(datasets, search=search, probed=probe)
    write_json(output, result)
    log(f"\nDone. {len(datasets)} datasets written to {output}")
    return result