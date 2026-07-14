# SPARQL UPDATE: add OIH canonical depth name on aliased PropertyValues.
#
# For each schema:PropertyValue under schema:variableMeasured whose
# schema:name is one of the designated aliases, INSERT an additional
# schema:name "DepBelowSurf" in the same named graph. Original names
# and min/max/unit triples are left unchanged.
#
# Apply against Oxigraph (or any SPARQL 1.1 Update endpoint), e.g.:
#   curl -sS -X POST 'http://localhost:7878/update' \
#     -H 'Content-Type: application/sparql-update' \
#     -H 'User-Agent: DOOS-OxigraphLoader/1.0' \
#     --data-binary @SPARQL/alias_depthbelowsurf.ru
#
# Re-running is safe: FILTER NOT EXISTS skips nodes that already have
# the canonical name.

PREFIX schema: <https://schema.org/>

INSERT {
  GRAPH ?g {
    ?vm schema:name "DepBelowSurf" .
  }
}
WHERE {
  GRAPH ?g {
    ?subj schema:variableMeasured ?vm .
    ?vm a schema:PropertyValue ;
        schema:name ?name .
    VALUES ?name {
      "depth"
      "Depth"
      "Min_Depth"
      "MinDepth"
      "MaxDepth"
      "depth_m"
      "Sample_Depth"
      "DEPTH"
      "Btl_Depth"
      "depth_CTD"
      "depth_max"
      "max_depth"
      "press"
      "Actual_Depth"
    }
    FILTER NOT EXISTS { ?vm schema:name "DepBelowSurf" }
  }
}
