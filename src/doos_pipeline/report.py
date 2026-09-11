"""JSON-LD run metrics for published provider graphs.

This module only writes structured JSON-LD. PDF and web dashboards are
separate programs that consume the file.

The document is self-contained JSON-LD (embedded @context) so a dashboard
can treat it as plain JSON (`metrics.recordCount`, histograms) or as RDF.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import RDF

from . import __version__
from .providers.registry import Provider
from .shacl import collect_rdf_files

DOOS_VOCAB = "https://w3id.org/doos/pipeline#"
SCHEMA_HTTPS = "https://schema.org/"
SCHEMA_HTTP = "http://schema.org/"
HASH_MAX_BYTES = 32 * 1024 * 1024
PREDICATE_HISTOGRAM_LIMIT = 40

# Same alias set as SPARQL/alias_depthbelowsurf.ru, plus the canonical name.
DEPTH_NAME_ALIASES = {
    "DepBelowSurf",
    "depth",
    "Depth",
    "Min_Depth",
    "MinDepth",
    "MaxDepth",
    "depth_m",
    "Sample_Depth",
    "DEPTH",
    "Btl_Depth",
    "depth_CTD",
    "depth_max",
    "max_depth",
    "press",
    "Actual_Depth",
}

_PREFIXES = (
    ("schema:", SCHEMA_HTTPS),
    ("schema:", SCHEMA_HTTP),
    ("rdf:", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
    ("rdfs:", "http://www.w3.org/2000/01/rdf-schema#"),
    ("xsd:", "http://www.w3.org/2001/XMLSchema#"),
    ("prov:", "http://www.w3.org/ns/prov#"),
    ("geosparql:", "http://www.opengis.net/ont/geosparql#"),
    ("sf:", "http://www.opengis.net/ont/sf#"),
    ("cr:", "http://mlcommons.org/croissant/"),
    ("dct:", "http://purl.org/dc/terms/"),
    ("cchdo:", "https://cchdo.ucsd.edu/vocab#"),
)

REPORT_CONTEXT = {
    "@vocab": DOOS_VOCAB,
    "schema": SCHEMA_HTTPS,
    "prov": "http://www.w3.org/ns/prov#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "doos": DOOS_VOCAB,
    "name": "schema:name",
    "description": "schema:description",
    "dateCreated": {"@id": "schema:dateCreated", "@type": "xsd:dateTime"},
    "startedAtTime": {"@id": "prov:startedAtTime", "@type": "xsd:dateTime"},
    "endedAtTime": {"@id": "prov:endedAtTime", "@type": "xsd:dateTime"},
    "wasGeneratedBy": "prov:wasGeneratedBy",
    "used": "prov:used",
    "hasPart": {"@id": "schema:hasPart", "@container": "@set"},
    "count": {"@id": "doos:count", "@type": "xsd:integer"},
    "fileCount": {"@type": "xsd:integer"},
    "byteCount": {"@type": "xsd:integer"},
    "recordCount": {"@type": "xsd:integer"},
    "tripleCount": {"@type": "xsd:integer"},
    "namedGraphCount": {"@type": "xsd:integer"},
    "parseErrorCount": {"@type": "xsd:integer"},
    "truncated": {"@type": "xsd:boolean"},
}


def _schema(*local_names: str) -> tuple[URIRef, ...]:
    iris = []
    for name in local_names:
        iris.append(URIRef(SCHEMA_HTTPS + name))
        iris.append(URIRef(SCHEMA_HTTP + name))
    return tuple(iris)


DATASET_TYPES = set(_schema("Dataset"))
PV_TYPES = set(_schema("PropertyValue"))
NAME_PREDS = set(_schema("name"))
DESC_PREDS = set(_schema("description"))
URL_PREDS = set(_schema("url"))
VM_PREDS = set(_schema("variableMeasured"))
MIN_PREDS = set(_schema("minValue"))
MAX_PREDS = set(_schema("maxValue"))


def compact_curie(iri: str) -> str:
    """Return a CURIE when a known prefix matches, else the full IRI."""
    for prefix, ns in _PREFIXES:
        if iri.startswith(ns):
            return prefix + iri[len(ns) :]
    return iri


def namespace_of(iri: str) -> str | None:
    if not iri.startswith("http://") and not iri.startswith("https://"):
        return None
    if "#" in iri:
        return iri.rsplit("#", 1)[0] + "#"
    if "/" in iri:
        return iri.rsplit("/", 1)[0] + "/"
    return None


def _is_depth_name(name: str) -> bool:
    if name in DEPTH_NAME_ALIASES:
        return True
    lowered = name.lower().replace(" ", "").replace("_", "")
    return (
        "depth" in lowered
        or "depbelow" in lowered
        or lowered in {"press", "pres", "pressure", "dbar"}
    )


def _literals(graph: Graph, subject, predicates) -> list[str]:
    values = []
    for pred in predicates:
        for obj in graph.objects(subject, pred):
            values.append(str(obj))
    return values


def _has_any(graph: Graph, subject, predicates) -> bool:
    for pred in predicates:
        if next(graph.objects(subject, pred), None) is not None:
            return True
    return False


@dataclass
class GraphStats:
    """Mutable counters accumulated across one or more RDF files."""

    file_count: int = 0
    byte_count: int = 0
    triple_count: int = 0
    named_graphs: set[str] = field(default_factory=set)
    datasets: set[str] = field(default_factory=set)
    datasets_with_name: set[str] = field(default_factory=set)
    datasets_with_description: set[str] = field(default_factory=set)
    datasets_with_url: set[str] = field(default_factory=set)
    datasets_with_depbelowsurf: set[str] = field(default_factory=set)
    datasets_with_depth: set[str] = field(default_factory=set)
    datasets_with_depth_range: set[str] = field(default_factory=set)
    types: Counter = field(default_factory=Counter)
    predicates: Counter = field(default_factory=Counter)
    namespaces: Counter = field(default_factory=Counter)
    variable_names: Counter = field(default_factory=Counter)
    depth_names: Counter = field(default_factory=Counter)
    variable_measured_count: int = 0
    depth_property_values: int = 0
    depth_with_range: int = 0
    parse_errors: list[dict] = field(default_factory=list)
    truncated: bool = False
    sha256: str | None = None

    def absorb_graph(self, graph: Graph, graph_iri: str | None = None) -> None:
        if graph_iri:
            self.named_graphs.add(graph_iri)
        for subj, pred, obj in graph:
            self.triple_count += 1
            pred_iri = str(pred)
            self.predicates[pred_iri] += 1
            ns = namespace_of(pred_iri)
            if ns:
                self.namespaces[ns] += 1
            if pred != RDF.type:
                continue
            type_iri = str(obj)
            self.types[type_iri] += 1
            if obj in DATASET_TYPES:
                self.datasets.add(str(subj))
        for dataset in [s for s, _, o in graph.triples((None, RDF.type, None)) if o in DATASET_TYPES]:
            key = str(dataset)
            if _has_any(graph, dataset, NAME_PREDS):
                self.datasets_with_name.add(key)
            if _has_any(graph, dataset, DESC_PREDS):
                self.datasets_with_description.add(key)
            if _has_any(graph, dataset, URL_PREDS):
                self.datasets_with_url.add(key)
            for vm_pred in VM_PREDS:
                for pv in graph.objects(dataset, vm_pred):
                    self.variable_measured_count += 1
                    names = _literals(graph, pv, NAME_PREDS)
                    has_min = _has_any(graph, pv, MIN_PREDS)
                    has_max = _has_any(graph, pv, MAX_PREDS)
                    depth_hit = False
                    for name in names:
                        self.variable_names[name] += 1
                        if name == "DepBelowSurf":
                            self.datasets_with_depbelowsurf.add(key)
                            depth_hit = True
                        if _is_depth_name(name):
                            self.depth_names[name] += 1
                            self.datasets_with_depth.add(key)
                            depth_hit = True
                    if depth_hit:
                        self.depth_property_values += 1
                        if has_min and has_max:
                            self.depth_with_range += 1
                            self.datasets_with_depth_range.add(key)


def _histogram(counter: Counter, *, limit: int | None = None) -> dict:
    ranked = counter.most_common()
    shown = ranked if limit is None else ranked[:limit]
    leftover = ranked[limit:] if limit is not None else []
    entries = [
        {"@type": "HistogramBucket", "@id": iri, "curie": compact_curie(iri), "count": count}
        for iri, count in shown
    ]
    other = sum(count for _, count in leftover)
    return {
        "@type": "Histogram",
        "bucket": entries,
        "otherCount": other,
        "distinctCount": len(counter),
    }


def _name_histogram(counter: Counter) -> dict:
    entries = [
        {"@type": "HistogramBucket", "name": name, "count": count}
        for name, count in counter.most_common()
    ]
    return {
        "@type": "Histogram",
        "bucket": entries,
        "otherCount": 0,
        "distinctCount": len(counter),
    }


def _ratio(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(part / whole, 4)


def _file_sha256(path: Path) -> str | None:
    if not path.is_file() or path.stat().st_size > HASH_MAX_BYTES:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_into_stats(path: Path, rdf_format: str, stats: GraphStats) -> None:
    stats.file_count += 1
    stats.byte_count += path.stat().st_size
    if rdf_format == "nquads":
        dataset = Dataset()
        dataset.parse(str(path), format="nquads")
        for graph in dataset.graphs():
            identifier = str(graph.identifier)
            default_id = str(dataset.default_context.identifier)
            graph_iri = None if identifier == default_id else identifier
            stats.absorb_graph(graph, graph_iri)
        return
    graph = Graph()
    graph.parse(str(path), format=rdf_format)
    stats.absorb_graph(graph)


def collect_output_files(
    root: Path, provider: Provider, max_files: int | None
) -> tuple[list[tuple[Path, str]], bool]:
    """All published RDF files for a provider, optionally capped."""
    files: list[tuple[Path, str]] = []
    truncated = False
    for path, fmt, _shacl in provider.resolve_outputs(root):
        if max_files is not None and len(files) >= max_files:
            truncated = True
            break
        remaining = None if max_files is None else max_files - len(files)
        batch = collect_rdf_files(path, fmt, remaining)
        files.extend(batch)
        if remaining is not None and len(batch) == remaining:
            truncated = True
    return files, truncated


def analyze_provider_outputs(
    *,
    root: Path,
    provider: Provider,
    max_files: int | None = None,
) -> GraphStats:
    """Scan published RDF for one provider. Does not rewrite those files."""
    stats = GraphStats()
    files, truncated = collect_output_files(root, provider, max_files)
    stats.truncated = truncated
    if len(files) == 1:
        stats.sha256 = _file_sha256(files[0][0])
    for path, rdf_format in files:
        try:
            _parse_into_stats(path, rdf_format, stats)
        except Exception as e:
            stats.parse_errors.append({"path": str(path), "message": str(e)})
    return stats


def _metrics_node(stats: GraphStats) -> dict:
    n_records = len(stats.datasets)
    return {
        "@type": "RunMetrics",
        "fileCount": stats.file_count,
        "byteCount": stats.byte_count,
        "recordCount": n_records,
        "tripleCount": stats.triple_count,
        "namedGraphCount": len(stats.named_graphs),
        "parseErrorCount": len(stats.parse_errors),
        "truncated": stats.truncated,
        "sha256": stats.sha256,
        "typeHistogram": _histogram(stats.types),
        "predicateHistogram": _histogram(
            stats.predicates, limit=PREDICATE_HISTOGRAM_LIMIT
        ),
        "namespaceHistogram": _histogram(stats.namespaces),
        "depth": {
            "@type": "DepthMetrics",
            "variableMeasuredCount": stats.variable_measured_count,
            "depthPropertyValueCount": stats.depth_property_values,
            "depthWithRangeCount": stats.depth_with_range,
            "variableNameHistogram": _name_histogram(stats.variable_names),
            "depthNameHistogram": _name_histogram(stats.depth_names),
        },
        "completeness": {
            "@type": "CompletenessMetrics",
            "recordCount": n_records,
            "withName": len(stats.datasets_with_name),
            "withDescription": len(stats.datasets_with_description),
            "withUrl": len(stats.datasets_with_url),
            "withDepBelowSurf": len(stats.datasets_with_depbelowsurf),
            "withDepthVariable": len(stats.datasets_with_depth),
            "withDepthRange": len(stats.datasets_with_depth_range),
            "nameRatio": _ratio(len(stats.datasets_with_name), n_records),
            "descriptionRatio": _ratio(len(stats.datasets_with_description), n_records),
            "urlRatio": _ratio(len(stats.datasets_with_url), n_records),
            "depBelowSurfRatio": _ratio(len(stats.datasets_with_depbelowsurf), n_records),
            "depthVariableRatio": _ratio(len(stats.datasets_with_depth), n_records),
            "depthRangeRatio": _ratio(len(stats.datasets_with_depth_range), n_records),
        },
    }


def build_report(
    *,
    root: Path,
    provider: Provider,
    work_dir: Path,
    manifest: dict | None = None,
    max_files: int | None = None,
) -> dict:
    """Build a self-contained JSON-LD pipeline report for one provider."""
    generated = datetime.now(timezone.utc)
    stamp = generated.strftime("%Y%m%dT%H%M%SZ")
    report_id = f"urn:doos:report:{provider.name}:{stamp}"
    stats = analyze_provider_outputs(
        root=root, provider=provider, max_files=max_files
    )
    activity = {
        "@id": f"{report_id}#activity",
        "@type": "prov:Activity",
        "name": f"doos_pipeline {provider.name}",
        "used": [str(path) for path, _fmt, _shacl in provider.resolve_outputs(root)],
        "startedAtTime": (manifest or {}).get("started_at") or generated.isoformat(),
        "endedAtTime": (manifest or {}).get("finished_at") or generated.isoformat(),
        "exitCode": (manifest or {}).get("exit_code"),
        "dryRun": (manifest or {}).get("dry_run", False),
        "steps": (manifest or {}).get("steps") or [],
        "software": {
            "@type": "schema:SoftwareApplication",
            "name": "doos_pipeline",
            "softwareVersion": __version__,
        },
    }
    outputs = []
    for path, fmt, shacl in provider.resolve_outputs(root):
        outputs.append(
            {
                "@type": "schema:DataDownload",
                "contentUrl": str(path),
                "encodingFormat": fmt,
                "name": path.name,
                "shaclEligible": shacl,
                "exists": path.exists(),
            }
        )
    description = (
        f"DOOS graph generation report for {provider.name}: "
        f"{stats.file_count} file(s), {len(stats.datasets)} record(s), "
        f"{stats.triple_count} triple(s)."
    )
    return {
        "@context": REPORT_CONTEXT,
        "@id": report_id,
        "@type": ["PipelineReport", "prov:Entity", "schema:Dataset"],
        "name": f"DOOS pipeline report: {provider.name}",
        "description": description,
        "dateCreated": generated.isoformat(),
        "provider": provider.name,
        "providerStatus": provider.status,
        "providerDescription": provider.description,
        "namedGraph": provider.graph,
        "conformsTo": DOOS_VOCAB + "PipelineReport",
        "wasGeneratedBy": activity,
        "distribution": outputs,
        "metrics": _metrics_node(stats),
        "parseError": stats.parse_errors,
        "manifest": str(work_dir / "run.json") if manifest else None,
    }


def build_report_set(parts: list[dict], work_dir: Path) -> dict:
    """Roll up per-provider reports for ``run --all``."""
    generated = datetime.now(timezone.utc)
    stamp = generated.strftime("%Y%m%dT%H%M%SZ")
    summaries = []
    for part in parts:
        metrics = part.get("metrics") or {}
        summaries.append(
            {
                "@id": part.get("@id"),
                "@type": "PipelineReport",
                "provider": part.get("provider"),
                "name": part.get("name"),
                "recordCount": metrics.get("recordCount"),
                "tripleCount": metrics.get("tripleCount"),
                "fileCount": metrics.get("fileCount"),
                "completeness": metrics.get("completeness"),
            }
        )
    return {
        "@context": REPORT_CONTEXT,
        "@id": f"urn:doos:report:set:{stamp}",
        "@type": ["PipelineReportSet", "prov:Entity", "schema:Dataset"],
        "name": "DOOS pipeline report set",
        "dateCreated": generated.isoformat(),
        "hasPart": summaries,
        "workDir": str(work_dir),
    }


def write_report(document: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def report_summary_line(document: dict) -> str:
    metrics = document.get("metrics") or {}
    return (
        f"records={metrics.get('recordCount', 0)} "
        f"triples={metrics.get('tripleCount', 0)} "
        f"files={metrics.get('fileCount', 0)} "
        f"depBelowSurf={((metrics.get('completeness') or {}).get('withDepBelowSurf', 0))}"
    )
