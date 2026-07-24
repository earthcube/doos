"""Stage 1 — extract: embedded JSON-LD reuse, normalization, honest no-data."""

from __future__ import annotations

DATASET_PAGE = """<html><head>
<script type="application/ld+json">
{ "@context":"https://schema.org/", "@graph":[
  {"@type":"WebPage","name":"ignore me"},
  {"@type":["Dataset"],
   "name":"Argo Floats",
   "description":"Temperature and salinity profiles from the global Argo array.",
   "url":"https://example.org/argo",
   "keywords":["argo","temperature"]} ]}
</script></head><body></body></html>"""


def test_picks_dataset_from_graph(extract):
    out = extract.extract_from_html(DATASET_PAGE, "https://in.example/x", use_llm=False)
    assert out["source"] == "embedded-jsonld"
    assert out["name"] == "Argo Floats"
    assert out["url"] == "https://example.org/argo"          # from JSON-LD, not input
    assert out["keywords"] == ["argo", "temperature"]


def test_comma_separated_keywords_split(extract):
    html = ('<html><head><script type="application/ld+json">'
            '{"@type":"Dataset","name":"X","description":"y",'
            '"url":"https://e.org/x","keywords":"ocean, temperature ,salinity"}'
            "</script></head></html>")
    out = extract.extract_from_html(html, "https://e.org/x", use_llm=False)
    assert out["keywords"] == ["ocean", "temperature", "salinity"]


def test_no_metadata_no_llm_is_honest(extract):
    html = "<html><head><title>plain</title></head><body>nothing</body></html>"
    out = extract.extract_from_html(html, "https://e.org/none", use_llm=False)
    assert out["source"] == "none"
    assert out["name"] is None and out["description"] is None
    assert out["keywords"] == []
    # keys always present (fixed contract)
    assert set(out) == {"url", "name", "description", "keywords", "source"}


def test_keys_always_present(extract):
    out = extract.extract_from_html(DATASET_PAGE, "https://in/x", use_llm=False)
    assert set(out) == {"url", "name", "description", "keywords", "source"}


def test_run_extract_via_file_url_and_schema(extract, validate, tmp_path):
    page = tmp_path / "page.html"
    page.write_text(DATASET_PAGE, encoding="utf-8")
    r = extract.run_extract(f"file://{page}", out_dir=tmp_path, use_llm=False)
    assert r["source"] == "embedded-jsonld"
    assert (tmp_path / "01_extracted.json").exists()


def test_fetch_failure_degrades_not_crashes(extract, tmp_path):
    # A nonexistent file:// target makes urlopen raise; run_extract must NOT
    # propagate it (that would crash the pipeline) — it degrades to source=none
    # and records the error, still writing 01_extracted.json.
    missing = tmp_path / "does_not_exist.html"
    r = extract.run_extract(f"file://{missing}", out_dir=tmp_path, use_llm=False)
    assert r["source"] == "none"
    assert r["name"] is None and r["keywords"] == []
    assert "error" in r and r["error"]
    assert (tmp_path / "01_extracted.json").exists()
