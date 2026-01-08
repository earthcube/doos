# Sources notes


## Source info

Provides via graph call:  https://qlever-ui.geocodes-aws-dev.earthcube.org/deepoceans/GxLMVz

_config for deep ocean sources_

```yaml
  - community: deepoceans
    hostname: deepoceans
    landing_introduction: An interdisciplinary [geoscience subfield] data and tool search engine. 2 or 3 more sentences to describe the website.
    description: deepoceans
    name: deepoceans
    color: "#660000"
    url: https://www.earthcube.org
    logo: https://storage.googleapis.com/kaggle-datasets-images/180285/405369/be611f54205eff89100cd3f79172c9ab/dataset-cover.jpg?t=2019-05-02-02-32-11
    graph:
      main_namespace: deepoceans
      summary_namespace: deepoceans_summary
    sources:
      - bcodmo
      - cchdo
      - ssdbiodp
      - metsrcn
      - osmc
      - obis
      - argo
      - osnap
      - seabed2030
      - wodb
      - gebcogb
      - gebcogufn
      - emodnet
```

## Table of source notes

| Source                          | Status                  | Stack      | URL                                            | Additional Info                                                                                                                                        |
|---------------------------------|-------------------------|------------|------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| AODN                            | Need mapping workflow   | GeoNetwork | https://portal.aodn.org.au/                    | Sources are XML based look at the xml version (replace JSON-LD with xml) and see if I can convert the ISO 115 to schema.org XSLT templates for mapping |
| BODC                            | Indexing                |            | https://www.bodc.ac.uk/                        | Thought: Ask BODC if they can break up their sitemap so that there is one just for datasets <br> See search example at the provided URL                |
| ARGO GDAC                       | Augmenting graphs ready |            | https://argo.ucsd.edu/data/data-from-gdacs/    | Status: parquet based file generation works.  Needs a workflow to the GitHub concept (see Technical section)                                           |
| OBIS                            | Augmenting graphs ready |            | https://obis.org/                              | Status: depth data is integrated into the graph products.  OBIS needs spatial to scope records with just lat-long not only poly (lat long added)       |
| CIOOS                           |                         |            | https://cioos.ca/                              | This might be a priority based on their interest in better alignment with OIH                                                                          |
| CCHDO                           | Indexing                |            | https://cchdo.ucsd.edu/                        | (Indexable) (being indexed)                                                                                                                            |
| EMODNET                         |                         |            | https://emodnet.ec.europa.eu/en                | check   https://emodnet.ec.europa.eu/en/sitemap.xml                                                                                                                                                 |
| BCO-DMO                         | Starting                |            | https://www.bco-dmo.org/                       | Will start working with Adam starting now                                                                                                              |
| Australian Antarctic Data Group |                         |            | https://data.aad.gov.au/                       |                                                                                                                                                        |



Notes:

* [AODN Example](https://catalogue.aodn.org.au/geonetwork/srv/api/records/528f280c-b151-45c4-9526-e0746510a617/formatters/jsonld )
* [old link to ui?](https://qlever-test.geocodes-aws-dev.earthcube.org/#/search/?q=bodc&searchExactMatch=false&resourceType=all)    