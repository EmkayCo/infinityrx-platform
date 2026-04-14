"""Script to download and load the FDA NDC Directory into drug_database.

Downloads https://www.accessdata.fda.gov/cder/ndctext.zip, extracts it,
and bulk-upserts ~130K drugs, ~300K packages, ~400-600K active ingredients,
and ~300-500K pharmacological class entries.

Usage:
    python scripts/load_fda_ndc.py [--dry-run] [--parse-only]

Options:
    --dry-run       Runs the pipeline but skips the DB load (parse + count only).
    --parse-only    Downloads and parses without a DB session (for local testing
                    when PostgreSQL is not accessible).

Requires:
    - DATABASE_URL_SYNC env var pointing to a running PostgreSQL instance, OR
    - --parse-only flag for dry-run without a DB.

Expected counts (2024 FDA NDC file):
    drugs:                  ~130,000
    drug_packages:          ~300,000
    drug_active_ingredients: ~400,000-600,000
    drug_pharm_classes:      ~300,000-500,000
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
logger = logging.getLogger("load_fda_ndc")


def _count_records(parse_only: bool) -> None:
    """Download and parse; report yielded counts per table."""
    from shared.data_ingestion.downloader import download_to_file, unzip_if_zipped
    from shared.data_ingestion.sources.fda_ndc import _parse_packages, _parse_products

    dest = Path("data/reference/fda-ndc")

    async def _download() -> Path:
        return await download_to_file(
            "https://www.accessdata.fda.gov/cder/ndctext.zip",
            dest_dir=dest,
            filename="ndctext.zip",
        )

    logger.info("Downloading FDA NDC ZIP...")
    zip_path = asyncio.run(_download())
    logger.info("Extracting ZIP...")
    extracted = unzip_if_zipped(zip_path, zip_path.parent)

    if extracted.is_dir():
        product_txt = extracted / "product.txt"
        package_txt = extracted / "package.txt"
    else:
        product_txt = extracted.parent / "product.txt"
        package_txt = extracted.parent / "package.txt"

    counts: dict[str, int] = defaultdict(int)

    logger.info("Parsing product.txt...")
    for record in _parse_products(product_txt):
        row = record["row"]
        counts["drugs"] += 1
        # Count exploded ingredients
        if row.get("substance_name"):
            substances = row["substance_name"].split(";")
            strengths = (row.get("active_numerator_strength") or "").split(";")
            units = (row.get("active_ingred_unit") or "").split(";")
            if len(substances) == len(strengths) == len(units):
                counts["drug_active_ingredients"] += len(substances)
            # else: mismatched — would be an error sample in real run
        if row.get("pharm_classes"):
            counts["drug_pharm_classes"] += len(
                [c for c in row["pharm_classes"].split(",") if c.strip()]
            )
        if counts["drugs"] % 10_000 == 0:
            logger.info("  drugs parsed: %d", counts["drugs"])

    logger.info("Parsing package.txt...")
    for record in _parse_packages(package_txt):
        counts["drug_packages"] += 1
        if counts["drug_packages"] % 50_000 == 0:
            logger.info("  packages parsed: %d", counts["drug_packages"])

    print("\n" + "=" * 50)
    print("PARSE-ONLY RECORD COUNTS:")
    for table, count in sorted(counts.items()):
        print(f"  {table}: {count:,}")
    print("=" * 50)


async def _run_full_pipeline() -> None:
    """Run the full FDANDCIngester pipeline against a real database."""
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL_SYNC not set; use --parse-only for no-DB run")
        sys.exit(1)

    engine = create_engine(db_url, echo=False)
    with Session(engine) as session:
        from shared.data_ingestion.sources.fda_ndc import FDANDCIngester

        ingester = FDANDCIngester(db_session=session)
        logger.info("Starting FDANDCIngester.run()...")
        result = await ingester.run(run_type="manual_trigger")

    print("\n" + "=" * 50)
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
    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Download + parse without DB — prints record counts only",
    )
    args = parser.parse_args()

    if args.parse_only:
        _count_records(parse_only=True)
    else:
        asyncio.run(_run_full_pipeline())


if __name__ == "__main__":
    main()
