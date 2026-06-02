#!/usr/bin/env python3
"""
Parallel SHACL validator that streams structured results directly to Parquet.

Uses ProcessPoolExecutor + multiprocessing.Queue + background writer thread
(the proven high-throughput pattern from conccurrent/streamToParquet.py).

Each validated graph produces zero or more rows (one per SHACL ValidationResult).
This format is ideal for later analytics with polars, duckdb, or pandas.

Example:
    python validateToParquet.py http://localhost:7007 ../SHACL/ERDDAP.ttl \
        --output-dir shacl_results --workers 8 --batch-size 5000

Requirements:
    - The improved defs/ modules (endpoint handling)
    - pyshacl + rdflib (for structured extraction)
"""

import argparse
import json
import multiprocessing as mp
import sys
import threading
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue as _Queue
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from defs.getGraphs import query_sparql_endpoint
from defs.getShape import read_shapefile
from defs.getConstruct import (
    construct_graph,
    make_sparql_client,
    set_persistent_sparql_client,
)
from defs.shaclValidator import validate_with_shacl_results

# Sentinel used to signal shutdown to the background writer thread.
# Must be a value that survives pickling across Manager().Queue().
_SHUTDOWN = "__SHUTDOWN_SENTINEL__"

# Stable output schema for SHACL validation result rows.
# All fields are explicitly nullable to be tolerant of missing data from
# validation errors / partial graphs while still providing good type
# information for analytics tools (polars, duckdb, pandas, etc.).
_SHACL_RESULT_SCHEMA = pa.schema(
    [
        pa.field("graph_uri", pa.string(), nullable=True),
        pa.field("result_id", pa.string(), nullable=True),
        pa.field("severity", pa.string(), nullable=True),
        pa.field("focus_node", pa.string(), nullable=True),
        pa.field("result_path", pa.string(), nullable=True),
        pa.field("message", pa.string(), nullable=True),
        pa.field("source_shape", pa.string(), nullable=True),
        pa.field("source_constraint", pa.string(), nullable=True),
        pa.field("value", pa.string(), nullable=True),
        pa.field("validation_duration_ms", pa.float64(), nullable=True),
        pa.field("has_results", pa.bool_(), nullable=True),
    ]
)

# --------------------------------------------------------------------------- #
# Per-worker globals (populated by initializer in spawn'ed processes)
# --------------------------------------------------------------------------- #

_worker_shapes_text: str | None = None
_worker_endpoint: str | None = None


def _init_worker(endpoint: str, shapes_text: str) -> None:
    """Initializer run once per worker process.

    Creates one reusable SPARQLWrapper client with keep-alive enabled
    and stores the (read-only) shapes text. This avoids re-creating
    clients and re-sending large shapes strings on every task.
    """
    global _worker_shapes_text, _worker_endpoint

    _worker_shapes_text = shapes_text
    _worker_endpoint = endpoint

    # Create and register a single well-configured client for this process
    client = make_sparql_client(endpoint)
    set_persistent_sparql_client(client)


# --------------------------------------------------------------------------- #
# Streaming writer
# --------------------------------------------------------------------------- #


