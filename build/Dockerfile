# In-memory Oxigraph SPARQL server for loading DOOS provider outputs.
#
# Build:
#   docker build -t doos-oxigraph build/
#
# Run (in-memory, nothing persisted; data is lost on container stop):
#   docker run --rm -p 7878:7878 doos-oxigraph
#
# Then load the provider graphs from the repo root:
#   python scripts/loadToOxigraph/loadToOxigraph.py
#
# And test the endpoint:
#   python scripts/sparqlQueryl.py http://localhost:7878/query --query SPARQL/get100.rq
#
# Notes:
#   * No --location is passed, so Oxigraph uses an in-memory store.
#   * --union-default-graph makes the default graph the union of every named
#     graph, so a bare `{ ?s ?p ?o }` query (e.g. SPARQL/get100.rq) sees data
#     loaded into per-provider named graphs.
#   * Oxigraph 0.5.x parses JSON-LD natively (application/ld+json), so JSON-LD
#     sources are loaded as-is with no pre-conversion step.
#
FROM ghcr.io/oxigraph/oxigraph:0.5.5

EXPOSE 7878

# The base image's ENTRYPOINT is the `oxigraph` binary.
CMD ["serve", "--union-default-graph", "--bind", "0.0.0.0:7878"]
