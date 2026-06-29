#!/usr/bin/env python3
"""
AODN metadata pipeline: fetch GeoNetwork XML → ISO 19139 → JSON-LD → N-Triples.

Usage:
    python run_pipeline.py --uuid 528f280c-b151-45c4-9526-e0746510a617
    python run_pipeline.py --input-xml ./AODN_GN4_depth_metadata.xml --output-dir ./output
    python run_pipeline.py --uuid-file uuids.txt --output-dir ./runs/batch
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pyld import jsonld
from pyoxigraph import DefaultGraph, RdfFormat, Store

from defs.depth_columns import enrich_jsonld_depth, iso19139_sibling_path
from depth_from_distribution import probe_depth_record

DEFAULT_GRAPH = DefaultGraph()

AODN_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG_API = (
    "https://catalogue-imos.aodn.org.au/geonetwork/srv/api"
)
TO_ISO19139_XSLT = AODN_DIR / "transformations/ISO19139/toISO19139.xsl"
TO_JSONLD_XSLT = (
    AODN_DIR / "ISO19139mapping/ISO19139ToSDODatasetStandalone1.0.xslt"
)
USER_AGENT = "DOOS-AODN-pipeline/1.0"
TIMEOUT = 30


def fetch_record_xml(uuid: str, catalog_api: str) -> str:
    """Fetch ISO 19115-3 XML for a GeoNetwork record UUID."""
    url = f"{catalog_api.rstrip('/')}/records/{uuid}/formatters/xml"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return response.read().decode("utf-8")
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} fetching {url}") from e
    except URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e.reason}") from e


def run_convert(input_xml: Path, output_xml: Path) -> None:
    """Run ISO 19115-3 → ISO 19139 via Saxon."""
    cmd = [
        sys.executable,
        str(AODN_DIR / "convert_script.py"),
        "-input",
        str(input_xml),
        "-xslt",
        str(TO_ISO19139_XSLT),
        "-output",
        str(output_xml),
    ]
    subprocess.run(cmd, check=True, cwd=AODN_DIR)


def run_jsonld_transform(input_xml: Path, output_json: Path) -> dict:
    """Run ISO 19139 → JSON-LD via lxml and return the parsed document."""
    cmd = [
        sys.executable,
        str(AODN_DIR / "aodnTransform.py"),
        "-xml",
        str(input_xml),
        "-xslt",
        str(TO_JSONLD_XSLT),
        "-output",
        str(output_json),
    ]
    subprocess.run(cmd, check=True, cwd=AODN_DIR)
    with output_json.open(encoding="utf-8") as handle:
        return json.load(handle)


def export_nt(documents: list[dict], output_nt: Path) -> int:
    """Normalize JSON-LD documents to N-Triples via pyoxigraph."""
    store = Store()
    for doc in documents:
        normalized = jsonld.normalize(
            doc,
            {"algorithm": "URDNA2015", "format": "application/n-quads"},
        )
        if normalized and normalized.strip():
            store.load(
                io.StringIO(normalized),
                RdfFormat.N_QUADS,
                base_iri=None,
                to_graph=DEFAULT_GRAPH,
            )
    triple_count = len(list(store.quads_for_pattern(None, None, None, DEFAULT_GRAPH)))
    output_nt.parent.mkdir(parents=True, exist_ok=True)
    with output_nt.open("wb") as handle:
        store.dump(handle, RdfFormat.N_TRIPLES, from_graph=DEFAULT_GRAPH)
    return triple_count


def process_record(
    *,
    uuid: str | None,
    input_xml: Path | None,
    output_dir: Path,
    catalog_api: str,
    write_nt: bool,
    probe_depth: bool = False,
    depth_try_all: bool = False,
    depth_verbose: bool = False,
    depth_engine: str = "pandas",
    depth_crawl_prefix: bool = True,
    enrich_jsonld: bool = False,
) -> dict:
    """Transform one record and write artifacts under output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    record_id = uuid or input_xml.stem

    if input_xml is None:
        if not uuid:
            raise ValueError("Either --uuid or --input-xml is required")
        source_xml = output_dir / f"{uuid}_source.xml"
        source_xml.write_text(fetch_record_xml(uuid, catalog_api), encoding="utf-8")
    else:
        source_xml = input_xml.resolve()
        record_id = source_xml.stem

    iso19139_xml = output_dir / f"{record_id}_iso19139.xml"
    jsonld_path = output_dir / f"{record_id}.jsonld"

    run_convert(source_xml, iso19139_xml)
    doc = run_jsonld_transform(iso19139_xml, jsonld_path)

    manifest = {
        "record_id": record_id,
        "source_xml": str(source_xml),
        "iso19139_xml": str(iso19139_xml),
        "jsonld": str(jsonld_path),
        "dataset_id": doc.get("@id"),
        "variable_measured_count": len(doc.get("variableMeasured", [])),
        "has_dep_below_surf": any(
            item.get("name") == "DepBelowSurf"
            for item in doc.get("variableMeasured", [])
            if isinstance(item, dict)
        ),
    }

    if probe_depth or enrich_jsonld:
        depth_report_path = output_dir / f"{record_id}_depth_report.json"
        iso_path = iso19139_sibling_path(jsonld_path)
        report, depth_range = probe_depth_record(
            doc,
            jsonld_path=jsonld_path,
            iso19139_path=iso_path if iso_path.is_file() else None,
            try_all=depth_try_all,
            verbose=depth_verbose,
            engine=depth_engine,  # type: ignore[arg-type]
            crawl_prefix=depth_crawl_prefix,
        )
        depth_report_path.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["depth_report"] = str(depth_report_path)
        if depth_range:
            manifest["observed_depth_min"] = depth_range["min"]
            manifest["observed_depth_max"] = depth_range["max"]

        if enrich_jsonld and depth_range:
            doc = enrich_jsonld_depth(doc, depth_range)
            jsonld_path.write_text(
                json.dumps(doc, indent=2) + "\n",
                encoding="utf-8",
            )
            manifest["jsonld_enriched"] = True

    if write_nt:
        nt_path = output_dir / f"{record_id}.nt"
        manifest["nt"] = str(nt_path)
        manifest["triple_count"] = export_nt([doc], nt_path)

    return manifest


