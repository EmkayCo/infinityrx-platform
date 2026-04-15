"""
Bootstrap prescriber-directory schema via metadata.create_all().

WORKAROUND for a pre-existing migration gap: alembic migration 0004 ALTERs
prescriber_dir.prescribers but no prior migration creates the table. This
script imports the Prescriber model metadata and runs CREATE TABLE for every
table the module needs, idempotently.

Should be replaced by a proper 0000_baseline alembic migration. Tracked as
task #15 in this session.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "modules" / "prescriber-directory"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(MODULE_ROOT))

from sqlalchemy import create_engine  # noqa: E402

from shared.db.base import Base  # noqa: E402,F401
from src.models.tables import (  # noqa: E402,F401
    CredentialAlert,
    DataRefreshLog,
    Prescriber,
    PrescriberBase,
    PrescriberPharmacyRelationship,
    PracticeAffiliation,
    StatePrescribingRule,
    TaxonomyCode,
)
from src.models.nppes_tables import (  # noqa: E402,F401
    NppesPrescriberDetail,
    PrescriberAddress,
    PrescriberIdentifier,
    PrescriberTaxonomy,
)


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2
    sync_url = db_url.replace("+asyncpg", "+psycopg2")

    engine = create_engine(sync_url)
    with engine.begin() as conn:
        from sqlalchemy import text
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS prescriber_dir"))

    # PrescriberBase carries every model in this module.
    PrescriberBase.metadata.create_all(engine)
    print("✓ prescriber-directory schema bootstrapped via metadata.create_all()")
    return 0


if __name__ == "__main__":
    sys.exit(main())
