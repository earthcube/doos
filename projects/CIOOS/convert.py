import json
from typing import Any, Dict, List, Optional

def ckan_to_schemaorg_dataset(pkg: Dict[str, Any]) -> Dict[str, Any]:
    """
    High-performance, zero-dependency mapper: CKAN package → schema.org/Dataset JSON-LD.
    Only handles the exact elements you listed (standard CKAN + spatial/temporal + CIOOS extras).
    Returns clean, valid JSON-LD ready for embedding or API response.
    """
    # Base
    dataset: Dict[str, Any] = {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "@id": f"https://catalogue.cioos.ca/dataset/{pkg.get('name', pkg.get('id'))}",  # canonical URL
        "identifier": [
            pkg.get("id"),                                      # CKAN id
            pkg.get("name"),                                    # CKAN name (slug)
            pkg.get("unique-resource-identifier-full")          # DOI if present
        ],
        "name": pkg.get("title"),
        "description": pkg.get("notes"),
        "license": pkg.get("license_id"),                       # often "odc-by" or full URL
        "url": f"https://catalogue.cioos.ca/dataset/{pkg.get('name')}",
        "isAccessibleForFree": pkg.get("isopen", False),
    }

    # Organization → publisher
    if org := pkg.get("organization"):
        dataset["publisher"] = {
            "@type": "Organization",
            "name": org.get("title") or org.get("name"),
            "identifier": org.get("id")
        }

    # Resources → distribution (array of DataDownload)
    if resources := pkg.get("resources"):
        dataset["distribution"] = [
            {
                "@type": "DataDownload",
                "name": r.get("name"),
                "contentUrl": r.get("url"),
                "encodingFormat": r.get("format") or r.get("mimetype"),
                "license": r.get("license") or pkg.get("license_id")
            }
            for r in resources
        ]

    # Spatial / bbox → spatialCoverage
    spatial = pkg.get("spatial")
    if isinstance(spatial, dict) and spatial.get("type") == "Polygon":  # GeoJSON
        dataset["spatialCoverage"] = {
            "@type": "Place",
            "geo": {
                "@type": "GeoShape",
                "polygon": " ".join(f"{lon} {lat}" for lon, lat in spatial["coordinates"][0])
            }
        }
    elif bbox_fields := {k: v for k, v in pkg.items() if k.startswith("bbox-")}:
        # Fallback to bbox-* fields → GeoShape.box (south west north east)
        box = f"{bbox_fields.get('bbox-south-lat', '')} {bbox_fields.get('bbox-west-long', '')} " \
              f"{bbox_fields.get('bbox-north-lat', '')} {bbox_fields.get('bbox-east-long', '')}"
        dataset["spatialCoverage"] = {
            "@type": "Place",
            "geo": {"@type": "GeoShape", "box": box.strip()}
        }

    # Temporal
    if temporal := pkg.get("temporal-extent"):
        begin = temporal.get("begin") or temporal.get("start")
        end = temporal.get("end") or temporal.get("end")
        if begin and end:
            dataset["temporalCoverage"] = f"{begin}/{end}"
        elif begin:
            dataset["temporalCoverage"] = begin

    # CIOOS ocean extras
    if eov := pkg.get("eov"):
        dataset["variableMeasured"] = [
            {"@type": "PropertyValue", "name": f"EOV: {val}"} for val in (eov if isinstance(eov, list) else [eov])
        ]
    if ecv := pkg.get("ecv"):
        dataset.setdefault("keywords", []).extend(
            [f"ECV: {val}" for val in (ecv if isinstance(ecv, list) else [ecv])]
        )

    # cited-responsible-party → creator/contributor (role-based)
    if parties := pkg.get("cited-responsible-party"):
        creators = []
        for p in parties if isinstance(parties, list) else [parties]:
            role = p.get("role", "").lower()
            entry = {"@type": "Organization" if p.get("organisation-name") else "Person", "name": p.get("name") or p.get("organisation-name")}
            if role in ("author", "principalinvestigator", "custodian"):
                creators.append(entry)
        if creators:
            dataset["creator"] = creators

    # Extra CIOOS fields as additionalProperty (clean & extensible)
    extras = []
    for key in ("frequency-of-update", "progress", "included_in_data_catalogue"):
        if val := pkg.get(key):
            extras.append({"@type": "PropertyValue", "name": key, "value": val})
    if extras:
        dataset["additionalProperty"] = extras

    # State / type (for completeness, though rarely needed in schema.org)
    if pkg.get("state") != "active":
        dataset["additionalProperty"] = dataset.get("additionalProperty", []) + [
            {"@type": "PropertyValue", "name": "ckanState", "value": pkg.get("state")}
        ]

    return dataset


# =============================================================================
# EXAMPLE USAGE (drop-in replacement for your earlier get_ckan_metadata)
# =============================================================================
def example_usage():
    # Simulate a minimal CKAN package with exactly the elements you listed
    sample_pkg = {
        "id": "10-25976-4y34-rn27",
        "name": "peskotomuhkati-nation-coastal-restoration",
        "title": "Peskotomuhkati Nation Coastal Restoration – water quality monitoring",
        "notes": "Long-term water quality monitoring for coastal restoration.",
        "license_id": "odc-by",
        "resources": [{"name": "Access data", "url": "https://doi.org/10.25976/4y34-rn27"}],
        "organization": {"title": "DataStream"},
        "isopen": True,
        "state": "active",
        "type": "dataset",

        "spatial": {"type": "Polygon", "coordinates": [[[-67.788, 44.705], [-66.445, 44.705], [-66.445, 45.858], [-67.788, 45.858], [-67.788, 44.705]]]},
        # or bbox-* fields if GeoJSON missing
        "bbox-south-lat": 44.705, "bbox-west-long": -67.788, "bbox-north-lat": 45.858, "bbox-east-long": -66.445,

        "temporal-extent": {"begin": "2019-09-25", "end": "2026-03-04"},

        "eov": ["other"],
        "ecv": ["water quality"],
        "cited-responsible-party": [{"role": "author", "name": "Passamaquoddy Recognition Group Inc."}],
        "frequency-of-update": "monthly",
        "progress": "onGoing",
        "unique-resource-identifier-full": "https://doi.org/10.25976/4y34-rn27",
        "included_in_data_catalogue": "CIOOS National"
    }

    ld = ckan_to_schemaorg_dataset(sample_pkg)
    print(json.dumps(ld, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    example_usage()
