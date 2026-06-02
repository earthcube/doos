#!/usr/bin/env python3
"""
Shared infrastructure for high-throughput SHACL validation result streaming to Parquet.

This module contains the reusable components used by both the pyshacl and pyrudof
parallel Parquet validators:
- StreamingParquetWriter (with sanitization and error diagnostics)
- The background writer loop
- The shutdown sentinel

The goal is to avoid duplicating complex multiprocessing + Parquet writing logic
across multiple validator frontends.
"""

import json
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from queue import Empty
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

# Sentinel used to signal shutdown to the background writer thread.
# Must survive pickling across Manager().Queue() when using ProcessPoolExecutor + "spawn".
_SHUTDOWN = "__SHUTDOWN_SENTINEL__"


class StreamingParquetWriter:
    """Background-threaded batch writer for SHACL validation results.

    Features:
    - Defensive row sanitization for type safety
    - Automatic diagnostic dump (bad_rows_*.json) on write failure
    - Fatal error tracking so the main thread can surface clear failures
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
        self._fatal_error: Exception | None = None

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def add_result(self, result: dict[str, Any]) -> None:
        with self.lock:
            if self._fatal_error:
                return

            if not isinstance(result, dict):
                self.report_fatal_error(
                    TypeError(
                        f"Writer received non-dict item (type={type(result).__name__}). "
                        "This should never happen."
                    )
                )
                return

            self.current_batch.append(result)
            if len(self.current_batch) >= self.batch_size:
                self._flush()

    def _sanitize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(row, dict):
            raise TypeError(
                f"_sanitize_row received non-dict (type={type(row).__name__}): {row!r}"
            )

        return {k: self._coerce_value(k, v) for k, v in row.items()}

    def _coerce_value(self, key: str, value: Any) -> Any:
        if value is None:
            return None
        if key == "validation_duration_ms":
            return float(value)
        if key == "has_results":
            return bool(value)
        return str(value)

    def _flush(self, schema: pa.Schema | None = None) -> None:
        if not self.current_batch:
            return

        sanitized = [self._sanitize_row(r) for r in self.current_batch]
        fname = (
            self.output_dir / f"{self.base_filename}_{self.file_counter:06d}.parquet"
        )

        try:
            if schema is not None:
                table = pa.Table.from_pylist(sanitized, schema=schema)
            else:
                table = pa.Table.from_pylist(sanitized)

            pq.write_table(table, fname, compression="zstd")

            n = len(self.current_batch)
            self.total_written += n
            self.file_counter += 1
            print(
                f"  Wrote batch {self.file_counter}: {n:,} rows → {fname.name} (total {self.total_written:,})"
            )
        except Exception as exc:
            self._fatal_error = exc
            self._dump_bad_rows(self.current_batch, exc)
            print(
                f"  ERROR flushing batch: {exc}. Bad rows written to bad_rows_*.json in output dir.",
                file=sys.stderr,
            )
        finally:
            self.current_batch.clear()

    def _dump_bad_rows(self, bad_rows: list[dict], error: Exception) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = self.output_dir / f"bad_rows_{ts}.json"

        debug_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "row_count": len(bad_rows),
            "rows": [
                {
                    "index_in_batch": i,
                    "keys": list(row.keys()),
                    "types": {k: type(v).__name__ for k, v in row.items()},
                    "reprs": {k: repr(v)[:500] for k, v in row.items()},
                    "raw": row,
                }
                for i, row in enumerate(bad_rows)
            ],
        }

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
        with self.lock:
            if self._fatal_error is None:
                self._fatal_error = exc

    def finalize(self, schema: pa.Schema | None = None) -> None:
        with self.lock:
            if self.current_batch:
                if schema is not None:
                    sanitized = [self._sanitize_row(r) for r in self.current_batch]
                    table = pa.Table.from_pylist(sanitized, schema=schema)
                    fname = (
                        self.output_dir
                        / f"{self.base_filename}_{self.file_counter:06d}.parquet"
                    )
                    pq.write_table(table, fname, compression="zstd")
                    self.total_written += len(self.current_batch)
                    self.file_counter += 1
                    self.current_batch.clear()

            if self._fatal_error:
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


def writer_loop(queue, writer: StreamingParquetWriter) -> None:
    """Background thread target that consumes from the result queue and feeds the writer."""
    while True:
        try:
            item = queue.get(timeout=1)
        except Empty:
            continue
        if item == _SHUTDOWN:
            break
        try:
            if isinstance(item, list):
                for row in item:
                    writer.add_result(row)
            elif isinstance(item, dict):
                writer.add_result(item)
            else:
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
            break