def load_uuid_file(path: Path) -> list[str]:
    """Load UUIDs from a text file (one per line, # comments allowed)."""
    uuids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        uuids.append(line.split()[0])
    return uuids


def main():
    parser = argparse.ArgumentParser(
        description="AODN GeoNetwork metadata → schema.org JSON-LD → N-Triples"
    )
    parser.add_argument("--uuid", type=str, help="GeoNetwork record UUID")
    parser.add_argument(
        "--uuid-file",
        type=str,
        help="Text file with one UUID per line",
    )
    parser.add_argument(
        "--input-xml",
        type=str,
        help="Local ISO 19115-3/19139 XML file (skip fetch)",
    )
    parser.add_argument(
        "--catalog-api",
        type=str,
        default=DEFAULT_CATALOG_API,
        help=f"GeoNetwork API base URL (default: {DEFAULT_CATALOG_API})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: ./runs/<timestamp>)",
    )
    parser.add_argument(
        "--no-nt",
        action="store_true",
        help="Skip N-Triples export",
    )
    parser.add_argument(
        "--probe-depth",
        action="store_true",
        help="Download tabular distributions and probe depth column min/max",
    )
    parser.add_argument(
        "--depth-try-all",
        action="store_true",
        help="With --probe-depth, probe every tabular/prefix distribution",
    )
    parser.add_argument(
        "--depth-verbose",
        action="store_true",
        help="With --probe-depth, log skipped/failed distributions to stderr",
    )
    parser.add_argument(
        "--depth-engine",
        choices=["pandas", "polars"],
        default="pandas",
        help="Tabular loader for csv/tsv/parquet when probing depth",
    )
    parser.add_argument(
        "--no-crawl-prefix",
        action="store_true",
        help="With --probe-depth, skip expanding ?prefix= S3 listing URLs",
    )
    parser.add_argument(
        "--enrich-jsonld",
        action="store_true",
        help="Write observed depth min/max into DepBelowSurf (implies --probe-depth)",
    )
    args = parser.parse_args()

    if not args.uuid and not args.uuid_file and not args.input_xml:
        parser.error("Provide --uuid, --uuid-file, or --input-xml")

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        output_dir = AODN_DIR / "runs" / stamp

    write_nt = not args.no_nt
    probe_depth = args.probe_depth or args.enrich_jsonld
    depth_kwargs = {
        "probe_depth": probe_depth,
        "depth_try_all": args.depth_try_all,
        "depth_verbose": args.depth_verbose,
        "depth_engine": args.depth_engine,
        "depth_crawl_prefix": not args.no_crawl_prefix,
        "enrich_jsonld": args.enrich_jsonld,
    }
    manifests = []

    try:
        if args.input_xml:
            manifests.append(
                process_record(
                    uuid=None,
                    input_xml=Path(args.input_xml),
                    output_dir=output_dir,
                    catalog_api=args.catalog_api,
                    write_nt=write_nt,
                    **depth_kwargs,
                )
            )
        elif args.uuid:
            manifests.append(
                process_record(
                    uuid=args.uuid,
                    input_xml=None,
                    output_dir=output_dir,
                    catalog_api=args.catalog_api,
                    write_nt=write_nt,
                    **depth_kwargs,
                )
            )
        elif args.uuid_file:
            for uuid in load_uuid_file(Path(args.uuid_file)):
                record_dir = output_dir / uuid
                manifests.append(
                    process_record(
                        uuid=uuid,
                        input_xml=None,
                        output_dir=record_dir,
                        catalog_api=args.catalog_api,
                        write_nt=write_nt,
                        **depth_kwargs,
                    )
                )

        run_manifest = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "output_dir": str(output_dir.resolve()),
            "records": manifests,
        }
        manifest_path = output_dir / "run.json"
        manifest_path.write_text(
            json.dumps(run_manifest, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(run_manifest, indent=2))
    except (RuntimeError, subprocess.CalledProcessError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()