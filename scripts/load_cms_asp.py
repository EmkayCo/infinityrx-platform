"""Script to download and load CMS ASP pricing data into drug_database.

Scrapes https://www.cms.gov/medicare/payment/all-fee-schedules/part-b-drugs/asp-drug-pricing-files
to find the latest quarterly XLSX, downloads it, and bulk-upserts into:
  drug_database.drug_asp_pricing          (current — upsert by hcpcs_code)
  drug_database.drug_asp_pricing_history  (append-only — quarterly changes)

Usage:
    python scripts/load_cms_asp.py [--dry-run]

Options:
    --dry-run   Scrapes and parses without a DB load (prints record counts).

Requires:
    - DATABASE_URL_SYNC env var pointing to a running PostgreSQL instance, OR
    - --dry-run flag for no-DB run.

Expected counts (2026 ASP dataset):
    Records parsed from XLSX: ~600-1,200 HCPCS codes per quarter
"""

from __future__ import annotations

import argparse
import asyncio
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
logger = logging.getLogger("load_cms_asp")


async def _dry_run_parse() -> None:
    """Scrape CMS page, download latest XLSX, parse and count records (no DB)."""
    from shared.data_ingestion.sources.cms_asp import CMSASPIngester, _parse_xlsx

    from unittest.mock import MagicMock
    mock_db = MagicMock()
    ingester = CMSASPIngester(db_session=mock_db)

    logger.info("Scraping CMS page and downloading latest ASP XLSX...")
    try:
        file_path = await ingester.download()
    except Exception as exc:
        logger.error("Download/scrape failed: %s", exc)
        # If network unavailable, try any cached file
        cached_dir = Path("data/reference/cms-asp")
        xlsx_files = list(cached_dir.glob("*.xlsx")) if cached_dir.exists() else []
        if xlsx_files:
            file_path = sorted(xlsx_files)[-1]
            logger.info("Using cached file: %s", file_path)
        else:
            logger.error("No cached ASP XLSX available. Aborting.")
            sys.exit(1)

    logger.info("Parsing ASP records from %s ...", file_path)
    records = list(_parse_xlsx(file_path))
    parsed_count = len(records)

    quarters = {r.get("effective_quarter") for r in records}
    hcpcs_codes = {r.get("hcpcs_code") for r in records}
    vaccine_rows = [r for r in records if r.get("vaccine_awp") == "Y"]

    print("\n" + "=" * 55)
    print("DRY-RUN PARSE COUNTS (CMS ASP):")
    print(f"  XLSX file:             {file_path.name}")
    print(f"  Total records parsed:  {parsed_count:,}")
    print(f"  Unique HCPCS codes:    {len(hcpcs_codes):,}")
    print(f"  Effective quarters:    {sorted(quarters)}")
    print(f"  Vaccine AWP=Y rows:    {len(vaccine_rows):,}")
    print("=" * 55)


async def _run_full_pipeline() -> None:
    """Run the full CMSASPIngester pipeline against a real database."""
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL_SYNC not set; use --dry-run for no-DB run")
        sys.exit(1)

    engine = create_engine(db_url, echo=False)
    with Session(engine) as session:
        from shared.data_ingestion.sources.cms_asp import CMSASPIngester

        ingester = CMSASPIngester(db_session=session)
        logger.info("Starting CMSASPIngester.run()...")
        result = await ingester.run(run_type="manual_trigger")

    print("\n" + "=" * 55)
    print("FULL PIPELINE RESULT (CMS ASP):")
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
        help="Scrape + parse without DB — prints record counts only",
    )
    args = parser.parse_args()

    if args.dry_run:
        asyncio.run(_dry_run_parse())
    else:
        asyncio.run(_run_full_pipeline())


if __name__ == "__main__":
    main()
