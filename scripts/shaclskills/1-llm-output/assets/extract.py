#!/usr/bin/env python
"""
Stage 1 — LLM Output (SHACL-for-AI-outputs flow).

Given a dataset **URL**, produce ``01_extracted.json`` with the fixed MINIMAL
field set (PLAN.md §4.1): ``url``, ``name``, ``description``, ``keywords[]``,
plus a ``source`` marker. Keys are ALWAYS present (null / [] when absent) so
downstream stages are deterministic.

Strategy = **reuse-embedded-else-extract** (PLAN.md §0a.3):
  1. Fetch the URL (UA, timeout, size cap).
  2. If the page carries embedded ``schema.org`` JSON-LD with ``@type`` Dataset
     (or DataCatalog), parse and reuse it — deterministic, no LLM.
  3. Otherwise fall back to LLM extraction from the page's visible text (via
     ``orchestration/llm.py``). With no ``LLM_API_KEY`` this step is
     skipped and the fields stay null/[] with ``source="none"``.

Usage (CLI):
    python extract.py URL [--out-dir DIR] [--no-llm]
    # file:// URLs work for local fixtures / testing.

Usage (import, e.g. from a LangGraph node):
    from extract import run_extract
    summary = run_extract("https://example.org/dataset", out_dir="runs/<id>")
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

_SHACLSKILLS_ROOT = Path(__file__).resolve().parents[2]
if str(_SHACLSKILLS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHACLSKILLS_ROOT))

_UA = "Mozilla/5.0 (compatible; DOOS-shaclskills/0.1; +https://earthcube.org)"
_MAX_BYTES = 5_000_000

_LLM_SYSTEM = (
    "You extract dataset metadata from a web page's text. Return ONLY a JSON "
    "object with EXACTLY these keys: url (string), name (string or null), "
    "description (string or null), keywords (array of strings). Use the given "
    "page URL for url. Use null / [] when a field is not clearly present — do "
    "NOT invent names, descriptions, or keywords unsupported by the text. No "
    "preamble, no code fences, JSON only."
)

_SCRIPT_LD_JSON = re.compile(
    r'<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


# --------------------------------------------------------------------------- #
# Fetch
# --------------------------------------------------------------------------- #
def fetch_url(url: str, timeout: int = 20) -> tuple[int | None, str, str]:
    """Return (status, content_type, body_text). Raises on network failure."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        status = getattr(resp, "status", None)
        content_type = resp.headers.get("Content-Type", "") or ""
        raw = resp.read(_MAX_BYTES)
    charset = "utf-8"
    m = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
    if m:
        charset = m.group(1)
    return status, content_type, raw.decode(charset, errors="replace")


# --------------------------------------------------------------------------- #
# Embedded JSON-LD path
# --------------------------------------------------------------------------- #
def _flatten_jsonld(obj) -> list[dict]:
    """Yield candidate nodes from a parsed JSON-LD value (dict/list/@graph)."""
    out: list[dict] = []
    if isinstance(obj, list):
        for item in obj:
            out.extend(_flatten_jsonld(item))
    elif isinstance(obj, dict):
        if "@graph" in obj and isinstance(obj["@graph"], list):
            out.extend(_flatten_jsonld(obj["@graph"]))
        out.append(obj)
    return out


def _type_names(node: dict) -> list[str]:
    t = node.get("@type") or node.get("type")
    if t is None:
        return []
    types = t if isinstance(t, list) else [t]
    return [str(x).rsplit("#", 1)[-1].rsplit("/", 1)[-1].split(":")[-1] for x in types]


def find_jsonld_blocks(html: str) -> list[dict]:
    blocks: list[dict] = []
    for raw in _SCRIPT_LD_JSON.findall(html):
        try:
            parsed = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        blocks.extend(_flatten_jsonld(parsed))
    return blocks


def pick_dataset(blocks: list[dict]) -> dict | None:
    """First Dataset node, else first DataCatalog, else None."""
    for want in ("Dataset", "DataCatalog"):
        for node in blocks:
            if want in _type_names(node):
                return node
    return None


def _as_text(v) -> str | None:
    """Coerce a JSON-LD value (str / list / langmap / object) to plain text."""
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, list):
        for item in v:
            t = _as_text(item)
            if t:
                return t
        return None
    if isinstance(v, dict):
        return _as_text(v.get("@value") or v.get("name"))
    return str(v)


