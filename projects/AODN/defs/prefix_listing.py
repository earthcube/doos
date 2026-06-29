"""Resolve tabular object URLs from AODN S3 prefix-listing distributions."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

from defs.depth_columns import TABULAR_EXTENSIONS, classify_distribution

S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

# Hostname → bucket name (from data.aodn.org.au/aodn.js getS3BucketByUrl mapping).
HOST_BUCKET_MAP = {
    "data.aodn.org.au": "imos-data",
    "imos-data.prod.aodn.org.au": "imos-data",
    "imos-data.aodn.org.au": "imos-data",
    "data-test.aodn.org.au": "imos-test-data",
    "imos-test-data.prod.aodn.org.au": "imos-test-data",
    "imos-test-data.aodn.org.au": "imos-test-data",
}

USER_AGENT = "DOOS-AODN-depth-probe/1.0"
TIMEOUT = 30
MAX_PREFIX_OBJECTS = 200


def prefix_from_listing_url(url: str) -> str | None:
    """Extract the S3 prefix query parameter from a listing URL."""
    query = parse_qs(urlparse(url).query)
    values = query.get("prefix")
    if not values:
        return None
    prefix = unquote(values[0]).strip()
    return prefix or None


def bucket_for_host(hostname: str) -> str | None:
    """Return the S3 bucket name for an AODN data hostname."""
    return HOST_BUCKET_MAP.get(hostname.lower())


def public_object_url(hostname: str, key: str) -> str:
    """Build a public HTTP URL for an object key under an AODN data host."""
    return f"https://{hostname}/{key.lstrip('/')}"


def list_s3_objects(
    bucket: str,
    prefix: str,
    *,
    region: str = "ap-southeast-2",
    max_keys: int = MAX_PREFIX_OBJECTS,
) -> list[dict[str, Any]]:
    """List object keys under an S3 prefix via the public ListObjectsV2 API."""
    base = f"https://{bucket}.s3.{region}.amazonaws.com/"
    query = f"list-type=2&prefix={prefix}&max-keys={max_keys}"
    request = Request(f"{base}?{query}", headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            payload = response.read()
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} listing s3://{bucket}/{prefix}") from e
    except URLError as e:
        raise RuntimeError(f"Network error listing s3://{bucket}/{prefix}: {e.reason}") from e

    root = ET.fromstring(payload)
    objects: list[dict[str, Any]] = []
    for entry in root.findall("s3:Contents", S3_NS):
        key_el = entry.find("s3:Key", S3_NS)
        size_el = entry.find("s3:Size", S3_NS)
        if key_el is None or not key_el.text:
            continue
        key = key_el.text
        size = int(size_el.text) if size_el is not None and size_el.text else 0
        objects.append({"key": key, "size": size})
    return objects


def rank_prefix_objects(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank tabular objects discovered under a prefix listing."""

    def score(item: dict[str, Any]) -> tuple[int, int]:
        key = item["key"]
        url = f"https://imos-data.s3.ap-southeast-2.amazonaws.com/{key}"
        kind = classify_distribution(url)
        if kind != "tabular":
            return (-1, 0)

        points = 0
        lowered = key.lower()
        if any(token in lowered for token in ("summary", "processed", "data")):
            points += 3
        if "depth" in lowered:
            points += 2
        if lowered.endswith((".csv", ".tsv", ".parquet")):
            points += 2
        if lowered.endswith((".xls", ".xlsx", ".xlsm")):
            points += 1
        return (points, int(item.get("size") or 0))

    ranked = sorted(objects, key=score, reverse=True)
    return [item for item in ranked if score(item)[0] >= 0]


def tabular_urls_from_prefix(
    listing_url: str,
    *,
    max_objects: int = MAX_PREFIX_OBJECTS,
) -> list[dict[str, str]]:
    """Resolve downloadable tabular URLs from an AODN ?prefix= listing URL."""
    parsed = urlparse(listing_url)
    prefix = prefix_from_listing_url(listing_url)
    if not prefix:
        raise ValueError(f"prefix listing URL has no prefix parameter: {listing_url}")

    bucket = bucket_for_host(parsed.hostname or "")
    if not bucket:
        raise ValueError(f"unknown AODN data host for prefix listing: {parsed.hostname}")

    objects = list_s3_objects(bucket, prefix, max_keys=max_objects)
    ranked = rank_prefix_objects(objects)[:max_objects]
    hostname = parsed.hostname or "data.aodn.org.au"

    results: list[dict[str, str]] = []
    for item in ranked:
        key = item["key"]
        ext = f".{key.rsplit('.', 1)[-1].lower()}" if "." in key else ""
        if ext not in TABULAR_EXTENSIONS:
            continue
        results.append(
            {
                "key": key,
                "url": public_object_url(hostname, key),
                "name": key.rsplit("/", 1)[-1],
            }
        )
    return results