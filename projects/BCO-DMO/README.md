# BCO-DMO

Indexer facade for **Biological and Chemical Oceanography Data Management
Office** datasets. This directory does not reimplement harvest or mapping: it
runs the skill pipeline and publishes N-Triples for Oxigraph load.

**Provider:** [BCO-DMO](https://www.bco-dmo.org/)  
**ERDDAP:** `https://erddap.bco-dmo.org/erddap`  
**Implementation:** [`skills/DOOS_bundle/doos-bco-dmo-index/`](../../skills/DOOS_bundle/doos-bco-dmo-index/)  
**Status:** Working

Access notes: [`docs/bco-dmo-access-review.md`](../../docs/bco-dmo-access-review.md).

## What this does

```
ERDDAP search or catalog → ISO 19115 depth/pressure scan → output.nt → publish
```

`run_pipeline.py` subprocesses
`skills/DOOS_bundle/doos-bco-dmo-index/assets/run_pipeline.py` (same flags),
writes run artifacts under `runs/<UTC-stamp>/`, and copies `output.nt` to
`output/output.nt`.

Native `variableMeasured` names (`depth`, `Sample_Depth`, …) are left as-is.
Canonical `DepBelowSurf` is added at load time (`python -m doos_pipeline load -- --wait --alias`).

## Commands

From the **DOOS repo root**, with the monorepo venv active. The skill pipeline
also needs `requests`, `tqdm`, `pyld`, and `pyoxigraph` (not all are in the
minimal root `requirements.txt`):

```bash
source .venv/bin/activate
uv pip install -r skills/DOOS_bundle/doos-bco-dmo-index/assets/requirements.txt

# Keyword search (skill default is "depth" if neither --search nor --catalog)
python projects/BCO-DMO/run_pipeline.py --search depth --limit 5

# Full catalog (network-heavy; ~2,500 datasets)
python projects/BCO-DMO/run_pipeline.py --catalog

# Via the repo wrapper (not included in run --all; needs --include-heavy)
PYTHONPATH=src python -m doos_pipeline run --provider bcodmo -- --search depth --limit 5
PYTHONPATH=src python -m doos_pipeline report --provider bcodmo
```

`--search` and `--catalog` are mutually exclusive. Extra `doos_pipeline` args
after `--` replace that step's `default_args` (empty here) and are forwarded
unchanged.

## Artifacts

```
projects/BCO-DMO/
├── run_pipeline.py          # this facade
├── runs/<UTC-stamp>/        # gitignored per-run inventory, summary, output.nt, run.json
└── output/output.nt         # published N-Triples (Oxigraph / doos_pipeline)
```

Start from `runs/<stamp>/run.json` for counts (`inventory_datasets`,
`depth_matches`, `triples`).

## Load

```bash
python scripts/loadToOxigraph/loadToOxigraph.py --wait --alias
```

Named graph: `urn:doos:bcodmo`. Path:
`projects/BCO-DMO/output/output.nt`.
