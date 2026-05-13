"""Load OIG LEIE (List of Excluded Individuals/Entities) into shared.

Downloads the monthly UPDATED.csv from oig.hhs.gov, upserts into
shared.oig_leie_exclusions via flush_upsert_batch, then runs cross-
reference UPDATEs to flip is_excluded on prescriber_dir.prescribers
and pharmacy_dir.pharmacies where NPI matches an active exclusion.

Pipeline: OigLeieIngester (DataSourceIngester child)
  download -> scrape OIG page -> fetch UPDATED.csv
  parse    -> stream CSV rows
  load     -> flush_upsert_batch on natural key -> cross-reference SQL

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_oig_leie.py

Environment:
    DATABASE_URL_SYNC - set by switch_env.sh
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (
    _REPO_ROOT,
    _REPO_ROOT / "modules" / "prescriber-directory",
    _REPO_ROOT / "modules" / "pharmacy-directory",
):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_oig_leie")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _run() -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.oig_leie import OigLeieIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = OigLeieIngester(db_session=session)
        logger.info("Starting OIG LEIE pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    print(f"\n{'=' * 60}")
    print("OIG LEIE Load Result")
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
            text("SELECT count(*) FROM shared.oig_leie_exclusions")
        ).scalar()
        print(f"  shared.oig_leie_exclusions: {cnt:,} rows")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d - check logs", result.records_errored)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_run())