class StreamingParquetWriter:
    """Background-threaded batch writer for SHACL validation results.

    Includes defensive sanitization and robust error handling so that a
    single bad row (from a worker or an unusual SHACL result) does not
    corrupt the entire output run.
    """

    def __init__(
        self,
        output_dir: Path,
        batch_size: int = 5000,
        base_filename: str = "shacl_results",
    ):
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.base_filename = base_filename
        self.current_batch: list[dict[str, Any]] = []
        self.file_counter = 0
        self.total_written = 0
        self.lock = threading.Lock()
        self._fatal_error: Exception | None = None  # set if writer thread dies badly

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def add_result(self, result: dict[str, Any]) -> None:
        with self.lock:
            if self._fatal_error:
                return  # stop accepting work after a fatal writer error

            # Hard defense: never let non-dict garbage (e.g. sentinels that
            # survived pickling, stray objects, etc.) into current_batch.
            # This prevents AttributeError later in _sanitize_row.
            if not isinstance(result, dict):
                self.report_fatal_error(
                    TypeError(
                        f"Writer received non-dict item (type={type(result).__name__}). "
                        "This should never happen — likely a sentinel or internal error leaked through."
                    )
                )
                return

            self.current_batch.append(result)
            if len(self.current_batch) >= self.batch_size:
                self._flush()

    def _sanitize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Force values into types that match _SHACL_RESULT_SCHEMA.

        This is the primary defense against type mismatches coming from
        pyshacl/rdflib workers or edge-case graphs.
        """
        if not isinstance(row, dict):
            # This should be impossible due to guards in add_result + writer loop,
            # but we keep a loud guard here for future-proofing.
            raise TypeError(
                f"_sanitize_row received non-dict (type={type(row).__name__}): {row!r}"
            )

        return {
            "graph_uri": (
                str(row.get("graph_uri")) if row.get("graph_uri") is not None else None
            ),
            "result_id": (
                str(row.get("result_id")) if row.get("result_id") is not None else None
            ),
            "severity": (
                str(row.get("severity")) if row.get("severity") is not None else None
            ),
            "focus_node": (
                str(row.get("focus_node"))
                if row.get("focus_node") is not None
                else None
            ),
            "result_path": (
                str(row.get("result_path"))
                if row.get("result_path") is not None
                else None
            ),
            "message": (
                str(row.get("message")) if row.get("message") is not None else None
            ),
            "source_shape": (
                str(row.get("source_shape"))
                if row.get("source_shape") is not None
                else None
            ),
            "source_constraint": (
                str(row.get("source_constraint"))
                if row.get("source_constraint") is not None
                else None
            ),
            "value": str(row.get("value")) if row.get("value") is not None else None,
            "validation_duration_ms": (
                float(_v)
                if (_v := row.get("validation_duration_ms")) is not None
                else None
            ),
            "has_results": (
                bool(row.get("has_results"))
                if row.get("has_results") is not None
                else None
            ),
        }

    def _flush(self) -> None:
        """Flush current batch. Never lets a bad row kill the whole run."""
        if not self.current_batch:
            return

        sanitized = [self._sanitize_row(r) for r in self.current_batch]

        fname = (
            self.output_dir / f"{self.base_filename}_{self.file_counter:06d}.parquet"
        )

        try:
            table = pa.Table.from_pylist(sanitized, schema=_SHACL_RESULT_SCHEMA)
            pq.write_table(table, fname, compression="zstd")

            n = len(self.current_batch)
            self.total_written += n
            self.file_counter += 1
            print(
                f"  Wrote batch {self.file_counter}: {n:,} rows → {fname.name} (total {self.total_written:,})"
            )
        except Exception as exc:
            # Record the failure, dump the offending rows for later analysis,
            # then clear the batch so we don't lose previously written files.
            self._fatal_error = exc
            self._dump_bad_rows(self.current_batch, exc)
            print(
                f"  ERROR flushing batch: {exc}. Bad rows written to bad_rows_*.json in output dir.",
                file=sys.stderr,
            )
        finally:
            self.current_batch.clear()

    def _dump_bad_rows(self, bad_rows: list[dict], error: Exception) -> None:
        """Write the problematic rows + error context to a JSON file for debugging."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = self.output_dir / f"bad_rows_{ts}.json"

        debug_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "row_count": len(bad_rows),
            "rows": [],
        }

        for i, row in enumerate(bad_rows):
            debug_info["rows"].append(
                {
                    "index_in_batch": i,
                    "keys": list(row.keys()),
                    "types": {k: type(v).__name__ for k, v in row.items()},
                    "reprs": {k: repr(v)[:500] for k, v in row.items()},  # cap size
                    "raw": row,  # full data for manual inspection
                }
            )

        try:
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(debug_info, f, indent=2, default=str)
            print(
                f"  Wrote diagnostic data for bad rows to: {out_path.name}",
                file=sys.stderr,
            )
        except Exception as dump_exc:
            print(
                f"  Failed to write bad_rows diagnostic file: {dump_exc}",
                file=sys.stderr,
            )

    def report_fatal_error(self, exc: Exception) -> None:
        """Called by the writer thread when it encounters an unrecoverable problem."""
        with self.lock:
            if self._fatal_error is None:
                self._fatal_error = exc

    def finalize(self) -> None:
        with self.lock:
            if self.current_batch:
                self._flush()

            if self._fatal_error:
                # Re-raise so the caller gets a clear failure instead of silent data loss
                raise RuntimeError(
                    f"Writer thread encountered a fatal error during Parquet writing. "
                    f"See bad_rows_*.json in {self.output_dir} for details. "
                    f"Original error: {self._fatal_error}"
                ) from self._fatal_error

        print(
            f"\nFinalized: {self.total_written:,} total result rows in {self.file_counter} files"
        )
        self._write_metadata()

    def _write_metadata(self) -> None:
        meta = self.output_dir / "dataset_info.txt"
        files = sorted(self.output_dir.glob(f"{self.base_filename}_*.parquet"))
        with meta.open("w") as f:
            f.write("SHACL validation results\n")
            f.write(f"Created: {datetime.now().isoformat()}\n")
            f.write(f"Total files: {len(files)}\n")
            f.write(f"Total rows: {self.total_written:,}\n\n")
            for p in files:
                f.write(f"  {p.name}\n")


