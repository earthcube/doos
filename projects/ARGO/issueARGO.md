# ARGO GeoParquet to RDF: Status

## Current Status

| Command | Status | Notes |
|---------|--------|-------|
| `info` | Working | Parquet metadata inspection |
| `tocsv` | Working | CSV export with WKT geometry |
| `tordf` | Working | JSON-LD template to N-Triples |
| `rml` | Wired up | Needs ARGO-specific mapping files |

**Data**: `argo_profiles_features_nmdis.parquet`, output in `data/output/`


## Next Steps

Really, just trying this is the next appraoch.  If you can generate metadata records and publish
them to a location we can harvest, the rest will be trim work. 

### Immediate
- [ ] Create ARGO-specific RML mapping (`RML/argo_profiles.ttl`)
- [ ] Add temporal mapping for profile date/time
- [ ] Expand variable coverage (temperature, salinity, conductivity)

### Integration  (DeCODER side)
- [ ] Verify ODIS-Arch alignment with depth profile
- [ ] Add provenance/attribution metadata
- [ ] Load into triplestore for query testing
