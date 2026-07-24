"""ISO 19115 depth/pressure variable scan and schema.org JSON-LD transform."""

import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

from defs.common import TIMEOUT, load_json, log, make_session, write_json

NS = {
    "gmd": "http://www.isotc211.org/2005/gmd",
    "gco": "http://www.isotc211.org/2005/gco",
    "gmx": "http://www.isotc211.org/2005/gmx",
    "xlink": "http://www.w3.org/1999/xlink",
}

DEPTH_PRESSURE_TERMS = ("depth", "press", "bathy", "dbar")

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


def _clean_uri(href: str | None) -> str | None:
    """Normalize a BCO-DMO LOD href into a resource URI (drop a trailing .rdf)."""
    if not href:
        return None
    return href[:-4] if href.endswith(".rdf") else href


def _keyword_entries(md_keywords) -> list[tuple[str, str | None]]:
    """Return [(name, href), ...] for the keywords in one MD_Keywords element."""
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


def parse_variables(xml_text: str) -> list[dict]:
    """Extract measured variables from a BCO-DMO ISO 19115 record."""
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


def is_depth_pressure(variable: dict) -> bool:
    """Return True if either the column or standardized name looks depth/pressure related."""
    haystack = " ".join(
        filter(None, [variable.get("name"), variable.get("standard_name")])
    ).lower()
    return any(term in haystack for term in DEPTH_PRESSURE_TERMS)


