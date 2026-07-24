# AI × FAIR data and discovery — exploration notes


**DOOS Deep Ocean Depth Augmentation**
* Review the activity at: https://github.com/earthcube/doos/blob/main/projects/README.md
* Review the tooling at: https://github.com/earthcube/doos/tree/main/scripts
* how do we know the DOOS approach is working?
  * address data typing for things like nan reports
  * is it doing the depth correctly?  (SHACL)
    * helps with alignment to SPARQL
  * the issue of coverage, and how that is expressed in search
    * precision and recall 


**AI wants data?**
* could we leverage the DOOS approach to integrate other resources into the graph for ecoforecast and earth surface???
* using the DeCODER graph in the AI UX via web via CLI, etc 
* MCP Protocol for DeCODER graph
* personal knowledge graph (harpathy)
* what does a DeCODER graph look like in teh context of the NSF All praise AI direction

Ideas to show
mermaid of the DOOS flow with SHACL validation and perhaps other validation in it.   
the python multi-agent approach with Blueprint, but then mention we could extend this to metadata for doos or others.  


**General approaches**
* MCP for the graph
  * exposing the skill bundles 
* text to SPARQL for the graph
* SPARQL: Qlever and natural language SPARQL https://github.com/sparna-git/Sparnatural and perhaps the work I did in the production section of coffee notes


---

## Possible next builds

Architecture menu (not yet implemented):

1. **DOOS discovery MCP** — expose Oxigraph/QLever + curated SPARQL templates as MCP tools.
2. **Provider FAIR crawler multi-agent** — extract → map → SHACL → review → export per source.
3. **Shared skill catalog** — align DOOS and ai-blueprint-core skills (assess, intake, extract, validate) under one layout and conventions.
