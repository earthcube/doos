#!/usr/bin/env python3
"""
Load DOOS provider outputs into a running Oxigraph server.

Reads a YAML config listing provider sources (N-Quads / N-Triples / JSON-LD,
files or directories) and pushes them to an Oxigraph server over the SPARQL
Graph Store HTTP Protocol. Pair this with build/Dockerfile, which starts an
in-memory Oxigraph server with a union default graph.

Named graphs:
  - Triple formats (nt, ttl, jsonld) require a config ``graph`` IRI; the payload
    is POSTed into that named graph.
  - Quad formats (nq, trig) without ``graph`` keep the embedded graph names.
  - Quad formats *with* ``graph`` collapse all triples into that IRI (embedded
    graph names are discarded) and POST as N-Triples with ``?graph=``.

Optionally export the full store (all named graphs) as a single N-Quads file
via GET /store after loading.

Optionally apply a SPARQL UPDATE that aliases depth ``variableMeasured`` names
to ``DepBelowSurf`` (``--alias``; default file ``SPARQL/alias_depthbelowsurf.ru``).

Usage:
  # 1. start the server (in-memory)
  docker build -t doos-oxigraph build/
  docker run --rm --network host doos-oxigraph

  # 2. load the configured sources (and optionally dump N-Quads)
  python scripts/loadToOxigraph/loadToOxigraph.py --wait
  python scripts/loadToOxigraph/loadToOxigraph.py --wait --export output/doos.nq

  # 2b. load and apply DepBelowSurf name aliases
  python scripts/loadToOxigraph/loadToOxigraph.py --wait --alias

  # 3. dump an already-loaded store without re-loading sources
  python scripts/loadToOxigraph/loadToOxigraph.py --export-only --export output/doos.nq

  # 3b. alias only (skip load) against a running store
  python scripts/loadToOxigraph/loadToOxigraph.py --export-only --alias

  # 4. test the endpoint
  python scripts/sparqlQueryl.py http://localhost:7878/query --query SPARQL/get100.rq
"""

import argparse
import io
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
import yaml
from pyoxigraph import DefaultGraph, RdfFormat, Store
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CONFIG = SCRIPT_DIR / "oxigraph_load.yaml"
DEFAULT_ALIAS_UPDATE = REPO_ROOT / "SPARQL" / "alias_depthbelowsurf.ru"
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

# config format key -> pyoxigraph RdfFormat for quad payloads
QUAD_RDF_FORMATS = {
    "nq": RdfFormat.N_QUADS,
    "trig": RdfFormat.TRIG,
}
NT_MIME = "application/n-triples"


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


def quads_to_ntriples(data: bytes, fmt: str) -> bytes:
    """Collapse a quad-format payload into N-Triples (drop graph terms).

    Loads N-Quads or TriG into an in-memory store, then serializes every triple
    from the default graph and all named graphs as N-Triples. Used when a YAML
    ``graph`` IRI overrides embedded named graphs on a quad source.
    """
    rdf_format = QUAD_RDF_FORMATS.get(fmt)
    if rdf_format is None:
        raise ValueError(f"cannot collapse format '{fmt}' to N-Triples")

    store = Store()
    store.load(io.BytesIO(data), rdf_format)

    out = io.BytesIO()
    store.dump(out, RdfFormat.N_TRIPLES, from_graph=DefaultGraph())
    for graph_name in store.named_graphs():
        store.dump(out, RdfFormat.N_TRIPLES, from_graph=graph_name)
    return out.getvalue()


