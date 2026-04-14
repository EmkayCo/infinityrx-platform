"""Run the OIG LEIE ingester against the live DB."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_REPO_ROOT, _REPO_ROOT / "modules" / "prescriber-directory", _REPO_ROOT / "modules" / "pharmacy-directory"):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s %(message)s")
logger = logging.getLogger("load_oig_leie")


async def main() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL_SYNC required")
        sys.exit(1)
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine = create_engine(db_url, echo=False)
    with Session(engine) as session:
        from shared.data_ingestion.sources.oig_leie import OigLeieIngester
        ingester = OigLeieIngester(db_session=session)
        result = await ingester.run(run_type="manual_trigger")
    print("=" * 60)
    print(f"OIG LEIE: status={result.status}")
    print(f"  records_in_source:  {result.records_in_source:,}")
    print(f"  records_inserted:   {result.records_inserted:,}")
    print(f"  records_updated:    {result.records_updated:,}")
    print(f"  records_errored:    {result.records_errored:,}")
    print(f"  duration:           {result.duration_seconds:.1f}s")
    if result.error_message:
        print(f"  error: {result.error_message}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
