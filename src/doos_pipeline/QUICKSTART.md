# Quickstart — `doos_pipeline`

From the **repository root**. This wrapper subprocesses the existing provider
CLIs; it does not reimplement them. Details: [`README.md`](README.md).

```bash
source .venv/bin/activate          # Python >= 3.13
export PYTHONPATH=src
python -m doos_pipeline --help
```

`uv run` works the same: `PYTHONPATH=src uv run python -m doos_pipeline …`

---

## 1. See what is registered

```bash
python -m doos_pipeline list
python -m doos_pipeline list --json
```

`run` = can be invoked. `all` = included in `run --all` without `--include-heavy`.
`output exists` = the published graph file is already on disk.

| name | `run --all` | Typical cost |
|---|---|---|
| `aodn` `cchdo` `cioos` | yes | local samples |
| `argo` `obis` `bodc` `bcodmo` | only with `--include-heavy` | parquet / sitemap / ERDDAP |
| `erddap` | never (`runnable: false`) | notes only |

---

## 2. Local sample pass (safe)

Uses in-tree AODN XML, CCHDO bottle NetCDF, CIOOS example. Does **not** start
ARGO, OBIS, BODC harvest, or BCO-DMO.

```bash
python -m doos_pipeline run --all --dry-run    # print commands only
python -m doos_pipeline run --all
```

Each run writes `runs/doos_pipeline/<utc>/run.json` and `report.jsonld`.

---

## 3. Full index

Two meanings. Pick one.

### A. Every runnable provider (catalog / network)

This is the one-shot “index everything the registry knows how to run”:

```bash
python -m doos_pipeline run --all --include-heavy --dry-run
python -m doos_pipeline run --all --include-heavy
```

That uses each provider’s **default_args / default_steps** in
[`config.yaml`](config.yaml). It is not always a complete harvest:

- **BODC** default step is `inventory` only (no sitemap harvest).
- **BCO-DMO** with no extra args uses the skill default `--search depth` (not `--catalog`).
- **AODN** default is the bundled sample XML, not a GeoNetwork crawl.
- **CCHDO** default is `extract` + `schema` on the sample bottle file.
- **ARGO** / **OBIS** run their configured parquet → RDF defaults (large).

### B. Explicit full harvest (recommended)

Run providers you care about, then report, SHACL, load. Oxigraph must already
be up for the load step (`docker run --rm --network host doos-oxigraph` or the
compose stack).

```bash
export PYTHONPATH=src

# --- generate graphs ---
python -m doos_pipeline run --provider argo
python -m doos_pipeline run --provider obis
python -m doos_pipeline run --provider aodn -- --uuid 528f280c-b151-45c4-9526-e0746510a617
python -m doos_pipeline run --provider cchdo
python -m doos_pipeline run --provider cioos
python -m doos_pipeline run --provider bcodmo -- --catalog
python -m doos_pipeline run --provider bodc --step inventory
python -m doos_pipeline run --provider bodc --step harvest
python -m doos_pipeline run --provider bodc --step validate
python -m doos_pipeline run --provider bodc --step export

# --- metrics on whatever was published ---
python -m doos_pipeline report --all

# --- OIH depth SHACL on published files (does not rewrite them) ---
python -m doos_pipeline validate --all --limit 0

# --- push into local Oxigraph; alias depth names to DepBelowSurf ---
python -m doos_pipeline load -- --wait --alias
```

PDF from the last report (separate tool, needs `reportlab`):

```bash
python scripts/reportPdf/report_to_pdf.py runs/doos_pipeline/<utc>/report.jsonld
```

---

## 4. Per-provider recipes

Args after `--` **replace** that step’s `default_args`. They are not appended.
`--all` rejects extra args (providers do not share a CLI).

### Smoke tests (small / limited)