def _as_keywords(v) -> list[str]:
    """schema:keywords may be a comma-separated string, a list, or DefinedTerms."""
    if v is None:
        return []
    items = v if isinstance(v, list) else [v]
    out: list[str] = []
    for item in items:
        text = _as_text(item)
        if not text:
            continue
        # A single string field may itself be comma-separated.
        parts = [p.strip() for p in text.split(",")] if "," in text else [text]
        out.extend(p for p in parts if p)
    seen, deduped = set(), []
    for k in out:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return deduped


def normalize_jsonld(node: dict, fallback_url: str) -> dict:
    url = _as_text(node.get("url"))
    if not url:
        at_id = node.get("@id")
        url = at_id if isinstance(at_id, str) and at_id.startswith("http") else None
    return {
        "url": url or fallback_url,
        "name": _as_text(node.get("name")),
        "description": _as_text(node.get("description")),
        "keywords": _as_keywords(node.get("keywords")),
        "source": "embedded-jsonld",
    }


# --------------------------------------------------------------------------- #
# LLM fallback path
# --------------------------------------------------------------------------- #
def html_to_text(html: str, max_chars: int = 6000) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def llm_extract(page_text: str, url: str) -> dict | None:
    """Return minimal fields via the LLM, or None if unavailable/failed."""
    try:
        from orchestration.llm import complete, llm_available

        if not llm_available():
            return None
        raw = complete(_LLM_SYSTEM, json.dumps({"url": url, "page_text": page_text}))
        raw = raw.strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return None
        data = json.loads(raw[start : end + 1])
        return {
            "url": (data.get("url") or url),
            "name": _as_text(data.get("name")),
            "description": _as_text(data.get("description")),
            "keywords": _as_keywords(data.get("keywords")),
            "source": "llm-extracted",
        }
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def extract_from_html(html: str, url: str, use_llm: bool = True) -> dict:
    """Embedded-else-LLM extraction from already-fetched HTML."""
    node = pick_dataset(find_jsonld_blocks(html))
    if node is not None:
        return normalize_jsonld(node, url)
    if use_llm:
        viallm = llm_extract(html_to_text(html), url)
        if viallm is not None:
            return viallm
    return {"url": url, "name": None, "description": None, "keywords": [],
            "source": "none"}


def run_extract(url: str, out_dir: str | Path = ".", use_llm: bool = True) -> dict:
    """Fetch ``url``, extract metadata, write ``01_extracted.json``; return it
    (augmented with ``extracted_json`` path, ``http_status`` and any ``error``).

    A network failure (timeout, reset, DNS, 4xx/5xx) degrades to an empty
    ``source="none"`` record with the error captured, rather than crashing the
    pipeline — downstream validation then reports the missing fields.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    status: int | None = None
    error: str | None = None
    try:
        status, _content_type, body = fetch_url(url)
        extracted = extract_from_html(body, url, use_llm=use_llm)
    except Exception as e:  # noqa: BLE001 — any fetch failure must not crash the run
        error = f"{type(e).__name__}: {e}"
        extracted = {"url": url, "name": None, "description": None,
                     "keywords": [], "source": "none"}

    extracted_json = out_dir / "01_extracted.json"
    extracted_json.write_text(json.dumps(extracted, indent=2), encoding="utf-8")

    result = dict(extracted)
    result["extracted_json"] = str(extracted_json)
    result["http_status"] = status
    if error:
        result["error"] = error
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 1: extract minimal dataset metadata from a URL "
        "(reuse embedded schema.org JSON-LD, else LLM-extract).",
    )
    parser.add_argument("url", help="Dataset URL (file:// works for fixtures)")
    parser.add_argument("--out-dir", default=".", help="Directory for 01_extracted.json")
    parser.add_argument(
        "--no-llm", action="store_true", help="Disable the LLM extraction fallback."
    )
    args = parser.parse_args(argv)

    r = run_extract(args.url, args.out_dir, use_llm=not args.no_llm)
    print(f"source={r['source']}  name={r['name']!r}  "
          f"keywords={len(r['keywords'])}  -> {r['extracted_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
