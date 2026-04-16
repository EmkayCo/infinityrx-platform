"""Load FDA Orange Book into drug_database.

Downloads orange_book.zip, extracts three tilde-delimited files, and
populates:

  drug_database.drug_orange_book  — upsert by (appl_type, appl_no, product_no)
  drug_database.drug_patents       — scoped-replace by (appl_type, appl_no, product_no)
  drug_database.drug_exclusivity   — scoped-replace by (appl_type, appl_no, product_no)

Pipeline: FDAOrangeBookIngester (DataSourceIngester child)
  download → FDA orange_book.zip → local file
  parse    → products, patents, exclusivity records
  load     → flush_upsert_batch + flush_scoped_replace_batch

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_orange_book.py [--dry-run]

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
logger = logging.getLogger("load_orange_book")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _dry_run() -> None:
    """Download + parse without DB; report per-table record counts."""
    from collections import Counter
    from unittest.mock import MagicMock

    from shared.data_ingestion.sources.fda_orange_book import FDAOrangeBookIngester

    ingester = FDAOrangeBookIngester(db_session=MagicMock())
    cached = _REPO_ROOT / "data" / "reference" / "fda-orange-book" / "orange_book.zip"

    logger.info("Downloading Orange Book ZIP...")
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
    print("Orange Book DRY-RUN record counts")
    print(f"{'=' * 60}")
    for table, count in sorted(counts.items()):
        print(f"  {table:30s}  {count:>10,}")
    print(f"{'=' * 60}")


async def _run() -> None:
    """Full pipeline: download → parse → load."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.fda_orange_book import FDAOrangeBookIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = FDAOrangeBookIngester(db_session=session)
        logger.info("Starting FDA Orange Book pipeline...")
        result = await ingester.run(run_type="manual_trigger")

    print(f"\n{'=' * 60}")
    print("Orange Book Load Result")
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
        for table in ("drug_orange_book", "drug_patents", "drug_exclusivity"):
            cnt = conn.execute(
                text(f"SELECT count(*) FROM drug_database.{table}")
            ).scalar()
            print(f"  drug_database.{table}: {cnt:,} rows")

        # Cross-ref join rate against drugs.application_number
        joined = conn.execute(
            text(
                "SELECT count(DISTINCT ob.application_number) "
                "FROM drug_database.drug_orange_book ob "
                "INNER JOIN drug_database.drugs d "
                "  ON d.application_number = ob.application_number"
            )
        ).scalar()
        total = conn.execute(
            text(
                "SELECT count(DISTINCT application_number) "
                "FROM drug_database.drug_orange_book "
                "WHERE application_number IS NOT NULL"
            )
        ).scalar()
        if total:
            pct = 100 * (joined or 0) / total
            print(f"  cross-ref join rate: {joined}/{total}  ({pct:.1f}%)")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d — check logs", result.records_errored)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load FDA Orange Book")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download + parse without DB load (prints record counts only)",
    )
    args = parser.parse_args()
    asyncio.run(_dry_run() if args.dry_run else _run())


if __name__ == "__main__":
    main()
