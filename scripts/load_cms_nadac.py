"""Script to download and load CMS NADAC pricing data into drug_database.

Downloads the full NADAC dataset from the CMS Medicaid Socrata API
(~85,000 records as of 2026), paginating 10K records per page, and
bulk-upserts into:
  drug_database.drug_nadac_pricing          (current — upsert by ndc_11)
  drug_database.drug_nadac_pricing_history  (append-only — price changes)

Usage:
    python scripts/load_cms_nadac.py [--dry-run]

Options:
    --dry-run   Downloads and parses without a DB load (prints record counts).

Requires:
    - DATABASE_URL_SYNC env var pointing to a running PostgreSQL instance, OR
    - --dry-run flag for no-DB run.

Expected counts (2026 NADAC dataset):
    drug_nadac_pricing (current rows): ~85,000
    Records parsed from API:           ~85,000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure repo root and drug-database module root are on sys.path
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


async def _dry_run_parse() -> None:
    """Download from CMS Socrata API and report parsed record counts (no DB)."""
    from shared.data_ingestion.sources.cms_nadac import CMSNADACIngester, _parse_record

    from unittest.mock import MagicMock
    mock_db = MagicMock()
    ingester = CMSNADACIngester(db_session=mock_db)

    logger.info("Downloading NADAC data from CMS Medicaid API (paginated)...")
    try:
        file_path = await ingester.download()
    except Exception as exc:
        logger.error("Download failed: %s", exc)
        # If network unavailable, try any cached file
        cached = Path("data/reference/cms-nadac/nadac_full.json")
        if cached.exists():
            logger.info("Using cached file: %s", cached)
            file_path = cached
        else:
            logger.error("No cached file available. Aborting.")
            sys.exit(1)

    logger.info("Parsing NADAC records from %s ...", file_path)
    raw_data = json.loads(file_path.read_text())
    total_raw = len(raw_data)
    parsed_count = 0
    skipped_count = 0

    for raw in raw_data:
        result = _parse_record(raw)
        if result is not None:
            parsed_count += 1
        else:
            skipped_count += 1

    print("\n" + "=" * 55)
    print("DRY-RUN PARSE COUNTS (CMS NADAC):")
    print(f"  Total raw API records:    {total_raw:,}")
    print(f"  Successfully parsed:      {parsed_count:,}")
    print(f"  Skipped (invalid/missing):{skipped_count:,}")
    print("=" * 55)


async def _run_full_pipeline() -> None:
    """Run the full CMSNADACIngester pipeline against a real database."""
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL_SYNC not set; use --dry-run for no-DB run")
        sys.exit(1)

    engine = create_engine(db_url, echo=False)
    with Session(engine) as session:
        from shared.data_ingestion.sources.cms_nadac import CMSNADACIngester

        ingester = CMSNADACIngester(db_session=session)
        logger.info("Starting CMSNADACIngester.run()...")
        result = await ingester.run(run_type="manual_trigger")

    print("\n" + "=" * 55)
    print("FULL PIPELINE RESULT (CMS NADAC):")
    print(f"  status:             {result.status}")
    print(f"  records_in_source:  {result.records_in_source:,}")
    print(f"  records_processed:  {result.records_processed:,}")
    print(f"  records_inserted:   {result.records_inserted:,}")
    print(f"  records_updated:    {result.records_updated:,}")
    print(f"  records_errored:    {result.records_errored:,}")
    print(f"  duration_seconds:   {result.duration_seconds:.1f}s")
    if result.error_message:
        print(f"  error:              {result.error_message}")
    print("=" * 55)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download + parse without DB — prints record counts only",
    )
    args = parser.parse_args()

    if args.dry_run:
        asyncio.run(_dry_run_parse())
    else:
        asyncio.run(_run_full_pipeline())


if __name__ == "__main__":
    main()
