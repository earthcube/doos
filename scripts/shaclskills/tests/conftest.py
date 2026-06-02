"""Shared pytest fixtures for the SHACL-for-AI-outputs bundle.

Stage modules live in sibling dirs whose names start with digits / contain
hyphens, so they are loaded by file path (same trick as orchestration/nodes.py).
All tests run with the LLM disabled so behavior is deterministic regardless of
whether an LLM API key is set in the environment.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

BUNDLE_ROOT = Path(__file__).resolve().parents[1]

# Make `import orchestration...` work for the driver tests.
if str(BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(BUNDLE_ROOT))


def _load(rel_path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, BUNDLE_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Force the LLM off for every test (deterministic)."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture(scope="session")
def extract():
    return _load("1-llm-output/assets/extract.py", "t_extract")


@pytest.fixture(scope="session")
def lift():
    return _load("2-rdf-knowledge-graph/assets/lift.py", "t_lift")


@pytest.fixture(scope="session")
def validate():
    return _load("3-shacl-validation/assets/validate.py", "t_validate")


@pytest.fixture(scope="session")
def parse_report():
    return _load("4-violation-report/assets/parse_report.py", "t_parse_report")


@pytest.fixture(scope="session")
def repair():
    return _load("5-repair/assets/repair.py", "t_repair")


# --- small helpers -------------------------------------------------------- #
GOOD_EXTRACTED = {
    "url": "https://example.org/d",
    "name": "Example Dataset",
    "description": "A sufficiently long description of the example dataset that "
    "comfortably exceeds the fifty character minimum required by the shape.",
    "keywords": ["alpha", "beta"],
    "source": "embedded-jsonld",
}


@pytest.fixture
def good_extracted():
    return dict(GOOD_EXTRACTED)
