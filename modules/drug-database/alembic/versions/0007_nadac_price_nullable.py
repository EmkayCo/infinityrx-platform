"""Drop NOT NULL on drug_nadac_pricing.nadac_per_unit (+ history).

BUG-03a. CMS NADAC legitimately publishes rows with NULL prices for
discontinued or temporarily unavailable drugs. The original schema
declared `nadac_per_unit NUMERIC(18,6) NOT NULL`, so
`_validate_nadac_row` had to reject every null-price row — ~17% of
the feed (478K rows out of ~2M) was being thrown away even though
knowing the NDC exists in the NADAC catalog is useful for analytics
regardless of whether the current price is available.

This migration drops the NOT NULL on both the current table and the
history table. Rows with a null price will now load; downstream queries
that need only priced rows can filter `WHERE nadac_per_unit IS NOT NULL`.

Revision ID: 0007_nadac_price_nullable
Revises: 0006_widen_nadac_indicators
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_nadac_price_nullable"
down_revision: Union[str, None] = "0006_widen_nadac_indicators"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "drug_database"


def upgrade() -> None:
    for table in ("drug_nadac_pricing", "drug_nadac_pricing_history"):
        op.alter_column(
            table,
            "nadac_per_unit",
            existing_type=sa.Numeric(18, 6),
            nullable=True,
            schema=_SCHEMA,
        )


def downgrade() -> None:
    # Downgrade replaces any NULLs with 0 so the NOT NULL constraint can
    # be re-applied. Not ideal for real data — this is purely to keep
    # the migration reversible for test rollbacks.
    for table in ("drug_nadac_pricing", "drug_nadac_pricing_history"):
        op.execute(
            f"UPDATE {_SCHEMA}.{table} SET nadac_per_unit = 0 "
            f"WHERE nadac_per_unit IS NULL"
        )
        op.alter_column(
            table,
            "nadac_per_unit",
            existing_type=sa.Numeric(18, 6),
            nullable=False,
            schema=_SCHEMA,
        )
