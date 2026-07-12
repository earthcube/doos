#!/usr/bin/env python3
"""
Load DOOS provider outputs into a running Oxigraph server.

Reads a YAML config listing provider sources (N-Quads / N-Triples / JSON-LD,
files or directories) and pushes them to an Oxigraph server over the SPARQL
Graph Store HTTP Protocol. Pair this with build/Dockerfile, which starts an
in-memory Oxigraph server with a union default graph.

Optionally export the full store (all named graphs) as a single N-Quads file
via GET /store after loading.

Usage:
  # 1. start the server (in-memory)
  docker build -t doos-oxigraph build/
  docker run --rm --network host doos-oxigraph

  # 2. load the configured sources (and optionally dump N-Quads)
  python scripts/loadToOxigraph/loadToOxigraph.py --wait
  python scripts/loadToOxigraph/loadToOxigraph.py --wait --export output/doos.nq

  # 3. dump an already-loaded store without re-loading sources
  python scripts/loadToOxigraph/loadToOxigraph.py --export-only --export output/doos.nq

  # 4. test the endpoint
  python scripts/sparqlQueryl.py http://localhost:7878/query --query SPARQL/get100.rq
"""

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
import yaml
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CONFIG = SCRIPT_DIR / "oxigraph_load.yaml"
USER_AGENT = "DOOS-OxigraphLoader/1.0"
HTTP_TIMEOUT = 30
# Full-store dumps can be large; allow a long read timeout (connect stays short).
EXPORT_TIMEOUT = (HTTP_TIMEOUT, 600)
EXPORT_CHUNK_SIZE = 1 << 20  # 1 MiB

# format -> (mime type, is_quads, [file extensions])
FORMATS = {
    "nt": ("application/n-triples", False, ["nt"]),
    "nq": ("application/n-quads", True, ["nq"]),
    "ttl": ("text/turtle", False, ["ttl"]),
    "trig": ("application/trig", True, ["trig"]),
    "jsonld": ("application/ld+json", False, ["jsonld", "json"]),
}


def resolve_files(path: Path, exts: list[str]) -> list[Path]:
    """Return the files for a source path (a single file or a directory)."""
    if path.is_file():
        return [path]
    if path.is_dir():
        files: list[Path] = []
        for ext in exts:
            files.extend(sorted(path.glob(f"*.{ext}")))
        return files
    return []


