"""Discover skills, prompts, and static graph context for MCP resources."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import (
    COOKBOOK_PATH,
    DOOS_ROOT,
    PATTERNS_PATH,
    PROMPTS_DIR,
    SKILLS_DIR,
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Pull simple name/description fields from YAML frontmatter (best-effort)."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    block = match.group(1)
    meta: dict[str, str] = {}
    # name: value
    for key in ("name", "description", "license"):
        m = re.search(
            rf"^{key}:\s*(?:>\s*)?(.*?)(?=\n[a-zA-Z_-]+:|\Z)",
            block,
            re.MULTILINE | re.DOTALL,
        )
        if m:
            val = m.group(1).strip()
            # Collapse folded YAML description
            val = re.sub(r"\n\s+", " ", val).strip().strip("\"'")
            meta[key] = val
    return meta


def list_skills() -> list[dict[str, Any]]:
    """Walk skills/**/SKILL.md and return catalog entries."""
    if not SKILLS_DIR.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for skill_md in sorted(SKILLS_DIR.rglob("SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        rel = skill_md.relative_to(DOOS_ROOT).as_posix()
        name = meta.get("name") or skill_md.parent.name
        entries.append(
            {
                "name": name,
                "description": meta.get("description", ""),
                "path": rel,
                "dir": skill_md.parent.relative_to(DOOS_ROOT).as_posix(),
            }
        )
    return entries


def read_skill(name: str) -> tuple[str, Path]:
    """Return (text, path) for a skill by frontmatter name or directory name."""
    for skill_md in sorted(SKILLS_DIR.rglob("SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        meta = _parse_frontmatter(text)
        skill_name = meta.get("name") or skill_md.parent.name
        if skill_name == name or skill_md.parent.name == name:
            return text, skill_md
    raise FileNotFoundError(f"skill not found: {name}")


def list_prompt_files() -> list[dict[str, str]]:
    """List markdown files under prompts/."""
    if not PROMPTS_DIR.is_dir():
        return []
    out: list[dict[str, str]] = []
    for path in sorted(PROMPTS_DIR.glob("*.md")):
        out.append(
            {
                "name": path.stem,
                "path": path.relative_to(DOOS_ROOT).as_posix(),
                "filename": path.name,
            }
        )
    return out


def read_prompt_file(name: str) -> str:
    """Read prompts/<name>.md (with or without .md suffix)."""
    stem = name.removesuffix(".md")
    path = PROMPTS_DIR / f"{stem}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {name}")
    return path.read_text(encoding="utf-8")


def read_patterns() -> str:
    """Read triple-pattern context for host-side text→SPARQL."""
    if not PATTERNS_PATH.is_file():
        return (
            f"(patterns file missing: {PATTERNS_PATH})\n"
            "Use schema.org Dataset + variableMeasured patterns from the cookbook."
        )
    return PATTERNS_PATH.read_text(encoding="utf-8")


def read_cookbook() -> str:
    """Read condensed schema.org SPARQL cookbook."""
    if COOKBOOK_PATH.is_file():
        return COOKBOOK_PATH.read_text(encoding="utf-8")
    return "# Cookbook missing\nSee skills/DOOS_bundle/doos-sparql/SKILL.md\n"
