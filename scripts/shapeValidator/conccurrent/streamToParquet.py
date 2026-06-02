#!/usr/bin/env python3
"""
High-throughput concurrent downloader with streaming Parquet output.

Pattern: ProcessPoolExecutor workers + background thread writing to Parquet
in batches via a multiprocessing Queue. Avoids loading everything in memory.

This is useful when you have hundreds of thousands to millions of independent
I/O-bound tasks whose results you want to persist efficiently.

NOTE: For SHACL validation use case, adapt the result dict and writer schema
to store validation results (e.g. graph_uri, validation_nt, duration_ms, error)
instead of raw HTTP response bodies.

Usage examples:
    python streamToParquet.py --count 5000 --batch-size 2000
    python streamToParquet.py --urls urls.txt --workers 16
"""

import argparse
import atexit
import multiprocessing as mp
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from queue import Empty
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import requests

# --------------------------------------------------------------------------- #
# Streaming Parquet Writer (runs in a background thread)
# --------------------------------------------------------------------------- #


class StreamingParquetWriter:
    """
    Thread-safe batch writer that flushes Parquet files when batch_size is reached.
    Designed to be fed from a multiprocessing.Queue by a background thread.
    """

    def __init__(
        self,
        output_dir: Path = Path("parquet_output"),
        batch_size: int = 1000,
        base_filename: str = "responses",
    ):
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.base_filename = base_filename
        self.current_batch: list[dict[str, Any]] = []
        self.file_counter = 0
        self.total_written = 0
        self.lock = threading.Lock()

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def add_result(self, result: dict[str, Any]) -> None:
        with self.lock:
            self.current_batch.append(result)
            if len(self.current_batch) >= self.batch_size:
                self._write_batch()

    def _write_batch(self) -> None:
        if not self.current_batch:
            return

        filename = self.output_dir / f"{self.base_filename}_{self.file_counter:06d}.parquet"

        # Build columnar data — keep this schema stable for a given workload
        data = {
            "request_id": [r.get("request_id", 0) for r in self.current_batch],
            "url": [r.get("url", "") for r in self.current_batch],
            "status_code": [r.get("status_code", 0) for r in self.current_batch],
            "content": [r.get("content", b"") for r in self.current_batch],
            "content_length": [r.get("content_length", 0) for r in self.current_batch],
            "content_type": [r.get("content_type", "unknown") for r in self.current_batch],
            "download_time": [r.get("download_time", 0.0) for r in self.current_batch],
            "timestamp": [r.get("timestamp", "") for r in self.current_batch],
            "process_name": [r.get("process_name", "") for r in self.current_batch],
            "error": [r.get("error", "") for r in self.current_batch],
        }

        table = pa.table(data)
        pq.write_table(table, filename, compression="snappy")

        n = len(self.current_batch)
        self.total_written += n
        self.file_counter += 1
        print(f"Written batch {self.file_counter}: {n:,} records → {filename.name}")
        print(f"  Total so far: {self.total_written:,}")

        self.current_batch.clear()

    def finalize(self) -> None:
        with self.lock:
            if self.current_batch:
                self._write_batch()

        print(f"\nFinalized: {self.total_written:,} total records in {self.file_counter} files")
        self._write_dataset_metadata()

    def _write_dataset_metadata(self) -> None:
        files = sorted(self.output_dir.glob(f"{self.base_filename}_*.parquet"))
        meta = self.output_dir / "dataset_info.txt"
        with meta.open("w") as f:
            f.write(f"Dataset created: {datetime.now().isoformat()}\n")
            f.write(f"Total files: {len(files)}\n")
            f.write(f"Total records: {self.total_written:,}\n")
            f.write("Files:\n")
            for p in files:
                f.write(f"  {p.name}\n")


# Sentinel for clean shutdown
_SHUTDOWN_SENTINEL = object()


