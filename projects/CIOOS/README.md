# CIOOS Notes

## Notes

- [ ]  Need to review the emails for further details on the CKAN CKAN (Comprehensive Knowledge Archive Network) record mapping to schema.org type dataset in JSON-LD

Notes:

A key goal is depth mapping.  Need to review how the gmd:verticleElement is used in the CKAN record and compare it to the approach for encding depth in schema.org at https://book.oceaninfohub.org/thematics/depth/index.html.  

1. Vertical Extent (Metadata Structure)
In the harvest_document_content (the ISO 19115 XML section), there is an explicit placeholder for vertical data:

Vertical Element: The record contains a <gmd:verticalElement> tag.

Missing Values: Within that element, the minimumValue and maximumValue are both marked as gco:nilReason="missing".

Vertical CRS: The Vertical Coordinate Reference System (which would define if depth is measured in meters, pressure in decibars, etc.) is also marked as "missing".



## Metadata elements of the CIKOOS CKAN record

```
Standard CKAN: id, name, title, notes, license_id, resources (array), organization, isopen, state, type: "dataset".
Spatial/temporal: spatial (GeoJSON), bbox-* fields, temporal-extent.
CIOOS/ocean extras: eov (array), ecv, cited-responsible-party (array of objects), frequency-of-update, progress, unique-resource-identifier-full (DOI), included_in_data_catalogue.
```


## Example mapping to Schema.org Dataset in JSON-LD

```json
{
  "@context": "https://schema.org/",
  "@type": "Dataset",
  "@id": "https://catalogue.cioos.ca/dataset/peskotomuhkati-nation-coastal-restoration",
  "identifier": [
    "10-25976-4y34-rn27",
    "peskotomuhkati-nation-coastal-restoration",
    "https://doi.org/10.25976/4y34-rn27"
  ],
  "name": "Peskotomuhkati Nation Coastal Restoration – water quality monitoring",
  "description": "Long-term water quality monitoring for coastal restoration.",
  "license": "odc-by",
  "url": "https://catalogue.cioos.ca/dataset/peskotomuhkati-nation-coastal-restoration",
  "isAccessibleForFree": true,
  "publisher": {
    "@type": "Organization",
    "name": "DataStream"
  },
  "distribution": [
    {
      "@type": "DataDownload",
      "name": "Access data",
      "contentUrl": "https://doi.org/10.25976/4y34-rn27",
      "encodingFormat": null
    }
  ],
  "spatialCoverage": {
    "@type": "Place",
    "geo": {
      "@type": "GeoShape",
      "polygon": "-67.788 44.705 -66.445 44.705 -66.445 45.858 -67.788 45.858 -67.788 44.705"
    }
  },
  "temporalCoverage": "2019-09-25/2026-03-04",
  "variableMeasured": [
    {
      "@type": "PropertyValue",
      "name": "EOV: other"
    }
  ],
  "keywords": ["ECV: water quality"],
  "creator": [
    {
      "@type": "Organization",
      "name": "Passamaquoddy Recognition Group Inc."
    }
  ],
  "additionalProperty": [
    {
      "@type": "PropertyValue",
      "name": "frequency-of-update",
      "value": "monthly"
    },
    {
      "@type": "PropertyValue",
      "name": "progress",
      "value": "onGoing"
    },
    {
      "@type": "PropertyValue",
      "name": "included_in_data_catalogue",
      "value": "CIOOS National"
    }
  ]
}


```
