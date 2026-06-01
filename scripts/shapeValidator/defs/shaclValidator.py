from pyshacl import validate

from rdflib import Graph, Namespace
from rdflib.namespace import RDF

SH = Namespace("http://www.w3.org/ns/shacl#")


def validate_with_shacl(rdf_graph_text, shacl_shape_text):
    """
    Validate an RDF graph against a SHACL shape graph using pyshacl.

    Args:
        rdf_graph_text (str): RDF graph content as text
        shacl_shape_text (str): SHACL shape graph content as text
        output_format (str): Output format - one of: human, table, turtle, xml, json-ld, nt, n3

    Returns:
        tuple: (is_valid, validation_report, validation_text)
            - is_valid (bool): True if validation passed, False otherwise
            - validation_report (Graph): The validation report as an RDF graph
            - validation_text (str): The validation report in the requested format
    """

    try:
        # Perform SHACL validation
        is_valid, validation_graph, validation_text = validate(
            rdf_graph_text,
            data_graph_format="ttl",
            shacl_graph_format="ttl",
            shacl_graph=shacl_shape_text,
            inference="rdfs",
            serialize_report_graph=False,
        )

        # print("--------------------------------------------")
        # print(is_valid)
        # print("--------------------------------------------")
        # print(validation_graph)
        # print("--------------------------------------------")
        # print(validation_text)

        # return is_valid, validation_graph, validation_text

        skolemver = validation_graph.skolemize(authority="http://gleaner.io")
        # return skolemver.serialize(format="nt")

        return skolemver.serialize(format="nt")

    except Exception as e:
        raise Exception(f"SHACL validation error: {e}")


def validate_with_shacl_simple(rdf_graph_text, shacl_shape_text):
    """
    Simplified version that returns only the validation text result.

    Args:
        rdf_graph_text (str): RDF graph content as text
        shacl_shape_text (str): SHACL shape graph content as text
        output_format (str): Output format - one of: human, table, turtle, xml, json-ld, nt, n3

    Returns:
        str: The validation report in the requested format
    """

    try:
        # Perform SHACL validation
        is_valid, validation_graph, validation_text = validate(
            rdf_graph_text,
            data_graph_format="ttl",
            shacl_graph_format="ttl",
            shacl_graph=shacl_shape_text,
            inference="rdfs",
            serialize_report_graph=True,
        )

        # print("--------------------------------------------")
        # print(is_valid)
        # print("--------------------------------------------")
        # print(validation_graph)
        # print("--------------------------------------------")
        # print(validation_text)

        # return is_valid, validation_graph, validation_text
        return validation_text

    except Exception as e:
        raise Exception(f"SHACL validation error: {e}")


def validate_with_shacl_results(
    rdf_graph_text: str, shacl_shape_text: str
) -> tuple[bool, list[dict]]:
    """
    Validate and return structured results suitable for Parquet / analytics.

    Returns:
        (is_valid, list_of_result_dicts)

    Each dict contains keys:
        - result_id
        - severity
        - focus_node
        - result_path
        - message
        - source_shape
        - source_constraint
        - value
    """
    try:
        is_valid, validation_graph, _ = validate(
            rdf_graph_text,
            data_graph_format="ttl",
            shacl_graph_format="ttl",
            shacl_graph=shacl_shape_text,
            inference="rdfs",
            serialize_report_graph=False,
        )

        # Skolemize for stable identifiers
        skolem_graph = validation_graph.skolemize(authority="http://gleaner.io")

        results = []
        for res in skolem_graph.subjects(RDF.type, SH.ValidationResult):
            row = {
                "result_id": str(res),
                "severity": _get_obj(skolem_graph, res, SH.resultSeverity),
                "focus_node": _get_obj(skolem_graph, res, SH.focusNode),
                "result_path": _get_obj(skolem_graph, res, SH.resultPath),
                "message": _get_obj(skolem_graph, res, SH.resultMessage),
                "source_shape": _get_obj(skolem_graph, res, SH.sourceShape),
                "source_constraint": _get_obj(skolem_graph, res, SH.sourceConstraintComponent),
                "value": _get_obj(skolem_graph, res, SH.value),
            }
            results.append(row)

        return bool(is_valid), results

    except Exception as e:
        raise Exception(f"SHACL validation error: {e}") from e


def _get_obj(g: Graph, subject, predicate):
    """Return string value of first object or None."""
    for obj in g.objects(subject, predicate):
        return str(obj)
    return None


# --------------------------------------------------------------------------- #
# pyrudof (Rust) structured results extractor
# --------------------------------------------------------------------------- #


def validate_with_rudof_results(
    data_graph_ttl: str, shapes_ttl: str, skolemize: bool = True
) -> tuple[bool, list[dict]]:
    """
    Validate using pyrudof/rudof and return structured results in the exact
    same format as validate_with_shacl_results for Parquet/analytics compatibility.

    Returns:
        (is_valid, list_of_result_dicts) with the same keys as the pyshacl version.
    """
    try:
        from pyrudof import Rudof, RudofConfig, ShaclFormat, RDFFormat, ResultShaclValidationFormat
    except ImportError:
        raise ImportError(
            "pyrudof is required for this validator. Install with: pip install pyrudof"
        )

    rudof = Rudof(RudofConfig())

    # Load shapes
    rudof.read_shacl(input=shapes_ttl, format=ShaclFormat.Turtle)

    # Load data into default graph (rudof limitation with very long graph URIs)
    rudof.read_data(input=data_graph_ttl, format=RDFFormat.Turtle)

    # Run validation
    rudof.validate_shacl()

    # Get N-Triples report
    report_nt = rudof.serialize_shacl_validation_results(
        format=ResultShaclValidationFormat.NTriples
    )

    if skolemize and report_nt:
        try:
            from rdflib import Graph, Namespace
            from rdflib.namespace import RDF

            SH = Namespace("http://www.w3.org/ns/shacl#")
            g = Graph()
            g.parse(data=report_nt, format="nt")
            skolemized = g.skolemize(authority="http://gleaner.io")
            report_nt = skolemized.serialize(format="nt")
        except Exception:
            pass  # fall back to raw report

    if not report_nt or not report_nt.strip():
        return True, []

    # Parse and extract structured rows (same shape as pyshacl path)
    try:
        from rdflib import Graph, Namespace
        from rdflib.namespace import RDF

        SH = Namespace("http://www.w3.org/ns/shacl#")

        g = Graph()
        g.parse(data=report_nt, format="nt")

        results = []
        for res in g.subjects(RDF.type, SH.ValidationResult):
            row = {
                "result_id": str(res),
                "severity": _get_obj(g, res, SH.resultSeverity),
                "focus_node": _get_obj(g, res, SH.focusNode),
                "result_path": _get_obj(g, res, SH.resultPath),
                "message": _get_obj(g, res, SH.resultMessage),
                "source_shape": _get_obj(g, res, SH.sourceShape),
                "source_constraint": _get_obj(g, res, SH.sourceConstraintComponent),
                "value": _get_obj(g, res, SH.value),
            }
            results.append(row)

        # Conformance: no ValidationResults present (rudof reports focus on violations)
        is_valid = len(results) == 0
        return is_valid, results

    except Exception as e:
        raise Exception(f"Error parsing pyrudof validation report: {e}") from e
