---
name: doos-graph-inspect
description: >
  Inspect an RDF graph via MCP helper scripts — types, contents, and resource
  retrieval. Experimental; prefer doos-sparql for portable SPARQL against an
  endpoint. Triggers: graph inspect, graph MCP, RDF types, /doos-graph-inspect.
license: Apache-2.0
metadata:
  project: DOOS
  author: GoFAIR US
  version: "1.0"
---

# Graph inspection

Leverage the script to access the graph MCP to address various queries. 

**Helper Scripts Available**:
- `scripts/graph-client.py` - simple script to call an MCP server for further resources

  Run with: uv run graph-client.py -query "What are the distinct types in the RDF graph"
