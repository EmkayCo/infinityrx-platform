"""Load FDA NDC Directory into drug_database.

Downloads https://www.accessdata.fda.gov/cder/ndctext.zip, streams product.txt
and package.txt through the shared batching primitives, and populates:

  drug_database.drugs                   — upsert by product_id
  drug_database.drug_packages           — upsert by ndc_package_code_11
  drug_database.drug_active_ingredients — scoped-replace by drug_id
  drug_database.drug_pharm_classes      — scoped-replace by drug_id

Pipeline: FDANDCIngester (DataSourceIngester child)
  download → FDA ndctext.zip → local file
  parse    → drugs, ingredients, pharm_classes, packages
  load     → flush_upsert_batch + scoped replace via ScopedReplacer pattern

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_fda_ndc.py [--dry-run]

Environment:
    DATABASE_URL_SYNC — set by switch_env.sh
"""

from __future__ import annotations

import argparse
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
logger = logging.getLogger("load_fda_ndc")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _dry_run() -> None:
    """Download + parse without a DB; report per-table record counts."""
    from collections import Counter
    from unittest.mock import MagicMock

    from shared.data_ingestion.sources.fda_ndc import FDANDCIngester

    ingester = FDANDCIngester(db_session=MagicMock())
    cached = _REPO_ROOT / "data" / "reference" / "fda-ndc" / "ndctext.zip"

    logger.info("Downloading FDA NDC ZIP...")
    try:
        file_path = await ingester.download()
    except Exception as exc:
        logger.warning("Download failed (%s), falling back to cached ZIP", exc)
        if cached.exists():
            file_path = cached
        else:
            logger.error("No cached ZIP at %s — aborting", cached)
            sys.exit(1)

    counts: Counter[str] = Counter()
    for record in ingester.parse(file_path):
        counts[record["table"]] += 1

    print(f"\n{'=' * 60}")
    print("FDA NDC DRY-RUN record counts")
    print(f"{'=' * 60}")
    for table, count in sorted(counts.items()):
        print(f"  {table:30s}  {count:>10,}")
    print(f"{'=' * 60}")


async def _run() -> None:
    """Full pipeline: download → parse → load via FDANDCIngester."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.fda_ndc import FDANDCIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = FDANDCIngester(db_session=session)
        logger.info("Starting FDA NDC pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    if result.status == "failed":
        logger.error("Ingest failed: %s", getattr(result, "error_message", "unknown"))
        sys.exit(2)

    print(f"\n{'=' * 60}")
    print("FDA NDC Load Result")
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
        for table in (
            "drugs",
            "drug_packages",
            "drug_active_ingredients",
            "drug_pharm_classes",
        ):
            cnt = conn.execute(
                text(f"SELECT count(*) FROM drug_database.{table}")
            ).scalar()
            print(f"  drug_database.{table}: {cnt:,} rows")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d — check logs", result.records_errored)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load FDA NDC Directory")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download + parse without DB load (prints record counts only)",
    )
    args = parser.parse_args()
    asyncio.run(_dry_run() if args.dry_run else _run())


if __name__ == "__main__":
    main()
