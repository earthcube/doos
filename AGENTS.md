# AGENTS.md
## Purpose
This file provides instructions for agentic coding agents (like opencode)
working in this DOOS (Deep Ocean Observation System) monorepo. DOOS focuses
on RDF/SHACL/schema.org for ocean data depth profiles, GeoParquet to RDF,
validators, SPARQL queries. Python 3.12+ primary language.

Key dirs:
- `projects/`: Subprojects (AODC XML, BCO-DMO depth analyzer, OBIS, geoparquet2RDF, ERDDAP, CCHDO schemas)
- `scripts/shapeValidator/`: SHACL validation tools (validateToOxigraph.py, etc.)
- `SHACL/`: Shapes files (.ttl)
- `SPARQL/`: Queries/scripts (.py, .rq)
- `docs/`: Notes (sources.md, vision.md)

No Cursor rules (.cursor/), Copilot instructions (.github/), pre-commit,
CI workflows (.github/workflows/), pytest/tox found.

## Environment Setup
```bash
# Create venv (README: 3.12, pyproject.toml: >=3.13)
uv venv .venv --python 3.12
source .venv/bin/activate  # Linux/Mac
# or use `uv run` prefix for commands

# Install deps (root requirements.txt)
uv pip install -r requirements.txt
# geopandas pandas rdflib pyshacl morph_kgc pyld pyarrow

# For subprojects e.g. geoparquet2RDF extra deps already in root
```

Git repo: yes. NEVER commit unless user asks explicitly.

## Build Commands
No formal build. pyproject.toml for packaging (`uv build` or `python -m build`).

```bash
uv build  # wheel/sdist
```

## Lint & Quality Commands
No configs (ruff.toml, .prettierrc, eslint). Use standards:

**Lint (ruff recommended):**
```bash
uv pip install ruff
ruff check .  # Lint all Python
ruff check scripts/ projects/  # Specific dirs
ruff check --fix .  # Auto-fix
```

**Format (black):**
```bash
uv pip install black
black .  # Format all Python (line-length=88 default)
```

**Typecheck (mypy):**
```bash
uv pip install mypy
mypy .  # Strict typing (add pyproject.toml [tool.mypy])
```

**Security (bandit):**
```bash
uv pip install bandit
bandit -r .
```

Run ALL after changes: `ruff check --fix . && black . && mypy .`

## Test Commands
**No pytest/unittests/tox found.** Only manual scripts:
- `scripts/shapeValidator/testIOBound.py`
- `scripts/shapeValidator/testThreadPool.py`

**Run all tests:** None. Run scripts manually:
```bash
python scripts/shapeValidator/testIOBound.py
python scripts/shapeValidator/testThreadPool.py
```

**Run single test:** Direct execution:
```bash
cd scripts/shapeValidator
python testIOBound.py
```

**Add tests?** Propose pytest:
```
uv add --dev pytest pytest-cov
pytest tests/ -v  # All
pytest tests/test_foo.py::test_bar -v  # Single test function
pytest tests/test_foo.py -k 'bar' -v  # Single by name
```

Verify changes: run scripts, check RDF output, SHACL validation.

## Code Conventions
Follow existing patterns. Mimic style.

### Naming
- **snake_case**: functions (`print_info`, `rml_mapping`), vars (`gdf`, `output_dir`), files (`geopan.py`)
- **PascalCase**: Classes (none seen)
- **UPPER_CASE**: Constants (none prominent)
- Descriptive: `construct_graph`, `validate_with_shacl`, `analyze_depth_columns`

### Imports
**Order (mimic samples):**
1. stdlib: `import sys, os, json, argparse`
2. 3rd party: `import geopandas as gpd`, `from rdflib import Graph`
3. Local: `from defs.shaclValidator import validate_with_shacl`

**Examples:**
```python
#!/usr/bin/env python3  # Shebang for CLIs
import sys
import os
import argparse
import json
from pathlib import Path  # Preferred over os.path

import geopandas as gpd
import pandas as pd
from rdflib import Graph
import pyoxigraph

from defs.getGraphs import query_sparql_endpoint  # Relative/local
```

