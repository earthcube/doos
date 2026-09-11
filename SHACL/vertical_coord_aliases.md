# Vertical coordinate aliases (`vertical_coord.ttl`)

Fork **3** (DOOS session, 2026-09-11): keep [`depth_one.ttl`](depth_one.ttl) strict (`DepBelowSurf` only, for post-map graphs such as `bodc_validated.nq`). Use [`vertical_coord.ttl`](vertical_coord.ttl) for **raw** provider JSON-LD / RDF where the vertical coordinate may be named as depth **or** in-water pressure.

This table is for domain-specialist review. Do **not** treat it as final ontology mapping.

## How the shape works

- Target: `schema:Dataset`
- Requires exactly one `schema:name` and one `schema:description` (same as `depth_one.ttl`)
- Requires ≥1 `schema:variableMeasured` whose `schema:name` is in the **depth** or **pressure** seed below (`sh:in`)
- Chemistry / meteorological “pressure” strings are listed under **Excludes** and are **not** in the shape

Inventory sources (dashboard branch): BODC harvest/validated/release, CCHDO schema JSON, ERDDAP GOOS summoned JSON-LD, AODN, ARGO sample, OBIS `output.nq`, BCO-DMO `output.nt`. Argos track ERDDAP (`erddap_anibos_example.json`) was skipped (no depth/pressure VMs).

## Depth aliases (in shape)

