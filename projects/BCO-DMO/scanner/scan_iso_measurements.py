#!/usr/bin/env python3
"""
Scan BCO-DMO ISO 19115 metadata for depth/pressure measurements.

Reads the JSON produced by ``scan_erddap.py`` (an ERDDAP search/inventory),
fetches each dataset's ISO 19115-2 record from www.bco-dmo.org, and extracts the
measured variables. Variables whose name relates to depth or pressure are
reported, then expressed as a schema.org ``Dataset`` with ``variableMeasured``
PropertyValue entries following the ODIS depth pattern:

    https://book.odis.org/thematics/depth/index.html

BCO-DMO ISO records describe variables in two parallel keyword blocks:
  * type="theme"       — the dataset's own column names    (-> dataset-parameter LOD URI)
  * type="featureType" — BCO-DMO Standard Parameter names   (-> parameter LOD URI)
The blocks are index-aligned, so each column is paired with its standardized
parameter and the canonical LOD URI is used as the PropertyValue propertyID.

The ISO record holds no numeric measurement values, so each matched variable is
enriched from the dataset's ERDDAP ``info`` JSON: ``actual_range`` supplies
minValue/maxValue, ``units`` supplies unitText/unitCode, and ``long_name``
supplies the description.

Usage:
    # Scan every dataset in the input and print findings + JSON-LD
    python scan_iso_measurements.py --input scan_results.json

    # Limit to the first 5 datasets while testing
    python scan_iso_measurements.py --input scan_results.json --limit 5

    # Suppress the JSON-LD and only print the plain-text findings
    python scan_iso_measurements.py --input scan_results.json --no-jsonld

    # Write one <datasetID>.jsonld file per match into a directory
    python scan_iso_measurements.py --input scan_results.json --save-dir jsonld_out
"""

import argparse
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

USER_AGENT = "BCO-DMO-Scanner/1.0 (DOOS; dfils@ucsd.edu)"
TIMEOUT = 30

# ISO 19139 / 19115-2 namespaces used by BCO-DMO records.
NS = {
    "gmd": "http://www.isotc211.org/2005/gmd",
    "gco": "http://www.isotc211.org/2005/gco",
    "gmx": "http://www.isotc211.org/2005/gmx",
    "xlink": "http://www.w3.org/1999/xlink",
}

# A variable is considered depth/pressure related if its name (column or
# standardized) contains one of these case-insensitive substrings.
DEPTH_PRESSURE_TERMS = ("depth", "press", "bathy", "dbar")

# Conservative unit-text -> unitCode URIs, applied only when the unit is
# unambiguous. Mirrors the ODIS depth pattern's recommended URIs.
UNIT_CODE = {
    "m": [
        "https://qudt.org/vocab/unit/M",
        "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
    ],
    "meter": [
        "https://qudt.org/vocab/unit/M",
        "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
    ],
    "meters": [
        "https://qudt.org/vocab/unit/M",
        "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
    ],
    "dbar": ["https://qudt.org/vocab/unit/BAR"],
}


def _session():
    """Return a requests Session with the project's standard User-Agent."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _clean_uri(href):
    """Normalize a BCO-DMO LOD href into a resource URI (drop a trailing .rdf)."""
    if not href:
        return None
    return href[:-4] if href.endswith(".rdf") else href


def _keyword_entries(md_keywords):
    """
    Return [(name, href), ...] for the keywords in one MD_Keywords element.

    Keyword content is either a gmx:Anchor (carrying an xlink:href to a LOD
    parameter URI) or a plain gco:CharacterString.
    """
    entries = []
    for kw in md_keywords.findall("gmd:keyword", NS):
        anchor = kw.find("gmx:Anchor", NS)
        if anchor is not None:
            name = (anchor.text or "").strip()
            href = anchor.get(f"{{{NS['xlink']}}}href")
        else:
            cs = kw.find("gco:CharacterString", NS)
            name = (cs.text or "").strip() if cs is not None else ""
            href = None
        if name:
            entries.append((name, href))
    return entries


def parse_variables(xml_text):
    """
    Extract the measured variables from a BCO-DMO ISO 19115 record.

    Pairs the dataset's column-name keyword block (type="theme") with the
    BCO-DMO Standard Parameters block (type="featureType") by position. Returns
    one dict per variable:

        {
            "name": column name,
            "dataset_parameter_uri": LOD dataset-parameter URI or None,
            "standard_name": standardized parameter name or None,
            "standard_parameter_uri": LOD parameter URI or None,
        }
    """
    root = ET.fromstring(xml_text)

    columns = []
    standards = []
    for md in root.iter(f"{{{NS['gmd']}}}MD_Keywords"):
        type_code = md.find("gmd:type/gmd:MD_KeywordTypeCode", NS)
        kind = type_code.get("codeListValue") if type_code is not None else None
        entries = _keyword_entries(md)
        if kind == "theme":
            columns = entries
        elif kind == "featureType":
            standards = entries

    paired = len(columns) == len(standards)
    variables = []
    for i, (name, href) in enumerate(columns):
        std_name, std_href = standards[i] if paired else (None, None)
        variables.append(
            {
                "name": name,
                "dataset_parameter_uri": _clean_uri(href),
                "standard_name": std_name,
                "standard_parameter_uri": _clean_uri(std_href),
            }
        )
    return variables


def is_depth_pressure(variable):
    """Return True if either the column or standardized name looks depth/pressure related."""
    haystack = " ".join(
        filter(None, [variable.get("name"), variable.get("standard_name")])
    ).lower()
    return any(term in haystack for term in DEPTH_PRESSURE_TERMS)


def _norm(text):
    """Lowercase and strip non-alphanumerics for fuzzy name matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower()) if text else ""