def _norm(text: str | None) -> str:
    """Lowercase and strip non-alphanumerics for fuzzy name matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower()) if text else ""


def fetch_erddap_variables(
    session: requests.Session, info_url: str
) -> dict[str, dict[str, str]]:
    """Return {variable_name: {attribute: value, ...}} from an ERDDAP info JSON."""
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


def match_erddap_attrs(
    iso_name: str, erddap_variables: dict[str, dict[str, str]]
) -> dict[str, str] | None:
    """Find the ERDDAP attributes for an ISO variable name."""
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


def parse_actual_range(value) -> tuple[float | None, float | None]:
    """Parse an ERDDAP actual_range like '0.5, 200.0' into (min, max) floats."""
    try:
        lo, hi = (part.strip() for part in str(value).split(",")[:2])
        return float(lo), float(hi)
    except (ValueError, TypeError):
        return None, None


def to_property_value(variable: dict, attrs: dict | None = None) -> dict:
    """Express one variable as a schema.org PropertyValue (ODIS depth pattern)."""
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
        lo, hi = parse_actual_range(attrs.get("actual_range"))
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


def build_jsonld(
    record: dict,
    depth_vars: list[dict],
    erddap_variables: dict | None = None,
) -> dict:
    """Build a schema.org Dataset JSON-LD document for one dataset."""
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


def iso_url_for(record: dict) -> str | None:
    """Return the ISO 19115 URL for a dataset record, or None if unavailable."""
    return record.get("access", {}).get("iso_19115", {}).get("url")


def _format_match_report(
    record: dict,
    url: str,
    depth_vars: list[dict],
    variables: list[dict],
    erddap_variables: dict,
) -> str:
    """Build the plain-text report block for one matched dataset."""
    dataset_id = record.get("datasetID", "?")
    lines = [
        "=" * 78,
        f"{dataset_id}  —  {record.get('title', '')}",
        f"ISO: {url}",
        f"Depth/pressure variables ({len(depth_vars)} of {len(variables)}):",
    ]
    for v in depth_vars:
        std = f"  [{v['standard_name']}]" if v.get("standard_name") else ""
        prop = v.get("standard_parameter_uri") or v.get("dataset_parameter_uri")
        lines.append(f"  • {v['name']}{std}")
        if prop:
            lines.append(f"      propertyID: {prop}")
        attrs = match_erddap_attrs(v["name"], erddap_variables)
        if attrs:
            lo, hi = parse_actual_range(attrs.get("actual_range"))
            units = attrs.get("units")
            if lo is not None and hi is not None:
                unit_str = f" {units}" if units else ""
                lines.append(f"      range: {lo} – {hi}{unit_str}")
            elif units:
                lines.append(f"      units: {units}")
    return "\n".join(lines)


def scan_dataset(
    session: requests.Session,
    record: dict,
) -> dict | None:
    """
    Scan one inventory record for depth/pressure variables.

    Returns:
        dict match record with depth_vars, jsonld, and report text, or None if
        no match / skipped.
    """
    dataset_id = record.get("datasetID", "?")
    url = iso_url_for(record)
    if not url:
        log(f"[skip] {dataset_id}: no ISO 19115 URL")
        return None

    try:
        resp = session.get(url, timeout=TIMEOUT)
        resp.raise_for_status()
        variables = parse_variables(resp.text)
    except (requests.RequestException, ET.ParseError) as e:
        log(f"[skip] {dataset_id}: {e}")
        return None

    depth_vars = [v for v in variables if is_depth_pressure(v)]
    if not depth_vars:
        return None

    erddap_variables = {}
    info_url = record.get("access", {}).get("erddap_info", {}).get("url")
    if info_url:
        try:
            erddap_variables = fetch_erddap_variables(session, info_url)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status in (401, 403):
                log(
                    f"[note] {dataset_id}: ERDDAP data access restricted "
                    f"(HTTP {status}); using ISO metadata only."
                )
            else:
                log(f"[warn] {dataset_id}: ERDDAP enrichment failed: {e}")
        except (requests.RequestException, ValueError, KeyError) as e:
            log(f"[warn] {dataset_id}: ERDDAP enrichment failed: {e}")

    doc = build_jsonld(record, depth_vars, erddap_variables)
    report = _format_match_report(record, url, depth_vars, variables, erddap_variables)

    return {
        "datasetID": dataset_id,
        "title": record.get("title"),
        "iso_url": url,
        "depth_variables": depth_vars,
        "jsonld": doc,
        "report": report,
    }


def run_scan_iso_measurements(
    input_path: Path,
    *,
    output: Path,
    jsonld_dir: Path | None = None,
    report_output: Path | None = None,
    limit: int | None = None,
    print_jsonld: bool = False,
    embed_jsonld_in_summary: bool = False,
) -> dict:
    """
    Scan ERDDAP inventory records for depth/pressure variables and write outputs.

    Args:
        input_path: ERDDAP inventory JSON from ``run_scan_erddap``
        output: Path for the summary JSON (matches metadata; JSON-LD optional)
        jsonld_dir: Optional directory for per-dataset ``<datasetID>.jsonld`` files
        report_output: Optional path for a plain-text findings report
        limit: Process only the first N datasets from the input
        print_jsonld: Echo JSON-LD documents to stdout
        embed_jsonld_in_summary: Include full JSON-LD in the written summary file

    Returns:
        dict: Summary payload; ``matches`` always include ``jsonld`` for RDF export
    """
    data = load_json(input_path)
    datasets = data.get("datasets", [])
    if limit is not None:
        datasets = datasets[:limit]

    log(
        f"Scanning {len(datasets)} dataset(s) from {input_path} "
        f"for depth/pressure measurements...\n"
    )

    if jsonld_dir is not None:
        jsonld_dir.mkdir(parents=True, exist_ok=True)

    session = make_session()
    matches = []
    report_blocks = []

    for record in datasets:
        match = scan_dataset(session, record)
        if match is None:
            continue

        jsonld_path = None
        if jsonld_dir is not None:
            jsonld_path = jsonld_dir / f"{match['datasetID']}.jsonld"
            jsonld_path.write_text(
                json.dumps(match["jsonld"], indent=2), encoding="utf-8"
            )
            log(f"saved: {jsonld_path}")

        report_blocks.append(match["report"])
        if print_jsonld:
            print(match["report"])
            print("\nschema.org JSON-LD:")
            print(json.dumps(match["jsonld"], indent=2))
            print()

        matches.append(
            {
                "datasetID": match["datasetID"],
                "title": match["title"],
                "iso_url": match["iso_url"],
                "depth_variables": match["depth_variables"],
                "jsonld": match["jsonld"],
                "jsonld_file": str(jsonld_path) if jsonld_path else None,
            }
        )

    summary_matches = matches
    if not embed_jsonld_in_summary:
        summary_matches = [
            {key: value for key, value in match.items() if key != "jsonld"}
            for match in matches
        ]

    result = {
        "input": str(input_path),
        "scanned": len(datasets),
        "match_count": len(matches),
        "matches": summary_matches,
    }
    write_json(output, result)

    # Full match records (with jsonld) for downstream RDF export.
    result["matches"] = matches

    if report_output is not None:
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_body = "\n\n".join(report_blocks)
        if report_body:
            report_body += "\n"
        report_output.write_text(report_body, encoding="utf-8")
        log(f"Report written to {report_output}")

    summary = (
        f"Done. {len(matches)} of {len(datasets)} dataset(s) had depth/pressure "
        f"measurements. Summary written to {output}."
    )
    if jsonld_dir is not None:
        summary += f" {len(matches)} JSON-LD file(s) in {jsonld_dir}/."
    log(summary)
    return result