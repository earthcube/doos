# GeoCroissant alignment review

Review of `amundsen509_geocroissant.jsonld` against the [GeoCroissant 1.0 spec](https://docs.mlcommons.org/croissant/docs/croissant-geo-spec.html), with focus on GeoSPARQL elements and how they land in RDF.

---

## Spec framework (what GeoCroissant actually requires)

GeoCroissant does **not** define its own geometry properties. For geometry it delegates to **external vocabularies** (Use Case 8):

> If a required metadata attribute is already defined in an established external vocabulary (e.g., **GeoSPARQL**), GeoCroissant recommends **reusing that term verbatim** by declaring the appropriate prefix/IRI mapping in the JSON-LD `@context`.

The Use Case 4 table makes this explicit:

| GeoCroissant role | External vocabulary |
|---|---|
| `geocr:spatialIndex` (optional index hook) | — |
| Geometry encoding | `geosparql:hasGeometry`, `geosparql:asWKT` |
| Record exposure | `cr:recordSet` |

STAC interoperability (Use Case 2) reinforces the same mapping:

| STAC `geometry` | External vocabulary |
|---|---|
| — | `geosparql:hasGeometry`, `geosparql:asWKT` |

| STAC `bbox` | `schema:spatialCoverage` / `GeoShape.box` |

So GeoSPARQL terms are **normative external vocabulary**, not optional embellishment. The file is aligned with that design principle.

---

## Element-by-element justification

### 1. `@context` — `geosparql` prefix

```json
"geosparql": "http://www.opengis.net/ont/geosparql#"
```

**Aligned.** Use Case 8 requires prefix/IRI declaration before using external terms. The file uses `geosparql:hasGeometry` and `geosparql:asWKT` as prefixed properties, which expand to the correct OGC IRIs (verified via `pyld` expansion).

### 2. `conformsTo` — dual Croissant + GeoCroissant declaration

```json
"conformsTo": [
  "http://mlcommons.org/croissant/1.0",
  "http://mlcommons.org/croissant/geo/1.0"
]
```

**Aligned.** Prerequisites require both base Croissant and GeoCroissant conformance URIs. Using Croissant 1.0 (source ERDDAP export version) instead of 1.1 is explicitly allowed (“Croissant 1.0 or 1.1”).

### 3. `geocr:coordinateReferenceSystem`

```json
"geocr:coordinateReferenceSystem": "EPSG:4326"
```

**Aligned.** Listed under Generic Geospatial Datasets and Use Case 2 (STAC `proj:epsg` mapping). Pairs with `CRS84` in WKT literals (`EPSG:4326` ≈ WGS 84 / CRS84 for lon-lat).

### 4. Dataset `spatialCoverage` — layered 2D + 3D geometry

The file uses three coordinated layers:

| Layer | Mechanism | Spec basis |
|---|---|---|
| Horizontal extent | `GeoShape.box` | Use Case 2 / STAC `bbox` → `spatialCoverage` |
| Human + schema.org discovery | `GeoShape` + `geosparql:asWKT` inside `geo[]` | Use Case 8: direct GeoSPARQL term on schema.org structure |
| Graph-queryable geometry | `geosparql:hasGeometry` → geometry node → `geosparql:asWKT` | Use Case 4 canonical pattern |

**`geosparql:hasGeometry` on `Place` (dataset level)**

```json
"spatialCoverage": {
  "@type": "Place",
  "geo": [ ... ],
  "geosparql:hasGeometry": {
    "@id": "amundsen509:datasetDepthExtent",
    "geosparql:asWKT": { ... }
  }
}
```

**Justified.** Use Case 4: `hasGeometry` “links a **dataset/record** to a GeoSPARQL geometry node.” Here the dataset links to extent via `schema:spatialCoverage` → `Place` → `hasGeometry` → `amundsen509:datasetDepthExtent`. RDF triples:

```
_:place geosparql:hasGeometry <amundsen509:datasetDepthExtent> .
<amundsen509:datasetDepthExtent> geosparql:asWKT "…LINESTRING Z…"^^geosparql:wktLiteral .
```

Named geometry IRIs (`amundsen509:datasetDepthExtent`) are good practice for persistent SPARQL references.

**`geosparql:asWKT` inside `GeoShape`**

```json
{
  "@type": "GeoShape",
  "geosparql:asWKT": {
    "@value": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> LINESTRING Z (...)",
    "@type": "geosparql:wktLiteral"
  }
}
```

**Justified, with nuance.** GeoCroissant normative examples show only `box` inside `GeoShape`; they do not show `asWKT` on `GeoShape`. However:

- Use Case 8 explicitly authorizes embedding GeoSPARQL properties wherever schema.org structure carries spatial information.
- Use Case 2 maps STAC `geometry` → `hasGeometry`/`asWKT`, while `bbox` → `spatialCoverage` — this file implements **both** paths, which matches the STAC split.
- The OIH depth profile (referenced in README) uses exactly this `GeoShape` + `geosparql:asWKT` pattern for `POINT Z`.

The duplication (`GeoShape.asWKT` **and** `hasGeometry.asWKT`) is redundant in RDF but **intentionally dual-purpose**: schema.org/OIH consumers read `geo[]`; GeoSPARQL engines traverse `hasGeometry` → geometry node.

### 5. WKT literal typing and CRS prefix

```json
"@value": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84> LINESTRING Z (...)",
"@type": "geosparql:wktLiteral"
```

**Aligned.** Use Case 4: `asWKT` encodes geometry as a **typed WKT literal** for GeoSPARQL functions (`geof:sfWithin`, etc.). Appendix C filters use `^^geosparql:wktLiteral`. Expansion produces the correct datatype IRI.

CRS84 URI prefix in the literal is standard OGC WKT practice and consistent with OIH examples.

### 6. Z-dimensional WKT (`LINESTRING Z`, `MULTIPOINT Z`, `POINT Z`)

**Justified as a valid GeoSPARQL extension, not explicitly exemplified in GeoCroissant.**

GeoCroissant examples are EO-imagery-centric (2D `box`, 2D polygons). The spec does not prohibit 3D WKT — it says reuse GeoSPARQL terms verbatim, and GeoSPARQL/WKT supports Z/M dimensions. For CTD profiles:

- `LINESTRING Z` at fixed lon/lat with varying Z = vertical cast extent (positioning claim)
- `MULTIPOINT Z` = shallow/deep bounds
- `POINT Z` = deepest sample location

Z as depth below surface (positive down) follows CF metadata from the source dataset (`geospatial_vertical_positive=down`), which is domain-correct even though GeoCroissant does not define vertical axis semantics.

### 7. `spatialRecordSet` — Use Case 4 record-level geometry

**Structure aligned with Use Case 3 record pattern, extended for Use Case 4.**

Use Case 3 defines record fields:

```json
"@id": "records_recordset/spatialCoverage",
"dataType": "sc:Place"
```

The file mirrors that (`spatialRecordSet/spatialCoverage`, `dataType: sc:Place`) and adds `geosparql:hasGeometry` inside each `Place` in `data[]` — the Use Case 4 extension of the Use Case 3 skeleton.

RDF produced for cast 96:

```
_:record → _:place (via spatialCoverage field value)
_:place geosparql:hasGeometry → <amundsen509:cast096DepthProfile>
<amundsen509:cast096DepthProfile> geosparql:asWKT → "LINESTRING Z…"^^wktLiteral
```

**Aligned** with the geometry chain Use Case 4 describes (`hasGeometry` → `asWKT`), even though geometry sits under `spatialCoverage` rather than directly on the record node.

### 8. `cr:recordSet` presence

**Aligned.** Use Case 4 lists `cr:recordSet` as a key property for atomic, queryable records. The file has two record sets (`dataRecordSet` for ML tabular schema, `spatialRecordSet` for GeoSPARQL footprints), both linked via `cr:recordSet` on the dataset.

### 9. `variableMeasured` / `DepBelowSurf`

**Outside GeoSPARQL scope but complementary.** GeoCroissant does not govern depth variables; that is OIH/schema.org territory. It does not conflict with Use Case 4 — it provides the second OIH depth pattern (measured variable with min/max) alongside the geometry positioning claim.

---

## Gaps and query-path caveats

These are not violations, but places where the document diverges from spec **examples** or where Appendix C queries need adaptation.

| Item | Status | Detail |
|---|---|---|
| `geocr:spatialIndex` | Optional, absent | Spec: “optional indexing hook.” Not required. Could add H3/geohash tokens later for coarse filtering. |
| Appendix C Query 1 as written | Needs traversal | Query assumes `?record geosparql:hasGeometry ?geom` **directly** on the record. In this file, `hasGeometry` is on the nested `Place`, not the record blank node. Working query: `?dataset cr:recordSet/cr:data ?record . ?record …/spatialCoverage ?place . ?place geosparql:hasGeometry ?geom .` |
| Appendix C `geocr:Dataset` / `geocr:recordSet` | Illustrative SPARQL aliases | JSON-LD authoring uses `sc:Dataset` and `cr:recordSet` (as in all spec JSON examples). RDF emits `schema:Dataset` and `cr:recordSet` — correct for JSON-LD; Appendix C uses geocr classes as query convenience. |
| `geosparql:asWKT` on `GeoShape` | Not in normative GeoCroissant JSON examples | Allowed under Use Case 8 external vocabulary reuse; matches OIH. Redundant with `hasGeometry` path. |
| Cast coordinates in `spatialRecordSet` | Illustrative, not sourced from ERDDAP | Spec does not require live data in `data[]`; values are placeholders demonstrating geometry encoding. |
| Dataset centroid for `LINESTRING Z` | Derived, not explicit in source | Reasonable aggregation of bbox + depth min/max; not a spec violation. |

---

## RDF expansion summary (machine verification)

`pyld` expansion confirms:

- All `geosparql:hasGeometry` assertions use the correct IRI `http://www.opengis.net/ont/geosparql#hasGeometry`
- All `asWKT` literals are typed `geosparql:wktLiteral`
- Named geometry nodes (`amundsen509:datasetDepthExtent`, `cast096DepthProfile`, `cast100MaxDepth`) are stable query targets
- `dct:conformsTo` emits both Croissant and GeoCroissant URIs
- `geocr:coordinateReferenceSystem` emits under the stable `geocr` namespace (unversioned, per spec)

---

## Overall verdict

**The GeoSPARQL elements are well-aligned with GeoCroissant 1.0**, particularly:

1. **Use Case 8** — GeoSPARQL reused as external vocabulary, not reinvented
2. **Use Case 4** — `hasGeometry` + `asWKT` + `wktLiteral` geometry chain is correctly implemented
3. **Use Case 2** — STAC-style split between `spatialCoverage.box` (horizontal) and `hasGeometry`/`asWKT` (exact geometry)
4. **Use Case 3** — Record-level `spatialCoverage` as `sc:Place` with geometry payloads in `data[]`

The main extensions beyond spec examples are **3D WKT for ocean depth** (valid GeoSPARQL, driven by OIH depth guidance) and **dual encoding** (`GeoShape.asWKT` plus `hasGeometry` node). Both are defensible under Use Case 8’s “employ the external property directly” rule.

The one practical refinement for tighter Appendix C compatibility would be placing `geosparql:hasGeometry` **directly on each record node** (alongside or instead of nesting under `Place`), so `?record geosparql:hasGeometry ?geom` works without an extra hop. That is a query-ergonomics improvement, not a spec compliance fix.