"""Load FDB NDDF Plus drops into drug_database.

Reads operator-managed drops at `data/reference/fdb/TEL251759D/` via
`FDBLocalDropAdapter` and writes to `fdb_price_type_desc` +
`fdb_ndc_price_history`. Three modes per SPEC §4.7:

  --mode fdb_initial   one-time full DB.zip baseline (~15.6M rows)
  --mode fdb_weekly    routine UPD.zip application (typical ~10k-100k)
  --mode fdb_rebase    operator-triggered DB.zip re-baseline (recovery)

Idempotency: composite UNIQUE on
  (ndc_11, price_type, effective_date, as_of_date, transaction_code,
   drop_sequence)
catches duplicates. Replay of the same drop produces 0 net new rows.

Usage:
    source infrastructure/scripts/switch_env.sh dev
    python scripts/load_fdb.py --mode fdb_weekly
    python scripts/load_fdb.py --mode fdb_initial --dry-run

Environment:
    DATABASE_URL_SYNC — set by switch_env.sh
    FDB_DROP_ROOT     — defaults to data/reference/fdb/TEL251759D/
"""
from __future__ import annotations

import argparse
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
logger = logging.getLogger("load_fdb")


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC_REFERENCE") or os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        logger.error(
            "DATABASE_URL_SYNC not set. "
            "Run: source infrastructure/scripts/switch_env.sh dev"
        )
        sys.exit(1)
    # async driver doesn't work for sync engine
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _resolve_root() -> Path:
    raw = os.environ.get("FDB_DROP_ROOT")
    if raw:
        return Path(raw)
    return _REPO_ROOT / "data" / "reference" / "fdb" / "TEL251759D"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["fdb_initial", "fdb_weekly", "fdb_rebase", "fdb_tier_a"],
        required=True,
        help=(
            "ingestion mode. Phase 09: fdb_initial / fdb_weekly / "
            "fdb_rebase (pricing-only via FDBPricingIngester). B9.B+: "
            "fdb_tier_a (generic TableSpec-driven loader; reads "
            "fdb_specs.REGISTERED_SPECS filtered by loader_group='fdb_tier_a')."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse + count rows; do not write to the DB",
    )
    parser.add_argument(
        "--ingestion-run-id",
        default=None,
        help="optional shared.ingestion_runs FK to record on each inserted row",
    )
    args = parser.parse_args()

    # Imports deferred until after sys.path setup so module imports resolve.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from drug_database.services.fdb_adapter import FDBLocalDropAdapter

    db_url = _resolve_db_url()
    root = _resolve_root()
    if not root.exists():
        logger.error("FDB drop root not found: %s", root)
        return 2

    engine = create_engine(db_url)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()

    try:
        adapter = FDBLocalDropAdapter(root)

        if args.mode == "fdb_tier_a":
            # B9.B C19: generic TableSpec-driven loader.
            from drug_database.services.fdb_tier_loader import load_tier_group
            drop = adapter.discover_latest_drop()
            tier_result = load_tier_group(
                session, adapter, drop,
                group="fdb_tier_a", dry_run=args.dry_run,
            )
            logger.info(
                "fdb_ingest_summary mode=%s drop_date=%s "
                "tables_loaded=%d total_inserted=%d total_skipped=%d "
                "dry_run=%s",
                args.mode, tier_result.drop_date,
                len(tier_result.table_summaries),
                tier_result.total_inserted,
                tier_result.total_skipped,
                tier_result.dry_run,
            )
            return 0

        # Phase 09 modes — fdb_initial / fdb_weekly / fdb_rebase
        from drug_database.services.fdb_pricing_ingester import FDBPricingIngester
        ingester = FDBPricingIngester(
            adapter=adapter,
            session=session,
            ingestion_run_id=args.ingestion_run_id,
        )
        result = ingester.run(mode=args.mode, dry_run=args.dry_run)
    finally:
        session.close()
        engine.dispose()

    logger.info(
        "fdb_ingest_summary mode=%s drop_date=%s "
        "price_type_desc_inserted=%d "
        "rnp3_inserted=%d rnp3_duplicate_skipped=%d rnp3_invalid_skipped=%d "
        "dry_run=%s",
        result.mode,
        result.drop_date,
        result.price_type_desc_inserted,
        result.rnp3_inserted,
        result.rnp3_duplicate_skipped,
        result.rnp3_invalid_skipped,
        result.dry_run,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
