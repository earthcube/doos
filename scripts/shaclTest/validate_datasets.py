#!/usr/bin/env python3
"""Fetch schema:Dataset records from a SPARQL endpoint and validate them
with pwin/SHACL_Engine against a SHACL shapes graph.

The shapes graph may be an HTTP(S) URL or a local Turtle file.

Example:
  python3 validate_datasets.py
  python3 validate_datasets.py --shapes ../../SHACL/depth_one.ttl
  python3 validate_datasets.py --limit 0
  python3 validate_datasets.py --limit ALL --endpoint URL --shapes URL
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import shacl

DEFAULT_ENDPOINT = "https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans"
DEFAULT_SHAPES = (
    "https://raw.githubusercontent.com/OHDSI/gaiaCatalog/"
    "refs/heads/main/shapeGraphs/googleRecommended.ttl"
)
DEFAULT_OUT = Path(__file__).resolve().parent / "shacl_results"

CONSTRUCT_QUERY = """
PREFIX schema: <https://schema.org/>
CONSTRUCT {{
  ?s ?p ?o .
  ?o ?p2 ?o2 .
}}
WHERE {{
  {{
    SELECT DISTINCT ?s WHERE {{
      ?s a schema:Dataset .
    }}{limit_clause}
  }}
  ?s ?p ?o .
  OPTIONAL {{ ?o ?p2 ?o2 . }}
}}
"""

DATASET_TYPE = "https://schema.org/Dataset"
NT_TYPE_RE = re.compile(
    r"^<([^>]+)>\s+<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>\s+<([^>]+)>\s*\."
)


def parse_limit(value: str) -> int | None:
    """Parse --limit. 0 or ALL means no SPARQL LIMIT (return every Dataset)."""
    stripped = value.strip()
    if stripped.lower() in {"all", "*"}:
        return None
    try:
        n = int(stripped)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"limit must be a non-negative integer or ALL (got {value!r})"
        ) from exc
    if n < 0:
        raise argparse.ArgumentTypeError("limit must be >= 0 (0 or ALL means no LIMIT)")
    if n == 0:
        return None
    return n


def limit_clause(limit: int | None) -> str:
    if limit is None:
        return ""
    return f"\n    LIMIT {limit}"


def http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "dataset-shacl-validate/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def is_http_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def shapes_path_from_source(source: str) -> Path:
    if source.startswith("file:"):
        parsed = urllib.parse.urlparse(source)
        return Path(urllib.parse.unquote(parsed.path))
    return Path(source)


def shapes_basename(source: str) -> str:
    if is_http_url(source):
        name = Path(urllib.parse.urlparse(source).path).name
    else:
        name = shapes_path_from_source(source).name
    return name or "shapes.ttl"


def load_shapes(source: str) -> str:
    """Return Turtle text from an HTTP(S) URL or a local file."""
    if is_http_url(source):
        return http_get(source).decode("utf-8")
    path = shapes_path_from_source(source)
    if not path.is_file():
        raise FileNotFoundError(f"Shapes file not found: {path}")
    return path.read_text(encoding="utf-8")


def sparql_construct(endpoint: str, query: str, timeout: int = 180) -> str:
    req = urllib.request.Request(
        endpoint,
        data=query.encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/n-triples",
            "Content-Type": "application/sparql-query",
            "User-Agent": "dataset-shacl-validate/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    return body.decode("utf-8")


def dataset_iris(nt_text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for line in nt_text.splitlines():
        m = NT_TYPE_RE.match(line.strip())
        if not m:
            continue
        s, t = m.group(1), m.group(2)
        if t == DATASET_TYPE and s not in seen:
            seen.add(s)
            found.append(s)
    return found


def nt_term_to_plain(term: str | None) -> str | None:
    if term is None:
        return None
    if term.startswith("<") and term.endswith(">"):
        return term[1:-1]
    return term


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="SPARQL endpoint URL")
    parser.add_argument(
        "--shapes",
        default=DEFAULT_SHAPES,
        help="HTTP(S) URL or local path to a Turtle SHACL shapes graph",
    )
    parser.add_argument(
        "--limit",
        type=parse_limit,
        default=100,
        help="Number of schema:Dataset IRIs to CONSTRUCT. 0 or ALL omits LIMIT",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory")
    args = parser.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    try:
        shapes_ttl = load_shapes(args.shapes)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Shapes download failed: {exc}", file=sys.stderr)
        return 1
    print(f"Shapes:   {args.shapes}")
    shapes_path = out / shapes_basename(args.shapes)
    shapes_path.write_text(shapes_ttl, encoding="utf-8")
    print(f"  saved {shapes_path} ({len(shapes_ttl)} bytes)")

    query = CONSTRUCT_QUERY.format(limit_clause=limit_clause(args.limit))
    (out / "construct.rq").write_text(query.strip() + "\n", encoding="utf-8")
    print(f"SPARQL:   {args.endpoint}")
    if args.limit is None:
        print("  CONSTRUCT 1-hop neighbourhood of all schema:Dataset IRIs")
    else:
        print(f"  CONSTRUCT 1-hop neighbourhood of {args.limit} schema:Dataset IRIs")
    try:
        data_nt = sparql_construct(args.endpoint, query)
    except urllib.error.HTTPError as exc:
        print(f"SPARQL request failed: {exc.code} {exc.reason}", file=sys.stderr)
        print(exc.read().decode("utf-8", errors="replace")[:2000], file=sys.stderr)
        return 1

    data_path = out / "datasets.nt"
    data_path.write_text(data_nt, encoding="utf-8")
    datasets = dataset_iris(data_nt)
    n_triples = sum(1 for line in data_nt.splitlines() if line.strip() and not line.startswith("#"))
    print(f"  got {n_triples} triples covering {len(datasets)} Dataset resources")
    print(f"  saved {data_path}")

    if not datasets:
        print("No schema:Dataset resources in CONSTRUCT result; aborting.", file=sys.stderr)
        return 2

    print("Validating with pwin/SHACL_Engine (Python bindings)…")
    compiled = shacl.Shapes.from_turtle(shapes_ttl)
    report = compiled.validate_turtle(data_nt)

    report_ttl = report.serialize()
    report_path = out / "validation_report.ttl"
    report_path.write_text(report_ttl, encoding="utf-8")

    rows = []
    by_component: Counter[str] = Counter()
    by_path: Counter[str] = Counter()
    by_focus: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()

    for r in report.results:
        focus = nt_term_to_plain(r.focus_node) or ""
        path = nt_term_to_plain(r.path) or ""
        component = r.component or ""
        severity = r.severity or ""
        by_component[component] += 1
        by_path[path] += 1
        by_focus[focus] += 1
        by_severity[severity] += 1
        rows.append(
            {
                "severity": severity,
                "component": component,
                "focus_node": focus,
                "path": path,
                "value": nt_term_to_plain(r.value),
                "source_shape": r.source_shape,
                "message": r.message or ("; ".join(r.messages) if r.messages else ""),
            }
        )

    results_csv = out / "validation_results.csv"
    with results_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "severity",
                "component",
                "focus_node",
                "path",
                "value",
                "source_shape",
                "message",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    focus_set = set(datasets)
    datasets_with_results = {iri for iri in by_focus if iri in focus_set}
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "pwin/SHACL_Engine (Python package shacl)",
        "endpoint": args.endpoint,
        "shapes_source": args.shapes,
        "shapes_kind": "url" if is_http_url(args.shapes) else "file",
        "requested_datasets": args.limit,
        "datasets_in_graph": len(datasets),
        "triples_in_graph": n_triples,
        "conforms": bool(report.conforms),
        "result_count": len(report),
        "datasets_with_results": len(datasets_with_results),
        "severity_counts": dict(by_severity),
        "results_by_component": dict(by_component.most_common()),
        "results_by_path": dict(by_path.most_common()),
        "results_per_dataset": {
            iri: by_focus.get(iri, 0) for iri in datasets
        },
        "dataset_iris": datasets,
        "outputs": {
            "data": str(data_path),
            "shapes": str(shapes_path),
            "report_ttl": str(report_path),
            "results_csv": str(results_csv),
        },
    }
    summary_path = out / "validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"conforms: {report.conforms}")
    print(f"results:  {len(report)}")
    print(f"severity: {dict(by_severity)}")
    print("by constraint component:")
    for name, n in by_component.most_common():
        print(f"  {n:6d}  {name}")
    print("by property path:")
    for name, n in by_path.most_common():
        print(f"  {n:6d}  {name or '(node-level)'}")
    print()
    print("Wrote:")
    print(f"  {data_path}")
    print(f"  {shapes_path}")
    print(f"  {report_path}")
    print(f"  {results_csv}")
    print(f"  {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
