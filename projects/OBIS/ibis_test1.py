import ibis
import duckdb

ibis.set_backend("duckdb")
data = "./obis_20240625.parquet"
t = ibis.read_parquet(data)
expr = (t.group_by("dataset_id").aggregate({t.minimumDepthInMeters.min(), t.maximumDepthInMeters.max()}))
expr.to_parquet("idMinMaxDepth.parquet")
