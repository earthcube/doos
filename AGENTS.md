# AGENTS.md
## Purpose
Instructions for agentic coding agents working in DOOS (Deep Ocean Observation System) monorepo.
RDF/SHACL/schema.org for ocean data depth profiles, GeoParquet to RDF, validators, SPARQL queries.

Key dirs:
- `projects/`: Subprojects (AODC XML, BCO-DMO, OBIS, geoparquet2RDF, ERDDAP, ARGO, CCHDO)
- `scripts/shapeValidator/`: SHACL validation tools (validateToOxigraph.py, testIOBound.py, testThreadPool.py)
- `SHACL/`: Shapes files (.ttl)
- `SPARQL/`: Queries/scripts (.py, .rq)
- `docs/`: Notes (sources.md, vision.md)

## Environment Setup
```bash
uv venv .venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt  # geopandas pandas rdflib pyshacl morph_kgc pyld pyarrow
```

Git repo: yes. NEVER commit unless user asks explicitly.

## Build, Lint, Test Commands
**Build:** `uv build` (wheel/sdist)

**Lint/format/typecheck:**
```bash
ruff check . && ruff check --fix .  # Lint
black .                             # Format
mypy .                              # Typecheck
```

**Tests:** No pytest. Manual scripts only:
```bash
python scripts/shapeValidator/testIOBound.py <url> <shapefile>
python scripts/shapeValidator/testThreadPool.py <url> <shapefile>
```

**Add pytest (optional):**
```bash
uv add --dev pytest pytest-cov
pytest tests/ -v                    # All tests
pytest tests/test_foo.py::test_bar  # Single test
```

## Code Conventions
### Naming
- **snake_case**: functions, vars, files (`print_info`, `gdf`, `geopan.py`)
- **PascalCase**: Classes (rare)
- Descriptive names: `construct_graph`, `validate_with_shacl`

### Imports
**Order (mimic samples):**
1. stdlib: `import sys, os, json, argparse`
2. 3rd party: `import geopandas as gpd`, `from rdflib import Graph`
3. Local: `from defs.shaclValidator import validate_with_shacl`

```python
#!/usr/bin/env python3
import sys
import os
import argparse
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
from rdflib import Graph
import pyoxigraph

from defs.getGraphs import query_sparql_endpoint
```

### Formatting
4-space indent (PEP8), black-compatible: line-length ~88-100, Unix LF. Blank lines: 2 before/after functions, 1 between imports sections.

### Typing
Minimal type hints (none in samples). Optional: `from typing import Dict, List`

### Docstrings
Google/PEP257 style required for public functions/CLIs:
```python
def main():
    """
    Main function that takes a URL and shapefile from command line arguments
    and queries the SPARQL endpoint.
    """
    ...

def fetch_jsonld(url):
    """
    Fetch HTML from the given URL and extract embedded JSON-LD.
    
    Args:
        url: URL to the HTML page containing embedded JSON-LD
    
    Returns:
        dict: Parsed JSON-LD data
    
    Raises:
        Exception: If URL is invalid or no valid JSON-LD Dataset is found
    """
```

### Error Handling
Broad try/except. Print errors, sys.exit(1):
```python
try:
    gdf.to_csv(csv_output, index=False)
except Exception as e:
    print(f"Error writing CSV: {e}")
    sys.exit(1)

if len(sys.argv) != 3:
    print("Usage: ...")
    sys.exit(1)
```

Specific: `except HTTPError as e:`, `except URLError as e:`. No logging. Use `print(..., file=sys.stderr)`.

### CLI Scripts
All scripts use `argparse` + `if __name__ == "__main__":`:
```python
parser = argparse.ArgumentParser(description="...")
parser.add_argument("--url", required=True)
args = parser.parse_args()
```

Progress: `from tqdm import tqdm`. JSON: `json.load/dump(indent=2)`. File I/O: `with open(..., 'r', encoding='utf-8') as f:`. Prefer `Path(output_file).parent.mkdir(parents=True, exist_ok=True)`.

### RDF/SHACL Specific
rdflib: `Graph().parse(data=ntriples, format='nt')`. pyoxigraph: `store.load(shr, RdfFormat.TURTLE)`. pyshacl: `validate_with_shacl(r, sf)`. morph-kgc: `morph_kgc.materialize(config, data_dict)`. pyld: `jsonld.to_rdf(doc, {'format': 'application/n-quads'})`.

Output: N-Triples (.nt), N-Quads (.nq), Turtle (.ttl).

### Security Best Practices
No secrets in code. User-Agent: `'BCO-DMO-Depth-Analyzer/1.0'`. Timeouts: `urlopen(..., timeout=30)`. Validate inputs: `if all(col in gdf.columns ...)`. Temp dirs: `tempfile.mkdtemp(prefix='...')`.

## Subprojects Guidelines
**projects/geoparquet2RDF/geopan.py:** CLI (info/tocsv/rml). Mimic RML mappings.
**projects/BCO-DMO/bcodmo-depth/scripts/JsonLdDepthAnalyzer.py:** JSON-LD fetch/analyze depth.
**scripts/shapeValidator/validateToOxigraph.py:** SPARQL+SHACL batch validation.

Extend patterns, don't rewrite.

## Opencode Skills
- `fair-assessment`: Assess FAIR principles
- `oih-graph`: RDF graph queries

Use `skill` tool when relevant.

## Verification After Changes
1. Lint/format/typecheck
2. Run affected scripts: `python path/to/script.py --help`
3. Manual test RDF/SHACL output
4. `git diff` + `git status` before commit

Last updated: 2025-03-19