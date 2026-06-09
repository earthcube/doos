# SPARQL 

## Notes

https://qlever-ui.geocodes-aws-dev.earthcube.org/deepoceans/u8Bki7

```sparql
PREFIX schema: <http://schema.org/>
PREFIX sschema: <https://schema.org/>
SELECT DISTINCT   ?name ?propertyId  ?unitCode  ?unitText ?repo (count(?subj) as ?datasetcount)  (count(?name) as ?count) WHERE
{ graph ?g {
  ?subj sschema:variableMeasured ?vm .
  ?vm a sschema:PropertyValue .
  ?vm sschema:name ?name .
  FILTER(CONTAINS(LCASE(?name), "depth")) .
  OPTIONAL {?vm sschema:propertyID ?propertyId .} 
   OPTIONAL {?vm sschema:unitCode ?unitCode .} 
    OPTIONAL {?vm sschema:unitText ?unitText .} 
  }
bind(REPLACE(str(?g),"urn:gleaner.io:([^:]+):([^:]+):data:[^\\s]+" , "$2")  as ?repo)
 .
}
group by ?name ?propertyId ?unitCode ?unitText ?repo
ORDER BY ?name
```



https://qlever-ui.geocodes-aws-dev.earthcube.org/deepoceans/GxLMVz

SPARQL endpoint: https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans  


## Endpoints

https://qlever-ui.geocodes-aws-dev.earthcube.org