def wait_for_server(endpoint: str, retries: int = 30, delay: float = 1.0) -> None:
    """Block until the SPARQL endpoint answers, or exit after retries.

    ``retries`` and ``delay`` control total wait budget (retries * delay seconds).
    Docker compose load jobs should pass a higher ``--wait-retries`` on slow starts.
    """
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
    """Load one configured source. Returns the number of files loaded.

    For quad formats (nq, trig): if ``graph`` is set, embedded graph names are
    discarded and all triples are loaded into that IRI; if omitted, graphs from
    the data are preserved. Triple formats always require ``graph``.
    """
    name = source.get("name", "?")
    fmt = source.get("format")
    if fmt not in FORMATS:
        raise ValueError(f"source '{name}': unknown format '{fmt}'")
    mime, is_quads, exts = FORMATS[fmt]

    graph = source.get("graph")
    override_quads = bool(is_quads and graph)
    if not is_quads and not graph:
        raise ValueError(
            f"source '{name}': triple format '{fmt}' requires a 'graph' IRI"
        )
    if override_quads:
        print(
            f"  note: source '{name}' is a quad format with 'graph' set; "
            f"collapsing embedded graphs into {graph}",
            file=sys.stderr,
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
        post_mime = mime
        post_graph = graph
        if override_quads:
            # Strip graph terms, then POST as N-Triples into the target graph.
            blob = quads_to_ntriples(blob, fmt)
            post_mime = NT_MIME
            post_graph = graph
        elif is_quads:
            # Preserve embedded graph names; do not pass ?graph=.
            post_graph = None
        desc = f"{name} ({fmt}, {len(files)} file(s))"
        if override_quads:
            desc += f" -> {graph}"
        with tqdm(total=1, desc=desc) as bar:
            post_data(store_url, blob, post_mime, post_graph)
            bar.update(1)

    return len(files)


def apply_sparql_update(endpoint: str, update_file: Path) -> None:
    """POST a SPARQL UPDATE file to the endpoint's /update service.

    Used for post-load transforms such as aliasing depth variableMeasured
    names to DepBelowSurf (see SPARQL/alias_depthbelowsurf.ru).
    """
    path = update_file if update_file.is_absolute() else REPO_ROOT / update_file
    if not path.is_file():
        raise FileNotFoundError(f"SPARQL update file not found: {path}")

    update_url = f"{endpoint.rstrip('/')}/update"
    body = path.read_text(encoding="utf-8")
    # Strip leading comment-only lines for a cleaner log line; send full body.
    print(f"\nApplying SPARQL UPDATE from {path} -> {update_url}")
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/sparql-update",
    }
    resp = requests.post(
        update_url, data=body.encode("utf-8"), headers=headers, timeout=HTTP_TIMEOUT
    )
    resp.raise_for_status()
    print(f"  OK (HTTP {resp.status_code})")


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
        "--wait-retries",
        type=int,
        default=30,
        metavar="N",
        help="With --wait, number of attempts (default: 30; use ~90 in Docker)",
    )
    parser.add_argument(
        "--wait-delay",
        type=float,
        default=1.0,
        metavar="SEC",
        help="With --wait, seconds between attempts (default: 1.0)",
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
        help="Skip loading sources; only dump and/or apply --alias "
        "(requires --export and/or --alias)",
    )
    parser.add_argument(
        "--alias",
        nargs="?",
        const=DEFAULT_ALIAS_UPDATE,
        default=None,
        type=Path,
        metavar="UPDATE",
        help="After load (or alone with --export-only), POST a SPARQL UPDATE "
        "that aliases designated depth variableMeasured names to DepBelowSurf. "
        f"Optional path to a .ru file (default: "
        f"{DEFAULT_ALIAS_UPDATE.relative_to(REPO_ROOT)})",
    )
    return parser.parse_args()


def main():
    """Read the config and load each source into Oxigraph; optional alias/export."""
    args = parse_args()

    if args.export_only and not args.export and not args.alias:
        print(
            "Error: --export-only requires --export PATH and/or --alias",
            file=sys.stderr,
        )
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
            wait_for_server(
                endpoint,
                retries=max(1, args.wait_retries),
                delay=max(0.1, args.wait_delay),
            )

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

        # After load so aliases apply to newly ingested data; before export so
        # dumped N-Quads include DepBelowSurf when both flags are used.
        if args.alias is not None:
            apply_sparql_update(endpoint, args.alias)

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
