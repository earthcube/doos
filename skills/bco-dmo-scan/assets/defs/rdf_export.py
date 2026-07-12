"""Merge JSON-LD documents into a single N-Triples file via pyoxigraph."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pyoxigraph
from pyld import jsonld
from pyoxigraph import DefaultGraph

from defs.common import log

DEFAULT_GRAPH = DefaultGraph()


def export_jsonld_to_nt(documents: list[dict], output_path: Path) -> dict:
    """
    Load JSON-LD documents into one pyoxigraph Store and dump N-Triples.

    Each document is URDNA2015-normalized to N-Quads, then loaded into the
    default graph of a shared store. That avoids both blank-node collisions from
    concatenating per-file ``.nt`` strings and dump errors when JSON-LD parsing
    would otherwise leave triples in named graphs (N-Triples cannot encode
    datasets). pyld does not support ``application/n-triples`` for normalize;
    N-Quads is the supported intermediate format.

    Args:
        documents: schema.org Dataset JSON-LD dicts
        output_path: Destination ``.nt`` file path

    Returns:
        dict: ``{document_count, triple_count, output_path}``
    """
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    store = pyoxigraph.Store()
    seen_ids: set[str] = set()
    loaded = 0

    for doc in documents:
        doc_id = doc.get("@id")
        if doc_id:
            if doc_id in seen_ids:
                log(f"[warn] duplicate @id in export batch: {doc_id}")
            seen_ids.add(doc_id)

        normalized = jsonld.normalize(
            doc,
            {"algorithm": "URDNA2015", "format": "application/n-quads"},
        )
        if not normalized or not normalized.strip():
            continue

        store.load(
            io.StringIO(normalized),
            "application/n-quads",
            base_iri=None,
            to_graph=DEFAULT_GRAPH,
        )
        loaded += 1

    triple_count = len(list(store.quads_for_pattern(None, None, None, DEFAULT_GRAPH)))

    with output_path.open("wb") as handle:
        store.dump(
            handle,
            "application/n-triples",
            from_graph=DEFAULT_GRAPH,
        )

    log(
        f"Wrote {triple_count} triples from {loaded} document(s) "
        f"to {output_path}"
    )

    return {
        "document_count": loaded,
        "triple_count": triple_count,
        "output_path": str(output_path),
    }


def export_jsonld_paths_to_nt(paths: list[Path], output_path: Path) -> dict:
    """Load JSON-LD from disk paths and write a merged N-Triples file."""
    documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(paths)
    ]
    return export_jsonld_to_nt(documents, output_path)