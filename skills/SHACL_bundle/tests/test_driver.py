"""Driver — end-to-end orchestration and loop stop conditions (no LLM)."""

from __future__ import annotations

from orchestration.run import run_pipeline

GOOD_PAGE = """<html><head><script type="application/ld+json">
{"@type":"Dataset","name":"Tide Gauge Records",
 "description":"Long-term sea level measurements from a network of coastal tide gauges over several decades.",
 "url":"https://example.org/tides","keywords":["tides","sea level"]}
</script></head></html>"""

SHORT_DESC_PAGE = """<html><head><script type="application/ld+json">
{"@type":"Dataset","name":"Reef Survey","description":"Too short.",
 "url":"https://example.org/reef","keywords":["reef"]}
</script></head></html>"""


def _file_url(tmp_path, html):
    p = tmp_path / "page.html"
    p.write_text(html, encoding="utf-8")
    return f"file://{p}"


def test_happy_path_conforms(tmp_path):
    url = _file_url(tmp_path, GOOD_PAGE)
    final = run_pipeline(url, run_id="ok", runs_dir=tmp_path / "runs", use_llm=False)
    assert final["conforms"] is True
    assert final["n_violations"] == 0
    assert final.get("iteration", 0) == 0          # no repair needed
    assert final["raid_json"].endswith("06_raid.json")


def test_happy_path_skips_repair(tmp_path):
    url = _file_url(tmp_path, GOOD_PAGE)
    final = run_pipeline(url, run_id="ok2", runs_dir=tmp_path / "runs", use_llm=False)
    # stage5 never ran -> no stage5 events
    assert not any(ev.startswith("stage5") for ev in final["events"])


def test_short_description_stops_on_no_progress(tmp_path):
    # reword needs the LLM; with it off, one repair pass then no-progress stop.
    url = _file_url(tmp_path, SHORT_DESC_PAGE)
    final = run_pipeline(url, run_id="short", runs_dir=tmp_path / "runs",
                         max_iterations=3, use_llm=False)
    assert final["conforms"] is False
    assert final["n_violations"] == 1
    assert final["iteration"] == 1                 # stopped after one futile pass
    assert final["raid_json"].endswith("06_raid.json")   # still records the run


def test_run_dir_artifacts_written(tmp_path):
    url = _file_url(tmp_path, GOOD_PAGE)
    final = run_pipeline(url, run_id="arts", runs_dir=tmp_path / "runs", use_llm=False)
    from pathlib import Path

    run_dir = Path(final["run_dir"])
    for f in ("00_input.json", "01_extracted.json", "02_graph.ttl",
              "03_conforms.json", "04_report.json", "06_raid.json", "06_record.md"):
        assert (run_dir / f).exists(), f
