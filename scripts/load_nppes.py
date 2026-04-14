#!/usr/bin/env python3
"""Load the latest CMS NPPES weekly dissemination file.

Usage:
    python scripts/load_nppes.py [--dry-run] [--sample]

Options:
    --dry-run   Parse the sample CSV only, no DB writes. Reports yielded counts.
    --sample    Use the bundled synthetic sample CSV instead of downloading.

Exits 0 on success, 1 on failure.

LESSON-010: NPI is public — plaintext throughout.
LESSON-011: Global reference tables — no TenantScopedMixin.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
import time
from pathlib import Path

# ── sys.path setup ────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_PRESCRIBER_DIR = _PROJECT_ROOT / "modules" / "prescriber-directory"

for _p in [str(_PROJECT_ROOT), str(_PRESCRIBER_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("load_nppes")

# ── Sample CSV ────────────────────────────────────────────────────────────
_SAMPLE_CSV = (
    _PROJECT_ROOT
    / "shared"
    / "data_ingestion"
    / "tests"
    / "sample_data"
    / "nppes"
    / "npidata_sample.csv"
)


# ── Dry-run / parse-only path ─────────────────────────────────────────────

def _dry_run(csv_path: Path) -> None:
    """Parse the CSV, validate NPIs, count rows — no DB writes."""
    from src.services.nppes_ingestion import (
        _build_addresses,
        _build_detail,
        _build_identifiers,
        _build_taxonomies,
        _or_none,
    )
    from src.utils.validators import NpiValidationError, validate_npi
    import re

    _NPI_RE = re.compile(r"\A\d{10}\Z")

    individuals = 0
    organizations = 0
    total_addresses = 0
    total_taxonomies = 0
    total_identifiers = 0
    errored = 0
    skipped = 0
    pharmacy_supplements = 0
    now_dt = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    row_count = 0
    with csv_path.open(newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            row_count += 1
            npi = row.get("NPI", "").strip()

            if not _NPI_RE.fullmatch(npi):
                skipped += 1
                continue
            try:
                validate_npi(npi)
            except NpiValidationError:
                errored += 1
                continue

            entity_type = _or_none(row.get("Entity Type Code", ""))
            addresses = _build_addresses(npi, row, now_dt)
            taxonomies = _build_taxonomies(npi, row, now_dt)
            identifiers = _build_identifiers(npi, row, now_dt)

            if entity_type == "1":
                individuals += 1
            else:
                organizations += 1

            # Check pharmacy supplement eligibility
            if entity_type == "2" and any(
                t.taxonomy_code and t.taxonomy_code.startswith("333") for t in taxonomies
            ):
                pharmacy_supplements += 1

            total_addresses += len(addresses)
            total_taxonomies += len(taxonomies)
            total_identifiers += len(identifiers)

            if row_count % 10_000 == 0:
                logger.info(
                    "Progress: %d rows parsed (%d individuals, %d orgs)",
                    row_count, individuals, organizations,
                )

    print("\n── NPPES Dry-Run Results ──────────────────────────────────")
    print(f"  CSV path:               {csv_path}")
    print(f"  Total rows read:        {row_count}")
    print(f"  Individuals (type=1):   {individuals}")
    print(f"  Organizations (type=2): {organizations}")
    print(f"  Pharmacy supplements:   {pharmacy_supplements}  (entity=2 + taxonomy 333*)")
    print(f"  Total addresses:        {total_addresses}")
    print(f"  Total taxonomies:       {total_taxonomies}")
    print(f"  Total identifiers:      {total_identifiers}")
    print(f"  Skipped (bad format):   {skipped}")
    print(f"  Errored (Luhn fail):    {errored}")
    print("──────────────────────────────────────────────────────────\n")


# ── Live load path ────────────────────────────────────────────────────────

async def _live_load(sample: bool) -> None:
    """Download (or use sample) and load into the DB."""
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error(
            "DATABASE_URL_SYNC or DATABASE_URL must be set for live load. "
            "Use --dry-run or --sample to test without a DB."
        )
        sys.exit(1)

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        if sample:
            logger.info("Using bundled sample CSV: %s", _SAMPLE_CSV)
            csv_path = _SAMPLE_CSV
        else:
            # Download via NppesIngester
            from shared.data_ingestion.sources.nppes import NppesIngester

            ingester = NppesIngester(db_session=db)
            logger.info("Downloading latest NPPES weekly file...")
            t0 = time.monotonic()
            csv_path = await ingester.download()
            logger.info("Download complete in %.1fs → %s", time.monotonic() - t0, csv_path)

        # Pass 1: core Prescriber upsert
        from src.services.nppes_upsert import run_nppes_import

        logger.info("Pass 1: core Prescriber upsert...")
        t1 = time.monotonic()
        with csv_path.open(newline="", encoding="utf-8") as fh:
            refresh_log = run_nppes_import(db, fh, data_source="nppes", refresh_type="weekly")
        db.commit()
        elapsed_1 = time.monotonic() - t1
        logger.info(
            "Pass 1 complete in %.1fs — added=%d updated=%d",
            elapsed_1, refresh_log.records_added, refresh_log.records_updated,
        )

        # Pass 2: satellite tables
        from src.services.nppes_ingestion import load_nppes_satellite_tables

        logger.info("Pass 2: satellite tables (addresses, taxonomies, identifiers)...")
        t2 = time.monotonic()
        stats = load_nppes_satellite_tables(db, csv_path)
        db.commit()
        elapsed_2 = time.monotonic() - t2

        total_elapsed = elapsed_1 + elapsed_2

        print("\n── NPPES Live Load Results ────────────────────────────────")
        print(f"  Individuals (type=1):   {stats.individuals}")
        print(f"  Organizations (type=2): {stats.organizations}")
        print(f"  Pharmacy supplements:   {stats.pharmacy_supplements}  (T2 awareness)")
        print(f"  Total addresses:        {stats.total_addresses}")
        print(f"  Total taxonomies:       {stats.total_taxonomies}")
        print(f"  Total identifiers:      {stats.total_identifiers}")
        print(f"  Errored rows:           {stats.records_errored}")
        print(f"  Elapsed (pass 1):       {elapsed_1:.1f}s")
        print(f"  Elapsed (pass 2):       {elapsed_2:.1f}s")
        print(f"  Total elapsed:          {total_elapsed:.1f}s")
        print("──────────────────────────────────────────────────────────\n")

    except Exception:
        logger.exception("Live load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
        engine.dispose()


# ── Entry point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Load NPPES weekly data")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse only — no DB writes. Reports yielded counts.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use the bundled synthetic sample CSV instead of downloading.",
    )
    args = parser.parse_args()

    t0 = time.monotonic()

    if args.dry_run:
        csv_path = _SAMPLE_CSV if args.sample else _SAMPLE_CSV
        logger.info("Dry-run mode — parsing %s", csv_path)
        _dry_run(csv_path)
    else:
        asyncio.run(_live_load(sample=args.sample))

    logger.info("Total wall time: %.1fs", time.monotonic() - t0)


if __name__ == "__main__":
    main()
