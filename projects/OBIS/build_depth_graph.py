"""Build the OBIS auxiliary depth graph.

Derives per-dataset depth ranges from the OBIS parquet export and emits
schema.org JSON-LD that can be loaded into a triplestore. The OBIS API does
not expose per-dataset depth statistics, so this produces an "auxiliary" graph
to test with and share back with OBIS.

Pipeline (each stage consumes the previous stage's output):

  1. aggregate_depth  obis_<date>.parquet  -> idMinMaxDepth.parquet
  2. generate_jsonld  idMinMaxDepth.parquet + jsonld/obis_source/ -> jsonld/output_raw[_strict]/
  3. build_nquads     jsonld/output_raw/   -> output.nq

Loading output.nq (or the JSON-LD dirs) into a live SPARQL store is a separate,
alternative step handled by jsonldLoader.sh / jsonldDirLoader.sh.

Usage:
  uv run python build_depth_graph.py                 # run all stages
  uv run python build_depth_graph.py --stage 2 3     # run a subset
  uv run python build_depth_graph.py --source obis_20240625.parquet
"""

import argparse
import glob
import io
import json
import os

import duckdb
import pandas as pd
import pyoxigraph
from pyld import jsonld
from pyoxigraph import RdfFormat

# --- Default paths (override via CLI) --------------------------------------
SOURCE_PARQUET = "./obis_20240625.parquet"  # OBIS export from https://obis.org/data/access/
AGG_PARQUET = "./idMinMaxDepth.parquet"
SOURCE_GLOB = "./jsonld/obis_source/*.jsonld"
RAW_DIR = "./jsonld/output_raw"
STRICT_DIR = "./jsonld/output_raw_strict"
OUTPUT_NQ = "./output.nq"
GRAPH_BASE = "http://oceaninfohub.org/graph/obisdepth"

# Aggregation produces these exact (parenthesised, capitalised) column names so
# that stage 2 can reference them by name. Originally an artifact of ibis's
# auto-naming; pinned here with explicit SQL aliases.
COL_MIN = "Min(minimumDepthInMeters)"
COL_MAX = "Max(maximumDepthInMeters)"

# Single source of truth for the emitted depth JSON-LD shape. Follows the ODIS
# depth pattern: https://github.com/iodepo/odis-arch/blob/master/book/thematics/depth/index.md
DEPTH_TEMPLATE = """ {{
  "@context": {{
    "@vocab": "https://schema.org/"
  }},
  "@id": "{docid}",
  "@type": "Dataset",
  "variableMeasured": [
    {{
      "@type": "PropertyValue",
      "name": "depth",
      "description": "Parsed and validated by OBIS.",
      "minValue": "{minv}",
      "maxValue": "{maxv}",
      "propertyID": "https://obis.org/data/access/",
      "measurementTechnique": "Parsed and validated by OBIS.",
      "unitText": "m",
      "unitCode": [
        "https://qudt.org/vocab/unit/M", "https://vocab.nerc.ac.uk/collection/P06/current/ULAA/",
        "http://dbpedia.org/resource/Metre"
      ]
    }}
  ]
}}
"""


def aggregate_depth(src_parquet=SOURCE_PARQUET, out_parquet=AGG_PARQUET):
    """Stage 1: group the OBIS export by dataset_id -> min/max depth."""
    print(f"[1] aggregating depth from {src_parquet} -> {out_parquet}")
    # Relation API keeps the file path out of the SQL string; the explicit
    # aliases pin the column names that stage 2 reads (see COL_MIN/COL_MAX).
    agg = duckdb.read_parquet(src_parquet).aggregate(
        f'dataset_id, '
        f'MIN(minimumDepthInMeters) AS "{COL_MIN}", '
        f'MAX(maximumDepthInMeters) AS "{COL_MAX}"',
        "dataset_id",
    )
    agg.write_parquet(out_parquet)
    print(f"    wrote {out_parquet}")


