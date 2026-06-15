"""Stage 4 — parse_report: deterministic fixType/autoFixable, sorting, schema."""

from __future__ import annotations

import json

import jsonschema

SH = "http://www.w3.org/ns/shacl#"


def _results(*rows):
    return rows


def _write_results(tmp_path, rows):
    p = tmp_path / "03_results.json"
    p.write_text(json.dumps(list(rows)), encoding="utf-8")
    return p


def _row(constraint, severity="Violation", path="https://schema.org/description"):
    return {
        "result_id": f"urn:{constraint}:{severity}",
        "severity": f"{SH}{severity}",
        "focus_node": "https://e.org/d",
        "result_path": path,
        "source_shape": "urn:shape",
        "source_constraint": f"{SH}{constraint}",
        "message": "msg",
        "value": None,
    }


def test_fixtype_mapping(parse_report, tmp_path):
    rows = [
        _row("MinCountConstraintComponent"),
        _row("DatatypeConstraintComponent"),
        _row("MaxCountConstraintComponent"),
        _row("MinLengthConstraintComponent"),
        _row("ClassConstraintComponent"),
    ]
    rep = parse_report.run_report(_write_results(tmp_path, rows), tmp_path, use_llm=False)
    by_constraint = {f["source_constraint"].split("#")[-1]: f for f in rep["findings"]}
    assert by_constraint["MinCountConstraintComponent"]["fixType"] == "add"
    assert by_constraint["DatatypeConstraintComponent"]["fixType"] == "coerce"
    assert by_constraint["MaxCountConstraintComponent"]["fixType"] == "remove"
    assert by_constraint["MinLengthConstraintComponent"]["fixType"] == "reword"
    assert by_constraint["ClassConstraintComponent"]["fixType"] == "manual"


def test_autofixable_is_not_manual(parse_report, tmp_path):
    rows = [_row("MinCountConstraintComponent"), _row("ClassConstraintComponent")]
    rep = parse_report.run_report(_write_results(tmp_path, rows), tmp_path, use_llm=False)
    for f in rep["findings"]:
        assert f["autoFixable"] == (f["fixType"] != "manual")


def test_violations_sorted_before_warnings(parse_report, tmp_path):
    rows = [
        _row("MinCountConstraintComponent", severity="Warning",
             path="https://schema.org/keywords"),
        _row("MinCountConstraintComponent", severity="Violation",
             path="https://schema.org/description"),
    ]
    rep = parse_report.run_report(_write_results(tmp_path, rows), tmp_path, use_llm=False)
    assert rep["findings"][0]["severity_bucket"] == "violation"


def test_summary_conforms_and_enrichment(parse_report, tmp_path):
    rows = [_row("MinCountConstraintComponent", severity="Warning")]
    rep = parse_report.run_report(_write_results(tmp_path, rows), tmp_path, use_llm=False)
    assert rep["summary"]["conforms"] is True       # no violations
    assert rep["summary"]["enrichment"] == "deterministic"


def test_output_validates_against_schema(parse_report, tmp_path):
    from pathlib import Path

    rows = [_row("MinCountConstraintComponent")]
    parse_report.run_report(_write_results(tmp_path, rows), tmp_path, use_llm=False)
    report = json.loads((tmp_path / "04_report.json").read_text())
    schema_path = Path(parse_report.__file__).parent / "violation_schema.json"
    jsonschema.validate(report, json.loads(schema_path.read_text()))


def test_empty_results_conforms(parse_report, tmp_path):
    rep = parse_report.run_report(_write_results(tmp_path, []), tmp_path, use_llm=False)
    assert rep["summary"]["conforms"] is True
    assert rep["findings"] == []