def wait_for_server(endpoint: str, retries: int = 30, delay: float = 1.0) -> None:
    """Block until the SPARQL endpoint answers, or exit after retries."""
    query_url = f"{endpoint.rstrip('/')}/query"
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(retries):
        try:
            resp = requests.get(
                query_url,
                params={"query": "ASK { ?s ?p ?o }"},
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
            if resp.ok:
                return
        except requests.RequestException:
            pass
        if attempt < retries - 1:
            time.sleep(delay)
    print(
        f"Error: Oxigraph not reachable at {endpoint} after {retries} attempts",
        file=sys.stderr,
    )
    sys.exit(1)


def post_data(store_url: str, data: bytes, mime: str, graph: str | None) -> None:
    """POST RDF bytes to the Graph Store endpoint, optionally into a graph."""
    headers = {"User-Agent": USER_AGENT, "Content-Type": mime}
    params = {} if graph is None else {"graph": graph}
    # Build the URL ourselves so the graph IRI is encoded exactly once.
    url = store_url
    if graph is not None:
        url = f"{store_url}?graph={quote(graph, safe='')}"
        params = {}
    resp = requests.post(
        url, data=data, headers=headers, params=params, timeout=HTTP_TIMEOUT
    )
    resp.raise_for_status()


def load_source(endpoint: str, source: dict) -> int:
    """Load one configured source. Returns the number of files loaded."""
    name = source.get("name", "?")
    fmt = source.get("format")
    if fmt not in FORMATS:
        raise ValueError(f"source '{name}': unknown format '{fmt}'")
    mime, is_quads, exts = FORMATS[fmt]

    graph = source.get("graph")
    if is_quads and graph:
        print(
            f"  note: source '{name}' is a quad format; ignoring 'graph' "
            f"(graph names come from the data)",
            file=sys.stderr,
        )
        graph = None
    if not is_quads and not graph:
        raise ValueError(
            f"source '{name}': triple format '{fmt}' requires a 'graph' IRI"
        )

    raw_path = Path(source["path"])
    path = raw_path if raw_path.is_absolute() else REPO_ROOT / raw_path
    files = resolve_files(path, exts)
    if not files:
        print(f"  warning: source '{name}': no files at {path}", file=sys.stderr)
        return 0

    store_url = f"{endpoint.rstrip('/')}/store"

    # Line-based RDF (nt/nq/ttl/trig) concatenates cleanly -> one request.
    # JSON-LD is one JSON document per file -> one request per file.
    if fmt == "jsonld":
        for f in tqdm(files, desc=f"{name} ({fmt})", unit="file"):
            post_data(store_url, f.read_bytes(), mime, graph)
    else:
        blob = b"\n".join(f.read_bytes() for f in files)
        with tqdm(total=1, desc=f"{name} ({fmt}, {len(files)} file(s))") as bar:
            post_data(store_url, blob, mime, graph)
            bar.update(1)

    return len(files)


def export_nquads(endpoint: str, output: Path) -> None:
    """Dump the full Oxigraph dataset as N-Quads to *output*.

    Uses GET /store with Accept: application/n-quads so named graphs are
    preserved in the fourth column. Streams the body to disk.
    """
    store_url = f"{endpoint.rstrip('/')}/store"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/n-quads",
    }
    output = Path(output)
    if output.parent and str(output.parent) not in (".", ""):
        output.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nExporting store to {output} (application/n-quads)...")
    with requests.get(
        store_url,
        headers=headers,
        stream=True,
        timeout=EXPORT_TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        nbytes = 0
        with output.open("wb") as fh:
            for chunk in resp.iter_content(chunk_size=EXPORT_CHUNK_SIZE):
                if chunk:
                    fh.write(chunk)
                    nbytes += len(chunk)

    print(f"  wrote {nbytes:,} bytes to {output}")


def graph_count(endpoint: str, top: int = 15) -> None:
    """Print total triple count and a capped named-graph list for a sanity check."""
    query_url = f"{endpoint.rstrip('/')}/query"
    headers = {"User-Agent": USER_AGENT, "Accept": "text/csv"}
    try:
        total = requests.get(
            query_url,
            params={"query": "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }"},
            headers=headers,
            timeout=HTTP_TIMEOUT,
        ).text.strip().splitlines()
        n_graphs = requests.get(
            query_url,
            params={
                "query": "SELECT (COUNT(DISTINCT ?g) AS ?c) "
                "WHERE { GRAPH ?g { ?s ?p ?o } }"
            },
            headers=headers,
            timeout=HTTP_TIMEOUT,
        ).text.strip().splitlines()
        graphs = requests.get(
            query_url,
            params={
                "query": "SELECT ?g (COUNT(*) AS ?c) WHERE { GRAPH ?g { ?s ?p ?o } } "
                f"GROUP BY ?g ORDER BY DESC(?c) LIMIT {top}"
            },
            headers=headers,
            timeout=HTTP_TIMEOUT,
        ).text.strip().splitlines()
    except requests.RequestException as e:
        print(f"  (could not read back counts: {e})", file=sys.stderr)
        return

    print("\nLoaded store summary:")
    if len(total) > 1:
        print(f"  default-graph (union) triples: {total[1]}")
    total_graphs = n_graphs[1] if len(n_graphs) > 1 else "?"
    print(f"  named graphs: {total_graphs} (top {top} by triple count):")
    for line in graphs[1:]:
        print(f"    {line}")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Load DOOS provider outputs into a running Oxigraph server."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"YAML source config (default: {DEFAULT_CONFIG.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="Override the endpoint from the config (e.g. http://localhost:7878)",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the server to come up before loading",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        metavar="PATH",
        help="After load (or alone with --export-only), dump the full store "
        "as N-Quads to PATH (named graphs preserved)",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Skip loading sources; only dump the store (requires --export)",
    )
    return parser.parse_args()


def main():
    """Read the config and load each source into Oxigraph; optional N-Quads export."""
    args = parse_args()

    if args.export_only and not args.export:
        print("Error: --export-only requires --export PATH", file=sys.stderr)
        sys.exit(1)

    if not args.config.exists() and not args.export_only:
        print(f"Error: config not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    try:
        config = {}
        if args.config.exists():
            config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
        endpoint = args.endpoint or config.get("endpoint")
        if not endpoint:
            raise ValueError("no endpoint set (config 'endpoint' or --endpoint)")

        if args.wait:
            wait_for_server(endpoint)

        if not args.export_only:
            sources = config.get("sources") or []
            if not sources:
                raise ValueError("config has no 'sources'")

            total_files = 0
            for source in sources:
                total_files += load_source(endpoint, source)

            print(f"\nDone: loaded {total_files} file(s) into {endpoint}")
        else:
            print(f"Export-only mode: skipping load from config ({endpoint})")

        if args.export:
            export_nquads(endpoint, args.export)

        graph_count(endpoint)
    except requests.HTTPError as e:
        print(f"Error: HTTP {e.response.status_code} from server: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
