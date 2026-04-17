"""Load NCPDP DataQ v3.1 Monthly Master into pharmacy_dir schema.

Parses 13 fixed-width files from the NCPDP ZIP archive and loads into:
  ncpdp_pharmacies (master) + 12 child tables (~1.07M+ rows total).

Pipeline: NCPDPDataQIngester (DataSourceIngester child)
  download → return pre-staged ZIP path (no HTTP — subscription service)
  parse    → stream 13 fixed-width files, yield per-table row dicts
  load     → BatchedUpserter (7 upsert tables) + scoped replace (6 child tables)

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_ncpdp.py [ZIP_PATH] [--dry-run]

ZIP_PATH defaults to data/reference/ncpdp/NCPDP_v3.1_Monthly_Master_20240501.ZIP
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PHARM_ROOT = _REPO_ROOT / "modules" / "pharmacy-directory"
for _p in (str(_REPO_ROOT), str(_PHARM_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s %(message)s",
)
logger = logging.getLogger("load_ncpdp")

_DEFAULT_ZIP = _REPO_ROOT / "data" / "reference" / "ncpdp" / "NCPDP_v3.1_Monthly_Master_20240501.ZIP"

_ALL_TABLES = [
    "ncpdp_pharmacies",
    "ncpdp_pharmacy_taxonomies",
    "ncpdp_pharmacy_state_licenses",
    "ncpdp_pharmacy_services",
    "ncpdp_pharmacy_remittance",
    "ncpdp_pharmacy_erx_capabilities",
    "ncpdp_pharmacy_medicaid",
    "ncpdp_pharmacy_fwa_actions",
    "ncpdp_pharmacy_coordinates",
    "ncpdp_pharmacy_additional_info",
    "ncpdp_pharmacy_patient_care",
    "ncpdp_pharmacy_programs",
    "ncpdp_pharmacy_recertification",
]


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _dry_run(zip_path: Path) -> None:
    """Parse all 13 files and report record counts (no DB)."""
    import zipfile

    from shared.data_ingestion.sources.ncpdp_dataq import _FILE_PARSERS, _parse_file

    counts: dict[str, int] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        available = set(zf.namelist())
        for filename, table_name, parser in _FILE_PARSERS:
            if filename not in available:
                counts[table_name] = 0
                continue
            counts[table_name] = sum(1 for _ in _parse_file(zf, filename, table_name, parser))
            logger.info("%-35s %8d records", filename, counts[table_name])

    total = sum(counts.values())
    print(f"\nDRY-RUN: NCPDP DataQ Parse Counts")
    for table, count in counts.items():
        print(f"  {table:<42} {count:>10,}")
    print(f"  {'TOTAL':<42} {total:>10,}")


async def _run(zip_path: Path) -> None:
    """Full pipeline: parse ZIP → load all 13 tables."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.ncpdp_dataq import NCPDPDataQIngester

    db_url = _resolve_db_url()
    engine = create_engine(db_url, echo=False)

    with Session(engine) as session:
        ingester = NCPDPDataQIngester(db_session=session, zip_path=zip_path)
        logger.info("Starting NCPDP DataQ pipeline (%s)...", zip_path.name)
        result = await ingester.run(run_type="manual_trigger")

    # Report
    print(f"\n{'=' * 60}")
    print("NCPDP DataQ Load Result")
    print(f"{'=' * 60}")
    print(f"  Status:             {result.status}")
    print(f"  Records in source:  {result.records_in_source:,}")
    print(f"  Records processed:  {result.records_processed:,}")
    print(f"  Records inserted:   {result.records_inserted:,}")
    print(f"  Records skipped:    {result.records_skipped:,}")
    print(f"  Records errored:    {result.records_errored:,}")
    print(f"  Duration:           {result.duration_seconds:.1f}s")
    if result.error_message:
        print(f"  Error:              {result.error_message}")
    print(f"{'=' * 60}")

    # Verify row counts per table
    with engine.connect() as conn:
        total = 0
        for t in _ALL_TABLES:
            cnt = conn.execute(text(f"SELECT count(*) FROM pharmacy_dir.{t}")).scalar()
            total += cnt
            print(f"  {t:<42} {cnt:>10,}")
        print(f"  {'TOTAL':<42} {total:>10,}")

    if result.records_errored > 0:
        logger.error("Non-zero error count: %d — check logs", result.records_errored)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load NCPDP DataQ Monthly Master")
    parser.add_argument(
        "zip_path",
        nargs="?",
        type=Path,
        default=_DEFAULT_ZIP,
        help="Path to NCPDP DataQ ZIP file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only — no DB load (prints record counts)",
    )
    args = parser.parse_args()

    if not args.zip_path.is_file():
        logger.error("ZIP not found: %s", args.zip_path)
        sys.exit(1)

    asyncio.run(_dry_run(args.zip_path) if args.dry_run else _run(args.zip_path))


if __name__ == "__main__":
    main()
