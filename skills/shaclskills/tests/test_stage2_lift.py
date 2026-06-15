"""Stage 2 — lift: deterministic schema.org mapping + IRI policy."""

from __future__ import annotations


def test_mints_stable_iri(lift, good_extracted):
    iri1 = lift.mint_iri(good_extracted, iri_base="https://base/d")
    iri2 = lift.mint_iri(good_extracted, iri_base="https://base/d")
    assert iri1 == iri2                         # deterministic
    assert iri1.startswith("https://base/d/")
    assert len(iri1.rsplit("/", 1)[-1]) == 16   # sha256[:16] slug


def test_iri_normalization_ignores_trailing_slash(lift):
    a = lift.mint_iri({"url": "https://e.org/x/"})
    b = lift.mint_iri({"url": "https://e.org/x"})
    assert a == b


def test_graph_uses_https_schema_and_iri_url(lift, good_extracted):
    g = lift.lift(good_extracted)
    ttl = g.serialize(format="turtle")
    assert "https://schema.org/" in ttl
    assert "http://schema.org/" not in ttl
    # url is emitted as an IRI, not a literal
    assert "<https://example.org/d>" in ttl
    assert g.serialize(format="turtle").count("schema:keywords") >= 1


def test_deterministic_output(lift, good_extracted):
    g1 = lift.lift(good_extracted).serialize(format="turtle")
    g2 = lift.lift(good_extracted).serialize(format="turtle")
    assert g1 == g2


def test_absent_fields_produce_no_triple(lift):
    g = lift.lift({"url": "https://e.org/x", "name": "N", "description": None,
                   "keywords": []})
    ttl = g.serialize(format="turtle")
    assert "schema:description" not in ttl
    assert "schema:keywords" not in ttl
    assert "schema:name" in ttl


def test_run_lift_writes_graph(lift, good_extracted, tmp_path):
    (tmp_path / "01_extracted.json").write_text(__import__("json").dumps(good_extracted))
    r = lift.run_lift(tmp_path / "01_extracted.json", out_dir=tmp_path)
    assert (tmp_path / "02_graph.ttl").exists()
    assert r["n_triples"] > 0
