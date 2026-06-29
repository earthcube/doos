"""Depth column detection and min/max statistics for tabular distributions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import pandas as pd

ISO_NS = {
    "gmd": "http://www.isotc211.org/2005/gmd",
    "gco": "http://www.isotc211.org/2005/gco",
}

TABULAR_EXTENSIONS = {".csv", ".tsv", ".parquet", ".xls", ".xlsx", ".xlsm"}
SKIP_EXTENSIONS = {".doc", ".docx", ".pdf", ".html", ".htm", ".xml", ".json", ".fcs"}

DEPTH_NAME_RE = re.compile(
    r"(?:^|[\s_\-])(?:depth|deph|pressure|pres)(?:[\s_\-]|$)|"
    r"(?:^|[\s_\-])(?:z|height)(?:[\s_\-]|$)",
    re.IGNORECASE,
)

CF_DEPTH_CODES = {"depth", "depth_of_chlorophyll_maximum"}
DEPTH_HINT_NAMES = {"depbelowsurf", "depth", "depth_of_chlorophyll_maximum", "pressure", "pres"}


def normalize_column_name(name: str) -> str:
    """Normalize a column header for fuzzy matching."""
    text = str(name).strip().lower()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def is_depth_hint(value: str) -> bool:
    """Return True when a variableMeasured name or alias is depth-related."""
    normalized = normalize_column_name(value)
    if normalized in DEPTH_HINT_NAMES:
        return True
    return bool(DEPTH_NAME_RE.search(normalized))


def depth_hints_from_jsonld(doc: dict[str, Any]) -> list[str]:
    """Collect depth-related names from schema.org variableMeasured entries."""
    hints: list[str] = []
    seen: set[str] = set()

    def add_hint(value: str | None) -> None:
        if not value:
            return
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            hints.append(value.strip())

    for entry in doc.get("variableMeasured") or []:
        if not isinstance(entry, dict):
            continue
        for field in ("name", "alternateName"):
            value = entry.get(field)
            if isinstance(value, str) and is_depth_hint(value):
                add_hint(value)
        url = entry.get("url") or ""
        if isinstance(url, str) and "/" in url:
            code = url.rsplit("/", 1)[-1]
            if is_depth_hint(code):
                add_hint(code)

    for keyword in doc.get("keywords") or []:
        if isinstance(keyword, str) and keyword.lower() in CF_DEPTH_CODES:
            add_hint(keyword)

    if not hints:
        add_hint("depth")

    return hints


def distribution_url(dist: dict[str, Any]) -> str | None:
    """Return the download URL from a schema.org distribution object."""
    for key in ("url", "dcat:accessURL", "contentUrl"):
        value = dist.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    dist_id = dist.get("@id")
    if isinstance(dist_id, str) and dist_id.startswith(("http://", "https://")):
        return dist_id
    return None


def classify_distribution(url: str) -> str:
    """Classify a distribution URL as tabular, prefix-listing, document, or other."""
    lowered = url.lower()
    if "?prefix=" in lowered:
        return "prefix-listing"

    path = urlparse(url).path.lower()
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    suffix = f".{ext}" if ext else ""

    if suffix in TABULAR_EXTENSIONS:
        return "tabular"
    if suffix in SKIP_EXTENSIONS:
        return "document"
    if not suffix:
        return "other"
    return f"other:{suffix}"


def rank_distributions(distributions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank tabular distributions most likely to contain depth columns."""

    def score(dist: dict[str, Any]) -> tuple[int, str]:
        url = distribution_url(dist) or ""
        kind = classify_distribution(url)
        if kind != "tabular":
            return (-1, url)

        points = 0
        name = str(dist.get("name") or "").lower()
        description = str(dist.get("description") or "").lower()
        text = f"{name} {description}"

        if "data.aodn.org.au" in url.lower():
            points += 4
        if any(token in text for token in ("summary", "processed", "data")):
            points += 3
        if "depth" in text:
            points += 2
        if url.lower().endswith((".csv", ".tsv", ".parquet")):
            points += 1
        if url.lower().endswith((".xls", ".xlsx", ".xlsm")):
            points += 1

        return (points, url)

    ranked = sorted(distributions, key=score, reverse=True)
    return [dist for dist in ranked if score(dist)[0] >= 0]


def match_depth_column(column: str, hints: list[str]) -> tuple[bool, str]:
    """Return whether a column is depth-related and how it matched."""
    normalized = normalize_column_name(column)

    for hint in hints:
        hint_norm = normalize_column_name(hint)
        if not hint_norm:
            continue
        if hint_norm == "depbelowsurf":
            if "depth" in normalized or "deph" in normalized:
                return True, "variableMeasured:DepBelowSurf"
            continue
        if normalized == hint_norm or hint_norm in normalized or normalized in hint_norm:
            return True, f"variableMeasured:{hint}"

    if DEPTH_NAME_RE.search(normalized):
        return True, "column_name"

    return False, ""


