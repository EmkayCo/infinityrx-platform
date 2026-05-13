"""Load the current CMS HCPCS Level II quarterly file into shared.hcpcs_codes.

CMS publishes HCPCS Level II quarterly at
https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update
This script picks the newest published zip and loads it via HcpcsIngester.

Level I (CPT) codes are AMA-licensed and **not** included in CMS's public
release — this script only loads the ~9k Level II codes plus ~580 modifiers.

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_hcpcs.py
    python scripts/load_hcpcs.py --source-zip /path/to/quarterly.zip
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
logger = logging.getLogger("load_hcpcs")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
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

    from shared.data_ingestion.sources.hcpcs import HcpcsIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False, future=True)

    with Session(engine) as session:
        ingester = HcpcsIngester(db_session=session, source_csv=source_zip)
        result = await ingester.run(run_type="manual_trigger")

    if result.status == "failed":
        logger.error("Ingest failed: %s", getattr(result, "error_message", "unknown"))
        sys.exit(2)

    print(f"\n{'=' * 60}")
    print("HCPCS Level II Load Result")
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
        cnt = conn.execute(text("SELECT count(*) FROM shared.hcpcs_codes")).scalar()
        modifiers = conn.execute(
            text("SELECT count(*) FROM shared.hcpcs_codes WHERE is_modifier = TRUE")
        ).scalar()
        distinct_codes = conn.execute(
            text("SELECT count(DISTINCT code) FROM shared.hcpcs_codes "
                 "WHERE is_modifier = FALSE")
        ).scalar()
        quarters = conn.execute(
            text("SELECT array_agg(DISTINCT publication_quarter ORDER BY publication_quarter) "
                 "FROM shared.hcpcs_codes")
        ).scalar()
        print(f"  shared.hcpcs_codes:     {cnt:,} rows "
              f"(regular codes={cnt - (modifiers or 0):,}, modifiers={modifiers or 0:,})")
        print(f"  distinct non-modifier:  {distinct_codes:,}")
        print(f"  publication_quarters:   {quarters}")
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
        help="Path to an already-downloaded quarterly zip. When omitted, "
             "the script scrapes the CMS quarterly-update page for the "
             "newest release and downloads it.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.source_zip))


if __name__ == "__main__":
    main()
