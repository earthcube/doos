# DOOS Project notes


## ToDO

- [ ] Need to run the [current providers](https://qlever-ui.geocodes-aws-dev.earthcube.org/deepoceans/GxLMVz) against SHACL to validate which are exposing graphs following the depth profile.
- [ ] Need to test the approach used in the depth profile in the GeoCroissant examples
- [ ] ERDDAP exposing JOSN-LD with depth based on DOOS/OIH profile
    - https://github.com/robertdcurrier/erddap2mcp
    - https://github.com/ERDDAP/erddap/pull/316
- [X] Email Colm about the January agenda
  - Mission Alignment with DOOS, OIH and DeCODER 
  - Colm is the new chair of ODIS operations.  Could we present the Depth profile to the operations group in January?  Talk with Colm and PLB to see if this could be a small part of the agenda. (5 to 10 minutes max)
- [x] Contact Chantel: Polar Data Science (PolDS 2025): ACM SIGSPATIAL International Workshop
- [X] Contact SOSO to discuss a meeting regarding depth and GeoCroissant
  - it will get on the agenda after the winter meeting
- [X] Contacted BCO-DMO, going to spec out some work for me to do to help integrate depth [bco-dmo](projects/BCO-DMO)
- [ ] email CIOOS
- [ ] Email the group interested in [geopartquet2RDF](projects/geoparquet2RDF) (in the projects' directory)
- [ ] Need to work up a SPARQL and SHACL that will then process the graph and generate a report (see [sources](./docs/sources.md))
  - [SHACL examples](SHACL)
- [ ] get the marine regions data on-line
- [ ] federated SPARQL query for the marine regions data and the metadata graph


## Setup

```bash
uv init
uv uv venv .venv --python 3.12
uv pip install -r requirements.txt      
```


## References

* https://deepoceans.geocodes-aws.earthcube.org/#/landing
* https://qlever-ui.geocodes-aws-dev.earthcube.org

