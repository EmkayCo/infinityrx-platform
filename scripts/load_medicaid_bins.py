"""Run the StateMedicaidBinLoader against all regional CSVs.

LOADER-08. Populates shared.government_program_bins from the curated
regional CSV files under data/reference/medicaid/. Each CSV has the
columns the StateMedicaidBinLoader expects (state, bin, pcn,
group_number, plan_type, plan_subtype, pbm_name, plan_name, mco_name,
confidence, source, source_date, notes) and is processed independently
so per-region errors don't abort the whole run.

Source CSVs (curated from state pharmacy provider portals and PBM
vendor documentation):
    data/reference/medicaid/midwest.csv
    data/reference/medicaid/northeast.csv
    data/reference/medicaid/south_central.csv
    data/reference/medicaid/southeast.csv
    data/reference/medicaid/west.csv

Usage:
    python scripts/load_medicaid_bins.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CSV_DIR = _REPO_ROOT / "data" / "reference" / "medicaid"
_REGIONAL_FILES = [
    "midwest.csv",
    "northeast.csv",
    "south_central.csv",
    "southeast.csv",
    "west.csv",
]

for _p in (_REPO_ROOT,):
    sp = str(_p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s %(message)s")
logger = logging.getLogger("load_medicaid_bins")


def main() -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from shared.data_ingestion.sources.state_medicaid_bins import (
        StateMedicaidBinLoader,
        VALID_STATES,
    )

    db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL_SYNC required")
        return 1
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine = create_engine(db_url, echo=False)

    total_upserted = 0
    total_errors = 0
    all_states_seen: set[str] = set()

    with Session(engine) as session:
        loader = StateMedicaidBinLoader(db=session)
        for name in _REGIONAL_FILES:
            path = _CSV_DIR / name
            if not path.is_file():
                logger.warning("Missing regional CSV: %s", path)
                continue
            logger.info("Loading %s", path.name)
            result = loader.load_csv(path, region=path.stem)
            session.commit()  # commit each region before the next

            print(f"  {path.name}: upserted={result.rows_upserted} "
                  f"skipped={result.rows_skipped} errors={len(result.errors)}")
            if result.per_state_counts:
                states = ", ".join(sorted(result.per_state_counts.keys()))
                print(f"     states: {states}")
            total_upserted += result.rows_upserted
            total_errors += len(result.errors)
            all_states_seen.update(result.per_state_counts.keys())

    missing_states = sorted(VALID_STATES - all_states_seen)
    print("=" * 60)
    print(f"State Medicaid BINs: rows_upserted={total_upserted}")
    print(f"  states covered : {len(all_states_seen)} / {len(VALID_STATES)}")
    print(f"  states missing : {', '.join(missing_states) if missing_states else '(none)'}")
    print(f"  errors         : {total_errors}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
