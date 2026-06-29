# DOOS — Deep Ocean Observation System

An [EarthCube](https://www.earthcube.org) project for harvesting, converting, validating,
and federating ocean observation metadata across multiple data providers into a common
knowledge graph.

## What it does

DOOS ingests metadata from ocean data providers, transforms it to
[Schema.org](https://schema.org) + [GeoSPARQL](https://www.ogc.org/standard/geosparql/)
RDF, validates it against OIH (Ocean Information Hub) SHACL profiles, and publishes it
to a federated SPARQL endpoint for cross-provider discovery.

The primary focus is exposing a consistent **depth profile** — ensuring that depth-below-
surface measurements (`DepBelowSurf`) are present and queryable across all sources.

## Data providers

| Subproject | Provider | Status |
|---|---|---|
| ARGO | Argo GDAC float data | Augmenting graphs ready |
| OBIS | Ocean Biodiversity Information System | Augmenting graphs ready |
| ERDDAP | NOAA OSMC via ERDDAP | Indexing |
| CCHDO | CCHDO bottle file data | Indexing |
| BCO-DMO | Biological and Chemical Oceanography Data Management (`skills/bco-dmo-scan/`) | Starting |
| AODN | Australian Ocean Data Network | Needs mapping workflow |
| BODC | British Oceanographic Data Centre | Indexing |
| CIOOS | Canadian Integrated Ocean Observing System | Candidate |

Candidate sources not yet subprojects: EMODNET, OceanSITES, marine-regions.

## Pipeline

```
Ingest → Transform → Validate → Export → Federated SPARQL
```

Transform approaches vary by provider: JSON-LD templates, RML/morph-kgc, XSLT (ISO 19139),
SSSOM field mappings, or SHACL-AF SPARQL rules. See `CLAUDE.md` for details.

## Live endpoints

- Search UI: <https://deepoceans.geocodes-aws.earthcube.org/#/landing>
- SPARQL (QLever): <https://qlever-ui.geocodes-aws-dev.earthcube.org/deepoceans/GxLMVz>

## Setup

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt   # core RDF/validation stack
uv sync                              # full deps (text2query, XSLT, pyrudof)
```

See `CLAUDE.md` for architecture, per-subproject notes, and validation commands.