| Alias | Seen in inventory sources | NERC / NVS | Notes |
|---|---|---|---|
| `DepBelowSurf` | BODC validated/release, AODN | [P01 ADEPZZ01](https://vocab.nerc.ac.uk/collection/P01/current/ADEPZZ01/) (altLabel) | Canonical post-map name in `depth_one.ttl` |
| `DEPH` | (seed; BODC-style) | [P09 DEPH](https://vocab.nerc.ac.uk/collection/P09/current/DEPH/) (altLabel; “DEPTH BELOW SEA SURFACE”) | |
| `depth` | OBIS, ARGO, AODN, ERDDAP GOOS, BCO-DMO | No clean NERC concept cited | Local / CF-ish |
| `Depth` | ERDDAP GOOS, BCO-DMO | No clean NERC concept cited | |
| `DEPTH` | CCHDO, BCO-DMO | No clean NERC concept cited | |
| `z` | (seed) | No clean NERC concept cited | |
| `Z` | (seed) | No clean NERC concept cited | |
| `Sample_Depth` | BCO-DMO | Local-only unless specialist finds NVS | |
| `depth_m` | BCO-DMO | Local-only | |
| `depth_sample` | BCO-DMO | Local-only | |
| `depth_CTD` | BCO-DMO | Local-only | |
| `depth nominal` | BCO-DMO | Local-only | |
| `btm_depth` | CCHDO | Local-only | |
| `Btm_depth` | BCO-DMO | Local-only | |
| `Bottom_Depth` | BCO-DMO | Local-only | |
| `Water_depth` | BCO-DMO | Local-only | |
| `package_depth` | CCHDO | Local-only | |
| `observation_depth` | ERDDAP GOOS | Local-only | |
| `OBSERVATION_DEPTH` | ERDDAP GOOS | Local-only | |
| `observation depth` | ERDDAP GOOS | Local-only | |
| `OBSERVATION DEPTH` | ERDDAP GOOS | Local-only | |
| `Actual_Depth` | BCO-DMO | Local-only | |
| `Target_Depth` | BCO-DMO | Local-only | |
| `Top_Depth` | BCO-DMO | Local-only | |
| `Start_depth` | BODC release | Local-only | |
| `Max_Depth` / `max_depth` / `MaxDepth` | BCO-DMO | Local-only | |
| `Min_Depth` / `MinDepth` | BCO-DMO | Local-only | |
| `middepth_cm` | BCO-DMO | Local-only | |
| `Btl_Depth` | BCO-DMO | Local-only | |
| `Sediment_depth` | BCO-DMO | Local-only | |
| `depth_seafloor_m` | BCO-DMO | Local-only | |
| `Sea Floor Depth Below Sea Surface` | ERDDAP GOOS | Local-only | |
| `depth_of_chlorophyll_maximum` | AODN | Local-only | |
| `fm_depth` / `sm_depth` | ERDDAP GOOS | Local-only | |

## Pressure aliases — in-water / vertical (in shape)

| Alias | Seen in inventory sources | NERC / NVS | Notes |
|---|---|---|---|
| `PRES` | ERDDAP GOOS | [P09 PRES](https://vocab.nerc.ac.uk/collection/P09/current/PRES/) (altLabel); [OG1 PRES](https://vocab.nerc.ac.uk/collection/OG1/current/PRES/) | Distinct from `Pres` (PREXISPS) |
| `Pres_Z` | BODC release | [P01 PRESPR01](https://vocab.nerc.ac.uk/collection/P01/current/PRESPR01/) (altLabel; profiling pressure, zero at sea level) | |
| `sea_water_pressure` | ERDDAP GOOS | [P07 CFSN0330](https://vocab.nerc.ac.uk/collection/P07/current/CFSN0330/) (**prefLabel** match, not altLabel) | |
| `sea water pressure` / `SEA WATER PRESSURE` / `Sea Water Pressure` / `SEA PRESSURE` | ERDDAP GOOS | Prefer CFSN0330; label spellings vary | |
| `pressure` / `Pressure` / `press` | CCHDO, ERDDAP GOOS, BCO-DMO | No single clean NERC for bare string | |
| `CTDPRS` | CCHDO | Local-only unless specialist finds NVS | |
| `ctd_pressure_raw` | CCHDO / GOOS | Local-only | |
| `downcast_pressure` | CCHDO / GOOS | Local-only | |
| `rev_pressure` | CCHDO / GOOS | Local-only | |
| `odf_pressure` | ERDDAP GOOS | Local-only | |
| `Pres_MCat` / `Pres_Mcat_interp` | BODC release | Local-only | |
| `PRES_ADJUSTED` | ERDDAP GOOS | Local-only | |
| `pressure_qc` / `PRES_QC` | CCHDO / GOOS | Local-only (QC flag names) | |

### Related NERC (not in seed — specialist note)

| Concept | URL | Why noted |
|---|---|---|
| `Pres` (in-situ) | [P01 PREXISPS](https://vocab.nerc.ac.uk/collection/P01/current/PREXISPS/) (altLabel) | **≠** `PRES` (P09/OG1); list both if promoting |
| `Dep_Pressure` | [P01 DEPHPR01](https://vocab.nerc.ac.uk/collection/P01/current/DEPHPR01/) | Pressure→depth bridge; **not** in the seed |

## Excludes (not in shape — do not treat as vertical coord)

| String / concept | Why excluded | NERC support |
|---|---|---|
| `partial_pressure_of_co2` (+ labels) | Chemistry (pCO₂), not vertical | [P07 JG8UUOE9](https://vocab.nerc.ac.uk/collection/P07/current/JG8UUOE9/) |
| `Press_GasStream` | Gas stream | — |
| `sea level pressure` | Meteorological | — |
| `air_pressure_at_sea_level` | Atmospheric | [P07 CFSN0022](https://vocab.nerc.ac.uk/collection/P07/current/CFSN0022/) |
| `Surface Air Pressure` / `surface_air_pressure` / `Air_press` | Atmospheric | — |
| `AirPress_Z` | Atmospheric vertical | [P01 CAPBZZ01](https://vocab.nerc.ac.uk/collection/P01/current/CAPBZZ01/) |

## Pattern notes

- **CCHDO / GOOS profile** data usually expose **pressure** as the vertical coordinate.
- **BODC validated** is **depth-named** (`DepBelowSurf`).
- **BODC harvest** (small currentmeter slice) had **no** depth/pressure VM names — bad prior for aliases.
- **OBIS / ARGO** samples often use bare `depth`.

## Specialist checklist

- [ ] Confirm depth alias list (drop noisy / instrument-prose near-misses)
- [ ] Confirm pressure alias list vs excludes
- [ ] Confirm or replace “local-only” rows with better NVS concepts
- [ ] Decide whether `Pres` (PREXISPS) and/or `Dep_Pressure` (DEPHPR01) should join the seed
