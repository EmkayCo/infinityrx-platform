"""Load SAM.gov exclusions into shared.sam_exclusions.

Paginates the SAM.gov v3 entity-information exclusions API (requires
SAM_API_KEY in environment), writes results to a local JSONL cache,
upserts into shared.sam_exclusions, then runs cross-reference UPDATEs
to flip is_excluded on prescriber_dir.prescribers and
pharmacy_dir.pharmacies by NPI.

Pipeline: SamExclusionsIngester (DataSourceIngester child)
  download -> paginate SAM.gov v3 API -> local JSONL
  parse    -> stream JSONL records
  load     -> per-row ORM upsert on natural key -> cross-reference SQL

BUG-07a (2026-04-15): the pre-fix v1 URL
https://api.sam.gov/exclusions/v1/ returned 404. The ingester now
uses https://api.sam.gov/entity-information/v3/exclusions; this
script is the first end-to-end verification.

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_sam.py

Environment:
    DATABASE_URL_SYNC - set by switch_env.sh
    SAM_API_KEY       - required. Register at sam.gov/api to obtain.
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
logger = logging.getLogger("load_sam")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
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

    from shared.data_ingestion.sources.sam_exclusions import SamExclusionsIngester

    if not os.environ.get("SAM_API_KEY", "").strip():
        logger.error(
            "SAM_API_KEY not set. "
            "Register at sam.gov/api to obtain a key."
        )
        sys.exit(1)

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = SamExclusionsIngester(db_session=session)
        logger.info("Starting SAM.gov pipeline (v3 endpoint)...")
        result = await ingester.run(run_type="manual_trigger")

    print(f"\n{'=' * 60}")
    print("SAM.gov Load Result")
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
            text("SELECT count(*) FROM shared.sam_exclusions")
        ).scalar()
        print(f"  shared.sam_exclusions: {cnt:,} rows")

    if result.status != "completed":
        sys.exit(1)
    if result.records_errored > 0:
        logger.warning(
            "Non-zero error count: %d (per-row upsert failures, non-fatal)",
            result.records_errored,
        )


if __name__ == "__main__":
    asyncio.run(_run())
