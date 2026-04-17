"""Load CMS ASP (Average Sales Price) pricing data into drug_database.

Scrapes the CMS page to find the latest quarterly XLSX, downloads it,
and upserts into drug_database.drug_asp_pricing (current row per HCPCS
code) with drug_database.drug_asp_pricing_history (quarter change
rows only) via the shared BatchedUpserter.

Pipeline: CMSASPIngester (DataSourceIngester child)
  download -> scrape CMS page -> fetch latest quarterly XLSX (or ZIP)
  parse    -> normalize HCPCS, Decimal(18,6) payment limit, quarter
  load     -> ASPIngestionService -> BatchedUpserter per-batch commit

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_cms_asp.py [--dry-run]

Environment:
    DATABASE_URL_SYNC - set by switch_env.sh
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
logger = logging.getLogger("load_cms_asp")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _dry_run() -> None:
    """Scrape + download + parse without DB; report per-quarter counts."""
    from unittest.mock import MagicMock

    from shared.data_ingestion.sources.cms_asp import CMSASPIngester, _parse_xlsx

    ingester = CMSASPIngester(db_session=MagicMock())
    cached_dir = _REPO_ROOT / "data" / "reference" / "cms-asp"

    logger.info("Scraping CMS ASP page...")
    try:
        file_path = await ingester.download()
    except Exception as exc:
        logger.warning("Download/scrape failed (%s), falling back to cached XLSX", exc)
        xlsx_files = sorted(cached_dir.glob("*.xlsx")) if cached_dir.exists() else []
        if not xlsx_files:
            logger.error("No cached XLSX at %s - aborting", cached_dir)
            sys.exit(1)
        file_path = xlsx_files[-1]

    records = list(_parse_xlsx(file_path))
    quarters = {r.get("effective_quarter") for r in records}
    hcpcs_codes = {r.get("hcpcs_code") for r in records}

    print(f"\n{'=' * 60}")
    print("CMS ASP DRY-RUN record counts")
    print(f"{'=' * 60}")
    print(f"  XLSX file:             {file_path.name}")
    print(f"  Total records parsed:  {len(records):,}")
    print(f"  Unique HCPCS codes:    {len(hcpcs_codes):,}")
    print(f"  Effective quarters:    {sorted(quarters)}")
    print(f"{'=' * 60}")


async def _run() -> None:
    """Full pipeline: download -> parse -> load via BatchedUpserter."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.cms_asp import CMSASPIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = CMSASPIngester(db_session=session)
        logger.info("Starting CMS ASP pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    print(f"\n{'=' * 60}")
    print("CMS ASP Load Result")
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
        for table in ("drug_asp_pricing", "drug_asp_pricing_history"):
            cnt = conn.execute(
                text(f"SELECT count(*) FROM drug_database.{table}")
            ).scalar()
            print(f"  drug_database.{table}: {cnt:,} rows")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d - check logs", result.records_errored)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load CMS ASP pricing")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape + parse without DB load (prints record counts only)",
    )
    args = parser.parse_args()
    asyncio.run(_dry_run() if args.dry_run else _run())


if __name__ == "__main__":
    main()
