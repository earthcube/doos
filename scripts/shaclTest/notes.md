The endpoint is valid, and a small validator is in place using **pwin/SHACL_Engine** (Python package `shacl` 0.1.10).

## Program

`/home/workdir/artifacts/validate_datasets.py`

It:

1. Downloads [googleRecommended.ttl](https://raw.githubusercontent.com/OHDSI/gaiaCatalog/refs/heads/main/shapeGraphs/googleRecommended.ttl)
2. `CONSTRUCT`s the 1-hop neighborhood of 100 `https://schema.org/Dataset` resources from  
   `https://qlever.geocodes-aws-dev.earthcube.org/graphspace/deepoceans`
3. Compiles the shapes with `shacl.Shapes.from_turtle(...)` and validates with `validate_turtle(...)`
4. Writes data + reports under `shacl_results/`

```bash
python3 /home/workdir/artifacts/validate_datasets.py
python3 /home/workdir/artifacts/validate_datasets.py --limit 50
```

Needs the `shacl` package (`pip install shacl`).

## Run results

| | |
|---|---|
| Datasets pulled | **100** |
| Triples in data graph | 29,054 |
| Conforms | **false** |
| SHACL results | **869** (all `Violation`) |
| Results per dataset | 8–11 (avg 8.7); none passed cleanly |

By constraint:

| Count | Component |
| ---: | --- |
| 833 | `MinCountConstraintComponent` |
| 31 | `NodeKindConstraintComponent` |
| 5 | `MaxCountConstraintComponent` |

By property (this shape is strict: several properties demand **exactly one** value, and `citation` demands **exactly 11**):

| Count | Path |
| ---: | --- |
| 126 | `schema:keywords` |
| 100 | `schema:alternateName` |
| 100 | `schema:citation` |
| 100 | `schema:sameAs` |
| 95 | `schema:identifier` |
| 95 | `schema:license` |
| 95 | `schema:version` |
| 95 | `schema:url` |
| 56 | `schema:variableMeasured` |
| 6 | `schema:spatialCoverage` |
| 1 | `schema:temporalCoverage` |

`ex:CreatorShape` never fired: it targets `https://schema.org/DataSet` (capital S), not `Dataset`.

## Output files

- `shacl_results/datasets.nt` — constructed RDF
- `shacl_results/googleRecommended.ttl` — shapes used
- `shacl_results/validation_report.ttl` — official `sh:ValidationReport`
- `shacl_results/validation_results.csv` — one row per result
- `shacl_results/validation_summary.json` — counts and per-dataset tallies
- `shacl_results/construct.rq` — the SPARQL used
