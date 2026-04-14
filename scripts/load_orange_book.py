"""Script to download and load the FDA Orange Book into drug_database.

Downloads https://www.fda.gov/media/76860/download (orange_book.zip),
extracts three tilde-delimited files, and bulk-upserts/replaces:

  drug_database.drug_orange_book  — ~35,000 products (upsert)
  drug_database.drug_patents       — ~15,000 patents  (delete-then-insert per appl key)
  drug_database.drug_exclusivity   — ~3,000 records   (delete-then-insert per appl key)

Also computes and reports the cross-reference join rate between
drug_orange_book.application_number and drugs.application_number.

Usage:
    python scripts/load_orange_book.py [--parse-only] [--cross-ref-only]

Options:
    --parse-only      Download + parse without a DB; prints record counts only.
    --cross-ref-only  Connect to DB and report cross-ref join rate (no download).

Requires:
    - DATABASE_URL_SYNC env var pointing to a running PostgreSQL instance, OR
    - --parse-only flag for dry-run without a DB.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from pathlib import Path

# Ensure repo root and drug-database module root are on sys.path
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


def _count_records_parse_only() -> None:
    """Download and parse; report yielded counts per table."""
    from shared.data_ingestion.downloader import download_to_file, unzip_if_zipped
    from shared.data_ingestion.sources.fda_orange_book import (
        _parse_exclusivity,
        _parse_patents,
        _parse_products,
    )

    dest = Path("data/reference/fda-orange-book")

    async def _download() -> Path:
        return await download_to_file(
            "https://www.fda.gov/media/76860/download",
            dest_dir=dest,
            filename="orange_book.zip",
        )

    logger.info("Downloading FDA Orange Book ZIP...")
    zip_path = asyncio.run(_download())
    logger.info("Extracting ZIP to %s...", zip_path.parent)
    extracted = unzip_if_zipped(zip_path, zip_path.parent)

    if extracted.is_dir():
        base = extracted
    else:
        base = extracted.parent

    products_path = base / "products.txt"
    patent_path = base / "patent.txt"
    exclusivity_path = base / "exclusivity.txt"

    counts: dict[str, int] = defaultdict(int)

    if products_path.exists():
        logger.info("Parsing products.txt...")
        for rec in _parse_products(products_path):
            counts["drug_orange_book"] += 1
            if counts["drug_orange_book"] % 5_000 == 0:
                logger.info("  products parsed: %d", counts["drug_orange_book"])
    else:
        logger.error("products.txt not found in %s", base)

    if patent_path.exists():
        logger.info("Parsing patent.txt...")
        for rec in _parse_patents(patent_path):
            counts["drug_patents"] += 1
            if counts["drug_patents"] % 5_000 == 0:
                logger.info("  patents parsed: %d", counts["drug_patents"])
    else:
        logger.error("patent.txt not found in %s", base)

    if exclusivity_path.exists():
        logger.info("Parsing exclusivity.txt...")
        for rec in _parse_exclusivity(exclusivity_path):
            counts["drug_exclusivity"] += 1
    else:
        logger.error("exclusivity.txt not found in %s", base)

    print("\n" + "=" * 60)
    print("PARSE-ONLY RECORD COUNTS:")
    for table, count in sorted(counts.items()):
        print(f"  {table}: {count:,}")
    print("=" * 60)


def _report_cross_ref(db_url: str) -> None:
    """Connect to DB and report how many Orange Book application_numbers match drugs."""
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, echo=False)
    with engine.connect() as conn:
        # Total distinct application_numbers in drug_orange_book
        total_ob = conn.execute(
            text(
                "SELECT COUNT(DISTINCT application_number) "
                "FROM drug_database.drug_orange_book "
                "WHERE application_number IS NOT NULL"
            )
        ).scalar() or 0

        # How many of those also appear as a prefix in drugs.application_number
        # (using equality join since both columns store the same format)
        matched = conn.execute(
            text(
                "SELECT COUNT(DISTINCT ob.application_number) "
                "FROM drug_database.drug_orange_book ob "
                "INNER JOIN drug_database.drugs d "
                "  ON ob.application_number = d.application_number "
                "WHERE ob.application_number IS NOT NULL"
            )
        ).scalar() or 0

    rate = (matched / total_ob * 100) if total_ob > 0 else 0.0
    print("\n" + "=" * 60)
    print("ORANGE BOOK ↔ NDC CROSS-REFERENCE JOIN RATE:")
    print(f"  distinct OB application_numbers:     {total_ob:,}")
    print(f"  matched in drugs.application_number: {matched:,}")
    print(f"  join rate:                           {rate:.1f}%")
    print(
        "  (< 100% expected — OB includes older discontinued drugs "
        "not in active NDC file)"
    )
    print("=" * 60)


async def _run_full_pipeline() -> None:
    """Run the full FDAOrangeBookIngester pipeline against a real database."""
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL_SYNC not set; use --parse-only for no-DB run")
        sys.exit(1)

    engine = create_engine(db_url, echo=False)
    with Session(engine) as session:
        from shared.data_ingestion.sources.fda_orange_book import FDAOrangeBookIngester

        ingester = FDAOrangeBookIngester(db_session=session)
        logger.info("Starting FDAOrangeBookIngester.run()...")
        result = await ingester.run(run_type="manual_trigger")

    print("\n" + "=" * 60)
    print("FULL PIPELINE RESULT:")
    print(f"  status:             {result.status}")
    print(f"  records_in_source:  {result.records_in_source:,}")
    print(f"  records_processed:  {result.records_processed:,}")
    print(f"  records_inserted:   {result.records_inserted:,}")
    print(f"  records_updated:    {result.records_updated:,}")
    print(f"  records_errored:    {result.records_errored:,}")
    print(f"  duration_seconds:   {result.duration_seconds:.1f}s")
    if result.error_message:
        print(f"  error:              {result.error_message}")
    print("=" * 60)

    # Report cross-ref join rate
    _report_cross_ref(db_url)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Download + parse without DB — prints record counts only",
    )
    parser.add_argument(
        "--cross-ref-only",
        action="store_true",
        help="Connect to DB and report cross-ref join rate (no download)",
    )
    args = parser.parse_args()

    if args.parse_only:
        _count_records_parse_only()
    elif args.cross_ref_only:
        import os
        db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
        if not db_url:
            logger.error("DATABASE_URL_SYNC not set")
            sys.exit(1)
        _report_cross_ref(db_url)
    else:
        asyncio.run(_run_full_pipeline())


if __name__ == "__main__":
    main()
