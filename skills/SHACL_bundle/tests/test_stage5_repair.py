"""Stage 5 — repair: add-from-source closes the loop; remove-extra; no fabrication."""

from __future__ import annotations

import json


def _pipeline_to_report(lift, validate, parse_report, tmp_path, extracted):
    """Run 2→3→4 deterministically and return the run dir."""
    (tmp_path / "01_extracted.json").write_text(json.dumps(extracted))
    lift.run_lift(tmp_path / "01_extracted.json", out_dir=tmp_path)
    validate.run_validation(tmp_path / "02_graph.ttl", out_dir=tmp_path)
    parse_report.run_report(tmp_path / "03_results.json", tmp_path, use_llm=False)
    return tmp_path


def test_add_from_source_closes_violation(lift, validate, parse_report, repair,
                                          good_extracted, tmp_path):
    # Build a graph MISSING the description, but supply a source that HAS one.
    nodesc = dict(good_extracted, description=None)
    _pipeline_to_report(lift, validate, parse_report, tmp_path, nodesc)

    full = tmp_path / "01_full.json"
    full.write_text(json.dumps(good_extracted))
    r = repair.run_repair(tmp_path / "02_graph.ttl", tmp_path / "04_report.json",
                          out_dir=tmp_path, extracted_path=full, use_llm=False)
    assert r["n_fixed"] == 1

    # Re-validate the repaired graph -> conforms.
    rv = validate.run_validation(tmp_path / "05_graph.ttl", out_dir=tmp_path / "rv")
    assert rv["conforms"] is True


def test_remove_extra_keeps_one(validate, parse_report, repair, tmp_path):
    ttl = ('@prefix schema: <https://schema.org/> .\n'
           '<https://e.org/d> a schema:Dataset ;\n'
           '  schema:name "Two URLs" ;\n'
           '  schema:description "A description that is comfortably longer than the '
           'fifty character minimum length requirement here." ;\n'
           '  schema:url <https://e.org/a>, <https://e.org/b> .\n')
    (tmp_path / "02_graph.ttl").write_text(ttl)
    validate.run_validation(tmp_path / "02_graph.ttl", out_dir=tmp_path)
    parse_report.run_report(tmp_path / "03_results.json", tmp_path, use_llm=False)
    repair.run_repair(tmp_path / "02_graph.ttl", tmp_path / "04_report.json",
                      out_dir=tmp_path, use_llm=False)
    repaired = (tmp_path / "05_graph.ttl").read_text()
    assert repaired.count("e.org/a") + repaired.count("e.org/b") == 1


def test_no_source_no_llm_does_not_fabricate(lift, validate, parse_report, repair,
                                             good_extracted, tmp_path):
    nodesc = dict(good_extracted, description=None)
    _pipeline_to_report(lift, validate, parse_report, tmp_path, nodesc)
    # extracted source ALSO lacks description, LLM off -> cannot fix honestly.
    src = tmp_path / "01_extracted.json"   # the nodesc one written above
    r = repair.run_repair(tmp_path / "02_graph.ttl", tmp_path / "04_report.json",
                          out_dir=tmp_path, extracted_path=src, use_llm=False)
    assert r["n_fixed"] == 0
    assert "schema:description" not in (tmp_path / "05_graph.ttl").read_text()


def test_audit_log_written(lift, validate, parse_report, repair, good_extracted,
                           tmp_path):
    nodesc = dict(good_extracted, description=None)
    _pipeline_to_report(lift, validate, parse_report, tmp_path, nodesc)
    repair.run_repair(tmp_path / "02_graph.ttl", tmp_path / "04_report.json",
                      out_dir=tmp_path, use_llm=False)
    assert (tmp_path / "run.log").exists()
    assert "[stage5]" in (tmp_path / "run.log").read_text()
