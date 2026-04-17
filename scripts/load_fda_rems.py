"""Load FDA REMS (Risk Evaluation and Mitigation Strategies) into drug_database.

Fetches REMS-mentioning drug labels from openFDA's label endpoint
(falls back to data/reference/fda-rems/fda_rems.json on network issues),
upserts into drug_database.drug_rems, and bulk-replaces drug_rems_ndc
for each parent.

Silent-bug caveat: openFDA labels in the current dataset don't populate
a top-level rems[] key, so rems_program_name falls back to
application_number and rems_type / etasu_requirements stay NULL.
See the module docstring in shared/data_ingestion/sources/fda_rems.py
and tasks/TODO-WAVE-REMS-EXTRACT.md for the follow-up.

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_fda_rems.py

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
_DRUG_DB_ROOT = _REPO_ROOT / "modules" / "drug-database"
for _p in (str(_REPO_ROOT), str(_DRUG_DB_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_fda_rems")


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

    from shared.data_ingestion.sources.fda_rems import FdaRemsIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = FdaRemsIngester(db_session=session)
        logger.info("Starting FDA REMS pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    print(f"\n{'=' * 60}")
    print("FDA REMS Load Result")
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
        for table in ("drug_rems", "drug_rems_ndc"):
            cnt = conn.execute(
                text(f"SELECT count(*) FROM drug_database.{table}")
            ).scalar()
            print(f"  drug_database.{table}: {cnt:,} rows")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d - check logs", result.records_errored)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_run())
