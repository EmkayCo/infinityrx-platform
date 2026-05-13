"""Load state Medicaid BIN/PCN/Group data into shared.government_program_bins.

Reads curated regional CSVs from ``data/reference/medicaid/`` and upserts
into shared.government_program_bins with confidence-based preference
(higher-confidence rows win cross-batch collisions). After load, reports
per-region counts, cross-region duplicates, and plan-type conflicts.

Pipeline: MedicaidBinIngester (DataSourceIngester child)
  download -> resolve data/reference/medicaid/ directory
  parse    -> no-op (StateMedicaidBinLoader owns the read/validate cycle)
  load     -> StateMedicaidBinLoader.load_all_regions()

Source CSVs (curated from state portals and PBM docs):
    data/reference/medicaid/{midwest,northeast,south_central,southeast,west}.csv

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_medicaid_bins.py

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
for _p in (_REPO_ROOT,):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_medicaid_bins")


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

    from shared.data_ingestion.sources.state_medicaid_bins import (
        VALID_STATES,
        MedicaidBinIngester,
    )

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = MedicaidBinIngester(db_session=session)
        logger.info("Starting Medicaid BINs pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    if result.status == "failed":
        logger.error("Ingest failed: %s", getattr(result, "error_message", "unknown"))
        sys.exit(2)

    print(f"\n{'=' * 60}")
    print("Medicaid BINs Load Result")
    print(f"{'=' * 60}")
    print(f"  Status:             {result.status}")
    print(f"  Records processed:  {result.records_processed:,}")
    print(f"  Records inserted:   {result.records_inserted:,}")
    print(f"  Records skipped:    {result.records_skipped:,}")
    print(f"  Records errored:    {result.records_errored:,}")
    print(f"  Duration:           {result.duration_seconds:.1f}s")
    if result.error_message:
        print(f"  Error:              {result.error_message}")
    print(f"{'=' * 60}")

    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT count(*) FROM shared.government_program_bins")
        ).scalar()
        states_covered = conn.execute(
            text("SELECT count(DISTINCT state) FROM shared.government_program_bins")
        ).scalar() or 0
        states_list = [
            row[0]
            for row in conn.execute(
                text("SELECT DISTINCT state FROM shared.government_program_bins ORDER BY state")
            ).fetchall()
        ]
        missing = sorted(VALID_STATES - set(states_list))
        print(f"  shared.government_program_bins: {cnt:,} rows")
        print(f"  States covered: {states_covered} / {len(VALID_STATES)}")
        print(f"  States missing: {', '.join(missing) if missing else '(none)'}")

    if result.records_errored > 0:
        logger.warning(
            "Non-zero error count: %d (row-level validation failures, non-fatal)",
            result.records_errored,
        )


if __name__ == "__main__":
    asyncio.run(_run())
