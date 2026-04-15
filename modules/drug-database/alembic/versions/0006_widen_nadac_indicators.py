"""Widen pharmacy_type_indicator + otc to VARCHAR(5) in drug_nadac_pricing.

BUG-03 fix: the CMS NADAC source file publishes multi-character values for
these columns — notably `C/I` (Chain/Independent combined), which is 3
characters — that don't fit the original VARCHAR(1) declaration and caused
`psycopg2.errors.StringDataRightTruncation: value too long for type
character varying(1)` on every batch.

Widening to VARCHAR(5) gives headroom for known values (`C`, `I`, `C/I`,
`Y`, `N`) plus a small margin. Applies to both the current table and the
history table so historical rows can carry the same values.

Revision ID: 0006_widen_nadac_indicators
Revises: 0005_fda_supplementary
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_widen_nadac_indicators"
down_revision: Union[str, None] = "0005_fda_supplementary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "drug_database"


def upgrade() -> None:
    for table in ("drug_nadac_pricing", "drug_nadac_pricing_history"):
        op.alter_column(
            table,
            "pharmacy_type_indicator",
            existing_type=sa.String(1),
            type_=sa.String(5),
            existing_nullable=True,
            schema=_SCHEMA,
        )
        op.alter_column(
            table,
            "otc",
            existing_type=sa.String(1),
            type_=sa.String(5),
            existing_nullable=True,
            schema=_SCHEMA,
        )


def downgrade() -> None:
    for table in ("drug_nadac_pricing", "drug_nadac_pricing_history"):
        # Downgrade truncates — must strip multi-char values first in a
        # real deploy. Here we just USING left(x, 1).
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} "
            f"ALTER COLUMN pharmacy_type_indicator "
            f"TYPE VARCHAR(1) USING LEFT(pharmacy_type_indicator, 1)"
        )
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} "
            f"ALTER COLUMN otc "
            f"TYPE VARCHAR(1) USING LEFT(otc, 1)"
        )
