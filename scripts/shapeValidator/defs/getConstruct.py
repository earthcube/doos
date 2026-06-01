from SPARQLWrapper import SPARQLWrapper, TURTLE

# Default for backward compatibility. Prefer passing endpoint explicitly.
_DEFAULT_ENDPOINT = "http://ghost.lan:7007/sparql"
sparql = SPARQLWrapper(_DEFAULT_ENDPOINT)

# Optional per-process persistent client (set via initializer in spawn'ed workers).
# Safe because each worker process has its own address space. Enables connection
# reuse / keep-alive for high-throughput parallel runs.
_persistent_client: SPARQLWrapper | None = None


def set_persistent_sparql_client(client: SPARQLWrapper | None) -> None:
    """Install a reusable SPARQLWrapper client for the current process.

    Intended to be called from a multiprocessing initializer. The client
    should already be configured (return format, keep-alive, headers, etc.).
    Subsequent calls to construct_graph() in the same process will reuse it
    after calling resetQuery().
    """
    global _persistent_client
    _persistent_client = client


def make_sparql_client(
    endpoint: str,
    *,
    use_keep_alive: bool = False,
    agent: str | None = "DOOS-ShapeValidator/1.0",
    timeout: int | None = 120,
) -> SPARQLWrapper:
    """Create a well-configured SPARQLWrapper client for reuse in workers.

    keep-alive is off by default because the optional 'keepalive' package
    (or platform support) is often not present, which otherwise produces
    noisy warnings on every worker.
    """
    client = SPARQLWrapper(endpoint)
    if agent:
        client.agent = agent
    if timeout:
        client.setTimeout(timeout)
    if use_keep_alive:
        client.setUseKeepAlive()
    return client


def construct_graph(graph_uri, endpoint=None):
    """
    Fetch all triples for a named graph via SPARQL CONSTRUCT.

    Args:
        graph_uri: The URI of the named graph to retrieve.
        endpoint: SPARQL endpoint URL. If omitted, falls back to default.

    Returns:
        str: Turtle serialization of the graph (or empty string on error).
    """
    endpoint = endpoint or _DEFAULT_ENDPOINT

    sparql_query = f"""
CONSTRUCT {{
  ?s ?p ?o
}}
WHERE {{
  GRAPH <{graph_uri}> {{
    ?s ?p ?o
  }}
}}
"""

    try:
        if _persistent_client is not None:
            # Reuse the per-process client (set by initializer in parallel workers)
            client = _persistent_client
            client.resetQuery()
            client.setReturnFormat(TURTLE)
            client.setQuery(sparql_query)
        else:
            # Original safe behavior: fresh client per call
            client = SPARQLWrapper(endpoint)
            client.setReturnFormat(TURTLE)
            client.setQuery(sparql_query)

        results = client.query().convert()
        # SPARQLWrapper returns bytes for TURTLE in many versions; normalize to str.
        if isinstance(results, (bytes, bytearray)):
            return results.decode("utf-8", errors="replace")
        return str(results)

    except Exception as e:
        print(f"Error constructing graph <{graph_uri}> from {endpoint}: {e}")
        return ""


# Example usage:
# uris = query_sparql_endpoint("http://ghost.lan:7007")
# print(uris)
