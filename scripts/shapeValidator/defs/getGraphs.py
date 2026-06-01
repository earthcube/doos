from typing import cast

from SPARQLWrapper import SPARQLWrapper, JSON

# Default endpoint for backward compatibility with existing callers.
# Prefer passing endpoint= explicitly for new code and reusability.
_DEFAULT_ENDPOINT = "http://ghost.lan:7007/sparql"
sparql = SPARQLWrapper(_DEFAULT_ENDPOINT)


def query_sparql_endpoint(url, endpoint=None, limit: int = 0):
    """
    Query a SPARQL endpoint (QLever) and return a list of named graph URIs.

    Args:
        url: The SPARQL endpoint URL (used as default if endpoint not provided).
        endpoint: Optional explicit SPARQL endpoint. If provided, used instead of url.
        limit: If > 0, the query is rewritten to use DISTINCT + ORDER BY ?g + LIMIT.
               This makes the result deterministic (first N graphs in lexicographic
               order of their URIs) and much more efficient for large endpoints.

    Returns:
        list[str]: Graph URIs (schema:Dataset named graphs).
                   When limit > 0 these are guaranteed unique and sorted.
    """
    endpoint = endpoint or url or _DEFAULT_ENDPOINT

    if limit > 0:
        # Use DISTINCT + ORDER BY so that LIMIT returns a deterministic,
        # meaningful "first N graphs" (lexicographically by graph URI).
        sparql_query = (
            "SELECT DISTINCT ?g "
            "WHERE { graph ?g { ?s a <https://schema.org/Dataset> } } "
            f"ORDER BY ?g LIMIT {limit}"
        )
    else:
        sparql_query = (
            "SELECT DISTINCT ?g WHERE { graph ?g { ?s a <https://schema.org/Dataset> } }"
        )

    try:
        # Create a fresh wrapper per call to avoid shared mutable state bugs
        # when this function is used from multiple threads/processes later.
        client = SPARQLWrapper(endpoint)
        client.setQuery(sparql_query)
        client.setReturnFormat(JSON)
        results = cast(dict, client.query().convert())
        graphs = [result["g"]["value"] for result in results["results"]["bindings"]]
        return graphs

    except KeyError as e:
        print(f"Unexpected response structure: {e}")
        return []
    except Exception as e:
        print(f"Error querying endpoint {endpoint}: {e}")
        return []


# Example usage:
# uris = query_sparql_endpoint("http://ghost.lan:7007")
# print(uris)
