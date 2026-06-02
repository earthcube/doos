"""LLM health probe + driver preflight (no real network calls).

The autouse `_no_llm` fixture (conftest) clears both API-key vars, so by default
the LLM is "not configured". Individual tests set a fake key and monkeypatch the
probe to simulate reachable / unreachable without touching the network.
"""

from __future__ import annotations

from orchestration import llm
from orchestration.run import preflight_llm, run_pipeline

GOOD_PAGE = """<html><head><script type="application/ld+json">
{"@type":"Dataset","name":"Tide Gauge Records",
 "description":"Long-term sea level measurements from a network of coastal tide gauges over several decades.",
 "url":"https://example.org/tides","keywords":["tides","sea level"]}
</script></head></html>"""


def _file_url(tmp_path, html=GOOD_PAGE):
    p = tmp_path / "page.html"
    p.write_text(html, encoding="utf-8")
    return f"file://{p}"


# --- check_llm() ---------------------------------------------------------- #

def test_check_llm_no_key_returns_false():
    ok, detail = llm.check_llm()           # keys cleared by autouse fixture
    assert ok is False
    assert "no API key" in detail


def test_check_llm_reports_failure_not_raises(monkeypatch):
    """A configured-but-broken LLM yields (False, error) — never an exception."""
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")

    def _boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(llm, "get_chat_model", _boom)
    ok, detail = llm.check_llm()
    assert ok is False
    assert "RuntimeError" in detail and "connection refused" in detail


def test_check_llm_success(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")

    class _FakeChat:
        def invoke(self, _):
            return "ok"

    monkeypatch.setattr(llm, "get_chat_model", lambda **k: _FakeChat())
    ok, detail = llm.check_llm()
    assert ok is True
    assert "@" in detail                   # "<model> @ <url>"


# --- preflight_llm() ------------------------------------------------------ #

def test_preflight_disabled():
    assert preflight_llm(False) == (False, "LLM: disabled (--no-llm)")


def test_preflight_no_key():
    eff, msg = preflight_llm(True)          # requested but no key
    assert eff is False
    assert "no key set" in msg


def test_preflight_probe_off_is_enabled(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    eff, msg = preflight_llm(True, probe=False)
    assert eff is True
    assert "not probed" in msg


def test_preflight_unreachable_degrades(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setattr("orchestration.run.check_llm",
                        lambda: (False, "APIConnectionError: down"))
    eff, msg = preflight_llm(True, probe=True)
    assert eff is False                     # degraded to deterministic
    assert "UNREACHABLE" in msg and "continuing deterministically" in msg


def test_preflight_connected(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setattr("orchestration.run.check_llm",
                        lambda: (True, "gpt-4o @ https://api.openai.com/v1"))
    eff, msg = preflight_llm(True, probe=True)
    assert eff is True
    assert "connected" in msg


# --- run_pipeline records the status -------------------------------------- #

def test_pipeline_records_unreachable_status(tmp_path, monkeypatch):
    """A broken LLM is reported in the run, but the pipeline still completes."""
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setattr("orchestration.run.check_llm",
                        lambda: (False, "APIConnectionError: down"))
    final = run_pipeline(_file_url(tmp_path), run_id="probe",
                         runs_dir=tmp_path / "runs", use_llm=True)
    assert "UNREACHABLE" in final["llm_status"]
    assert final["events"][0] == final["llm_status"]   # first trace line
    assert final["conforms"] is True                   # deterministic run still works


def test_pipeline_no_llm_status(tmp_path):
    final = run_pipeline(_file_url(tmp_path), run_id="off",
                         runs_dir=tmp_path / "runs", use_llm=False)
    assert final["llm_status"] == "LLM: disabled (--no-llm)"


# --- bounded client + reasoning controls --------------------------------- #

def test_strip_reasoning_removes_think_blocks():
    raw = "<think>let me reason\nabout this</think>\n\n{\"name\": \"X\"}"
    assert llm.strip_reasoning(raw) == '{"name": "X"}'
    # No think block -> unchanged (just trimmed).
    assert llm.strip_reasoning("  hello  ") == "hello"


def test_disable_thinking_env_gating(monkeypatch):
    monkeypatch.delenv("LLM_DISABLE_THINKING", raising=False)
    assert llm._thinking_extra_body() == {}
    monkeypatch.setenv("LLM_DISABLE_THINKING", "1")
    assert llm._thinking_extra_body() == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


def test_get_chat_model_is_bounded(monkeypatch):
    """The client carries a timeout + capped retries so a call can't hang."""
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_TIMEOUT", "37")
    chat = llm.get_chat_model()                 # constructs; no network call
    # langchain_openai stores these as request_timeout / max_retries.
    assert getattr(chat, "request_timeout", None) == 37.0
    assert getattr(chat, "max_retries", None) == llm.DEFAULT_MAX_RETRIES


def test_get_chat_model_disable_thinking_sets_extra_body(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("LLM_DISABLE_THINKING", "true")
    chat = llm.get_chat_model()
    assert getattr(chat, "extra_body", None) == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
