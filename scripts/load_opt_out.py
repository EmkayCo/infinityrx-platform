"""Load CMS Medicare Opt-Out Affidavits into prescriber_dir.medicare_opt_out.

Paginates the CMS Socrata-style Data API (anonymous, ~55K rows / 22 MB)
and upserts via shared.data_ingestion.batching.flush_upsert_batch. After
upsert, cross-references prescriber_dir.prescribers.medicare_opt_out to
flip the status flag on matching NPIs.

Pipeline: CmsOptOutIngester (DataSourceIngester child)
  download -> paginate CMS API -> data/reference/cms-opt-out/opt_out.json
  parse    -> stream rows, normalise dates + booleans + NPI
  load     -> flush_upsert_batch (unique_key=[npi]) + cross-reference SQL

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_opt_out.py

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
_PRESCRIBER_DIR = _REPO_ROOT / "modules" / "prescriber-directory"
for _p in (str(_REPO_ROOT), str(_PRESCRIBER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_opt_out")


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

    from shared.data_ingestion.sources.cms_opt_out import CmsOptOutIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = CmsOptOutIngester(db_session=session)
        logger.info("Starting CMS Opt-Out pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    if result.status == "failed":
        logger.error("Ingest failed: %s", getattr(result, "error_message", "unknown"))
        sys.exit(2)

    print(f"\n{'=' * 60}")
    print("CMS Opt-Out Load Result")
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
        for table in ("medicare_opt_out",):
            cnt = conn.execute(
                text(f"SELECT count(*) FROM prescriber_dir.{table}")
            ).scalar()
            print(f"  prescriber_dir.{table}: {cnt:,} rows")

        opted_out = conn.execute(
            text(
                "SELECT count(*) FROM prescriber_dir.prescribers "
                "WHERE medicare_opt_out IS TRUE"
            )
        ).scalar()
        print(f"  prescribers flagged medicare_opt_out=TRUE: {opted_out:,}")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d - check logs", result.records_errored)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_run())
