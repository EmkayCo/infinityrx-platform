"""Load the latest CMS ICD-10-CM code descriptions into shared.icd10_cm_codes.

CMS publishes the ICD-10-CM codeset twice per fiscal year (annual Oct 1
release + April mid-year update). This script picks the newest published
zip from https://www.cms.gov/medicare/coding-billing/icd-10-codes and
loads it via the Icd10CmIngester.

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_icd10.py
    python scripts/load_icd10.py --source-zip /path/to/already-extracted.zip
"""

from __future__ import annotations

import argparse
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
logger = logging.getLogger("load_icd10")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _run(source_zip: Path | None) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.icd10_cm import Icd10CmIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False, future=True)

    with Session(engine) as session:
        ingester = Icd10CmIngester(db_session=session, source_csv=source_zip)
        result = await ingester.run(run_type="manual_trigger")

    print(f"\n{'=' * 60}")
    print("ICD-10-CM Load Result")
    print(f"{'=' * 60}")
    print(f"  Status:             {result.status}")
    print(f"  Records in source:  {result.records_in_source:,}")
    print(f"  Records processed:  {result.records_processed:,}")
    print(f"  Records inserted:   {result.records_inserted:,}")
    print(f"  Records errored:    {result.records_errored:,}")
    print(f"  Duration:           {result.duration_seconds:.1f}s")
    if result.error_message:
        print(f"  Error:              {result.error_message}")

    with engine.connect() as conn:
        cnt = conn.execute(
            text("SELECT count(*) FROM shared.icd10_cm_codes")
        ).scalar()
        distinct_codes = conn.execute(
            text("SELECT count(DISTINCT code) FROM shared.icd10_cm_codes")
        ).scalar()
        distinct_dates = conn.execute(
            text("SELECT array_agg(DISTINCT effective_date ORDER BY effective_date) "
                 "FROM shared.icd10_cm_codes")
        ).scalar()
        print(f"  shared.icd10_cm_codes: {cnt:,} rows")
        print(f"  distinct codes:        {distinct_codes:,}")
        print(f"  effective_dates:       {distinct_dates}")
    print(f"{'=' * 60}")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d — check logs", result.records_errored)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-zip",
        type=Path,
        default=None,
        help="Path to an already-downloaded descriptions zip. When omitted, "
             "the script scrapes https://www.cms.gov/.../icd-10-codes for the "
             "newest April/October release and downloads it.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.source_zip))


if __name__ == "__main__":
    main()
