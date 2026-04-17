"""Load CMS Medicare Part D Prescribers by Provider into prescriber_dir.

Streams the CMS Socrata JSON dump (~3.26 GB for CY2023, ~1.38M rows) via
ijson and batch-upserts via shared.data_ingestion.batching.flush_upsert_batch.

Pipeline: CmsPartDPrescriberIngester (DataSourceIngester child)
  download -> paginate Socrata API -> data/reference/cms-part-d/part_d_prescriber.json
  parse    -> stream_json_array (ijson) -> normalised dicts (Decimal money fields)
  load     -> flush_upsert_batch (unique_key=[npi, year])

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_part_d.py [--limit N] [--year YYYY]

Flags:
    --limit N   Cap records yielded from parse() to N. Used for smoke tests
                so we don't spend 15-60 min loading the full dataset before
                confirming schema/types are right. Permanent affordance.
    --year YYYY Override the data year used to tag each row. Defaults to
                CmsPartDPrescriberIngester's _CURRENT_DATA_YEAR constant.

Environment:
    DATABASE_URL_SYNC - set by switch_env.sh
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import logging
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PRESCRIBER_DIR = _REPO_ROOT / "modules" / "prescriber-directory"
for _p in (str(_REPO_ROOT), str(_PRESCRIBER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_part_d")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load CMS Part D Prescribers")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap records yielded from parse() (smoke-test affordance)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Override data year; defaults to ingester's _CURRENT_DATA_YEAR",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.cms_part_d_prescriber import (
        CmsPartDPrescriberIngester,
    )

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = CmsPartDPrescriberIngester(db_session=session, year=args.year)

        if args.limit is not None:
            original_parse = ingester.parse

            def _limited_parse(file_path: Path) -> Iterator[dict[str, Any]]:
                yield from itertools.islice(original_parse(file_path), args.limit)

            ingester.parse = _limited_parse  # type: ignore[method-assign]
            logger.info("Smoke test: capping parse() output at %d records", args.limit)

        logger.info("Starting CMS Part D pipeline (year=%d)...", ingester._year)
        result = await ingester.run(run_type="manual_trigger")

    print(f"\n{'=' * 60}")
    print("CMS Part D Load Result")
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
            text("SELECT count(*) FROM prescriber_dir.medicare_part_d_utilization")
        ).scalar()
        print(f"  prescriber_dir.medicare_part_d_utilization: {cnt:,} rows")

        year_breakdown = conn.execute(
            text(
                "SELECT year, count(*) "
                "FROM prescriber_dir.medicare_part_d_utilization "
                "GROUP BY year ORDER BY year"
            )
        ).fetchall()
        for yr, n in year_breakdown:
            print(f"    year={yr}: {n:,}")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d - check logs", result.records_errored)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_run(_parse_args()))