def fetch_erddap_variables(session, info_url):
    """
    Return {variable_name: {attribute: value, ...}} from an ERDDAP info JSON.

    The info table lists one row per (variable, attribute); we collect the
    attribute rows (units, long_name, actual_range, ...) per variable.
    """
    resp = session.get(info_url, timeout=TIMEOUT)
    resp.raise_for_status()
    table = resp.json()["table"]
    cols = table["columnNames"]
    ri, vi = cols.index("Row Type"), cols.index("Variable Name")
    ai, val = cols.index("Attribute Name"), cols.index("Value")

    variables = {}
    for row in table["rows"]:
        if row[ri] != "attribute" or not row[vi]:
            continue
        variables.setdefault(row[vi], {})[row[ai]] = row[val]
    return variables


def match_erddap_attrs(iso_name, erddap_variables):
    """
    Find the ERDDAP attributes for an ISO variable name.

    ERDDAP sometimes renames a source column (e.g. "MaxDepth" becomes the
    "depth" axis), so fall back from an exact name match to a normalized match
    on the variable name and then on its long_name.
    """
    if iso_name in erddap_variables:
        return erddap_variables[iso_name]
    target = _norm(iso_name)
    for name, attrs in erddap_variables.items():
        if _norm(name) == target:
            return attrs
    for attrs in erddap_variables.values():
        if _norm(attrs.get("long_name")) == target:
            return attrs
    return None


def _parse_actual_range(value):
    """Parse an ERDDAP actual_range like '0.5, 200.0' into (min, max) floats."""
    try:
        lo, hi = (part.strip() for part in str(value).split(",")[:2])
        return float(lo), float(hi)
    except (ValueError, TypeError):
        return None, None


def to_property_value(variable, attrs=None):
    """
    Express one variable as a schema.org PropertyValue (ODIS depth pattern).

    Prefers the standardized BCO-DMO parameter URI as propertyID, falling back
    to the dataset-parameter URI. When ERDDAP attributes are supplied, fills in
    description (long_name), unitText/unitCode (units), and minValue/maxValue
    (actual_range).
    """
    prop_id = variable.get("standard_parameter_uri") or variable.get(
        "dataset_parameter_uri"
    )
    pv = {"@type": "PropertyValue", "name": variable["name"]}
    if variable.get("standard_name"):
        pv["alternateName"] = variable["standard_name"]
    if prop_id:
        pv["propertyID"] = prop_id

    if attrs:
        if attrs.get("long_name"):
            pv["description"] = attrs["long_name"]
        lo, hi = _parse_actual_range(attrs.get("actual_range"))
        if lo is not None:
            pv["minValue"] = lo
        if hi is not None:
            pv["maxValue"] = hi
        units = attrs.get("units")
        if units:
            pv["unitText"] = units
            code = UNIT_CODE.get(units.strip().lower())
            if code:
                pv["unitCode"] = code
    return pv


def build_jsonld(record, depth_vars, erddap_variables=None):
    """
    Build a schema.org Dataset JSON-LD document for one dataset.

    Args:
        record: A dataset entry from the scan_erddap.py output
        depth_vars: The depth/pressure variables to express as variableMeasured
        erddap_variables: ERDDAP info attributes keyed by variable name, used to
            enrich each PropertyValue with units and min/max values

    Returns:
        dict: a JSON-LD document
    """
    erddap_variables = erddap_variables or {}
    landing = record.get("access", {}).get("landing_page", {}).get("url")
    doc = {
        "@context": {"@vocab": "https://schema.org/"},
        "@id": landing or record.get("infoUrl"),
        "@type": "Dataset",
        "name": record.get("title"),
        "description": record.get("summary"),
        "identifier": record.get("datasetID"),
        "variableMeasured": [
            to_property_value(v, match_erddap_attrs(v["name"], erddap_variables))
            for v in depth_vars
        ],
    }
    if landing:
        doc["url"] = landing
    return {k: v for k, v in doc.items() if v is not None}