def main():
    parser = argparse.ArgumentParser(
        description="Concurrent downloader with streaming Parquet output"
    )
    parser.add_argument("--count", type=int, default=2000, help="Number of test URLs to process")
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows per Parquet file")
    parser.add_argument("--workers", type=int, default=0, help="Process pool size (0 = cpu_count)")
    parser.add_argument(
        "--output-dir",
        default="parquet_output",
        help="Directory for .parquet files and dataset_info.txt",
    )
    args = parser.parse_args()

    # Simple rotating test URLs (replace with real list / generator for production)
    base_urls = [
        "https://www.jython.org",
        "http://olympus.realpython.org/dice",
        "https://httpbin.org/json",
        "https://httpbin.org/html",
    ]
    sites = (base_urls * ((args.count // len(base_urls)) + 1))[: args.count]

    print(f"Preparing to download {len(sites):,} sites...")
    print(f"  batch_size={args.batch_size}, workers={args.workers or 'cpu_count'}")

    writer = StreamingParquetWriter(
        output_dir=Path(args.output_dir),
        batch_size=args.batch_size,
    )

    start = time.perf_counter()
    download_all_sites_streaming(sites, writer, max_workers=args.workers or None)
    duration = time.perf_counter() - start

    writer.finalize()
    print(f"\nCompleted {len(sites):,} sites in {duration:.2f}s")
    print(f"Average: {len(sites) / duration:.1f} sites/second")


def download_all_sites_streaming(
    sites, writer: StreamingParquetWriter, max_workers: int | None = None
):
    """
    Launch workers and stream results through a fast multiprocessing.Queue
    to a background writer thread.
    """
    ctx = mp.get_context("spawn")
    result_queue: mp.Queue = ctx.Queue(maxsize=5000)  # bounded for backpressure

    writer_thread = threading.Thread(
        target=_background_writer_loop,
        args=(result_queue, writer),
        daemon=True,
    )
    writer_thread.start()

    n_workers = max_workers or mp.cpu_count()
    print(f"Starting downloads with {n_workers} processes...")

    try:
        with ProcessPoolExecutor(
            max_workers=n_workers, mp_context=ctx, initializer=_init_worker
        ) as executor:
            future_to_id = {
                executor.submit(_download_one, url, i, result_queue): i
                for i, url in enumerate(sites)
            }

            completed = 0
            for future in as_completed(future_to_id):
                future.result()  # propagate worker exceptions
                completed += 1
                if completed % 1000 == 0:
                    print(
                        f"Progress: {completed:,}/{len(sites):,} ({completed / len(sites) * 100:.1f}%)"
                    )
    finally:
        result_queue.put(_SHUTDOWN_SENTINEL)
        writer_thread.join(timeout=60)


def _background_writer_loop(queue: mp.Queue, writer: StreamingParquetWriter) -> None:
    """Dedicated thread: pull from queue and hand to the Parquet writer."""
    while True:
        try:
            item = queue.get(timeout=2)
        except Empty:
            continue

        if item is _SHUTDOWN_SENTINEL:
            break
        try:
            writer.add_result(item)
        except Exception as exc:
            print(f"Writer error on item: {exc}", file=sys.stderr)


def _download_one(url: str, request_id: int, result_queue: mp.Queue) -> None:
    """Worker: download one URL and put a result dict on the queue."""
    start = time.perf_counter()
    try:
        with _session.get(url, timeout=30) as resp:
            elapsed = time.perf_counter() - start
            result = {
                "request_id": request_id,
                "url": url,
                "status_code": resp.status_code,
                "content": resp.content,
                "content_length": len(resp.content),
                "content_type": resp.headers.get("content-type", "unknown"),
                "download_time": elapsed,
                "timestamp": datetime.now().isoformat(),
                "process_name": mp.current_process().name,
                "error": "",
            }
            result_queue.put(result)

            if request_id % 2000 == 0:
                print(f"  Downloaded: {url} ({len(resp.content)} bytes)")
    except Exception as exc:
        elapsed = time.perf_counter() - start
        result_queue.put(
            {
                "request_id": request_id,
                "url": url,
                "status_code": 0,
                "content": b"",
                "content_length": 0,
                "content_type": "error",
                "download_time": elapsed,
                "timestamp": datetime.now().isoformat(),
                "process_name": mp.current_process().name,
                "error": str(exc),
            }
        )


# Per-process globals
_session: requests.Session


def _init_worker() -> None:
    """Called once per worker process."""
    global _session
    _session = requests.Session()
    _session.headers.update({"User-Agent": "StreamToParquet/2.0"})
    adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=32, max_retries=1)
    _session.mount("http://", adapter)
    _session.mount("https://", adapter)
    atexit.register(_session.close)


def read_streaming_results(output_dir: str = "parquet_output", base_filename: str = "responses"):
    """
    Convenience reader that concatenates all produced Parquet files.
    Returns a pandas DataFrame (or None on error).
    """

    try:
        files = sorted(Path(output_dir).glob(f"{base_filename}_*.parquet"))
        if not files:
            print("No Parquet files found")
            return None

        print(f"Reading {len(files)} Parquet files...")
        tables = [pq.read_table(f) for f in files]
        combined = pa.concat_tables(tables)
        df = combined.to_pandas()

        print(f"Loaded {len(df):,} rows")
        ok = (df["status_code"] == 200).sum()
        bytes_total = df["content_length"].sum()
        print(f"  Successful: {ok:,}  |  Total bytes: {bytes_total / (1024**2):.1f} MiB")
        return df
    except Exception as exc:
        print(f"Error reading results: {exc}", file=sys.stderr)
        return None


if __name__ == "__main__":
    main()

    # Optional post-run inspection (comment out in production)
    print("\n" + "=" * 60)
    print("Reading back written data (demo):")
    read_streaming_results()


def init_process():
    """Initialize each worker process"""
    global session
    session = requests.Session()

    # Optimize session for high-volume scraping
    session.headers.update({"User-Agent": "High-Volume-Scraper/1.0"})

    # Connection pooling for efficiency
    adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=50, max_retries=2)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    atexit.register(session.close)


def read_streaming_results():
    """
    Read back all the Parquet files as a single dataset
    """
    try:
        # Read all parquet files in the output directory
        parquet_files = list(Path("parquet_output").glob("responses_*.parquet"))

        if not parquet_files:
            print("No Parquet files found")
            return None

        print(f"Reading {len(parquet_files)} Parquet files...")

        # Read all files into a single table
        tables = []
        for file in sorted(parquet_files):
            table = pq.read_table(file)
            tables.append(table)

        # Combine all tables
        combined_table = pa.concat_tables(tables)
        df = combined_table.to_pandas()

        print(f"Loaded {len(df):,} total records")

        # Show summary stats
        successful = (df["status_code"] == 200).sum()
        total_bytes = df["content_length"].sum()

        print(f"Successful downloads: {successful:,}")
        print(f"Total bytes: {total_bytes:,} ({total_bytes/(1024**2):.1f} MB)")

        return df

    except Exception as e:
        print(f"Error reading results: {e}")
        return None


if __name__ == "__main__":
    main()

    # Read results back
    print("\n" + "=" * 60)
    print("Reading streaming results:")
    read_streaming_results()
