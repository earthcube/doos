#!/usr/bin/env python3
"""
Download a file from a URL and create an Attached RO-Crate Package (1.2).

Produces a directory containing:
  - ro-crate-metadata.json  (RO-Crate Metadata Document)
  - <downloaded-file>       (payload)

Usage:
    python make_rocrate.py <url> [--out-dir DIR] [--name NAME] [--description TEXT]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

_USER_AGENT = "DOOS-rocrate-skill/1.0 (+https://earthcube.org)"
_TIMEOUT = 30
_DEFAULT_LICENSE = "https://creativecommons.org/publicdomain/zero/1.0/"


def _filename_from_url(url: str) -> str:
    """Derive a filename from the URL path."""
    path = urlparse(url).path
    name = unquote(Path(path).name)
    return name or "download"


def _filename_from_disposition(header: str | None) -> str | None:
    """Parse filename from Content-Disposition header."""
    if not header:
        return None
    match = re.search(
        r'filename\*?=(?:UTF-8\'\')?"?([^";\n]+)"?',
        header,
        re.IGNORECASE,
    )
    if match:
        return unquote(match.group(1).strip())
    return None


def download_file(url: str) -> tuple[bytes, str, str, str]:
    """
    Download a file from a URL.

    Returns:
        Tuple of (body bytes, filename, content_type, final_url).
    """
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            body = resp.read()
            content_type = resp.headers.get("Content-Type", "") or ""
            disposition = resp.headers.get("Content-Disposition")
            final_url = resp.geturl()
    except Exception as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        sys.exit(1)

    filename = _filename_from_disposition(disposition) or _filename_from_url(final_url)
    if filename == "ro-crate-metadata.json":
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
        filename = f"download{ext}"

    return body, filename, content_type, final_url


def build_metadata(
    filename: str,
    source_url: str,
    content_size: int,
    encoding_format: str,
    download_time: str,
    *,
    crate_name: str | None = None,
    crate_description: str | None = None,
    license_url: str = _DEFAULT_LICENSE,
) -> dict:
    """Build a minimal RO-Crate 1.2 metadata document."""
    name = crate_name or filename
    description = crate_description or f"File downloaded from {source_url}"

    return {
        "@context": "https://w3id.org/ro/crate/1.2/context",
        "@graph": [
            {
                "@id": "ro-crate-metadata.json",
                "@type": "CreativeWork",
                "about": {"@id": "./"},
                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"},
            },
            {
                "@id": "./",
                "@type": "Dataset",
                "name": name,
                "description": description,
                "datePublished": download_time[:10],
                "license": {"@id": license_url},
                "hasPart": [{"@id": filename}],
            },
            {
                "@id": filename,
                "@type": "File",
                "name": filename,
                "description": f"Downloaded from {source_url}",
                "contentSize": str(content_size),
                "encodingFormat": encoding_format,
                "contentUrl": source_url,
                "sdDatePublished": download_time,
            },
            {
                "@id": license_url,
                "@type": "CreativeWork",
                "name": "CC0 1.0 Universal",
                "identifier": license_url,
            },
            {
                "@id": "#download",
                "@type": "CreateAction",
                "name": "Download file",
                "endTime": download_time,
                "object": {"@id": source_url},
                "result": {"@id": filename},
            },
        ],
    }


def make_rocrate(
    url: str,
    out_dir: Path,
    *,
    name: str | None = None,
    description: str | None = None,
    license_url: str = _DEFAULT_LICENSE,
) -> dict:
    """
    Download a URL and write an Attached RO-Crate Package to out_dir.

    Returns:
        Summary dict with paths and file metadata.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    body, filename, content_type, final_url = download_file(url)
    dest = out_dir / filename
    dest.write_bytes(body)

    media_type = content_type.split(";")[0].strip()
    encoding = media_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    metadata = build_metadata(
        filename,
        final_url,
        len(body),
        encoding,
        now,
        crate_name=name,
        crate_description=description,
        license_url=license_url,
    )

    meta_path = out_dir / "ro-crate-metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return {
        "crate_dir": str(out_dir.resolve()),
        "metadata_file": str(meta_path.resolve()),
        "data_file": str(dest.resolve()),
        "filename": filename,
        "content_size": len(body),
        "encoding_format": encoding,
        "source_url": final_url,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Download a file and create an Attached RO-Crate Package (1.2).",
    )
    parser.add_argument("url", help="URL of the file to download")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("ro-crate-output"),
        help="Output directory for the RO-Crate (default: ./ro-crate-output)",
    )
    parser.add_argument("--name", help="Root Dataset name (default: filename)")
    parser.add_argument("--description", help="Root Dataset description")
    parser.add_argument(
        "--license",
        default=_DEFAULT_LICENSE,
        help=f"License URI for the crate (default: {_DEFAULT_LICENSE})",
    )
    args = parser.parse_args()

    summary = make_rocrate(
        args.url,
        args.out_dir,
        name=args.name,
        description=args.description,
        license_url=args.license,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()