def generate_jsonld(agg_parquet=AGG_PARQUET, source_glob=SOURCE_GLOB,
                    raw_dir=RAW_DIR, strict_dir=STRICT_DIR):
    """Stage 2: resolve each dataset's @id and emit depth JSON-LD.

    Writes one <dataset_id>_depth.jsonld to raw_dir for every dataset, and the
    subset with non-null min AND max to strict_dir.
    """
    print(f"[2] generating JSON-LD from {agg_parquet}")
    df = pd.read_parquet(agg_parquet)

    # Resolve all source urls in a single read, then match dataset_id substrings
    # in memory (the original code re-scanned every source file per dataset).
    urls = [r[0] for r in duckdb.sql(
        f"SELECT url FROM read_json('{source_glob}')"
    ).fetchall()]

    def resolve(dataset_id):
        # url is https://obis.org/dataset/<dataset_id>; substring match. Source
        # datasets are harvested multiple times, so the same url recurs — dedup
        # so a dataset resolves to its distinct url(s) (normally exactly one).
        return sorted({u for u in urls if dataset_id in u})

    df["docid"] = df["dataset_id"].apply(resolve)
    unresolved = int((df["docid"].str.len() == 0).sum())
    if unresolved:
        print(f"    {unresolved}/{len(df)} datasets had no matching source url "
              f"and are skipped (no resolvable @id)")
    dfe = df.explode("docid").dropna(subset=["docid"])

    def render(row):
        return DEPTH_TEMPLATE.format(
            docid=row["docid"], minv=row[COL_MIN], maxv=row[COL_MAX]
        )

    # Start clean so the outputs (and output.nq) reflect only this run — stale
    # files from earlier runs against different inputs would otherwise leak in.
    _reset_dir(raw_dir)
    _reset_dir(strict_dir)

    n_raw = _write_jsonld(dfe, raw_dir, render)
    # NOTE: if a dataset_id matches multiple urls, rows share one filename
    # (keyed by dataset_id) and the last write wins. Preserved from the original.
    dfe_strict = dfe.dropna(subset=[COL_MIN, COL_MAX], how="any")
    n_strict = _write_jsonld(dfe_strict, strict_dir, render)
    print(f"    wrote {n_raw} files to {raw_dir}, {n_strict} files to {strict_dir}")


def _reset_dir(out_dir):
    """Create out_dir and clear any *_depth.jsonld this stage previously wrote."""
    os.makedirs(out_dir, exist_ok=True)
    for stale in glob.glob(os.path.join(out_dir, "*_depth.jsonld")):
        os.remove(stale)


def _write_jsonld(frame, out_dir, render):
    count = 0
    for _, row in frame.iterrows():
        filename = os.path.join(out_dir, f"{row['dataset_id']}_depth.jsonld")
        with open(filename, "w") as f:
            f.write(render(row))
        count += 1
    return count


def build_nquads(jsonld_dir=STRICT_DIR, out_nq=OUTPUT_NQ, graph_base=GRAPH_BASE):
    """Stage 3: normalize JSON-LD into per-file named graphs and dump N-Quads."""
    print(f"[3] building N-Quads from {jsonld_dir} -> {out_nq}")
    sources = glob.glob(os.path.join(jsonld_dir, "*"))
    store = pyoxigraph.Store()  # in-memory; swap for Store(path=...) to persist
    for s in sources:
        with open(s) as json_file:
            doc = json.load(json_file)
        normalized = jsonld.normalize(
            doc, {"algorithm": "URDNA2015", "format": "application/n-quads"}
        )
        graph_name = pyoxigraph.NamedNode(f"{graph_base}/{os.path.basename(s)}")
        store.load(io.StringIO(normalized), RdfFormat.N_QUADS,
                   base_iri=None, to_graph=graph_name)
    with open(out_nq, "wb") as f:
        store.dump(f, RdfFormat.N_QUADS)
    print(f"    loaded {len(sources)} files; wrote {out_nq}")


def main():
    parser = argparse.ArgumentParser(description="Build the OBIS auxiliary depth graph.")
    parser.add_argument("--stage", type=int, nargs="+", choices=[1, 2, 3],
                        default=[1, 2, 3], help="which stages to run (default: all)")
    parser.add_argument("--source", default=SOURCE_PARQUET, help="OBIS export parquet (stage 1)")
    parser.add_argument("--agg", default=AGG_PARQUET, help="aggregated depth parquet")
    parser.add_argument("--source-glob", default=SOURCE_GLOB, help="OBIS source JSON-LD glob")
    parser.add_argument("--raw-dir", default=RAW_DIR)
    parser.add_argument("--strict-dir", default=STRICT_DIR)
    parser.add_argument("--out-nq", default=OUTPUT_NQ)
    parser.add_argument("--nq-from", default=STRICT_DIR,
                        help="JSON-LD dir to feed stage 3 (default: strict dir)")
    args = parser.parse_args()

    if 1 in args.stage:
        aggregate_depth(args.source, args.agg)
    if 2 in args.stage:
        generate_jsonld(args.agg, args.source_glob, args.raw_dir, args.strict_dir)
    if 3 in args.stage:
        build_nquads(args.nq_from, args.out_nq)


if __name__ == "__main__":
    main()
