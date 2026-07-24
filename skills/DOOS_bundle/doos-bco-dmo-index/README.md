# BCO-DMO Index

Discover and inventory BCO-DMO datasets via ERDDAP, scan ISO 19115 metadata for
depth/pressure variables, and emit merged N-Triples (`output.nt`) following the
[ODIS depth pattern](https://book.odis.org/thematics/depth/index.html).

Part of the DOOS harvest → transform-to-RDF → SHACL-validate pipeline.

For background on BCO-DMO programmatic access options, see
[`docs/bco-dmo-access-review.md`](../../docs/bco-dmo-access-review.md).

This directory contains:

| Path | Purpose |
|---|---|
| `assets/run_pipeline.py` | **Primary CLI** — full two-stage pipeline in one command |
| `assets/main.py` | Lower-level CLI — `erddap`, `iso`, and `datasets` subcommands |
| `assets/defs/` | Library modules (ERDDAP inventory, ISO parse, RDF export) |
| `assets/export_nt.py` | Rebuild `output.nt` from existing JSON-LD or `iso_summary.json` |
| `SKILL.md` | Agent harness instructions (optional — not required to run the tools) |
| `references/` | ERDDAP search syntax notes |
| `runs/` | Default pipeline output per run (gitignored, created on first run) |
| `output/output.nt` | Published N-Triples for Oxigraph load (`scripts/loadToOxigraph/`) |

No agent harness is required. Run the Python tools directly from the command line.

## Setup

From the **DOOS repo root**:

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r skills/DOOS_bundle/doos-bco-dmo-index/assets/requirements.txt
```

Dependencies: `requests`, `tqdm`, `pyld`, `pyoxigraph`.

## Quickstart

Run the full pipeline with one command. If `--work-dir` is omitted, output is
written to `skills/DOOS_bundle/doos-bco-dmo-index/runs/<UTC-timestamp>/`.

```bash
# Keyword search (default search term is "depth" if neither --search nor --catalog is set)
python skills/DOOS_bundle/doos-bco-dmo-index/assets/run_pipeline.py --search depth

# Custom output directory
python skills/DOOS_bundle/doos-bco-dmo-index/assets/run_pipeline.py \
  --search "dissolved oxygen depth" \
  --work-dir skills/DOOS_bundle/doos-bco-dmo-index/runs/oxygen-test

# Smoke test — first 5 datasets only
python skills/DOOS_bundle/doos-bco-dmo-index/assets/run_pipeline.py --search depth --limit 5

# Full ERDDAP catalog (~2,500 datasets) instead of keyword search
python skills/DOOS_bundle/doos-bco-dmo-index/assets/run_pipeline.py --catalog --work-dir /tmp/bco-full
```

### Pipeline output layout

Each run writes everything under a single work directory:

```
runs/<timestamp>/
├── inventory.json      # ERDDAP dataset records + access route URLs
├── iso_summary.json    # depth/pressure match metadata (no embedded JSON-LD)
├── output.nt           # merged N-Triples (primary RDF output)
├── report.txt          # plain-text findings (omit with --no-report)
└── run.json            # manifest — params, counts, match list (start here)
```

Optional with `--write-jsonld`: a `jsonld/` directory of per-dataset files.

`runs/` is gitignored. Point `--work-dir` elsewhere if you want run artifacts
tracked in version control.

### Publishing for Oxigraph

`scripts/loadToOxigraph/oxigraph_load.yaml` loads BCO-DMO from
`skills/DOOS_bundle/doos-bco-dmo-index/output/output.nt`. After a pipeline run:

```bash
cp skills/DOOS_bundle/doos-bco-dmo-index/runs/<timestamp>/output.nt skills/DOOS_bundle/doos-bco-dmo-index/output/output.nt
```

To rebuild `output.nt` from legacy per-dataset JSON-LD files (or from
`iso_summary.json` with `--iso-summary`):

```bash
python skills/DOOS_bundle/doos-bco-dmo-index/assets/export_nt.py \
  --jsonld-dir skills/DOOS_bundle/doos-bco-dmo-index/output \
  --output skills/DOOS_bundle/doos-bco-dmo-index/output/output.nt
```

Export uses pyld URDNA2015 normalization to N-Quads, loads into a pyoxigraph
default graph, then dumps N-Triples.

## `run_pipeline.py` reference

```bash
python skills/DOOS_bundle/doos-bco-dmo-index/assets/run_pipeline.py --help
```

| Flag | Description |
|---|---|
| `--search KEYWORD` | ERDDAP full-text search (Google-like syntax; see below) |
| `--catalog` | Enumerate the full ERDDAP catalog instead of searching |
| `--work-dir PATH` | Output root (default: `skills/DOOS_bundle/doos-bco-dmo-index/runs/<timestamp>`) |
| `--probe` | Verify each dataset's access routes via a 1-byte ranged GET |
| `--limit N` | Process only the first N datasets at both stages |
| `--no-report` | Skip writing `report.txt` |
| `--no-nt` | Skip writing merged `output.nt` |
| `--write-jsonld` | Also write per-dataset JSON-LD under `jsonld/` |

`--search` and `--catalog` are mutually exclusive.

### ERDDAP search syntax

| Intent | Example |
|---|---|
| Multiple terms (AND) | `--search "oxygen depth"` |
| Exact phrase | `--search "\"Gulf of Maine\" depth"` |
| Exclude a term | `--search "bathymetry -satellite"` |

More examples: [`references/erddap-search-syntax.md`](references/erddap-search-syntax.md).

## Lower-level CLI (`assets/main.py`)

Use when you need only one stage of the pipeline.

```bash
python skills/DOOS_bundle/doos-bco-dmo-index/assets/main.py --help
python skills/DOOS_bundle/doos-bco-dmo-index/assets/main.py erddap --help
python skills/DOOS_bundle/doos-bco-dmo-index/assets/main.py iso --help
```

### Stage 1 — ERDDAP inventory

```bash
python skills/DOOS_bundle/doos-bco-dmo-index/assets/main.py erddap \
  --search depth \
  --output /tmp/inventory.json

python skills/DOOS_bundle/doos-bco-dmo-index/assets/main.py erddap \
  --probe --limit 25 \
  --output /tmp/inventory.json
```

Required: `--output`. Optional: `--search`, `--probe`, `--limit`.

### Stage 2 — ISO depth scan → N-Triples

```bash
python skills/DOOS_bundle/doos-bco-dmo-index/assets/main.py iso \
  --input /tmp/inventory.json \
  --output /tmp/iso_summary.json \
  --output-nt /tmp/output.nt \
  --report-output /tmp/report.txt
```

Required: `--input`, `--output`. Writes `output.nt` beside the summary by default.
Optional: `--output-nt`, `--no-nt`, `--jsonld-dir`, `--report-output`, `--limit`,
`--print-jsonld`.

## What the pipeline does

### Stage 1: ERDDAP inventory

Contacts `https://erddap.bco-dmo.org/erddap` and either:

- Fetches the full `allDatasets` catalog (~2,500 datasets), or
- Runs full-text search via `/search/index.json?searchFor=<term>`

For each dataset it records metadata (title, summary, extents, `dataStructure`)
and builds an `access` map of URLs: ERDDAP info JSON, OPeNDAP metadata, CSV
endpoint, file browser, BCO-DMO landing page, and ISO 19115 XML.

With `--probe`, each route is checked with a ranged GET (first byte only — large
data files are not downloaded).

### Stage 2: ISO → merged N-Triples

For each dataset in the inventory:

1. Fetches ISO 19115-2 XML from `www.bco-dmo.org/dataset/<id>/iso`
2. Pairs column-name keywords (`theme`) with BCO-DMO standard parameters
   (`featureType`) to get LOD `propertyID` URIs
3. Filters variables whose names contain `depth`, `press`, `bathy`, or `dbar`
4. Enriches from ERDDAP `info` JSON metadata (`actual_range`, `units`,
   `long_name`) — **not** by downloading tabular data
5. Builds interim schema.org JSON-LD in memory
6. URDNA2015-normalizes each document to N-Quads via **pyld**, loads all into
   one **pyoxigraph** default graph, and dumps merged N-Triples to `output.nt`

Direct JSON-LD parsing can leave triples in named graphs (a dataset), which
cannot be dumped as N-Triples. pyld's `normalize()` does not support
`application/n-triples`; N-Quads is the supported intermediate format. Sequential
loads into a shared default graph also avoid blank-node ID collisions from
concatenating per-file triple strings.

Datasets with restricted ERDDAP data (HTTP 401/403 on the info endpoint) fall
back to ISO-only output: semantic identity without `minValue`/`maxValue`.

Example `variableMeasured` entry:

```json
{
  "@type": "PropertyValue",
  "name": "depth",
  "alternateName": "depth",
  "propertyID": "http://lod.bco-dmo.org/id/parameter/808",
  "description": "Depth",
  "minValue": 0.5,
  "maxValue": 200.0,
  "unitText": "m",
  "unitCode": [
    "https://qudt.org/vocab/unit/M",
    "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/"
  ]
}
```

## Agent use (optional)

`SKILL.md` in this directory instructs coding agents to interpret natural-language
requests, translate them to `run_pipeline.py` flags, execute the pipeline, and
summarize results from `run.json`. Invoke via `/doos-bco-dmo-index` in supported
harnesses. The CLI tools above work independently of any agent.

## DOOS pipeline role

1. **Seed/search** via `run_pipeline.py` (or `main.py erddap`) → inventory +
   per-dataset access routes.
2. **Transform** via the ISO stage: combine ISO 19115 (semantic identity) with
   ERDDAP info JSON (numeric ranges, units) → merged `output.nt`.
3. Downstream: SHACL validation against OIH depth shapes, export to SPARQL
   endpoints (not handled in this skill).

## Dependencies

| Component | Packages |
|---|---|
| `run_pipeline.py`, `main.py erddap` | `requests`, `tqdm` |
| `run_pipeline.py`, `main.py iso`, `export_nt.py` | `pyld`, `pyoxigraph` |
| `main.py iso` | `requests`; ISO parsing uses stdlib `xml.etree` |
| `main.py datasets` (deprecated Playwright site search) | `playwright` |

Prefer `run_pipeline.py` or `main.py erddap --search` over the Playwright
`datasets` subcommand.