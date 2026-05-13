"""Load the latest CMS NPPES dissemination file (weekly / monthly / deactivation).

Pipeline: NppesIngester (DataSourceIngester child)
  download -> scrape CMS index for the chosen mode
  parse    -> stream rows (csv for weekly/monthly, xlsx for deactivation)
  load     -> nppes_upsert + satellite services (csv modes)
              OR batched UPDATE prescribers.status (deactivation mode)

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_nppes.py [--mode weekly|monthly|deactivation]
                                 [--dry-run] [--sample]

Options:
    --mode      which CMS file to fetch (default: weekly)
                  weekly       — dissemination file for NPIs changed in the last week
                  monthly      — full 7M-NPI registry snapshot (expect 15-60 min load)
                  deactivation — xlsx list of all historically-deactivated NPIs;
                                 only UPDATEs prescribers.status/deactivation_date
    --dry-run   Parse only - no DB writes. Reports yielded counts.
                (weekly mode only, using the bundled synthetic sample.)
    --sample    Use the bundled synthetic sample CSV instead of downloading.
                (weekly mode only.)

LESSON-010: NPI is public - plaintext throughout.
LESSON-011: Global reference tables - no TenantScopedMixin.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PRESCRIBER_DIR = _REPO_ROOT / "modules" / "prescriber-directory"
for _p in (str(_REPO_ROOT), str(_PRESCRIBER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SAMPLE_CSV = (
    _REPO_ROOT
    / "shared"
    / "data_ingestion"
    / "tests"
    / "sample_data"
    / "nppes"
    / "npidata_sample.csv"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_nppes")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _dry_run() -> None:
    """Parse the sample CSV without any DB writes."""
    _NPI_RE = re.compile(r"\A\d{10}\Z")

    row_count = 0
    individuals = 0
    organizations = 0
    with _SAMPLE_CSV.open(newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row_count += 1
            npi = (row.get("NPI") or "").strip()
            if not _NPI_RE.fullmatch(npi):
                continue
            entity = (row.get("Entity Type Code") or "").strip()
            if entity == "1":
                individuals += 1
            elif entity == "2":
                organizations += 1

    print(f"\n{'=' * 60}")
    print("NPPES DRY-RUN record counts")
    print(f"{'=' * 60}")
    print(f"  Sample CSV:           {_SAMPLE_CSV.name}")
    print(f"  Rows read:            {row_count:,}")
    print(f"  Individuals (type=1): {individuals:,}")
    print(f"  Organizations (type=2):  {organizations:,}")
    print(f"{'=' * 60}")


def _satellites_only(source_csv: Path, truncate: bool) -> None:
    """Run the satellite phase alone against an already-extracted CSV.

    Skips the CMS scrape, the zip download, and the core-prescribers
    upsert. Use this to recover from a ``completed_core`` run where the
    satellite phase was deferred or killed — the core baseline stays,
    and this call fills in the 4 satellite tables via
    ``load_nppes_satellite_tables``.

    When ``truncate`` is True, TRUNCATEs all 4 satellite tables first so
    the scoped-replace primitives start from a clean baseline rather
    than a partially-populated one. TRUNCATE is the right tool here
    because the satellite tables have no FK dependents and the 4-table
    set is self-contained.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from src.services.nppes_ingestion import load_nppes_satellite_tables

    if not source_csv.exists():
        logger.error("Source CSV not found: %s", source_csv)
        sys.exit(2)

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    if truncate:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "TRUNCATE "
                    "prescriber_dir.nppes_prescriber_details, "
                    "prescriber_dir.prescriber_addresses, "
                    "prescriber_dir.prescriber_taxonomies, "
                    "prescriber_dir.prescriber_identifiers "
                    "RESTART IDENTITY"
                )
            )
        logger.info("Satellites TRUNCATEd — starting from clean baseline")

    import time
    t0 = time.perf_counter()
    with Session(engine) as session:
        stats = load_nppes_satellite_tables(session, source_csv)
        session.commit()
    elapsed = time.perf_counter() - t0

    with engine.connect() as conn:
        counts = {
            "details":     conn.execute(text("SELECT count(*) FROM prescriber_dir.nppes_prescriber_details")).scalar(),
            "addresses":   conn.execute(text("SELECT count(*) FROM prescriber_dir.prescriber_addresses")).scalar(),
            "taxonomies":  conn.execute(text("SELECT count(*) FROM prescriber_dir.prescriber_taxonomies")).scalar(),
            "identifiers": conn.execute(text("SELECT count(*) FROM prescriber_dir.prescriber_identifiers")).scalar(),
        }
    total = sum(counts.values())

    print(f"\n{'=' * 60}")
    print("NPPES Satellite-Only Load Result")
    print(f"{'=' * 60}")
    print(f"  Individuals:        {stats.individuals:,}")
    print(f"  Organizations:      {stats.organizations:,}")
    print(f"  Total prescribers:  {stats.total_prescribers:,}")
    print(f"  Pharmacy supp:      {stats.pharmacy_supplements:,}")
    print(f"  Records skipped:    {stats.records_skipped:,}")
    print(f"  Records errored:    {stats.records_errored:,}")
    print(f"  Wall time:          {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print()
    print("  Satellite row counts:")
    for k, v in counts.items():
        print(f"    {k:<14} {v:>12,}")
    print(f"    {'total':<14} {total:>12,}")
    if elapsed > 0:
        print(f"  Rows/sec:           {total / elapsed:,.0f}")
    print(f"{'=' * 60}")

    if stats.records_errored > 0:
        logger.error("Non-zero error count: %d - check logs", stats.records_errored)
        sys.exit(1)


async def _run(mode: str, sample: bool) -> None:
    """Full pipeline: download or sample -> parse -> load via NppesIngester."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.nppes import NppesIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = NppesIngester(db_session=session, mode=mode)  # type: ignore[arg-type]

        if sample:
            if mode != "weekly":
                logger.error("--sample is only supported with --mode weekly")
                sys.exit(2)
            logger.info("Using bundled sample CSV: %s", _SAMPLE_CSV)
            records = ingester.parse(_SAMPLE_CSV)
            result = await ingester.load(records)
        else:
            logger.info("Starting NPPES pipeline (mode=%s)...", mode)
            result = await ingester.run(run_type="manual_trigger")

    print(f"\n{'=' * 60}")
    print("NPPES Load Result")
    print(f"{'=' * 60}")
    print(f"  Status:             {result.status}")
    print(f"  Records in source:  {result.records_in_source:,}")
    print(f"  Records processed:  {result.records_processed:,}")
    print(f"  Records inserted:   {result.records_inserted:,}")
    print(f"  Records updated:    {result.records_updated:,}")
    print(f"  Records skipped:    {result.records_skipped:,}")
    print(f"  Records errored:    {result.records_errored:,}")
    print(f"  Duration:           {result.duration_seconds:.1f}s")
    if result.error_message:
        print(f"  Error:              {result.error_message}")
    print(f"{'=' * 60}")

    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT count(*) FROM prescriber_dir.prescribers")
        ).scalar()
        print(f"  prescriber_dir.prescribers: {cnt:,} rows")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d - check logs", result.records_errored)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load CMS NPPES data")
    parser.add_argument(
        "--mode",
        choices=["weekly", "monthly", "deactivation"],
        default="weekly",
        help="Which CMS file to fetch. Default: weekly.",
    )
    parser.add_argument(
        "--phase",
        choices=["all", "satellites"],
        default="all",
        help="Which phase to run. 'all' (default) is the full pipeline. "
             "'satellites' skips download + core upsert and only loads the "
             "4 satellite tables against --source-csv — used to recover "
             "from a completed_core run.",
    )
    parser.add_argument(
        "--source-csv",
        type=Path,
        help="Path to an already-extracted NPPES CSV. Required with "
             "--phase satellites.",
    )
    parser.add_argument(
        "--truncate-satellites",
        action="store_true",
        help="With --phase satellites: TRUNCATE all 4 satellite tables "
             "before loading, so the run starts from a clean baseline. "
             "Without this flag the scoped-replace primitives will merge "
             "with any existing satellite rows on an NPI-by-NPI basis.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only - no DB writes. Reports yielded counts.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use the bundled synthetic sample CSV instead of downloading "
             "(weekly mode only).",
    )
    args = parser.parse_args()

    if args.dry_run:
        _dry_run()
    elif args.phase == "satellites":
        if args.source_csv is None:
            logger.error("--phase satellites requires --source-csv PATH")
            sys.exit(2)
        _satellites_only(args.source_csv, truncate=args.truncate_satellites)
    else:
        asyncio.run(_run(mode=args.mode, sample=args.sample))


if __name__ == "__main__":
    main()
