"""Shared constants and I/O helpers for the BCO-DMO scanner."""

import json
import sys
from pathlib import Path

import requests

USER_AGENT = "BCO-DMO-Scanner/1.0 (DOOS; dfils@ucsd.edu)"
TIMEOUT = 30


def make_session() -> requests.Session:
    """Return a requests Session with the project's standard User-Agent."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def write_json(path: Path, data: dict) -> None:
    """Write a dict as indented JSON, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_json(path: Path) -> dict:
    """Load and return a JSON object from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def log(message: str) -> None:
    """Print a progress message to stderr."""
    print(message, file=sys.stderr)