```bash
python -m doos_pipeline run --provider aodn
python -m doos_pipeline run --provider cchdo --step extract
python -m doos_pipeline run --provider cchdo --step schema
python -m doos_pipeline run --provider cchdo --step croissant
python -m doos_pipeline run --provider bcodmo -- --search depth --limit 5
python -m doos_pipeline run --provider bodc --step harvest -- --limit 50
```

### Catalog-scale / live fetch

```bash
# ARGO GeoParquet → N-Triples (default parquet + template)
python -m doos_pipeline run --provider argo

# OBIS stages 2 and 3 (JSON-LD + output.nq); stage 1 needs the parquet first
python -m doos_pipeline run --provider obis

# AODN one GeoNetwork record, or a UUID list
python -m doos_pipeline run --provider aodn -- --uuid 528f280c-b151-45c4-9526-e0746510a617
python -m doos_pipeline run --provider aodn -- --uuid-file projects/AODN/uuids.txt --output-dir projects/AODN/output

# BCO-DMO full ERDDAP catalog (~2,500 datasets)
python -m doos_pipeline run --provider bcodmo -- --catalog

# BCO-DMO keyword search (ERDDAP AND / quotes / -exclude)
python -m doos_pipeline run --provider bcodmo -- --search "dissolved oxygen depth"
python -m doos_pipeline run --provider bcodmo -- --search "\"Gulf of Maine\" depth"

# BODC live sitemap harvest (slow; robots crawl-delay 5s)
python -m doos_pipeline run --provider bodc --step harvest
python -m doos_pipeline run --provider bodc --step harvest -- --use-release-ids --limit 100
```

### Dry-run and custom wrapper work dir

```bash
python -m doos_pipeline run --provider bcodmo --dry-run -- --catalog
python -m doos_pipeline run --provider argo --dry-run
python -m doos_pipeline run --provider aodn --work-dir /tmp/doos-aodn -- --input-xml ./AODN_GN4_depth_metadata.xml --output-dir ./output
```

`--work-dir` is the wrapper’s `run.json` / `report.jsonld` directory, not the
provider’s RDF output path.

---

## 5. Report, validate, load (no new harvest)

```bash
# Metrics over already-published files
python -m doos_pipeline report --provider bcodmo
python -m doos_pipeline report --provider argo --max-files 50
python -m doos_pipeline report --all --output /tmp/doos.report.jsonld

# SHACL (default shapes: SHACL/depth_one.ttl; default --limit 25)
python -m doos_pipeline validate --provider aodn
python -m doos_pipeline validate --provider bodc --limit 0 --output /tmp/bodc_shacl.json
python -m doos_pipeline validate --provider bcodmo --shapes SHACL/googleRequired.ttl --json

# Load (forwards to scripts/loadToOxigraph/loadToOxigraph.py)
python -m doos_pipeline load --dry-run -- --wait
python -m doos_pipeline load -- --wait
python -m doos_pipeline load -- --wait --alias
python -m doos_pipeline load -- --wait --export output/doos.nq
python -m doos_pipeline load -- --export-only --alias    # alias a store that is already loaded
```

Skip the JSON-LD report after a harvest:

```bash
python -m doos_pipeline run --provider aodn --no-report
```

---

## 6. End-to-end one provider (copy-paste)

BCO-DMO example: search, publish `projects/BCO-DMO/output/output.nt`, report,
optional SHACL, load with depth aliases.

```bash
source .venv/bin/activate
export PYTHONPATH=src
uv pip install -r skills/DOOS_bundle/doos-bco-dmo-index/assets/requirements.txt

python -m doos_pipeline run --provider bcodmo -- --search depth --limit 20
python -m doos_pipeline report --provider bcodmo
python -m doos_pipeline validate --provider bcodmo --limit 0
python -m doos_pipeline load -- --wait --alias
```

Same shape for AODN (local sample, no extra skill deps):

```bash
python -m doos_pipeline run --provider aodn
python -m doos_pipeline report --provider aodn
python -m doos_pipeline validate --provider aodn
python -m doos_pipeline load -- --wait --alias
```