def iso_url_for(record):
    """Return the ISO 19115 URL for a dataset record, or None if unavailable."""
    return record.get("access", {}).get("iso_19115", {}).get("url")


def main():
    parser = argparse.ArgumentParser(
        description="Scan BCO-DMO ISO 19115 metadata for depth/pressure measurements"
    )
    parser.add_argument(
        "--input",
        default="scan_results.json",
        help="ERDDAP scan results JSON (default: scan_results.json)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N datasets (useful while testing)",
    )
    parser.add_argument(
        "--jsonld",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Print schema.org JSON-LD for matches (default: on; --no-jsonld to disable)",
    )
    parser.add_argument(
        "--save-dir",
        default=None,
        help="If set, write each match's JSON-LD to <save-dir>/<datasetID>.jsonld",
    )

    args = parser.parse_args()

    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    datasets = data.get("datasets", [])
    if args.limit is not None:
        datasets = datasets[: args.limit]

    print(
        f"Scanning {len(datasets)} dataset(s) from {args.input} "
        f"for depth/pressure measurements...\n",
        file=sys.stderr,
    )

    save_dir = None
    if args.save_dir:
        save_dir = Path(args.save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

    session = _session()
    match_count = 0
    saved_count = 0

    for record in datasets:
        dataset_id = record.get("datasetID", "?")
        url = iso_url_for(record)
        if not url:
            print(f"[skip] {dataset_id}: no ISO 19115 URL", file=sys.stderr)
            continue

        try:
            resp = session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            variables = parse_variables(resp.text)
        except (requests.RequestException, ET.ParseError) as e:
            print(f"[skip] {dataset_id}: {e}", file=sys.stderr)
            continue

        depth_vars = [v for v in variables if is_depth_pressure(v)]
        if not depth_vars:
            continue

        # Enrich with ERDDAP variable attributes (units + numeric actual_range);
        # the ISO record carries no numeric measurement values. One fetch per
        # dataset serves every matched variable.
        erddap_variables = {}
        info_url = record.get("access", {}).get("erddap_info", {}).get("url")
        if info_url:
            try:
                erddap_variables = fetch_erddap_variables(session, info_url)
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status in (401, 403):
                    # The dataset is access-restricted in ERDDAP even though its
                    # ISO metadata is public; fall back to ISO-only output.
                    print(
                        f"[note] {dataset_id}: ERDDAP data access restricted "
                        f"(HTTP {status}); using ISO metadata only.",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"[warn] {dataset_id}: ERDDAP enrichment failed: {e}",
                        file=sys.stderr,
                    )
            except (requests.RequestException, ValueError, KeyError) as e:
                print(
                    f"[warn] {dataset_id}: ERDDAP enrichment failed: {e}",
                    file=sys.stderr,
                )

        match_count += 1
        print("=" * 78)
        print(f"{dataset_id}  —  {record.get('title', '')}")
        print(f"ISO: {url}")
        print(f"Depth/pressure variables ({len(depth_vars)} of {len(variables)}):")
        for v in depth_vars:
            std = f"  [{v['standard_name']}]" if v.get("standard_name") else ""
            prop = v.get("standard_parameter_uri") or v.get("dataset_parameter_uri")
            print(f"  • {v['name']}{std}")
            if prop:
                print(f"      propertyID: {prop}")
            attrs = match_erddap_attrs(v["name"], erddap_variables)
            if attrs:
                lo, hi = _parse_actual_range(attrs.get("actual_range"))
                units = attrs.get("units")
                if lo is not None and hi is not None:
                    unit_str = f" {units}" if units else ""
                    print(f"      range: {lo} – {hi}{unit_str}")
                elif units:
                    print(f"      units: {units}")

        # Build the JSON-LD once; reused for both printing and saving.
        doc = build_jsonld(record, depth_vars, erddap_variables)

        if args.jsonld:
            print("\nschema.org JSON-LD:")
            print(json.dumps(doc, indent=2))

        if save_dir is not None:
            out_path = save_dir / f"{dataset_id}.jsonld"
            out_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            saved_count += 1
            print(f"saved: {out_path}")
        print()

    summary = (
        f"Done. {match_count} of {len(datasets)} dataset(s) had depth/pressure "
        f"measurements."
    )
    if save_dir is not None:
        summary += f" {saved_count} JSON-LD file(s) written to {save_dir}/."
    print(summary, file=sys.stderr)


if __name__ == "__main__":
    main()
