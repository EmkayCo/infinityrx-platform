"""Benchmark the NPPES satellite loader: VALUES vs COPY-staging paths.

Wave 11.5 added two COPY-backed primitives to ``shared.data_ingestion.batching``
(``flush_upsert_batch_copy`` + ``flush_scoped_replace_batch_copy``) and wired
``load_nppes_satellite_tables`` to dispatch through them by default. This
script measures the throughput delta against a real Postgres DB so we have
numbers to inform commit 11.5-3 (the full 30M-row satellite run).

Pipeline per path:

  1. TRUNCATE the 4 satellite tables + the temp staging table (if present).
  2. Stream the first ``--rows N`` NPI rows out of the input CSV into a
     tmp CSV (so the loader does its own CSV parsing exactly as prod would).
  3. Call ``load_nppes_satellite_tables(db, tmp_csv, use_copy=<mode>)``.
  4. Record wall time, total inserted-satellite rows, rows/sec.

Usage (from repo root, with the dev Postgres reachable):

    source infrastructure/scripts/switch_env.sh dev
    python scripts/bench_nppes_satellite.py \\
        --rows 2000 \\
        --source data/reference/nppes/monthly/npidata_pfile_20050523-20260412.csv

Operator-run only — not exercised by CI. LESSON-010/011 still apply: NPI is
public plaintext; no TenantScopedMixin on reference tables.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PRESCRIBER_DIR = _REPO_ROOT / "modules" / "prescriber-directory"
for _p in (str(_REPO_ROOT), str(_PRESCRIBER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.WARNING,  # keep progress logs off the bench output
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("bench_nppes_satellite")

_SATELLITE_TABLES = (
    "prescriber_dir.nppes_prescriber_details",
    "prescriber_dir.prescriber_addresses",
    "prescriber_dir.prescriber_taxonomies",
    "prescriber_dir.prescriber_identifiers",
)


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _trim_csv(source: Path, out: Path, rows: int) -> int:
    """Copy the first ``rows`` NPI rows from ``source`` to ``out``.

    Returns the number of rows written (excluding header). NPIs that fail the
    10-digit regex are still copied — the loader's own validation decides
    what to drop. This script just bounds input size.
    """
    written = 0
    with source.open("r", newline="", encoding="utf-8", errors="replace") as fh_in:
        reader = csv.reader(fh_in)
        header = next(reader)
        with out.open("w", newline="", encoding="utf-8") as fh_out:
            writer = csv.writer(fh_out)
            writer.writerow(header)
            for row in reader:
                writer.writerow(row)
                written += 1
                if written >= rows:
                    break
    return written


def _truncate_satellites(session_factory: object) -> None:
    """TRUNCATE all 4 satellite tables in a single statement."""
    from sqlalchemy import text

    with session_factory() as session:  # type: ignore[misc]
        session.execute(
            text("TRUNCATE " + ", ".join(_SATELLITE_TABLES) + " RESTART IDENTITY")
        )
        session.commit()


def _count_satellites(session_factory: object) -> dict[str, int]:
    """Return row count per satellite table."""
    from sqlalchemy import text

    counts: dict[str, int] = {}
    with session_factory() as session:  # type: ignore[misc]
        for tbl in _SATELLITE_TABLES:
            n = session.execute(text(f"SELECT count(*) FROM {tbl}")).scalar() or 0
            counts[tbl] = int(n)
    return counts


def _run_bench(
    label: str,
    csv_path: Path,
    session_factory: object,
    *,
    use_copy: bool,
) -> dict[str, object]:
    """Time a single loader invocation and report throughput."""
    from src.services.nppes_ingestion import load_nppes_satellite_tables

    print(f"\n{'─' * 60}")
    print(f"Path: {label}  (use_copy={use_copy})")
    print(f"{'─' * 60}")

    _truncate_satellites(session_factory)

    with session_factory() as session:  # type: ignore[misc]
        t0 = time.perf_counter()
        stats = load_nppes_satellite_tables(session, csv_path, use_copy=use_copy)
        session.commit()
        elapsed = time.perf_counter() - t0

    counts = _count_satellites(session_factory)
    total_inserted = sum(counts.values())
    rows_per_sec = total_inserted / elapsed if elapsed > 0 else 0.0

    print(f"  NPIs processed:    {stats.total_prescribers:,}")
    print(f"  Detail rows:       {counts[_SATELLITE_TABLES[0]]:,}")
    print(f"  Address rows:      {counts[_SATELLITE_TABLES[1]]:,}")
    print(f"  Taxonomy rows:     {counts[_SATELLITE_TABLES[2]]:,}")
    print(f"  Identifier rows:   {counts[_SATELLITE_TABLES[3]]:,}")
    print(f"  Satellite rows:    {total_inserted:,}")
    print(f"  Records errored:   {stats.records_errored:,}")
    print(f"  Wall time:         {elapsed:.2f}s")
    print(f"  Rows/sec (all 4):  {rows_per_sec:,.0f}")

    return {
        "label": label,
        "use_copy": use_copy,
        "npis": stats.total_prescribers,
        "total_rows": total_inserted,
        "elapsed_sec": elapsed,
        "rows_per_sec": rows_per_sec,
        "errored": stats.records_errored,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rows", type=int, default=2_000,
        help="Number of NPI rows to load per path (default 2000)",
    )
    parser.add_argument(
        "--source", type=Path, required=True,
        help="Path to a real NPPES CSV (weekly or monthly extract)",
    )
    args = parser.parse_args()

    if not args.source.exists():
        logger.error("Source CSV not found: %s", args.source)
        sys.exit(1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False, future=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    # Prepare trimmed input once and reuse across both paths so each
    # variant sees identical bytes.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_csv = Path(tmp) / "nppes_bench.csv"
        written = _trim_csv(args.source, tmp_csv, args.rows)
        print(f"\nTrimmed input: {written:,} rows → {tmp_csv}")

        values_result = _run_bench("VALUES", tmp_csv, factory, use_copy=False)
        copy_result = _run_bench("COPY",   tmp_csv, factory, use_copy=True)

    print(f"\n{'═' * 60}")
    print("SUMMARY")
    print(f"{'═' * 60}")
    print(f"  VALUES: {values_result['rows_per_sec']:>10,.0f} rows/sec")
    print(f"  COPY:   {copy_result['rows_per_sec']:>10,.0f} rows/sec")
    v = float(values_result["rows_per_sec"])  # type: ignore[arg-type]
    c = float(copy_result["rows_per_sec"])  # type: ignore[arg-type]
    if v > 0:
        print(f"  Speedup: {c / v:.2f}x")
    else:
        print("  Speedup: n/a (VALUES rows/sec was zero)")

    # Ensure the bench leaves satellites in a clean state; the monthly
    # baseline is core-only right now, so keeping the tables empty matches
    # the pre-11.5-3 state of dev.
    _truncate_satellites(factory)
    print("\n  Satellites TRUNCATEd — dev returns to pre-bench state.")


if __name__ == "__main__":
    main()
