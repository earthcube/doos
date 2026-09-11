# DOOS pipeline wrapper

Python CLI that runs the **existing** per-provider graph generators as
sub-tasks. It does not reimplement ingest, mapping, or RDF serialization, and
it does not edit anything under `projects/`.

```
existing project CLI (unchanged)
        │  writes its usual .jsonld / .nt / .nq
        ▼
wrapper records run.json
wrapper writes report.jsonld   ← metrics for dashboards / PDF later
optional SHACL on those published files
optional loadToOxigraph
```

Copy-paste command recipes (full index, per-provider, load): [`QUICKSTART.md`](QUICKSTART.md).

## Setup

Same as the rest of the monorepo (`PYTHONPATH=src`, like the Discovery MCP):

```bash
export PYTHONPATH=src
python -m doos_pipeline --help
```

Or: `PYTHONPATH=src uv run python -m doos_pipeline --help`

## Commands

```bash
# Registry: status, default steps, whether published output exists
python -m doos_pipeline list
python -m doos_pipeline list --json

# Run a provider's existing CLI (wrapper default_args if you pass nothing)
python -m doos_pipeline run --provider aodn
python -m doos_pipeline run --provider aodn -- --uuid 528f280c-b151-45c4-9526-e0746510a617
python -m doos_pipeline run --provider bodc --step harvest -- --limit 50
python -m doos_pipeline run --provider cchdo --step croissant
python -m doos_pipeline run --provider argo --dry-run
python -m doos_pipeline run --provider bcodmo -- --search depth --limit 5

# Local sample defaults only (AODN XML, CCHDO sample NetCDF, CIOOS example)
python -m doos_pipeline run --all

# Also ARGO / OBIS / BODC / BCO-DMO (catalog-scale or network)
python -m doos_pipeline run --all --include-heavy

# SHACL against files the project already wrote (does not rewrite them)
python -m doos_pipeline validate --provider aodn
python -m doos_pipeline validate --provider bodc --limit 0 --output /tmp/bodc_shacl.json

# JSON-LD metrics report (also written automatically after `run`)
python -m doos_pipeline report --provider cchdo
python -m doos_pipeline report --provider argo --max-files 50 --output /tmp/argo.report.jsonld
python -m doos_pipeline report --all

# Existing Oxigraph loader
python -m doos_pipeline load -- --wait
python -m doos_pipeline load -- --wait --alias
```

Args after `--` **replace** that step's `default_args` in `config.yaml` and are
forwarded unchanged to the project script. With `--all`, extra args are
rejected (providers do not share a CLI).

`--all` without `--include-heavy` skips catalog-scale jobs so a full BODC
sitemap harvest or ARGO parquet dump is never started by accident.

Each `run` writes `runs/doos_pipeline/<utc>/run.json` and, unless `--no-report`
or `--dry-run`, a sibling **`report.jsonld`**. That JSON-LD file is the
stable metrics contract for a later dashboard or PDF renderer. This package
does not generate PDF or HTML.

`run.json` is wrapper metadata only; provider output paths are unchanged.

## JSON-LD report

`report.jsonld` is self-contained JSON-LD (`@context` inlined) so a web UI can
read it as ordinary JSON. Typical paths:

| JSON path | Meaning |
|---|---|
| `provider` | Registry name (`argo`, `aodn`, …) |
| `metrics.recordCount` | Distinct `schema:Dataset` subjects |
| `metrics.tripleCount` | RDF statements parsed |
| `metrics.fileCount` / `byteCount` | Published RDF files scanned |
| `metrics.namedGraphCount` | Named graphs (N-Quads) |
| `metrics.typeHistogram.bucket` | Counts by `rdf:type` (`curie`, `count`) |
| `metrics.predicateHistogram.bucket` | Top predicates (rest in `otherCount`) |
| `metrics.namespaceHistogram.bucket` | Counts by namespace |
| `metrics.depth.variableNameHistogram` | All `variableMeasured` names |
| `metrics.depth.depthNameHistogram` | Depth-like names only |
| `metrics.depth.depthWithRangeCount` | Depth properties that have min and max |
| `metrics.completeness.*Ratio` | Share of datasets with name / description / url / `DepBelowSurf` / any depth / depth range |
| `parseError` | Files that failed to parse |
| `wasGeneratedBy` | PROV activity (commands, times, exit code) |
| `distribution` | Published output paths |

`@type` is `PipelineReport` + `prov:Entity` + `schema:Dataset`. Vocabulary base:
`https://w3id.org/doos/pipeline#`. Completeness flags follow the OIH depth
profile (`DepBelowSurf`) and Google Dataset Search (name, description, url)
without running SHACL — use `validate` for the shape report.

`--all` also writes a `PipelineReportSet` roll-up with `hasPart` summaries.

PDF rendering is a separate program: [`scripts/reportPdf/`](../../scripts/reportPdf/).
Web dashboards should likewise consume this file and do not belong in `doos_pipeline`.

## Registry

`config.yaml` maps a provider name to:

| Field | Meaning |
|---|---|
| `cwd` / `script` | Existing entry point, same as running the script by hand |
| `default_args` | Used when the user does not pass `-- …` |
| `default_steps` | Subset of `steps` to run (e.g. BODC inventory, not harvest) |
| `outputs` | Published paths the wrapper may list / SHACL-check / load |
| `run_on_all` | Included in `run --all` |

ERDDAP is listed but `runnable: false` (notes only).

## What this package does not do

- Change how any project generates graphs
- Canonicalize `variableMeasured` names (use `load -- --alias` for that)
- Replace BODC's own SHACL export filter
- Deduplicate RDF export libraries inside the projects
- Render PDF, HTML, or a dashboard (consume `report.jsonld` elsewhere)
