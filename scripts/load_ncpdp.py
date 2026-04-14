"""NCPDP DataQ v3.1 Monthly Master load script.

Instantiates NCPDPDataQIngester and runs against:
  1. A local PostgreSQL database if DATABASE_URL_SYNC is configured.
  2. Otherwise, performs a dry-run against a SQLite in-memory engine and
     reports per-file yielded record counts.

Usage:
    uv run python scripts/load_ncpdp.py [/path/to/NCPDP.ZIP]

The ZIP defaults to: data/reference/ncpdp/NCPDP_v3.1_Monthly_Master_20240501.ZIP

Expected counts:
    pharmacies:                ~82,643
    pharmacy_taxonomies:       ~205,638
    pharmacy_state_licenses:   ~100,701
    pharmacy_services:          ~81,456
    pharmacy_remittance:        ~79,169
    pharmacy_erx_capabilities:  ~69,807
    pharmacy_medicaid:          ~70,955
    pharmacy_fwa_actions:      ~383,862
    pharmacy_coordinates:        ~8,703
    pharmacy_additional_info:      ~424
    pharmacy_patient_care:         ~440
    pharmacy_programs:              ~43
    pharmacy_recertification:       ~38
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PHARM_ROOT = _REPO_ROOT / "modules" / "pharmacy-directory"

for _p in (str(_REPO_ROOT), str(_PHARM_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Minimal env defaults
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM="
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("load_ncpdp")

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import zipfile
from shared.data_ingestion.sources.ncpdp_dataq import _FILE_PARSERS, _parse_file


def dry_run_count(zip_path: Path) -> dict[str, int]:
    """Parse all 13 files and count records per table without DB writes."""
    counts: dict[str, int] = {}

    logger.info("Opening ZIP: %s", zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        available = set(zf.namelist())

        for filename, table_name, parser in _FILE_PARSERS:
            if filename not in available:
                logger.warning("Missing file: %s", filename)
                counts[table_name] = 0
                continue

            count = 0
            for _ in _parse_file(zf, filename, table_name, parser):
                count += 1

            counts[table_name] = count
            logger.info("%-35s %8d records", filename, count)

    return counts


async def full_load(zip_path: Path) -> None:
    """Load all 13 tables into the configured database."""
    from shared.db.base import Base
    from src.models.base import PharmacyBase
    import src.models.ncpdp_tables  # noqa: F401
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ.get("DATABASE_URL_SYNC", "sqlite:///:memory:")
    is_sqlite = db_url.startswith("sqlite")

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )

    if is_sqlite:
        # Map pharmacy_dir schema to None for SQLite
        engine = engine.execution_options(
            schema_translate_map={"pharmacy_dir": None, "shared": None}
        )
        # Patch UUID columns for SQLite
        from sqlalchemy import JSON, String
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy.dialects.postgresql import UUID as PG_UUID
        from sqlalchemy.types import TypeDecorator
        import uuid as _uuid_module

        class _UUIDString(TypeDecorator):  # type: ignore[misc]
            impl = String(36)
            cache_ok = True

            def process_bind_param(self, value, dialect):
                return str(value) if value is not None else None

            def process_result_value(self, value, dialect):
                return _uuid_module.UUID(str(value)) if value is not None else None

        from shared.data_ingestion.models import IngestionRun, IngestionSchedule
        all_tables = list(PharmacyBase.metadata.tables.values()) + [
            IngestionRun.__table__, IngestionSchedule.__table__
        ]
        for table in all_tables:
            if not getattr(table, "_sqlite_patched", False):
                for col in table.columns:
                    if isinstance(col.type, JSONB):
                        col.type = JSON()
                    elif isinstance(col.type, PG_UUID):
                        col.type = _UUIDString()
                    if col.server_default is not None and "gen_random_uuid" in str(col.server_default):
                        col.server_default = None
                table._sqlite_patched = True

        PharmacyBase.metadata.create_all(engine)
        Base.metadata.create_all(engine, tables=[IngestionRun.__table__, IngestionSchedule.__table__])
    else:
        # PostgreSQL: create schema if needed
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("CREATE SCHEMA IF NOT EXISTS pharmacy_dir"))
            conn.commit()
        PharmacyBase.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    db = Session()

    from shared.data_ingestion.sources.ncpdp_dataq import NCPDPDataQIngester

    ingester = NCPDPDataQIngester(db_session=db, zip_path=zip_path)

    logger.info("Starting NCPDP DataQ ingestion run...")
    t0 = time.monotonic()
    result = await ingester.run(run_type="manual_trigger")
    elapsed = time.monotonic() - t0

    logger.info(
        "Ingestion complete in %.1fs: status=%s processed=%d inserted=%d errored=%d",
        elapsed,
        result.status,
        result.records_processed,
        result.records_inserted,
        result.records_errored,
    )

    db.close()
    engine.dispose()


def main() -> None:
    zip_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "data/reference/ncpdp/NCPDP_v3.1_Monthly_Master_20240501.ZIP"
    )

    if not zip_path.is_file():
        logger.error("ZIP not found: %s", zip_path)
        sys.exit(1)

    db_url = os.environ.get("DATABASE_URL_SYNC", "sqlite:///:memory:")
    use_real_db = not db_url.startswith("sqlite")

    if use_real_db:
        logger.info("Loading into database: %s", db_url.split("@")[-1])
        asyncio.run(full_load(zip_path))
    else:
        logger.info("No real database configured — running dry-run count only")
        t0 = time.monotonic()
        counts = dry_run_count(zip_path)
        elapsed = time.monotonic() - t0

        print("\n=== NCPDP DataQ Dry-Run Record Counts ===")
        total = 0
        for table, count in counts.items():
            print(f"  {table:<40} {count:>10,}")
            total += count
        print(f"  {'TOTAL':<40} {total:>10,}")
        print(f"\nParsed {total:,} records in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