# --------------------------------------------------------------------------- #
# Worker (runs in separate process)
# --------------------------------------------------------------------------- #


def _validate_one(graph_uri: str, result_queue: _Queue[Any]) -> None:
    """Fetch graph, run SHACL, emit structured result rows (as a batch) to the queue.

    Uses per-worker globals populated by the initializer for endpoint and shapes.
    Batches all rows produced for this graph into a single queue put to reduce
    IPC and pickling overhead (especially valuable for graphs with many violations).
    """
    shapes_text = _worker_shapes_text or ""
    endpoint = _worker_endpoint or ""

    t0 = time.perf_counter()
    batch: list[dict[str, Any]] = []

    def _emit(row: dict[str, Any]) -> None:
        batch.append(row)

    try:
        rdf_text = construct_graph(graph_uri, endpoint=endpoint)
        duration_ms = (time.perf_counter() - t0) * 1000

        if not rdf_text or not rdf_text.strip():
            _emit(
                {
                    "graph_uri": graph_uri,
                    "result_id": None,
                    "severity": "Error",
                    "focus_node": None,
                    "result_path": None,
                    "message": "Empty graph or fetch failure",
                    "source_shape": None,
                    "source_constraint": None,
                    "value": None,
                    "validation_duration_ms": duration_ms,
                    "has_results": False,
                }
            )
            result_queue.put(batch)
            return

        is_valid, rows = validate_with_shacl_results(rdf_text, shapes_text)

        if not rows:
            _emit(
                {
                    "graph_uri": graph_uri,
                    "result_id": None,
                    "severity": "Info" if is_valid else "Warning",
                    "focus_node": graph_uri,
                    "result_path": None,
                    "message": (
                        "Graph passed validation"
                        if is_valid
                        else "Graph had no results but was not marked valid"
                    ),
                    "source_shape": None,
                    "source_constraint": None,
                    "value": None,
                    "validation_duration_ms": duration_ms,
                    "has_results": False,
                }
            )
            result_queue.put(batch)
            return

        for row in rows:
            row = dict(row)  # copy
            row["graph_uri"] = graph_uri
            row["validation_duration_ms"] = duration_ms
            row["has_results"] = True
            _emit(row)

        result_queue.put(batch)

    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        _emit(
            {
                "graph_uri": graph_uri,
                "result_id": None,
                "severity": "Error",
                "focus_node": graph_uri,
                "result_path": None,
                "message": f"Validation failure: {exc}",
                "source_shape": None,
                "source_constraint": None,
                "value": None,
                "validation_duration_ms": duration_ms,
                "has_results": False,
            }
        )
        result_queue.put(batch)


# --------------------------------------------------------------------------- #
# Main orchestration
# --------------------------------------------------------------------------- #


