# Notes


For the depth data they are looking at the variable representation of depth.  
Which I could likely infer into spatial with SHACL AF and SPARQL.

The measurement technique is not important  


Resource example:  https://catalogue.cioos.ca/dataset/ca-cioos_6143028b-028d-46c7-a67d-f3a513435e631.jsonld?frame=schemaorg  from  https://catalogue.cioos.ca/dataset/ca-cioos_6143028b-028d-46c7-a67d-f3a513435e631 



For all our datasets associated with an ERDDAP server (2/3 of the datasets) you always can retrieve the WKT + Z data that can be in some cases massive.

Let me know your thoughts about all this, I included Jared (our metadata committee chair) and Anne-Sophie our CIOOS director to keep them in the loop.



```json
{
  "@context": {
    "@vocab": "http://schema.org/"
  },
  "@id": "https://catalogue.hakai.org/dataset/ca-cioos_6143028b-028d-46c7-a67d-f3a513435e63",
  "@type": "Dataset",
  "about": {
    "@type": "Thing",
    "name": "resorg_hakai-institute",
    "url": "https://catalogue.cioos.ca/group/9fff2a15-ee3f-43dd-bf46-8722a11cd80c"
  },
  "dateModified": "2026-04-21T07:33:28.684485",
  "datePublished": "2026-01-23T19:23:19.485005",
  "description": "Temperature, conductivity, dissolved oxygen, fluorescence, photosynthetic active radiation, and turbidity data collected from 2012 to present by the Hakai Institute in waters surrounding Calvert Island, Johnstone Strait, and Quadra Island areas. This dataset presents data collected by oceanographic profiler instruments (RBR XR-620, RBR Concerto, RBR Maestro, and Seabird SBE 19plus v2) which have been automatically processed by following respective manufacturer's guidelines (see Hakai Water Properties Profile Processing and QA/QC Procedure Manual). \n\nThe provisional processed data are then quality controlled by applying a series of tests that are following the QARTOD standards and more tests specific to the Hakai Institute data (see Hakai Water Properties Profile Processing and QA/QC Procedure Manual).  \n\nThe research dataset provides a subset of the provisional dataset which has been manually reviewed and judged good for science quality level.\n\nData were collected by the Hakai Institute Oceanography Program, the Nearshore Program, and the Juvenile Salmon Program.",
  "distribution": {
    "@id": "https://catalogue.cioos.ca/dataset/13dc3c6c-9dd4-47a4-92ad-681c653d3565/resource/6a9b30f5-e39e-43e7-bf98-d1583ce225b0",
    "@type": "DataDownload",
    "description": "Complete Hakai provisional vertical water properties profile dataset  measured by oceanographic profilers",
    "encodingFormat": "ERDDAP",
    "name": "ERDDAP Dataset",
    "url": "https://catalogue.hakai.org/erddap/tabledap/HakaiWaterPropertiesInstrumentProfileProvisional.html"
  },
  "includedInDataCatalog": {
    "@type": "DataCatalog",
    "description": "",
    "name": "CIOOS/SIOOC",
    "url": "https://catalogue.cioos.ca"
  },
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "name": "Water Property Measurements from Conductivity-Temperature-Depth Profiles, BC, Canada (Provisional)",
  "publisher": {
    "@id": "https://catalogue.cioos.ca/organization/f6f187f7-19f2-4273-a45a-5d9406204873",
    "@type": "Organization",
    "contactPoint": {
      "@type": "ContactPoint",
      "contactType": "customer service",
      "url": "https://catalogue.cioos.ca"
    },
    "name": "CIOOS-Pacific"
  },
  "spatialCoverage": {
    "@type": "Place",
    "geo": {
      "@type": "GeoShape",
      "polygon": "{'type': 'Polygon', 'coordinates': [[[-128.5, 52.27], [-127.4, 52.21], [-127.2, 51.66], [-125.6, 51.13], [-124.8, 50.96], [-124.1, 50.43], [-124.7, 49.98], [-124.9, 49.8], [-126.7, 50.45], [-128.1, 51.37], [-128.4, 51.69], [-128.5, 52.27]]]}"
    }
  },
  "url": "https://catalogue.cioos.ca/dataset/ca-cioos_6143028b-028d-46c7-a67d-f3a513435e631"
}
```