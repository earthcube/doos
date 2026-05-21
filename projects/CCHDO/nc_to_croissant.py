#!/usr/bin/env python3
"""Transform NetCDF metadata JSON → MLCommons Croissant JSON-LD via SHACL-AF SPARQLRules.

Usage:
    python nc_to_croissant.py [metadata.json] [--shapes SHAPES_TTL] [--output OUT]
"""

import argparse
import json
import re
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD
from pyshacl import shacl_rules
from pyld import jsonld

CCHDO  = Namespace("https://cchdo.ucsd.edu/vocab#")
SCHEMA = Namespace("http://schema.org/")        # Croissant spec uses http, not https
CR     = Namespace("http://mlcommons.org/croissant/")
DCT    = Namespace("http://purl.org/dc/terms/")

SCRIPT_DIR    = Path(__file__).parent
DEFAULT_SHAPES = SCRIPT_DIR / "SHACL_AF" / "nc_metadata_to_croissant.ttl"

INCLUDE_NS = {str(SCHEMA), str(CR), str(DCT)}

CROISSANT_CONTEXT = {
    "@vocab":    "http://schema.org/",
    "sc":        "http://schema.org/",
    "cr":        "http://mlcommons.org/croissant/",
    "dct":       "http://purl.org/dc/terms/",
    "dataType":  {"@id": "http://mlcommons.org/croissant/dataType",  "@type": "@vocab"},
    "field":      "http://mlcommons.org/croissant/field",
    "fileObject": "http://mlcommons.org/croissant/fileObject",
    "recordSet":  "http://mlcommons.org/croissant/recordSet",
    "source":     "http://mlcommons.org/croissant/source",
    "extract":    "http://mlcommons.org/croissant/extract",
    "column":     "http://mlcommons.org/croissant/column",
    "isArray":    "http://mlcommons.org/croissant/isArray",
    "arrayShape": "http://mlcommons.org/croissant/arrayShape",
    "conformsTo": "http://purl.org/dc/terms/conformsTo",
}

# Map NetCDF dtype prefixes to schema.org dataType IRIs
_DTYPE_MAP = [
    ("float", SCHEMA.Float),
    ("int",   SCHEMA.Integer),
    ("|S",    SCHEMA.Text),
    ("U",     SCHEMA.Text),
    ("S",     SCHEMA.Text),
]

def _dtype_to_iri(dtype: str) -> URIRef:
    for prefix, iri in _DTYPE_MAP:
        if dtype.startswith(prefix):
            return iri
    return SCHEMA.Text


def build_intermediate_graph(meta: dict) -> Graph:
    g = Graph()
    g.bind("cchdo", CCHDO)

    slug   = re.sub(r"[^a-zA-Z0-9_\-]", "_", meta["source_file"].replace(".nc", ""))
    ds_uri = URIRef(f"urn:cchdo:dataset:{slug}")

    g.add((ds_uri, RDF.type,         CCHDO.NCDataset))
    g.add((ds_uri, CCHDO.sourceFile, Literal(meta["source_file"])))

    for var_name, var_info in meta["variables"].items():
        safe    = re.sub(r"[^a-zA-Z0-9_\-]", "_", var_name)
        var_uri = URIRef(f"urn:cchdo:var:{slug}:{safe}")
        attrs   = var_info.get("attributes", {})
        shape   = var_info["shape"]

        g.add((ds_uri,  CCHDO.hasVariable,   var_uri))
        g.add((var_uri, RDF.type,            CCHDO.NCVariable))
        g.add((var_uri, CCHDO.varName,       Literal(var_name)))
        g.add((var_uri, CCHDO.varSchemaType, _dtype_to_iri(var_info["dtype"])))
        g.add((var_uri, CCHDO.varIsArray,    Literal(len(shape) > 0, datatype=XSD.boolean)))
        g.add((var_uri, CCHDO.varArrayShape, Literal(f"({', '.join(str(d) for d in shape)})")))

        if std := attrs.get("standard_name"):
            g.add((var_uri, CCHDO.varStdName, Literal(std)))
        if whp := attrs.get("whp_name"):
            g.add((var_uri, CCHDO.varWhpName, Literal(whp)))

    return g


def apply_shacl_rules(data_graph: Graph, shapes_path: Path) -> Graph:
    return shacl_rules(
        data_graph,
        shacl_graph=str(shapes_path),
        shacl_graph_format="ttl",
    )


def extract_croissant_graph(full_graph: Graph) -> Graph:
    out = Graph()
    out.bind("sc",  SCHEMA)
    out.bind("cr",  CR)
    out.bind("dct", DCT)
    for s, p, o in full_graph:
        p_str = str(p)
        if any(p_str.startswith(ns) for ns in INCLUDE_NS):
            out.add((s, p, o))
        elif p == RDF.type and any(str(o).startswith(ns) for ns in INCLUDE_NS):
            out.add((s, p, o))
    return out


def to_jsonld(croissant_graph: Graph) -> dict:
    raw = json.loads(croissant_graph.serialize(format="json-ld"))
    frame = {
        "@context": CROISSANT_CONTEXT,
        "@type": "Dataset",
        "distribution": {"@type": "cr:FileObject"},
        "recordSet": {
            "@type": "cr:RecordSet",
            "field": {
                "@type": "cr:Field",
                "source": {
                    "fileObject": {"@embed": "@never"},
                    "extract": {},
                }
            }
        }
    }
    return jsonld.frame(raw, frame)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", nargs="?",
                        default="33RR20220430_bottle.metadata.json",
                        help="Path to metadata JSON file")
    parser.add_argument("--shapes", default=str(DEFAULT_SHAPES),
                        help="Path to SHACL-AF shapes Turtle file")
    parser.add_argument("--output", default=None,
                        help="Output path (default: <stem>.croissant.jsonld)")
    args = parser.parse_args()

    meta_path   = Path(args.metadata)
    shapes_path = Path(args.shapes)
    out_path    = Path(args.output) if args.output else \
                  meta_path.with_name(meta_path.stem.replace(".metadata", "") + ".croissant.jsonld")

    meta = json.loads(meta_path.read_text())

    print(f"Building intermediate RDF graph from {meta_path.name} ...")
    data_graph = build_intermediate_graph(meta)
    print(f"  {len(data_graph)} triples")

    print(f"Applying SHACL-AF rules from {shapes_path.name} ...")
    expanded = apply_shacl_rules(data_graph, shapes_path)
    print(f"  {len(expanded)} triples after expansion")

    croissant_graph = extract_croissant_graph(expanded)
    print(f"  {len(croissant_graph)} Croissant triples extracted")

    result = to_jsonld(croissant_graph)

    out_path.write_text(json.dumps(result, indent=2))

    rs = result.get("recordSet", {})
    if isinstance(rs, list):
        rs = rs[0] if rs else {}
    n_fields = len(rs.get("field", []))
    name = result.get("name", "")
    print(f"Written: {out_path}  (name={name!r}, {n_fields} fields)")


if __name__ == "__main__":
    main()
