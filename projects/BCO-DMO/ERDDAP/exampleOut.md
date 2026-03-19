(doos) ➜  ERDDAP git:(main) ✗ python rmlTestERDDAP.py

Latest dissolved oxygen (North Atlantic) datasets in BCO-DMO
- GOHSNAP oxygen mooring time series on OSNAP (2020–2022)
  - ID: bcodmo_dataset_986667_v1
  - Region: Subpolar North Atlantic boundary currents, Labrador and western Irminger Seas
  - Coverage: June 2020–July 2022; high-frequency moored DO sensors
  - Access: ERDDAP info page by ID (see Sources)

- OSNAP bottle‑calibrated DO profiles (2020, 2022)
  - ID: bcodmo_dataset_933743_v1
  - Region: Labrador Sea and western Irminger Sea (US‑OSNAP cruises AR45; AR69‑03)
  - Coverage: 2020 and 2022 CTD profiles, Winkler‑calibrated DO
  - Access: ERDDAP info/tabledap links (see Sources)

- OSNAP discrete samples: DO, DIC, TA (2020, 2022)
  - ID: bcodmo_dataset_934025_v1
  - Region: Labrador and western Irminger Seas (US‑OSNAP)
  - Coverage: Discrete bottle DO with carbonate system variables

- OOI Irminger Sea Array bottle‑calibrated DO profiles (2014–2022)
  - ID: bcodmo_dataset_904721_v1
  - Region: Irminger Sea (∼60.46°N, 38.44°W)
  - Coverage: Annual CTD/Winkler‑calibrated DO through 2022

- OOI Irminger Sea discrete DO, DIC, TA (2018–2019)
  - ID: bcodmo_dataset_904722_v1
  - Region: Irminger Sea Array
  - Coverage: Discrete bottle DO with carbonate variables (2018–2019)

Latest chlorophyll(-a/pigments) datasets in BCO-DMO (North Atlantic focus)
- Chlorophyll‑a near BATS (Sargasso Sea) in 2021 and 2023
  - ID: bcodmo_dataset_929873_v1
  - Region: Near the Bermuda Atlantic Time‑series Study site
  - Coverage: AE2113 (July 2021), AE2303 (January 2023); Chl‑a by fluorometry

- Mid‑Atlantic Bight shelfbreak dilution‑experiment chlorophyll (2018–2019)
  - ID: bcodmo_dataset_961794_v1
  - Region: New England Shelfbreak
  - Coverage: April 2018; May/July 2019; process experiments with Chl

- Tropical North Atlantic HPLC pigments (May 2018)
  - ID: bcodmo_dataset_769601
  - Region: Western Tropical North Atlantic (Amazon plume context)
  - Coverage: Diagnostic pigments including Chl‑a

- North Atlantic transect HPLC pigments (2012)
  - ID: bcodmo_dataset_517634
  - Region: Azores to Iceland (NA‑VICE, 2012)
  - Coverage: Pigment suite including Chl‑a

- Atlantic basin (not open North Atlantic): STING extracted chlorophyll a and pheophytin (2023)
  - ID: bcodmo_dataset_928980_v1
  - Region: Gulf of Mexico (included to note 2023 Chl availability in BCO‑DMO)

How these datasets compare with recent papers
- Subpolar North Atlantic dissolved oxygen
  - What recent studies say: OSNAP‑related work and subpolar ventilation studies (2019–2024) show that DO variability at subsurface to intermediate depths closely tracks winter deep convection strength and boundary‑current/overturning variability. Enhanced convection ventilates the water column, raising DO; weaker convection and stronger stratification favor DO drawdown via remineralization. These processes superimpose interannual swings on a broader context of global ocean deoxygenation.
  - What the BCO‑DMO datasets enable: 
    - GOHSNAP 2020–2022 moorings provide high‑frequency boundary‑current DO to resolve seasonal/interannual ventilation signals noted in OSNAP papers for that period.
    - OSNAP 2020/2022 cruise profiles and discrete bottles give calibrated vertical DO structure and oxygen–carbon relationships to diagnose physical versus biogeochemical controls.
    - OOI Irminger 2014–2022 extends context back nearly a decade, spanning years of strong and weak convection, aligning with the interannual patterns highlighted in recent OSNAP syntheses.

