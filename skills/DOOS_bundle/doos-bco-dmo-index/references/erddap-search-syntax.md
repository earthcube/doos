# ERDDAP search syntax (BCO-DMO)

Endpoint: `https://erddap.bco-dmo.org/erddap/search/index.json?searchFor=<term>`

## Rules

| User intent | `searchFor` value |
|---|---|
| Multiple concepts (AND) | Separate with spaces: `oxygen depth` |
| Exact phrase | Double quotes: `"Gulf of Maine"` |
| Exclude a term | Prefix with minus: `-satellite` |
| Single keyword | Plain word: `depth` |

## Translation examples

| Natural language | Search string |
|---|---|
| "datasets with depth measurements" | `depth` |
| "dissolved oxygen and depth" | `dissolved oxygen depth` |
| "CTD pressure casts" | `CTD pressure` |
| "mesophotic reef depth ranges" | `"mesophotic reef" depth` |
| "bathymetry but not satellite" | `bathymetry -satellite` |

## Full catalog

When the user wants every dataset (~2,500), use `--catalog` instead of `--search`.
Do not pass an empty search string.

## Notes

- Search covers title, summary, institution, and variable names — not data values.
- Zero matches returns an empty inventory; the pipeline still completes successfully.
- Spatial/temporal extents are null in search results (present in full catalog mode).