def depth_stats(series: pd.Series) -> dict[str, Any] | None:
    """Compute min/max for a numeric depth column."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return {
        "min": float(numeric.min()),
        "max": float(numeric.max()),
        "count": int(numeric.count()),
    }


def find_depth_columns(
    df: pd.DataFrame,
    hints: list[str],
) -> list[dict[str, Any]]:
    """Find depth-related columns and their min/max statistics."""
    results: list[dict[str, Any]] = []
    if df.empty:
        return results

    for column in df.columns:
        matched, matched_by = match_depth_column(str(column), hints)
        if not matched:
            continue
        stats = depth_stats(df[column])
        if stats is None:
            continue
        results.append(
            {
                "column": str(column),
                "matched_by": matched_by,
                **stats,
            }
        )
    return results


def iso19139_sibling_path(jsonld_path: Path) -> Path:
    """Return the conventional ISO 19139 sibling path for a JSON-LD file."""
    return jsonld_path.with_name(f"{jsonld_path.stem}_iso19139.xml")


def vertical_extent_from_iso19139(path: Path) -> dict[str, float] | None:
    """Parse gmd:EX_VerticalExtent min/max from an ISO 19139 XML file."""
    if not path.is_file():
        return None

    root = ET.parse(path).getroot()
    minimum = root.find(
        ".//gmd:EX_VerticalExtent/gmd:minimumValue/gco:Real", ISO_NS
    )
    maximum = root.find(
        ".//gmd:EX_VerticalExtent/gmd:maximumValue/gco:Real", ISO_NS
    )
    if minimum is None or maximum is None:
        minimum = root.find(
            ".//gmd:EX_VerticalExtent/gmd:minimumValue/gco:Decimal", ISO_NS
        )
        maximum = root.find(
            ".//gmd:EX_VerticalExtent/gmd:maximumValue/gco:Decimal", ISO_NS
        )

    if minimum is None or maximum is None or not minimum.text or not maximum.text:
        return None

    return {
        "min": float(minimum.text.strip()),
        "max": float(maximum.text.strip()),
    }


def flatten_depth_columns(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten sheet findings into a single list of depth column stats."""
    columns: list[dict[str, Any]] = []
    for finding in findings:
        sheet = finding.get("sheet")
        for column in finding.get("depth_columns") or []:
            columns.append({**column, "sheet": sheet})
    return columns


def compare_depth_to_metadata(
    depth_columns: list[dict[str, Any]],
    vertical_extent: dict[str, float] | None,
    *,
    tolerance: float = 0.5,
) -> dict[str, Any]:
    """Compare observed depth column ranges against ISO vertical extent."""
    comparison: dict[str, Any] = {
        "iso_vertical_extent": vertical_extent,
        "columns": [],
        "consistent": None,
    }

    if not depth_columns:
        comparison["consistent"] = False
        comparison["message"] = "no depth columns to compare"
        return comparison

    if vertical_extent is None:
        comparison["message"] = "no ISO vertical extent available for comparison"
        return comparison

    meta_min = vertical_extent["min"]
    meta_max = vertical_extent["max"]
    column_checks: list[dict[str, Any]] = []
    all_consistent = True

    for column in depth_columns:
        data_min = column["min"]
        data_max = column["max"]
        within = (
            data_min >= meta_min - tolerance
            and data_max <= meta_max + tolerance
        )
        column_checks.append(
            {
                "column": column["column"],
                "sheet": column.get("sheet"),
                "data_min": data_min,
                "data_max": data_max,
                "metadata_min": meta_min,
                "metadata_max": meta_max,
                "within_metadata_extent": within,
            }
        )
        if not within:
            all_consistent = False

    comparison["columns"] = column_checks
    comparison["consistent"] = all_consistent
    if all_consistent:
        comparison["message"] = "all depth column ranges fall within ISO vertical extent"
    else:
        comparison["message"] = (
            "one or more depth column ranges fall outside ISO vertical extent"
        )
    return comparison


def select_best_attempt(attempts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the best successful distribution attempt."""
    ok_attempts = [item for item in attempts if item.get("status") == "ok"]
    if not ok_attempts:
        return None

    def sort_key(item: dict[str, Any]) -> tuple[int, int, float]:
        findings = item.get("findings") or []
        depth_count = sum(len(f.get("depth_columns") or []) for f in findings)
        rows = sum(int(f.get("rows") or 0) for f in findings)
        max_depth = 0.0
        for column in flatten_depth_columns(findings):
            max_depth = max(max_depth, float(column.get("max") or 0))
        return (depth_count, rows, max_depth)

    return max(ok_attempts, key=sort_key)


def aggregate_depth_range(depth_columns: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Compute overall min/max across observed depth columns."""
    if not depth_columns:
        return None

    primary = next(
        (col for col in depth_columns if col.get("matched_by") == "variableMeasured:DepBelowSurf"),
        depth_columns[0],
    )
    overall_min = min(float(col["min"]) for col in depth_columns)
    overall_max = max(float(col["max"]) for col in depth_columns)
    return {
        "min": overall_min,
        "max": overall_max,
        "primary_column": primary.get("column"),
        "column_count": len(depth_columns),
    }


def enrich_jsonld_depth(doc: dict[str, Any], depth_range: dict[str, Any]) -> dict[str, Any]:
    """Write observed depth min/max into the DepBelowSurf variableMeasured entry."""
    enriched = json.loads(json.dumps(doc))
    variables = enriched.get("variableMeasured") or []
    if not isinstance(variables, list):
        return enriched

    for entry in variables:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") != "DepBelowSurf":
            continue
        entry["minValue"] = depth_range["min"]
        entry["maxValue"] = depth_range["max"]
        entry["unitText"] = entry.get("unitText") or "m"
        if depth_range.get("primary_column"):
            entry["value"] = (
                f"{depth_range['min']}–{depth_range['max']} m "
                f"(from {depth_range['primary_column']})"
            )
        else:
            entry["value"] = f"{depth_range['min']}–{depth_range['max']} m"
        break

    return enriched