- North Atlantic chlorophyll (BATS and shelfbreak)
  - What recent studies say: BATS literature documents strong seasonality with higher Chl during winter/early spring mixing and low Chl in stratified summers, with indications of longer‑term oligotrophication in the subtropical gyre as warming/stratification reduce nutrient supply. At the Mid‑Atlantic Bight shelfbreak, studies emphasize episodic upwelling and frontal dynamics as key drivers of biomass and production.
  - What the BCO‑DMO datasets enable:
    - BATS‑adjacent Chl‑a snapshots in summer 2021 and winter 2023 should reflect the classic seasonal contrast described in BATS publications; they provide recent benchmarks but are too short alone for trend detection.
    - Shelfbreak dilution‑experiment Chl (2018–2019) aligns with process‑study findings that link Chl variability to frontal/upwelling events rather than smooth seasonal cycles.

Notes and caveats
- ERDDAP preview requests for several IDs returned HTTP 400/401 during this session, so confirm variables/coverage on the “info” pages and via tabledap downloads.
- “Latest” here is based on dataset end years within the North Atlantic proper. Newer 2023 chlorophyll data exist in BCO‑DMO for other Atlantic sub‑regions (e.g., Gulf of Mexico).

Recommended follow‑ups
- Pull the OSNAP/GOHSNAP mooring DO time series (2020–2022) together with the OSNAP 2020/2022 cruise profiles to quantify seasonal/interannual DO anomalies and relate them to winter convection diagnostics from OSNAP publications.
- Compare BATS‑adjacent Chl‑a (2021/2023) against the BATS time‑series climatology and recent BATS publications to contextualize seasonal magnitude and variability.
- For broader coverage, complement in situ BCO‑DMO chlorophyll with satellite ocean‑color time series (e.g., MODIS/Aqua) over the same periods.

Key findings: 'The most recent subpolar North Atlantic dissolved oxygen datasets in BCO-DMO are the GOHSNAP OSNAP mooring time series (2020–2022; bcodmo_dataset_986667_v1) and OSNAP cruise-based bottle-calibrated DO profiles and discrete samples from 2020 and 2022 (bcodmo_dataset_933743_v1; bcodmo_dataset_934025_v1).', 'The OOI Irminger Sea Array dataset (2014–2022; bcodmo_dataset_904721_v1) provides longer context for subpolar DO variability, with supplementary discrete DO/DIC/TA from 2018–2019 (bcodmo_dataset_904722_v1).', 'The latest open-ocean North Atlantic chlorophyll in BCO-DMO is near BATS (summer 2021 and winter 2023; bcodmo_dataset_929873_v1); additional chlorophyll datasets are available for the Mid-Atlantic Bight shelfbreak (2018–2019; bcodmo_dataset_961794_v1) and for the tropical NA (2018; bcodmo_dataset_769601).', 'These DO datasets align with recent OSNAP literature emphasizing interannual oxygen variability driven by winter deep convection and boundary-current/overturning changes in the Labrador and Irminger Seas.', 'The BATS-adjacent chlorophyll snapshots are consistent with BATS publications reporting strong seasonality (higher winter/early spring, lower summer) and longer-term oligotrophication tendencies in the subtropical gyre.', 'Access to ERDDAP previews was limited by HTTP errors during this session; confirm variables and exact coverage via the dataset info/tabledap links before analysis.'

Sources: ['https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_986667_v1/index.json', 'https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_933743_v1/index.json', 'https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_934025_v1/index.json', 'https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_904721_v1/index.json', 'https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_904722_v1/index.json', 'https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_929873_v1/index.json', 'https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_961794_v1/index.json', 'https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_769601/index.json', 'https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_517634/index.json', 'https://erddap.bco-dmo.org/erddap/info/bcodmo_dataset_928980_v1/index.json', 'https://www.o-snap.org/publications/', 'https://www.bios.edu/research/projects/bats/']