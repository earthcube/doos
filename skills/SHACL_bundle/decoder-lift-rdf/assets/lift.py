#!/usr/bin/env python
"""
Stage 2 — decoder-lift-rdf (decoder pipeline).

Deterministic mapping of Stage 1's ``01_extracted.json`` (the MINIMAL field set:
``url``, ``name``, ``description``, ``keywords[]``) into a ``schema:Dataset`` RDF
graph, serialized as Turtle to ``02_graph.ttl``.

This stage is PURE and deterministic (PLAN.md §0a.1 / §4.2) — **no LLM**. The
same input always yields the same graph. It builds a JSON-LD document using the
bundled ``jsonld_context.json`` (``@vocab = https://schema.org/``) and lets
rdflib lift it to triples, so every type/property lands in the canonical
``https://schema.org/`` namespace that the Stage 3 shape targets.

IRI policy (PLAN.md §4.2, locked): the Dataset node IRI is
``<BASE>/<slug>`` where ``BASE`` defaults to
``https://doos.earthcube.org/id/dataset`` (override with ``$DOOS_IRI_BASE``) and
``slug`` is the first 16 hex chars of ``sha256(normalized_source_url)`` — stable
and collision-resistant. Blank nodes (none for the minimal set) are skolemized
here, not in Stage 3, so the validation report is stable across runs.

Usage (CLI):
    python lift.py 01_extracted.json [--out-dir DIR] [--iri-base BASE]

Usage (import, e.g. from a LangGraph node):
    from lift import run_lift
    summary = run_lift("01_extracted.json", out_dir="runs/<id>")
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from rdflib import Graph

CONTEXT_PATH = Path(__file__).resolve().parent / "jsonld_context.json"

DEFAULT_IRI_BASE = os.environ.get(
    "DOOS_IRI_BASE", "https://doos.earthcube.org/id/dataset"
)

# Skolemization authority — match Stage 3 / the shared validator for stable IRIs.
_SKOLEM_AUTHORITY = "http://gleaner.io"


def _normalize_url(url: str) -> str:
    """Light, deterministic URL normalization for stable slugging.

    Lowercases scheme + host, strips a single trailing slash on the path, and
    drops fragments. Query strings are preserved (they can be significant for
    dataset endpoints).
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def mint_iri(extracted: dict, iri_base: str = DEFAULT_IRI_BASE) -> str:
    """Mint the Dataset IRI: ``<iri_base>/<sha256(normalized identifier)[:16]>``.

    Prefers the source ``url``; falls back to ``name`` if no url is present so a
    graph can still be produced. Raises if neither is available.
    """
    seed = extracted.get("url") or extracted.get("name")
    if not seed or not str(seed).strip():
        raise ValueError(
            "Cannot mint a Dataset IRI: 01_extracted.json has neither 'url' nor 'name'."
        )
    normalized = _normalize_url(str(seed)) if extracted.get("url") else str(seed).strip()
    slug = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{iri_base.rstrip('/')}/{slug}"


def _coerce_keywords(value) -> list[str]:
    """Accept a list or a single string; return non-empty trimmed strings."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    return [str(k).strip() for k in value if k is not None and str(k).strip()]


def build_jsonld(extracted: dict, iri_base: str = DEFAULT_IRI_BASE) -> dict:
    """Build the JSON-LD document for the minimal field set.

    Only non-null / non-empty fields produce keys (absent ⇒ no triple; the Stage
    3 shape will warn). Identity is the minted IRI.
    """
    with CONTEXT_PATH.open(encoding="utf-8") as fh:
        context = json.load(fh)["@context"]

    doc: dict = {
        "@context": context,
        "@id": mint_iri(extracted, iri_base),
        "@type": "Dataset",
    }

    name = extracted.get("name")
    if name and str(name).strip():
        doc["name"] = str(name).strip()

    description = extracted.get("description")
    if description and str(description).strip():
        doc["description"] = str(description).strip()

    url = extracted.get("url")
    if url and str(url).strip():
        doc["url"] = str(url).strip()

    keywords = _coerce_keywords(extracted.get("keywords"))
    if keywords:
        doc["keywords"] = keywords

    return doc


def lift(extracted: dict, iri_base: str = DEFAULT_IRI_BASE) -> Graph:
    """Lift the extracted metadata to an rdflib Graph (skolemized)."""
    doc = build_jsonld(extracted, iri_base)
    graph = Graph()
    graph.parse(data=json.dumps(doc), format="json-ld")
    # Skolemize any blank nodes here (Stage 2), per the IRI policy.
    return graph.skolemize(authority=_SKOLEM_AUTHORITY)


def run_lift(
    input_path: str | Path,
    out_dir: str | Path = ".",
    iri_base: str = DEFAULT_IRI_BASE,
) -> dict:
    """Read ``01_extracted.json``, write ``02_graph.ttl``, return a summary.

    Returns:
        { "graph_ttl": <path>, "dataset_iri": <iri>, "n_triples": <int> }
    """
    input_path = Path(input_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    extracted = json.loads(input_path.read_text(encoding="utf-8"))
    graph = lift(extracted, iri_base)

    graph_ttl = out_dir / "02_graph.ttl"
    graph_ttl.write_text(graph.serialize(format="turtle"), encoding="utf-8")

    return {
        "graph_ttl": str(graph_ttl),
        "dataset_iri": mint_iri(extracted, iri_base),
        "n_triples": len(graph),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 2: lift 01_extracted.json (minimal schema.org Dataset "
        "fields) into 02_graph.ttl (Turtle).",
    )
    parser.add_argument("input", help="Stage 1 output, e.g. 01_extracted.json")
    parser.add_argument(
        "--out-dir", default=".", help="Directory to write 02_graph.ttl (default: cwd)"
    )
    parser.add_argument(
        "--iri-base",
        default=DEFAULT_IRI_BASE,
        help=f"Base IRI for the Dataset node (default: {DEFAULT_IRI_BASE}; "
        "env DOOS_IRI_BASE)",
    )
    args = parser.parse_args(argv)

    summary = run_lift(args.input, args.out_dir, args.iri_base)
    print(f"Wrote {summary['graph_ttl']} ({summary['n_triples']} triples)")
    print(f"  dataset IRI: {summary['dataset_iri']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
