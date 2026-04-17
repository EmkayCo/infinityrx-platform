"""Load CMS NADAC pricing data into drug_database.

Downloads the full NADAC dataset from the CMS Medicaid Socrata API,
upserts into drug_nadac_pricing (current row per NDC-11) and appends
to drug_nadac_pricing_history (price/date change rows only).

Pipeline: CMSNADACIngester (DataSourceIngester child)
  download → paginate Socrata API → local JSON
  parse    → normalize fields, Decimal(18,6) prices, date parsing
  load     → BatchedUpserter: per-batch commit, in-batch dedup, history

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_cms_nadac.py [--dry-run]

Environment:
    DATABASE_URL_SYNC — set by switch_env.sh
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"
for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_cms_nadac")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    # Async URL won't work for sync engine
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _dry_run() -> None:
    """Download and parse without DB — report record counts."""
    from unittest.mock import MagicMock

    from shared.data_ingestion.sources.cms_nadac import CMSNADACIngester

    ingester = CMSNADACIngester(db_session=MagicMock())
    cached = _REPO_ROOT / "data" / "reference" / "cms-nadac" / "nadac_full.json"

    logger.info("Downloading NADAC data (paginated)...")
    try:
        file_path = await ingester.download()
    except Exception as exc:
        logger.warning("Download failed (%s), trying cached file", exc)
        if cached.exists():
            file_path = cached
        else:
            logger.error("No cached file at %s — aborting", cached)
            sys.exit(1)

    count = sum(1 for _ in ingester.parse(file_path))
    print(f"\nDRY-RUN: {count:,} records parsed from {file_path.name}")


async def _run() -> None:
    """Full pipeline: download → parse → load via BatchedUpserter."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.cms_nadac import CMSNADACIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = CMSNADACIngester(db_session=session)
        logger.info("Starting CMS NADAC pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    # Report
    print(f"\n{'=' * 60}")
    print("CMS NADAC Load Result")
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

    # Verify row counts
    with engine.connect() as conn:
        for table in ("drug_nadac_pricing", "drug_nadac_pricing_history"):
            cnt = conn.execute(
                text(f"SELECT count(*) FROM drug_database.{table}")
            ).scalar()
            print(f"  {table}: {cnt:,} rows")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d — check logs", result.records_errored)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load CMS NADAC pricing data")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download + parse without DB load (prints record counts only)",
    )
    args = parser.parse_args()
    asyncio.run(_dry_run() if args.dry_run else _run())


if __name__ == "__main__":
    main()
