# Croissant mapping

## About

This directory holds Croissant and GeoCroissant JSON-LD metadata for ocean profile datasets, with a focus on expressing **depth** in a way that supports GeoSPARQL discovery.

| Spec | URL |
|------|-----|
| Croissant 1.0 | http://mlcommons.org/croissant/1.0 |
| GeoCroissant 1.0 | https://docs.mlcommons.org/croissant/docs/croissant-geo-spec.html |
| OIH Depth | https://book.odis.org/thematics/depth/index.html |

## Files

| File | Description |
|------|-------------|
| `amundsen509_83c3_3f3a_b60c.jsonld` | Full Croissant 1.0 export from ERDDAP (Amundsen Science `amundsen509` CTD dataset). 2D `spatialCoverage` only; depth appears in `variableMeasured` and record fields. |
| `amundsen509_geocroissant.jsonld` | Trimmed GeoCroissant derivative of the file above, with depth expressed via GeoSPARQL WKT (see below). |

## Depth representation approach

The OIH depth guidance defines two complementary patterns. The GeoCroissant file uses **both**, aligned with GeoCroissant **Use Case 4: Search and Discovery (GeoSPARQL)**.

### 1. Depth as a spatial property on geometry (positioning claim)

Depth is encoded in the **Z** dimension of GeoSPARQL WKT literals under `spatialCoverage`, using the external `geosparql` vocabulary (GeoCroissant reuses established vocabularies rather than inventing new terms).

- **CRS**: `CRS84` (`EPSG:4326`), coordinates ordered longitude latitude.
- **Z semantics**: depth below the sea surface in metres, **positive down** (consistent with CF `geospatial_vertical_positive=down` in the source ERDDAP metadata).
- **Geometry types used**:
  - `LINESTRING Z` — vertical extent at the dataset centroid (shallow to deep bound).
  - `MULTIPOINT Z` — shallow and deep bound as separate 3D points.
  - `geosparql:hasGeometry` + `geosparql:asWKT` — explicit geometry node for GeoSPARQL triple-store queries (Appendix C of the GeoCroissant spec).

The original 2D `box` bounding envelope is retained alongside the 3D geometries so horizontal discovery paths remain unchanged.

### 2. Depth as a measured variable (discovery metadata)

A trimmed `variableMeasured` entry names the depth axis `DepBelowSurf` (OIH depth-profile convention) with `minValue` / `maxValue`, NERC `propertyID`, and `unitText: m`. This covers datasets where depth is a profile coordinate rather than a single geometry vertex.

### 3. Record-level GeoSPARQL (cast footprints)

A separate `spatialRecordSet` holds illustrative CTD cast records. Each record's `spatialCoverage` carries cast-specific `geosparql:hasGeometry` / `geosparql:asWKT` values:

- `LINESTRING Z` for a full vertical cast profile.
- `POINT Z` for a deepest-sample location.

These mirror the query pattern in GeoCroissant Appendix C (`?record geosparql:hasGeometry ?geom . ?geom geosparql:asWKT ?wkt`).

### GeoCroissant-specific additions

- `conformsTo`: `http://mlcommons.org/croissant/1.0` and `http://mlcommons.org/croissant/geo/1.0`
- `geocr:coordinateReferenceSystem`: `EPSG:4326`
- `@context` prefixes: `geocr`, `geosparql`, `cr`, `dct`

### Size reduction

The GeoCroissant copy is intentionally smaller than the source Croissant file:

- One representative `FileObject` instead of 21 NetCDF distributions.
- Seven `dataRecordSet` fields (cast, station, lat/lon, depth, temperature, salinity) instead of the full ERDDAP column set.
- One `variableMeasured` entry (depth) instead of all observed parameters.
- Two illustrative `spatialRecordSet` rows instead of inline data for every cast.

## Minimal GeoSPARQL depth example (OIH)

```json
{
    "@context": {
        "@vocab": "https://schema.org/",
        "geosparql": "http://www.opengis.net/ont/geosparql#"
    },
    "@id": "https://example.org/permanentUrlToThisJsonDoc",
    "@type": "Dataset",
    "name": "Data set name",
    "spatialCoverage": {
        "@type": "Place",
        "geo": {
            "@type": "GeoShape",
            "url": "http://marineregions.org/mrgid/4252/geometries?source=25&attributeValue=16",
            "description": "an example POINT Z entry",
            "geosparql:asWKT": {
                "@value": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> POINT Z (30.5 75.2 125.8)",
                "@type": "geosparql:wktLiteral"
            }
        }
    }
}
```

## Example: dataset-level depth extent in GeoCroissant

From `amundsen509_geocroissant.jsonld`:

```json
"spatialCoverage": {
  "@type": "Place",
  "geo": [
    {
      "@type": "GeoShape",
      "box": "63.5352 -82.1352 67.8837 -75.8348"
    },
    {
      "@type": "GeoShape",
      "geosparql:asWKT": {
        "@value": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> LINESTRING Z (-78.985 65.70945 1.98, -78.985 65.70945 375.94)",
        "@type": "geosparql:wktLiteral"
      }
    }
  ],
  "geosparql:hasGeometry": {
    "@id": "amundsen509:datasetDepthExtent",
    "geosparql:asWKT": {
      "@value": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> LINESTRING Z (-78.985 65.70945 1.98, -78.985 65.70945 375.94)",
      "@type": "geosparql:wktLiteral"
    }
  }
}
```