- No `__future__` imports seen.
- Aliases: `gpd`, `pd` common.

### Formatting
- 4-space indent (PEP8).
- Black-compatible: line-length ~88-100.
- No trailing whitespace.
- Unix line endings (LF).

**Blank lines:**
- 2 before/after functions/classes.
- 1 between imports sections.

### Typing
**Minimal type hints.** None in samples. Optional:
```python
def fetch_jsonld(url: str) -> dict:
    ...
```

Recommend add: `from typing import Dict, List`

**pyproject.toml [tool.mypy]:** Add strict mode.

### Docstrings
**Google/PEP257 style.** Required for public functions/CLIs.

**Examples:**
```python
def main():
    \"\"\"
    Main function that takes a URL and shapefile from command line arguments
    and queries the SPARQL endpoint.
    \"\"\"
    ...

def fetch_jsonld(url):
    \"\"\"
    Fetch HTML from the given URL and extract embedded JSON-LD.

    Args:
        url: URL to the HTML page containing embedded JSON-LD
    
    Returns:
        dict: Parsed JSON-LD data
    
    Raises:
        Exception: If URL is invalid or no valid JSON-LD Dataset is found
    \"\"\"
```

### Error Handling
**Broad try/except.** Print errors, sys.exit(1).
```python
try:
    gdf.to_csv(csv_output, index=False)
except Exception as e:
    print(f"Error writing CSV: {e}")
    sys.exit(1)

# CLI arg validation
if len(sys.argv) != 3:
    print("Usage: ...")
    sys.exit(1)
```

**Specific:** `except HTTPError as e:`, `except URLError as e:`

No logging. Use `print(..., file=sys.stderr)` for progress/errors.

### CLI Scripts (argparse common)
All scripts use `argparse` + `if __name__ == "__main__":`
```python
parser = argparse.ArgumentParser(description="...")
parser.add_argument("--url", required=True)
args = parser.parse_args()
```

**Progress:** `from tqdm import tqdm`

**JSON handling:** `json.load/dump(indent=2)`

**File I/O:** `with open(..., 'r', encoding='utf-8') as f:`
Prefer `Path(output_file).parent.mkdir(parents=True, exist_ok=True)`

### RDF/SHACL Specific
- rdflib: `Graph().parse(data=ntriples, format='nt')`
- pyoxigraph: `store.load(shr, RdfFormat.TURTLE)`
- pyshacl: `validate_with_shacl(r, sf)`
- morph-kgc: `morph_kgc.materialize(config, data_dict)`
- pyld: `jsonld.to_rdf(doc, {'format': 'application/n-quads'})`

**Output:** N-Triples (.nt), N-Quads (.nq), Turtle (.ttl)

### Security Best Practices
- No secrets in code.
- User-Agent in requests: `'BCO-DMO-Depth-Analyzer/1.0'`
- Timeouts: `urlopen(..., timeout=30)`
- Validate inputs (e.g., col existence: `if all(col in gdf.columns ...)`)
- Temp dirs: `tempfile.mkdtemp(prefix='...')`

## Subprojects Guidelines
**projects/geoparquet2RDF/geopan.py:** CLI (info/tocsv/rml). Mimic RML mappings.
**projects/BCO-DMO/bcodmo-depth/scripts/JsonLdDepthAnalyzer.py:** JSON-LD fetch/analyze depth.
**scripts/shapeValidator/validateToOxigraph.py:** SPARQL+SHACL batch validation.

Extend patterns, don't rewrite.

## Opencode Skills
- `fair-assessment`: Assess FAIR principles (file:///.../SKILL.md)
- `oih-graph`: RDF graph queries (file:///.../SKILL.md)

Use `skill` tool when relevant.

## Verification After Changes
1. Lint/format/typecheck.
2. Run affected scripts: `python path/to/script.py --help`
3. Manual test RDF/SHACL output.
4. `git diff` + `git status` before commit.

Last updated: $(date)