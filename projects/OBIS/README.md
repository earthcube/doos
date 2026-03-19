

I had a chance to chat more with Pieter this morning.

There is no way currently to get depth statistics by dataset from the API except by going through all records 
but I wouldn't recommend that. 

One thing you could do is get dataset lists for depth slices, 
eg https://api.obis.org/dataset?startdepth=5000&enddepth=6000

This is not the best approach since you have to query by ranges and get the related resources.

However, there is a parquet export from https://obis.org/data/access/ .  Pieter said
that the parquet has depth which is an interpretation of the darwin 
core fields minimumDepthInMeters and maximumDepthInMeters.   So this might be the best route.

Pieter doesn't have time to work on this right away, but it might be easy for us to make an 
"auxiliary" graph that we can test with and also share with Pieter.  In the hopes it helps
him integrate the values into the production service. 

 SELECT *
· FROM read_json('./obis/*.jsonld',
·                format = 'auto',
‣                columns = {url: 'VARCHAR',
·                           name: 'VARCHAR'});


Can take the vale from the parquet, duck search the json and build the new
variableMeasure entries.   

just need to update the JSON-LD now with depth values like seen
in: https://github.com/iodepo/odis-arch/blob/master/book/thematics/depth/index.md


```python
import json

json_string = '{"myArray": [1, 2, 3]}'

# Load the JSON string into a Python dictionary
data = json.loads(json_string)

# Insert a new node at index 1
data["myArray"].insert(1, "new value")

# Write the updated JSON data back to a string
updated_json_string = json.dumps(data, indent=4)

print(updated_json_string)
```

## Depth example

```json
   {
  "@context": {
    "@vocab": "https://schema.org/"
  },
  "@id": "https://example.org/dataset/12345",
  "@type": "Dataset",
  "variableMeasured": [
    {
      "@type": "PropertyValue",
      "name": "minimumDepthInMeters",
      "description": "Parsed and validated by OBIS.",
      "value": "34.4",
      "propertyID": "https://obis.org/data/access/",
      "measurementTechnique": "Parsed and validated by OBIS.",
      "unitText": "m",
      "unitCode": [
        "https://qudt.org/vocab/unit/M", "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
        "http://dbpedia.org/resource/Metre"
      ]
    },
    {
      "@type": "PropertyValue",
      "name": "maximumDepthInMeters",
      "description": "Parsed and validated by OBIS.",
      "value": "123.4",
      "propertyID": "https://obis.org/data/access/",
      "measurementTechnique": "Parsed and validated by OBIS.",
      "unitText": "m",
      "unitCode": [
        "https://qudt.org/vocab/unit/M", "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
        "http://dbpedia.org/resource/Metre"
      ]
    }
  ]
}
```

or


```json
 {
  "@context": {
    "@vocab": "https://schema.org/"
  },
  "@id": "https://example.org/dataset/12345",
  "@type": "Dataset",
  "variableMeasured": [
    {
      "@type": "PropertyValue",
      "name": "depth",
      "description": "Parsed and validated by OBIS.",
      "minValue": "34.4",
      "maxValue": "123.4",
      "propertyID": "https://obis.org/data/access/",
      "measurementTechnique": "Parsed and validated by OBIS.",
      "unitText": "m",
      "unitCode": [
        "https://qudt.org/vocab/unit/M", "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
        "http://dbpedia.org/resource/Metre"
      ]
    }
  ]
}


```