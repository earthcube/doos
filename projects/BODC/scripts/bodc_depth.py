"""Shared BODC depth classification utilities."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import RDF

SCHEMA = Namespace("https://schema.org/")

DATASET_URI_RE = re.compile(
    r"https://api\.linked-systems\.uk/api/schema-org/dataset/(\d+)"
)
SERIES_LANDING_RE = re.compile(r"/data/documents/series/(\d+)/?")
P01_URI_RE = re.compile(
    r"https://vocab\.nerc\.ac\.uk/collection/P01/current/([A-Z0-9]+)/?"
)

KNOWN_TIER2_P01 = frozenset({"DBINAA01", "DEPHPRST", "DEPHFP01"})
KNOWN_TIER2_NAMES = frozenset(
    {"BinDep", "Start_depth", "BathyDepES_ISL", "SwathCBBathyDep"}
)
DEPTH_P01_PREFIXES = ("ADEP", "DEPH", "DBIN")
INSTRUMENT_DEPTH_RE = re.compile(r"at depth", re.IGNORECASE)

TIER_RANK = {
    "none": 0,
    "tier_instrument": 1,
    "tier2": 2,
    "tier1": 3,
}

API_DATASET_URL = "https://api.linked-systems.uk/api/schema-org/dataset/{series_id}"
USER_AGENT = "DOOS-BODC-Harvest/1.0"


def literal_value(obj):
    """Return a Python value from an RDF literal or URI."""
    if isinstance(obj, Literal):
        return obj.toPython()
    if isinstance(obj, URIRef):
        return str(obj)
    return str(obj)


def p01_code(property_id):
    """Extract a P01 parameter code from a propertyID URI or string."""
    if not property_id:
        return None
    match = P01_URI_RE.search(str(property_id))
    return match.group(1) if match else None


def is_tier2_depth(name, property_id, description):
    """Return True when a PropertyValue matches Tier 2 depth rules."""
    if name == "DepBelowSurf":
        return False

    code = p01_code(property_id)
    if code:
        if code in KNOWN_TIER2_P01:
            return True
        if code.startswith(DEPTH_P01_PREFIXES):
            return True

    if name in KNOWN_TIER2_NAMES:
        return True

    text = f"{name or ''} {description or ''}".lower()
    if "depth" in text and name not in KNOWN_TIER2_NAMES:
        if any(
            token in text
            for token in ("bindep", "bathy", "deph", "moored instrument depth")
        ):
            return True

    return False


def has_instrument_depth_signal(events, property_values):
    """Detect instrument-description depth signals outside P01 depth codes."""
    for event in events:
        for field in ("name", "description"):
            value = event.get(field, "")
            if value and INSTRUMENT_DEPTH_RE.search(value):
                return True

    for prop in property_values:
        name = prop.get("name", "")
        if name and INSTRUMENT_DEPTH_RE.search(name):
            return True

    return False


def classify_graph(dataset_uri, property_values, events):
    """Classify depth tiers for one dataset graph."""
    series_match = DATASET_URI_RE.search(str(dataset_uri))
    series_id = series_match.group(1) if series_match else None

    depth_names = []
    property_ids = []
    tier1_props = []
    tier2_props = []

    for prop in property_values:
        name = prop.get("name")
        if not name:
            continue

        property_id = prop.get("propertyID")
        description = prop.get("description")
        code = p01_code(property_id)

        if name == "DepBelowSurf" or code == "ADEPZZ01":
            tier1_props.append(prop)
            depth_names.append(name)
            if property_id:
                property_ids.append(str(property_id))
        elif is_tier2_depth(name, property_id, description):
            tier2_props.append(prop)
            depth_names.append(name)
            if property_id:
                property_ids.append(str(property_id))

    has_dep_below_surf = bool(tier1_props)
    instrument_depth = has_instrument_depth_signal(events, property_values)

    if has_dep_below_surf:
        tier = "tier1"
    elif tier2_props:
        tier = "tier2"
    elif instrument_depth:
        tier = "tier_instrument"
    else:
        tier = "none"

    min_value = None
    max_value = None
    if tier1_props:
        mins = [p["minValue"] for p in tier1_props if p.get("minValue") is not None]
        maxs = [p["maxValue"] for p in tier1_props if p.get("maxValue") is not None]
    else:
        mins = [p["minValue"] for p in tier2_props if p.get("minValue") is not None]
        maxs = [p["maxValue"] for p in tier2_props if p.get("maxValue") is not None]

    if mins:
        min_value = min(mins)
    if maxs:
        max_value = max(maxs)

    return {
        "series_id": series_id,
        "dataset_uri": str(dataset_uri),
        "tier": tier,
        "depth_names": sorted(set(depth_names)),
        "property_ids": sorted(set(property_ids)),
        "min_value": min_value,
        "max_value": max_value,
        "has_dep_below_surf": has_dep_below_surf,
        "has_instrument_depth_signal": instrument_depth,
        "tier1_count": len(tier1_props),
        "tier2_count": len(tier2_props),
    }


def extract_from_jsonld(doc):
    """Extract dataset fields needed for depth classification from JSON-LD."""
    dataset_uri = doc.get("@id") or doc.get("id")

    property_values = []
    measured = doc.get("variableMeasured") or []
    if isinstance(measured, dict):
        measured = [measured]
    for item in measured:
        if not isinstance(item, dict):
            continue
        property_values.append(
            {
                "name": item.get("name"),
                "propertyID": item.get("propertyID"),
                "description": item.get("description"),
                "minValue": item.get("minValue"),
                "maxValue": item.get("maxValue"),
            }
        )

    events = []
    about = doc.get("about") or []
    if isinstance(about, dict):
        about = [about]
    for item in about:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("@type", ""))
        if item_type == "Event" or item_type.endswith("Event"):
            events.append(
                {
                    "name": item.get("name"),
                    "description": item.get("description"),
                }
            )

    return dataset_uri, property_values, events


def classify_jsonld(doc):
    """Classify depth tiers from a live JSON-LD document."""
    dataset_uri, property_values, events = extract_from_jsonld(doc)
    record = classify_graph(dataset_uri, property_values, events)
    record["date_modified"] = doc.get("dateModified")
    return record


def load_graph_records(nq_path):
    """Load N-Quads and build per-named-graph inventory records."""
    dataset = Dataset()
    dataset.parse(str(nq_path), format="nquads")

    graphs = defaultdict(
        lambda: {
            "dataset_uri": None,
            "property_values": {},
            "events": {},
        }
    )

    for graph in dataset.graphs():
        graph_key = str(graph.identifier)

        for dataset_uri in graph.subjects(RDF.type, SCHEMA.Dataset):
            graphs[graph_key]["dataset_uri"] = str(dataset_uri)

            for vm_uri in graph.objects(dataset_uri, SCHEMA.variableMeasured):
                vm_key = str(vm_uri)
                entry = graphs[graph_key]["property_values"].setdefault(vm_key, {})
                entry["uri"] = vm_key

                for pred, obj in graph.predicate_objects(vm_uri):
                    pred_key = str(pred).rsplit("/", 1)[-1]
                    if pred_key in {"name", "description", "propertyID"}:
                        entry[pred_key] = literal_value(obj)
                    elif pred_key in {"minValue", "maxValue"}:
                        entry[pred_key] = literal_value(obj)

        for event_uri in graph.subjects(RDF.type, SCHEMA.Event):
            event_key = str(event_uri)
            entry = graphs[graph_key]["events"].setdefault(event_key, {})
            entry["uri"] = event_key

            for pred, obj in graph.predicate_objects(event_uri):
                pred_key = str(pred).rsplit("/", 1)[-1]
                if pred_key in {"name", "description"}:
                    entry[pred_key] = literal_value(obj)

    records = []
    skipped = 0
    for graph_uri, data in graphs.items():
        if not data["dataset_uri"]:
            skipped += 1
            continue

        record = classify_graph(
            data["dataset_uri"],
            list(data["property_values"].values()),
            list(data["events"].values()),
        )
        record["graph_uri"] = graph_uri
        records.append(record)

    stats = {
        "named_graphs_total": len(graphs),
        "named_graphs_with_dataset": len(records),
        "named_graphs_skipped": skipped,
    }
    return records, stats


def best_record_per_series(records):
    """Return the highest-tier record for each series_id."""
    series_best = {}
    for record in records:
        series_id = record.get("series_id")
        if not series_id:
            continue
        current = series_best.get(series_id)
        if current is None or TIER_RANK[record["tier"]] > TIER_RANK[current["tier"]]:
            series_best[series_id] = record
    return series_best


def summarize_records(records):
    """Build graph-level and series-level summary statistics."""
    graph_tier_counts = defaultdict(int)
    for record in records:
        graph_tier_counts[record["tier"]] += 1

    series_best = best_record_per_series(records)
    series_tier_counts = defaultdict(int)
    for record in series_best.values():
        series_tier_counts[record["tier"]] += 1

    unique_series = len(series_best)
    tier1_series = series_tier_counts["tier1"]
    tier2_only_series = sum(
        1 for record in series_best.values() if record["tier"] == "tier2"
    )

    return {
        "graphs": {
            "total": len(records),
            "by_tier": dict(graph_tier_counts),
            "with_dep_below_surf": sum(1 for r in records if r["has_dep_below_surf"]),
        },
        "series": {
            "unique_count": unique_series,
            "by_tier": dict(series_tier_counts),
            "tier1_count": tier1_series,
            "tier1_pct": round(100 * tier1_series / unique_series, 1)
            if unique_series
            else 0.0,
            "tier2_only_count": tier2_only_series,
            "tier2_only_pct": round(100 * tier2_only_series / unique_series, 1)
            if unique_series
            else 0.0,
            "instrument_only_count": series_tier_counts["tier_instrument"],
            "none_count": series_tier_counts["none"],
        },
    }


def load_release_series_index(inventory_path):
    """Load best-per-series records from a Phase 1 inventory JSON file."""
    payload = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    return best_record_per_series(payload.get("records", []))


def write_inventory_csv(output_dir, records, filename):
    """Write inventory records to CSV."""
    out_path = output_dir / filename
    fieldnames = [
        "series_id",
        "graph_uri",
        "tier",
        "has_dep_below_surf",
        "has_instrument_depth_signal",
        "depth_names",
        "property_ids",
        "min_value",
        "max_value",
        "tier1_count",
        "tier2_count",
        "dataset_uri",
        "date_modified",
    ]

    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["depth_names"] = ";".join(record.get("depth_names", []))
            row["property_ids"] = ";".join(record.get("property_ids", []))
            writer.writerow(row)
    return out_path


def depth_values_changed(release_record, live_record):
    """Return True when depth min/max differ between release and live records."""
    for field in ("min_value", "max_value"):
        release_val = release_record.get(field)
        live_val = live_record.get(field)
        if release_val is None and live_val is None:
            continue
        if release_val != live_val:
            return True
    return False


def build_harvest_diff(release_index, live_index):
    """Compare live harvest results against the release inventory."""
    release_ids = set(release_index)
    live_ids = set(live_index)

    new_series = sorted(live_ids - release_ids, key=int)
    missing_series = sorted(release_ids - live_ids, key=int)

    changed_depth = []
    shared = release_ids & live_ids
    for series_id in sorted(shared, key=int):
        release_record = release_index[series_id]
        live_record = live_index[series_id]
        entry = {
            "series_id": series_id,
            "release_tier": release_record.get("tier"),
            "live_tier": live_record.get("tier"),
        }
        changed = False
        if release_record.get("tier") != live_record.get("tier"):
            changed = True
        if depth_values_changed(release_record, live_record):
            changed = True
            entry["release_min_value"] = release_record.get("min_value")
            entry["release_max_value"] = release_record.get("max_value")
            entry["live_min_value"] = live_record.get("min_value")
            entry["live_max_value"] = live_record.get("max_value")
        if changed:
            changed_depth.append(entry)

    return {
        "release_series_count": len(release_ids),
        "live_series_count": len(live_ids),
        "new_series_count": len(new_series),
        "missing_series_count": len(missing_series),
        "changed_count": len(changed_depth),
        "new_series": new_series,
        "missing_series": missing_series,
        "changed": changed_depth,
    }