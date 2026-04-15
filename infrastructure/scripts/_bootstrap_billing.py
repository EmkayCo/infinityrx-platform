"""
Bootstrap billing.* tables via metadata.create_all().

WORKAROUND for a pre-existing missing-migrations gap: modules/billing/ has
~30 SQLAlchemy models in src/models/tables.py but NO alembic migration
history that creates them. Running this script imports BillingBase and
materializes every table the metadata knows about, idempotently.

Should be replaced by a proper alembic migration set under
modules/billing/alembic/. Tracked in tasks/loader-bugs.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = REPO_ROOT / "modules" / "billing"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(MODULE_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

from src.models.tables import BillingBase  # noqa: E402,F401


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set", file=sys.stderr)
        return 2
    sync_url = db_url.replace("+asyncpg", "+psycopg2")

    engine = create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS billing"))
    BillingBase.metadata.create_all(engine)
    print("✓ billing schema bootstrapped via metadata.create_all()")
    return 0


if __name__ == "__main__":
    sys.exit(main())
