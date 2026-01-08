| Source                          | Status                       | Stack      | URL                                            | Additional Info                                                                                                                                        |
|---------------------------------|------------------------------|------------|------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|
| AODN                            |                              | GeoNetwork | https://portal.aodn.org.au/                    | Sources are XML based look at the xml version (replace JSON-LD with xml) and see if I can convert the ISO 115 to schema.org XSLT templates for mapping |
| BODC                            | Indexing                     |            | https://www.bodc.ac.uk/                        | Thought: Ask BODC if they can break up their sitemap so that there is one just for datasets <br> See search example at the provided URL                |
| ARGO GDAC                       | Can be Generated             |            | https://argo.ucsd.edu/data/data-from-gdacs/    | Status: parquet based file generation works.  Needs a workflow to the GitHub concept (see Technical section)                                           |
| OBIS                            | Can be Generated / Indexing? |            | https://obis.org/                              | Status: depth data is integrated into the graph products.  OBIS needs spatial to scope records with just lat-long not only poly (lat long added)       |
| CIOOS                           |                              |            | https://cioos.ca/                              | This might be a priority based on their interest in better alignment with OIH                                                                          |
| CCHDO                           | Indexing                     |            | https://cchdo.ucsd.edu/                        | (Indexable) (being indexed)                                                                                                                            |
| EMODNET                         |                              |            | https://emodnet.ec.europa.eu/en                |                                                                                                                                                        |
| BCO-DMO                         | Starting                     |            | https://www.bco-dmo.org/                       | Will start working with Adam starting now                                                                                                              |
| Australian Antarctic Data Group |                              |            | https://data.aad.gov.au/                       |                                                                                                                                                        |



Notes:

* [AODN Example](https://catalogue.aodn.org.au/geonetwork/srv/api/records/528f280c-b151-45c4-9526-e0746510a617/formatters/jsonld )
* [old link to ui?](https://qlever-test.geocodes-aws-dev.earthcube.org/#/search/?q=bodc&searchExactMatch=false&resourceType=all)    