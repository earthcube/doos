from rdflib import Graph, URIRef, Literal, BNode
from SPARQLWrapper import SPARQLWrapper
import gzip
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Insert N-Quads or N-Triples into a SPARQL endpoint")
    parser.add_argument(
        "-t", "--token",
        type=str,
        required=True,
        help="Bearer token for authentication"
    )
    parser.add_argument(
        "-e", "--endpoint",
        type=str,
        default="http://workstation.lan:7019",
        help="SPARQL update endpoint URL"
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        default="output.nq.gz",
        help="Path to the RDF file (.nq, .nq.gz, .nt, .nt.gz)"
    )
    parser.add_argument(
        "-b", "--batch-size",
        type=int,
        default=1000,
        help="Number of statements per batch"
    )
    parser.add_argument(
        "-c", "--content-type",
        type=str,
        default="application/sparql-update",
        help="Content-Type header value"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["nquads", "ntriples"],
        default=None,
        help="Input format: nquads or ntriples (auto-detected from extension if not specified)"
    )
    parser.add_argument(
        "-g", "--graph",
        type=str,
        default=None,
        help="Target graph URI (required for N-Triples, optional for N-Quads as default)"
    )
    return parser.parse_args()


def detect_format(filename: str) -> str:
    """Detect format from file extension."""
    name = filename[:-3] if filename.endswith('.gz') else filename
    if name.endswith('.nq'):
        return 'nquads'
    elif name.endswith('.nt'):
        return 'ntriples'
    else:
        raise ValueError(f"Cannot detect format from extension: {filename}. Use --format to specify.")


def setup_sparql(endpoint_url: str, token: str, content_type: str) -> SPARQLWrapper:
    """Configure SPARQLWrapper with authentication."""
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setMethod('POST')
    sparql.setRequestMethod('postdirectly')
    sparql.addCustomHttpHeader("Content-Type", content_type)
    sparql.addCustomHttpHeader("Authorization", f"Bearer {token}")
    return sparql


def serialize_term(term) -> str:
    """Serialize an RDF term for SPARQL."""
    if isinstance(term, URIRef):
        return f"<{term}>"
    elif isinstance(term, BNode):
        return f"_:{term}"
    elif isinstance(term, Literal):
        # Properly escape the literal value
        escaped = str(term).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
        if term.datatype:
            return f'"{escaped}"^^<{term.datatype}>'
        elif term.language:
            return f'"{escaped}"@{term.language}'
        else:
            return f'"{escaped}"'
    else:
        raise ValueError(f"Unknown term type: {type(term)}")


def insert_batch(sparql: SPARQLWrapper, batch: list, default_graph: str = None):
    """Insert a batch of quads/triples into the SPARQL endpoint."""
    # Group by graph for efficient INSERT
    graphs = {}
    for item in batch:
        if len(item) == 4:
            s, p, o, g = item
        else:
            s, p, o = item
            g = None

        g_str = str(g) if g else (default_graph if default_graph else 'DEFAULT')
        if g_str not in graphs:
            graphs[g_str] = []
        graphs[g_str].append((s, p, o))

    # Build the SPARQL UPDATE query
    query = "INSERT DATA {"
    for g_str, triples in graphs.items():
        if g_str != 'DEFAULT':
            query += f" GRAPH <{g_str}> {{"
        for s, p, o in triples:
            s_str = serialize_term(s)
            p_str = serialize_term(p)
            o_str = serialize_term(o)
            query += f" {s_str} {p_str} {o_str} ."
        if g_str != 'DEFAULT':
            query += " }"
    query += " }"

    sparql.setQuery(query)
    try:
        sparql.query()
        print(f"Inserted {len(batch)} statements")
    except Exception as e:
        print(f"Error inserting batch: {e}")
        # Optionally print query preview for debugging
        # print(f"Query preview: {query[:500]}...")


def main():
    args = parse_args()

    rdf_format = args.format if args.format else detect_format(args.file)

    if rdf_format == 'ntriples' and not args.graph:
        print("Warning: No --graph specified for N-Triples. Data will be inserted into the default graph.")

    sparql = setup_sparql(args.endpoint, args.token, args.content_type)

    # Use rdflib to parse - it handles all the edge cases correctly
    # Map our format names to rdflib format names
    rdflib_format = 'nquads' if rdf_format == 'nquads' else 'nt'

    # Determine if file is gzipped
    open_func = gzip.open if args.file.endswith('.gz') else open

    # Read and parse the entire file with rdflib
    print(f"Parsing {args.file}...")

    with open_func(args.file, 'rt', encoding='utf-8') as f:
        content = f.read()

    # For N-Quads, we need to use ConjunctiveGraph or Dataset to preserve graph info
    if rdf_format == 'nquads':
        from rdflib import ConjunctiveGraph
        g = ConjunctiveGraph()
        g.parse(data=content, format='nquads')

        # Extract quads (s, p, o, graph)
        batch = []
        for s, p, o, ctx in g.quads((None, None, None, None)):
            graph_uri = ctx.identifier if ctx else None
            batch.append((s, p, o, graph_uri))
            if len(batch) >= args.batch_size:
                insert_batch(sparql, batch, args.graph)
                batch = []
        if batch:
            insert_batch(sparql, batch, args.graph)
    else:
        # N-Triples - use regular Graph
        g = Graph()
        g.parse(data=content, format='nt')

        batch = []
        for s, p, o in g:
            batch.append((s, p, o))
            if len(batch) >= args.batch_size:
                insert_batch(sparql, batch, args.graph)
                batch = []
        if batch:
            insert_batch(sparql, batch, args.graph)

    print("Done!")


if __name__ == "__main__":
    main()