"""Stage 3 — validate: conformance defined by severity, not pySHACL's boolean."""

from __future__ import annotations

GOOD = """@prefix schema: <https://schema.org/> .
<https://e.org/d> a schema:Dataset ;
  schema:name "Ocean temps" ;
  schema:description "A multi-year record of sea surface temperature observations across the North Atlantic basin." .
"""

BAD = """@prefix schema: <https://schema.org/> .
<https://e.org/d> a schema:Dataset ; schema:name "Ocean temps" .
"""


def _run(validate, tmp_path, ttl):
    (tmp_path / "g.ttl").write_text(ttl, encoding="utf-8")
    return validate.run_validation(tmp_path / "g.ttl", out_dir=tmp_path)


def test_good_conforms_despite_warnings(validate, tmp_path):
    r = _run(validate, tmp_path, GOOD)
    assert r["conforms"] is True            # zero violations
    assert r["n_violations"] == 0
    assert r["n_warnings"] > 0              # recommended fields missing
    assert r["raw_conforms"] is False        # pySHACL boolean trips on warnings


def test_missing_description_is_a_violation(validate, tmp_path):
    r = _run(validate, tmp_path, BAD)
    assert r["conforms"] is False
    assert r["n_violations"] == 1


def test_writes_three_artifacts(validate, tmp_path):
    _run(validate, tmp_path, GOOD)
    for f in ("03_report.ttl", "03_results.json", "03_conforms.json"):
        assert (tmp_path / f).exists()


def test_result_rows_have_expected_keys(validate, tmp_path):
    r = _run(validate, tmp_path, BAD)
    row = r["results"][0]
    for k in ("severity", "focus_node", "result_path", "source_constraint",
              "message"):
        assert k in row


def test_https_namespace_actually_matches(validate, tmp_path):
    # An http:// typed Dataset must NOT match the https shape (silent-conform trap).
    http_ttl = ('@prefix s: <http://schema.org/> .\n'
                '<https://e.org/d> a s:Dataset ; s:name "x" .\n')
    r = _run(validate, tmp_path, http_ttl)
    # No schema:Dataset (https) target => zero results at all.
    assert r["n_violations"] == 0 and r["n_warnings"] == 0
