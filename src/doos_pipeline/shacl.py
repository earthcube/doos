"""Optional SHACL check against files a provider already published.

Does not rewrite project outputs. Reports pass/fail only.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import Dataset, Graph

FORMAT_BY_SUFFIX = {
    ".nt": "nt",
    ".nq": "nquads",
    ".ttl": "turtle",
    ".jsonld": "json-ld",
    ".json": "json-ld",
}


def collect_rdf_files(path: Path, fmt: str, limit: int | None) -> list[tuple[Path, str]]:
    """Return (file, rdflib format) pairs under a published path."""
    if not path.exists():
        return []

    if path.is_file():
        suffix = path.suffix.lower()
        rdf_format = FORMAT_BY_SUFFIX.get(suffix)
        if fmt in FORMAT_BY_SUFFIX.values():
            mapped = {
                "nt": "nt",
                "nq": "nquads",
                "ttl": "turtle",
                "jsonld": "json-ld",
                "json": "json-ld",
                "mixed": rdf_format,
            }.get(fmt, rdf_format)
            rdf_format = mapped or rdf_format
        if not rdf_format:
            return []
        return [(path, rdf_format)]

    found: list[tuple[Path, str]] = []
    dir_suffixes = {
        ".nt": "nt",
        ".nq": "nquads",
        ".ttl": "turtle",
        ".jsonld": "json-ld",
        ".json": "json-ld",
    }
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        rdf_format = dir_suffixes.get(child.suffix.lower())
        if rdf_format is None:
            continue
        if child.suffix.lower() == ".json" and _skip_sidecar_json(child):
            continue
        found.append((child, rdf_format))
        if limit is not None and len(found) >= limit:
            break
    return found


def _skip_sidecar_json(path: Path) -> bool:
    """Skip inventory/manifest JSON that is not graph output."""
    name = path.name.lower()
    if name in {"run.json"}:
        return True
    suffixes = (
        "_report.json",
        "_inventory.json",
        "_summary.json",
        "_manifest.json",
        "_diff.json",
        "_results.json",
        "_verify.json",
    )
    return name.endswith(suffixes)


def _validate_graph(data_graph: Graph, shapes_path: Path) -> tuple[bool, str]:
    from pyshacl import validate

    conforms, _report_graph, report_text = validate(
        data_graph,
        shacl_graph=str(shapes_path),
        shacl_graph_format="turtle",
        inference="rdfs",
        serialize_report_graph=False,
    )
    return bool(conforms), str(report_text)


def validate_file(
    path: Path,
    rdf_format: str,
    shapes_path: Path,
    graph_limit: int | None,
) -> list[dict]:
    """Validate one RDF file. N-Quads are checked per named graph."""
    results: list[dict] = []
    if rdf_format == "nquads":
        dataset = Dataset()
        dataset.parse(str(path), format="nquads")
        graphs = list(dataset.graphs())
        if graph_limit is not None:
            graphs = graphs[:graph_limit]
        for graph in graphs:
            identifier = str(graph.identifier)
            try:
                conforms, text = _validate_graph(graph, shapes_path)
                results.append(
                    {
                        "path": str(path),
                        "graph": identifier,
                        "conforms": conforms,
                        "message": None if conforms else text,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "path": str(path),
                        "graph": identifier,
                        "conforms": False,
                        "message": str(e),
                    }
                )
        return results

    graph = Graph()
    graph.parse(str(path), format=rdf_format)
    try:
        conforms, text = _validate_graph(graph, shapes_path)
        results.append(
            {
                "path": str(path),
                "graph": None,
                "conforms": conforms,
                "message": None if conforms else text,
            }
        )
    except Exception as e:
        results.append(
            {
                "path": str(path),
                "graph": None,
                "conforms": False,
                "message": str(e),
            }
        )
    return results


def validate_provider_outputs(
    *,
    root: Path,
    provider,
    shapes_path: Path,
    limit: int | None = 25,
) -> dict:
    """SHACL-check published outputs. Never writes into the provider tree."""
    files: list[tuple[Path, str]] = []
    missing = []
    skipped = []
    for path, fmt, shacl in provider.resolve_outputs(root):
        if not shacl:
            skipped.append(str(path))
            continue
        if not path.exists():
            missing.append(str(path))
            continue
        remaining = None if limit is None else max(0, limit - len(files))
        if remaining == 0:
            break
        files.extend(collect_rdf_files(path, fmt, remaining))

    checks: list[dict] = []
    for path, rdf_format in files:
        remaining_graphs = None if limit is None else max(0, limit - len(checks))
        if remaining_graphs == 0:
            break
        checks.extend(
            validate_file(path, rdf_format, shapes_path, remaining_graphs)
        )

    passed = sum(1 for row in checks if row["conforms"])
    failed = len(checks) - passed
    return {
        "provider": provider.name,
        "shapes": str(shapes_path),
        "missing_outputs": missing,
        "skipped_outputs": skipped,
        "files_checked": len(files),
        "results": checks,
        "passed": passed,
        "failed": failed,
        "conforms": not missing and failed == 0,
    }
