#!/usr/bin/env python3
"""Transform NetCDF metadata JSON → schema.org JSON-LD via SHACL-AF SPARQLRules.

Usage:
    python nc_to_jsonld.py [metadata.json] [--shapes SHAPES_TTL] [--output OUT]
"""

import argparse
import json
import re
import sys
from pathlib import Path

import rdflib
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF
from pyshacl import shacl_rules
from pyld import jsonld

CCHDO  = Namespace("https://cchdo.ucsd.edu/vocab#")
SCHEMA = Namespace("https://schema.org/")

SCRIPT_DIR = Path(__file__).parent
DEFAULT_SHAPES = SCRIPT_DIR / "SHACL_AF" / "nc_metadata_to_schema.ttl"


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
        g.add((ds_uri,  CCHDO.hasVariable, var_uri))
        g.add((var_uri, RDF.type,          CCHDO.NCVariable))
        g.add((var_uri, CCHDO.varName,     Literal(var_name)))
        g.add((var_uri, CCHDO.varDtype,    Literal(var_info["dtype"])))

        attrs = var_info.get("attributes", {})
        if units := attrs.get("units"):
            g.add((var_uri, CCHDO.varUnits,       Literal(units)))
        if whp := attrs.get("whp_name"):
            g.add((var_uri, CCHDO.varWhpName,     Literal(whp)))
        if std := attrs.get("standard_name"):
            g.add((var_uri, CCHDO.varStdName,     Literal(std)))
        if conv := attrs.get("conventions"):
            g.add((var_uri, CCHDO.varConventions, Literal(conv)))
        if ref := attrs.get("reference_scale"):
            g.add((var_uri, CCHDO.varRefScale,    Literal(ref)))

    return g


def apply_shacl_rules(data_graph: Graph, shapes_path: Path) -> Graph:
    return shacl_rules(
        data_graph,
        shacl_graph=str(shapes_path),
        shacl_graph_format="ttl",
    )


def extract_schema_graph(full_graph: Graph) -> Graph:
    schema_uri = str(SCHEMA)
    out = Graph()
    out.bind("schema", SCHEMA)
    for s, p, o in full_graph:
        if str(p).startswith(schema_uri):
            out.add((s, p, o))
        elif p == RDF.type and str(o).startswith(schema_uri):
            out.add((s, p, o))
    return out


def to_jsonld(schema_graph: Graph) -> dict:
    raw = json.loads(schema_graph.serialize(format="json-ld"))
    frame = {
        "@context": {"@vocab": "https://schema.org/"},
        "@type": "Dataset",
        "variableMeasured": {"@type": "PropertyValue"},
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
                        help="Output JSON-LD path (default: <stem>.schema.shacl.jsonld)")
    args = parser.parse_args()

    meta_path   = Path(args.metadata)
    shapes_path = Path(args.shapes)
    out_path    = Path(args.output) if args.output else \
                  meta_path.with_name(meta_path.stem.replace(".metadata", "") + ".schema.shacl.jsonld")

    meta = json.loads(meta_path.read_text())

    print(f"Building intermediate RDF graph from {meta_path.name} ...")
    data_graph = build_intermediate_graph(meta)
    print(f"  {len(data_graph)} triples")

    print(f"Applying SHACL-AF rules from {shapes_path.name} ...")
    expanded = apply_shacl_rules(data_graph, shapes_path)
    print(f"  {len(expanded)} triples after expansion")

    schema_graph = extract_schema_graph(expanded)
    print(f"  {len(schema_graph)} schema.org triples extracted")

    result = to_jsonld(schema_graph)

    out_path.write_text(json.dumps(result, indent=2))
    n_vars = len(result.get("variableMeasured", []))
    print(f"Written: {out_path}  (name={result.get('name')!r}, {n_vars} variables)")


if __name__ == "__main__":
    main()