def main():
    parser = argparse.ArgumentParser(
        description="Parallel SHACL validator streaming structured results to Parquet files."
    )
    parser.add_argument("endpoint", help="SPARQL endpoint URL")
    parser.add_argument("shapefile", help="SHACL shapes (file path or URL)")
    parser.add_argument(
        "--output-dir", "-o", default="shacl_parquet_results", help="Output directory"
    )
    parser.add_argument(
        "--workers", type=int, default=0, help="Number of processes (0 = cpu_count)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=10000, help="Rows per Parquet file"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only first N graphs (for testing). Also pushes LIMIT into the initial SPARQL discovery query when > 0.",
    )
    args = parser.parse_args()

    print(f"Querying endpoint: {args.endpoint}")
    uris = query_sparql_endpoint(
        args.endpoint, endpoint=args.endpoint, limit=args.limit
    )
    if not uris:
        print("No graphs found.", file=sys.stderr)
        sys.exit(1)

    # Keep the Python slice as a safety net (the SPARQL LIMIT gives arbitrary
    # order without ORDER BY, and some callers may still want post-filtering).
    if args.limit > 0:
        uris = uris[: args.limit]

    print(f"Found {len(uris):,} graphs. Loading shapes...")
    shapes_text = read_shapefile(args.shapefile)

    writer = StreamingParquetWriter(
        output_dir=Path(args.output_dir),
        batch_size=args.batch_size,
    )

    n_workers = args.workers or mp.cpu_count()
    print(f"Starting validation with {n_workers} workers...")

    ctx = mp.get_context("spawn")

    # Use a Manager Queue. Raw ctx.Queue() objects cannot be safely passed
    # as arguments to ProcessPoolExecutor workers under the "spawn" start
    # method (they trigger "Queue objects should only be shared between
    # processes through inheritance"). Manager().Queue() returns a proxy
    # that is designed to be passed across the spawn boundary.
    with ctx.Manager() as manager:
        result_queue: _Queue[Any] = manager.Queue(maxsize=20000)

        # Start background writer thread
        writer_thread = threading.Thread(
            target=_writer_loop,
            args=(result_queue, writer),
            daemon=True,
        )
        writer_thread.start()

        start = time.perf_counter()

        try:
            with ProcessPoolExecutor(
                max_workers=n_workers,
                mp_context=ctx,
                initializer=_init_worker,
                initargs=(args.endpoint, shapes_text),
            ) as executor:
                futures = [
                    executor.submit(_validate_one, uri, result_queue) for uri in uris
                ]

                completed = 0
                for fut in as_completed(futures):
                    fut.result()  # re-raise worker errors
                    completed += 1
                    if completed % 500 == 0:
                        print(f"Progress: {completed:,}/{len(uris):,} graphs")

        finally:
            result_queue.put(_SHUTDOWN)
            writer_thread.join(timeout=120)

        duration = time.perf_counter() - start
        writer.finalize()

        print(f"\nDone in {duration:.1f}s ({len(uris)/duration:.1f} graphs/sec)")
        print(f"Results written to: {args.output_dir}/")


def _writer_loop(queue: _Queue[Any], writer: StreamingParquetWriter) -> None:
    while True:
        try:
            item = queue.get(timeout=1)
        except Empty:
            continue
        if item == _SHUTDOWN:
            break
        try:
            if isinstance(item, list):
                # Batched results from a worker (preferred for high-violation graphs)
                for row in item:
                    writer.add_result(row)
            elif isinstance(item, dict):
                writer.add_result(item)
            else:
                # Something weird arrived (should be impossible after sentinel check).
                # Report it so finalize() surfaces a clear error instead of a cryptic
                # AttributeError deep in sanitization.
                writer.report_fatal_error(
                    TypeError(
                        f"Writer loop received unexpected non-dict, non-list item from queue: "
                        f"type={type(item).__name__}, value={item!r}"
                    )
                )
                break
        except Exception as exc:
            print(f"Writer error: {exc}", file=sys.stderr)
            writer.report_fatal_error(exc)
            # Do not re-raise here; let the thread exit cleanly so the
            # main thread can observe the error via writer._fatal_error
            # in finalize().
            break


if __name__ == "__main__":
    main()
