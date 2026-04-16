"""Load OFAC SDN exclusions into shared.ofac_sdn + 3 child tables.

Reads pre-staged CSVs from data/reference/ofac-sdn/ (sdn / add / alt /
sdn_comments) and upserts via OfacSdnIngester. No HTTP download in
this wave — OFAC moved distribution behind sanctionslistservice and
the add.csv/alt.csv endpoints are currently 400; HTTP wiring is a
follow-up.

Pipeline: OfacSdnIngester (DataSourceIngester child)
  download -> return data/reference/ofac-sdn/ (stub, no HTTP)
  parse    -> stream 4 CSVs (positional cols, latin-1, "-0-" -> NULL)
  load     -> parent upsert + 3 child scoped-replaces

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_ofac.py

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
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_ofac")


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

    from shared.data_ingestion.sources.ofac_sdn import OfacSdnIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = OfacSdnIngester(db_session=session)
        logger.info("Starting OFAC SDN pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    print(f"\n{'=' * 60}")
    print("OFAC SDN Load Result")
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
        for table in ("ofac_sdn", "ofac_sdn_addresses",
                      "ofac_sdn_aliases", "ofac_sdn_comments"):
            cnt = conn.execute(
                text(f"SELECT count(*) FROM shared.{table}")
            ).scalar()
            print(f"  shared.{table}: {cnt:,} rows")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d - check logs", result.records_errored)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_run())
