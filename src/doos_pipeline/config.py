"""Load wrapper config and locate the DOOS repository root."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = PACKAGE_DIR / "config.yaml"


def repo_root() -> Path:
    """Return the monorepo root (directory that contains ``projects/`` and ``SHACL/``)."""
    env = os.environ.get("DOOS_ROOT")
    if env:
        return Path(env).resolve()

    for candidate in (PACKAGE_DIR.parent.parent, *PACKAGE_DIR.parents):
        if (candidate / "projects").is_dir() and (candidate / "SHACL").is_dir():
            return candidate

    raise RuntimeError(
        "Cannot find the DOOS repository root. Set DOOS_ROOT or run from a checkout "
        "that contains projects/ and SHACL/."
    )


def load_raw_config(path: Path | None = None) -> dict:
    """Load the YAML registry. Requires PyYAML (already used by loadToOxigraph)."""
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError(
            "PyYAML is required to read doos_pipeline/config.yaml. "
            "Install it or use the same environment as scripts/loadToOxigraph/."
        ) from e

    config_path = path or DEFAULT_CONFIG
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid config (expected mapping): {config_path}")
    return data
