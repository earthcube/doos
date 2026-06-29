---
name: bco-dmo-scan
description: >
  Search and index BCO-DMO datasets via ERDDAP, scan ISO 19115 for depth/pressure
  variables, and emit merged N-Triples (output.nt) from ODIS-pattern schema.org
  JSON-LD. Use when the user asks to scan, search, inventory, or index BCO-DMO
  datasets; find depth-related ocean data; build ERDDAP inventories; or transform
  BCO-DMO metadata to RDF. Trigger on: BCO-DMO, ERDDAP, depth profile, ISO 19115,
  variableMeasured, ODIS depth, ocean dataset search, output.nt. Use when the user
  runs /bco-dmo-scan.
metadata:
  short-description: "BCO-DMO ERDDAP search and depth RDF indexing"
  project: DOOS
  version: "1.0"
---

# BCO-DMO Scan

Search BCO-DMO's ERDDAP catalog, inventory dataset access routes, scan ISO 19115
metadata for depth/pressure variables, build schema.org JSON-LD in memory, and
write merged N-Triples (`output.nt`) following the
[ODIS depth pattern](https://book.odis.org/thematics/depth/index.html).

Scanner code lives in `assets/`. Human CLI documentation: `README.md` in this
directory.

## Workflow

1. **Intake** — extract parameters from the user's natural-language request.
2. **Confirm** — one-sentence plan before executing (unless the user said "just run it").
3. **Execute** — run `assets/run_pipeline.py` (do not chain manual steps).
4. **Report** — summarize counts, output paths, and 2–3 example matches.

## Natural-language intake

Read the user message and map to pipeline parameters:

| Parameter | Extract from NL | Default |
|---|---|---|
| `search` | Topic, variables, cruise, region | `depth` |
| `catalog` | "full catalog", "all datasets", "everything" | `false` |
| `probe` | "verify URLs", "check access", "probe routes" | `false` |
| `limit` | "quick test", "just a few", "first N" | none |
| `work_dir` | Explicit output path | timestamped `runs/<UTC-stamp>/` |

**Clarify only when needed** (max 1–2 questions):

- Vague scope ("ocean data") → ask for variables, region, or instrument.
- Full catalog vs keyword search unclear → ask (catalog is ~2,500 datasets).
- User gives no topic at all → default `search=depth` and mention the default.

**Do not over-interview.** "Scan BCO-DMO for depth datasets" → proceed with
`--search depth`.

### Translating prose → ERDDAP search strings

See `references/erddap-search-syntax.md`. Quick rules:

- Multiple concepts → space-separated (implicit AND): `dissolved oxygen depth`
- Exact phrase → quotes: `"Gulf of Maine"`
- Exclusion → `-term`: `bathymetry -satellite`
- Full catalog → `--catalog` (omit `--search`)

## Execute

From the **DOOS repo root**, with the monorepo venv active:

```bash
source .venv/bin/activate
python skills/bco-dmo-scan/assets/run_pipeline.py \
  --search "<translated-search-term>" \
  --work-dir skills/bco-dmo-scan/runs/<timestamp> \
  [--probe] [--limit N]
```

Full catalog:

```bash
python skills/bco-dmo-scan/assets/run_pipeline.py \
  --catalog \
  --work-dir skills/bco-dmo-scan/runs/<timestamp> \
  [--limit N]
```

Omit `--work-dir` to auto-create `skills/bco-dmo-scan/runs/<UTC-timestamp>/`.

### Output layout

```
runs/<timestamp>/
├── inventory.json      # ERDDAP dataset records + access URLs
├── iso_summary.json    # depth/pressure match metadata
├── output.nt           # merged N-Triples (primary RDF output)
├── report.txt          # plain-text findings (unless --no-report)
└── run.json            # manifest: params, counts, match list
```

Read `run.json` first when reporting results.

## Report back

Always include:

- Search term (or "full catalog") and whether `--probe` / `--limit` were used
- `inventory_datasets` vs `depth_matches` from `run.json` counts
- Absolute paths to `inventory.json`, `iso_summary.json`, `output.nt`, `run.json`
- Triple count from `run.json` `counts.triples`
- 2–3 example matches: `datasetID`, title, depth variable names, ranges if present

If `depth_matches` is 0, say so and suggest broadening the search term.

## Environment

Dependencies: `requests`, `tqdm`, `pyld`, `pyoxigraph` (`assets/requirements.txt`).

```bash
source .venv/bin/activate
python skills/bco-dmo-scan/assets/run_pipeline.py --help
```

Individual subcommands remain available via `assets/main.py erddap|iso` if needed,
but prefer `run_pipeline.py` for the full workflow.

## Failure handling

| Situation | Action |
|---|---|
| Empty search results | Report 0 datasets; suggest broader terms |
| HTTP / network error | Show stderr; do not retry more than twice |
| ERDDAP 401/403 on info | Note in report; ISO-only JSON-LD (no min/max) |
| Missing `.venv` | `uv venv .venv --python 3.13 && source .venv/bin/activate && uv pip install -r requirements.txt` |

## Do not

- Download full CSV/NetCDF data files (min/max come from ERDDAP `info` metadata).
- Use Playwright site search (`main.py datasets`) unless the user explicitly asks.
- Commit output files or `runs/` unless the user requests it.
- Invent dataset counts — read them from `run.json`.

## Lower-level CLI (optional)

```bash
python skills/bco-dmo-scan/assets/main.py erddap --search depth --output /tmp/inv.json
python skills/bco-dmo-scan/assets/main.py iso --input /tmp/inv.json --output /tmp/summary.json
python skills/bco-dmo-scan/assets/export_nt.py \
  --jsonld-dir skills/bco-dmo-scan/output \
  --output skills/bco-dmo-scan/output/output.nt
```

Use only when the user needs a single stage, not the full pipeline. `export_nt.py`
rebuilds `output.nt` from existing `.jsonld` files or an `iso_summary.json` with
embedded JSON-LD (pyld URDNA2015 → N-Quads → pyoxigraph default graph → N-Triples).