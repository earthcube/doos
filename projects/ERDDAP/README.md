# README


Draft Agenda

1) Review the approach for DOOS indexing based on ERDDAP
    - can we get data harvested to one or more ERDDAP instances that express the sitemap.xml + JSON-LD feature set

2) Review the ODIS / DeCODER docments for depth representation
    - can these be implemented in ERDDAP JSON-LD serialization?
    - better to leverage JSON-LD for application mapping?

3) Stetch goal, if we get this far
    - review approach based on query and UI for DeCODER

4) Non-priority topics
    - connection with CODATA CDIF?
    - connections with geo-croissant
    - relation to WMO/WIS2 parallel effort



## About

ref: https://github.com/iodepo/odis-arch/blob/master/book/thematics/depth/index.md

Below is an example of the ERDDAP JSON-LD output around a depth parameter from the GO SHIP CCHDO bottle data. The values are dependent on what has been defined in the variable attributes of the depth parameter itself - so those values will vary across datasets. Is this helpful?

## Example depth PropertyValue

```json
{
    "@type": "PropertyValue",
    "name": "depth",
    "alternateName": "Sea Floor Depth Below Sea Surface",
    "description": "Sea Floor Depth Below Sea Surface",
    "valueReference": [
        {
            "@type": "PropertyValue",
            "name": "axisOrDataVariable",
            "value": "data"
        },
        {
            "@type": "PropertyValue",
            "name": "_CoordinateAxisType",
            "value": "Height"
        },
        {
            "@type": "PropertyValue",
            "name": "_CoordinateZisPositive",
            "value": "down"
        },
        {
            "@type": "PropertyValue",
            "name": "_FillValue",
            "value": null
        },
        {
            "@type": "PropertyValue",
            "name": "axis",
            "value": "Z"
        },
        {
            "@type": "PropertyValue",
            "name": "C_format",
            "value": "%.1f"
        },
        {
            "@type": "PropertyValue",
            "name": "C_format_source",
            "value": "input_file"
        },
        {
            "@type": "PropertyValue",
            "name": "colorBarMaximum",
            "value": 8000
        },
        {
            "@type": "PropertyValue",
            "name": "colorBarMinimum",
            "value": -8000
        },
        {
            "@type": "PropertyValue",
            "name": "colorBarPalette",
            "value": "TopographyDepth"
        },
        {
            "@type": "PropertyValue",
            "name": "ioos_category",
            "value": "Location"
        },
        {
            "@type": "PropertyValue",
            "name": "long_name",
            "value": "Sea Floor Depth Below Sea Surface"
        },
        {
            "@type": "PropertyValue",
            "name": "missing_value",
            "value": null
        },
        {
            "@type": "PropertyValue",
            "name": "positive",
            "value": "down"
        },
        {
            "@type": "PropertyValue",
            "name": "source_name",
            "value": "btm_depth"
        },
        {
            "@type": "PropertyValue",
            "name": "standard_name",
            "value": "depth"
        },
        {
            "@type": "PropertyValue",
            "name": "whp_name",
            "value": "DEPTH"
        },
        {
            "@type": "PropertyValue",
            "name": "whp_unit",
            "value": "METERS"
        }
    ],
    "maxValue": 9460,
    "minValue": -100,
    "propertyID": "depth",
    "unitText": "m"
}
```
