# DOOS Project notes


## ToDO

### sources
- [ ] OBIS
  - incorporate the depth profile into the metadata graph
  - see if OBIS will integrate this from their end
- [ ] source: oceansites as a potential source of depth data, via ERDDAP? 
  - https://www.ocean-ops.org/oceansites/data/index.html 

### Contacts
- [ ] email AODC Sources are XML based look at the xml version (replace JSON-LD with xml) and see if I can convert the ISO 115 to schema.org XSLT templates for mapping  see [AODC](./projects/AODC)
- [ ] email CIOOS
- [ ] Email the ARGO,  interested in [geopartquet2RDF](projects/geoparquet2RDF) (in the projects' directory)
- [ ] BODC sitemap splitting would be nice to separate out the datasets
- [X] Email Colm about the January agenda
  - Mission Alignment with DOOS, OIH and DeCODER 
  - Colm is the new chair of ODIS operations.  Could we present the Depth profile to the operations group in January?  Talk with Colm and PLB to see if this could be a small part of the agenda. (5 to 10 minutes max)
- [x] Contact Chantel: Polar Data Science (PolDS 2025): ACM SIGSPATIAL International Workshop
  - find out if anyone is implementing depth profile
- [X] Contact SOSO to discuss a meeting regarding depth and GeoCroissant
  - it will get on the agenda after the winter meeting
- [X] Contacted BCO-DMO, going to spec out some work for me to do to help integrate depth [bco-dmo](projects/BCO-DMO)

### Activities 
- [ ] Need to run the [current providers](https://qlever-ui.geocodes-aws-dev.earthcube.org/deepoceans/GxLMVz) against SHACL to validate which are exposing graphs following the depth profile.  Need to work up a SPARQL and SHACL that will then process the graph and generate a report (see [sources](./docs/sources.md))  (would be good to check emodnet first and report results back)
  - [SHACL examples](SHACL)
- [ ] ERDDAP exposing JOSN-LD with depth based on DOOS/OIH profile
    - https://github.com/robertdcurrier/erddap2mcp
    - https://github.com/ERDDAP/erddap/pull/316
- [ ] get the marine regions data on-line
- [ ] federated SPARQL query for the marine regions data and the metadata graph
- [ ] Need to test the approach used in the depth profile in the GeoCroissant examples

## Setup

```bash
uv init
uv uv venv .venv --python 3.12
uv pip install -r requirements.txt      
```


## References

* https://deepoceans.geocodes-aws.earthcube.org/#/landing
* Test:  https://obisdepth.geocodes-aws.earthcube.org/#/landing 
* https://qlever-ui.geocodes-aws-dev.earthcube.org

