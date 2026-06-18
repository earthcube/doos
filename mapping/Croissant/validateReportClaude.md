# GeoCroissant alignment review — `amundsen509_geocroissant.jsonld`

Independent review by Claude (Opus 4.8), verified against the live
[GeoCroissant 1.0 spec](https://docs.mlcommons.org/croissant/docs/croissant-geo-spec.html)
and by expanding the JSON-LD with `pyld`. Focus areas requested: **GeoSPARQL
elements** and **depth representation**.

This review was commissioned as a cross-check of a prior review
(`validate.md`). Where the two disagree, the disagreements are called out
explicitly below.

---

## Bottom line

- The **GeoSPARQL machinery (Use Case 4 / Use Case 8) is genuinely
  well-aligned** — `geosparql:hasGeometry` → geometry node → `geosparql:asWKT`
  typed as `wktLiteral` is implemented correctly and expands to the right OGC
  IRIs.
- The **depth representation is entirely an extension** that GeoCroissant
  neither defines nor validates. It is defensible (driven by GeoSPARQL Z-WKT +
  OIH), but the spec offers no conformance basis for it, and the
  positive-down Z convention carries real interoperability risk.
- **Two concrete defects** that `validate.md` got wrong or missed, plus one
  minor inconsistency. All are mechanical to fix.

---

## What the spec actually requires (verified)

- **`geocr:` namespace** = `http://mlcommons.org/croissant/geo/` (unversioned).
  The file's prefix matches exactly. ✓
- **Geometry is delegated to GeoSPARQL.** GeoCroissant defines no geometry
  property of its own; Use Case 4 uses `geosparql:hasGeometry` /
  `geosparql:asWKT`, and Use Case 8 authorizes reusing such external terms
  verbatim via a `@context` prefix mapping. ✓
- **`geocr:coordinateReferenceSystem`** is a real defined property. ✓
- **The spec contains *zero* mention of depth, vertical axes, the Z dimension,
  or 3D geometry.** All normative examples are 2D EO imagery (`box`, 2D
  polygons). This is the single most important fact for the depth question:
  depth alignment cannot be judged *against the spec* because the spec is
  silent on it.

---

## GeoSPARQL elements — mostly aligned, one real defect

| Element | Verdict |
|---|---|
| `geosparql` prefix in `@context` | ✓ Expands to correct OGC IRI |
| `geosparql:hasGeometry` → node → `geosparql:asWKT` chain | ✓ Canonical Use Case 4 pattern (confirmed in expansion) |
| `wktLiteral` typing + CRS84 URI prefix in the literal | ✓ Correct |
| `box` (horizontal) + `asWKT` (exact geometry) split | ✓ Matches Use Case 2 STAC `bbox`/`geometry` split |
| Dual encoding (`GeoShape.asWKT` **and** `hasGeometry` node) | ⚠ Redundant in RDF; allowed under UC8 but not in normative examples |

### Defect #1 — undeclared `amundsen509:` prefix (validate.md is WRONG here)

The named geometry nodes use a prefix that is **never declared** in
`@context`. `pyld` expansion confirms they do **not** become proper HTTP IRIs —
they collapse to an invented URI scheme named `amundsen509`:

```
"@id": "amundsen509:datasetDepthExtent"   →  amundsen509:datasetDepthExtent
"@id": "amundsen509:cast096DepthProfile"  →  amundsen509:cast096DepthProfile
"@id": "amundsen509:cast100MaxDepth"      →  amundsen509:cast100MaxDepth
```

`validate.md` describes these as "stable query targets" and "good practice for
persistent SPARQL references." They are *stable* only as opaque strings — the
`amundsen509:` scheme is fabricated and non-dereferenceable, which is almost
certainly unintended. **Fix:** declare an `amundsen509` prefix so they resolve
to real HTTP IRIs.

### Query-path caveat (validate.md got this right)

`geosparql:hasGeometry` sits on the nested `Place`, not directly on the record
node. Appendix C's `?record geosparql:hasGeometry ?geom` therefore needs an
extra hop through `spatialCoverage`. Not a violation, but a query-ergonomics
note that stands.

---

## Depth representation — valid extension, unsupported by the spec, semantically risky

GeoCroissant says nothing about depth, so everything here is layered on via
GeoSPARQL + OIH, not GeoCroissant:

1. **Z-coordinate WKT** (`LINESTRING Z`, `MULTIPOINT Z`, `POINT Z`) — valid in
   GeoSPARQL/WKT generally; silent in GeoCroissant. Acceptable as an extension.
2. **`variableMeasured` / `DepBelowSurf`** with min/max + NERC `propertyID` —
   OIH / schema.org territory, fully outside GeoCroissant. Complementary, no
   conflict.

Two substantive interoperability concerns:

- **Z is positive-down.** GeoSPARQL/WKT Z is conventionally *elevation,
  positive up*. The depths here increase downward (1.98 → 375.94). A generic
  GeoSPARQL engine performing 3D `within`/distance will read these as heights
  and silently invert the vertical sense. The "positive down" meaning lives
  only in the `description` prose — it is **not machine-discoverable**.
- **No vertical CRS.** `geocr:coordinateReferenceSystem: "EPSG:4326"` and the
  WKT `CRS84` are both 2D horizontal CRSs. There is no compound/vertical CRS
  declaring the depth datum or units, so the Z axis semantics are undeclared at
  the data level. (Minor axis-order nuance: `box` is lat/lon per schema.org;
  WKT is lon/lat per CRS84 — each is internally correct, but the dataset-level
  `EPSG:4326` label is lat/lon-ordered while the geometries are CRS84 lon/lat.)

---

## Defect #2 — Croissant `data`/`key` keywords unmapped (validate.md MISSED this)

In `spatialRecordSet`, the inline-data keywords `data` and `key` are **not
mapped** in `@context`. Under `@vocab: https://schema.org/` they expand to the
wrong namespace (confirmed in expansion):

```
"data"  →  https://schema.org/data    (should be cr:data)
"key"   →  https://schema.org/key     (should be cr:key)
```

This means the `spatialRecordSet`'s embedded records are not valid Croissant
`RecordSet` data — a **base Croissant 1.0** conformance issue, independent of
GeoCroissant. **Fix:** add `"data": "cr:data"` and `"key": "cr:key"` to
`@context`.

---

## Minor / non-blocking

| Item | Note |
|---|---|
| `FileSet` `encodingFormat` | Declared `application/json` while globbing NetCDF `*.*`; inconsistent with the `application/x-netcdf` `FileObject`. Fixed to `application/x-netcdf` in the corrected copy. |
| `conformsTo` Croissant `1.0` vs `1.1` | Spec's own example pairs `geo/1.0` with `croissant/1.1`. `1.0` is the source ERDDAP export version and is defensible; left unchanged. |
| `spatialRecordSet` cast coordinates | Illustrative placeholders, not sourced from ERDDAP. Spec does not require live `data[]`. Left unchanged. |

---

## Machine verification (pyld expansion)

- `geosparql:hasGeometry` → `http://www.opengis.net/ont/geosparql#hasGeometry` ✓
- `geosparql:asWKT` → `http://www.opengis.net/ont/geosparql#asWKT` ✓
- `amundsen509:*` geometry node `@id`s expand to a fabricated `amundsen509:`
  scheme (Defect #1) ✗
- `data` / `key` expand to `https://schema.org/data` and
  `https://schema.org/key` instead of the `cr:` namespace (Defect #2) ✗

---

## Verdict vs. `validate.md`

`validate.md`'s high-level conclusions are sound: UC4/UC8 conformance, 3D WKT
treated as an extension, and the STAC-style `box`/`asWKT` split are all correct
calls. The parts that do **not** hold up:

1. Its claim that the named geometry IRIs are well-formed / "good practice" —
   they use an undeclared prefix and expand to a dummy scheme (**Defect #1**).
2. Its clean bill on RDF expansion — it missed the `data`/`key` keyword
   misbinding (**Defect #2**).

### Fixes applied in the corrected copy

A corrected file is provided at `amundsen509_geocroissant_fixed.jsonld` (the
original is left untouched for diffing). Changes:

1. Added `"amundsen509"` prefix to `@context` → named geometry nodes resolve to
   real HTTP IRIs.
2. Added `"data": "cr:data"` and `"key": "cr:key"` to `@context` → valid
   Croissant `RecordSet` data.
3. Changed the `FileSet` `encodingFormat` to `application/x-netcdf` for
   consistency with the files it globs.

The positive-down Z and missing vertical-CRS concerns are **not** auto-fixed —
they are modeling decisions for the data provider, not mechanical errors.
