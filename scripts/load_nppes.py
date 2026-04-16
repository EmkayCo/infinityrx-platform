"""Load the latest CMS NPPES weekly dissemination file.

Downloads the weekly NPPES ZIP from CMS (or uses the bundled synthetic
sample), runs the core Prescriber upsert via nppes_upsert.run_nppes_import,
then populates satellite tables (prescriber_addresses, prescriber_taxonomies,
prescriber_identifiers, nppes_prescriber_details) via
nppes_ingestion.load_nppes_satellite_tables.

Pipeline: NppesIngester (DataSourceIngester child)
  download -> scrape CMS index -> fetch latest weekly ZIP
  parse    -> stream CSV rows
  load     -> nppes_upsert + nppes_ingestion satellite services

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_nppes.py [--dry-run] [--sample]

Options:
    --dry-run   Parse only - no DB writes. Reports yielded counts.
    --sample    Use the bundled synthetic sample CSV instead of downloading.

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
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
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


async def _run(sample: bool) -> None:
    """Full pipeline: download or sample -> parse -> load via NppesIngester."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.nppes import NppesIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = NppesIngester(db_session=session)

        if sample:
            logger.info("Using bundled sample CSV: %s", _SAMPLE_CSV)
            # Bypass download+checksum by invoking parse/load directly against the sample.
            records = ingester.parse(_SAMPLE_CSV)
            result = await ingester.load(records)
        else:
            logger.info("Starting NPPES pipeline (latest weekly download)...")
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
    parser = argparse.ArgumentParser(description="Load CMS NPPES weekly data")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only - no DB writes. Reports yielded counts.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use the bundled synthetic sample CSV instead of downloading.",
    )
    args = parser.parse_args()

    if args.dry_run:
        _dry_run()
    else:
        asyncio.run(_run(sample=args.sample))


if __name__ == "__main__":
    main()
