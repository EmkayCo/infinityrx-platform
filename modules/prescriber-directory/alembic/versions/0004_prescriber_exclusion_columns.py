"""Add exclusion-tracking columns to prescriber_dir.prescribers.

Adds is_excluded / excluded_source / exclusion_date / exclusion_type to
the main prescribers table so OIG LEIE, DEA, and SAM cross-references
can flip the flag in-place during ingestion.

Revision ID: 0004_prescriber_exclusion_columns
Revises: 0003_dea_compliance_tables
Create Date: 2026-04-14
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_prescriber_excl_cols"
down_revision: Union[str, None] = "0003_dea_compliance_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "prescriber_dir"


def upgrade() -> None:
    with op.batch_alter_table("prescribers", schema=_SCHEMA) as batch:
        batch.add_column(sa.Column("is_excluded", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")))
        batch.add_column(sa.Column("excluded_source", sa.String(50), nullable=True))
        batch.add_column(sa.Column("exclusion_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("exclusion_type", sa.String(20), nullable=True))
    op.create_index(
        "ix_prescribers_is_excluded",
        "prescribers",
        ["is_excluded"],
        schema=_SCHEMA,
        postgresql_where=sa.text("is_excluded = TRUE"),
    )


def downgrade() -> None:
    op.drop_index("ix_prescribers_is_excluded", table_name="prescribers", schema=_SCHEMA)
    with op.batch_alter_table("prescribers", schema=_SCHEMA) as batch:
        batch.drop_column("exclusion_type")
        batch.drop_column("exclusion_date")
        batch.drop_column("excluded_source")
        batch.drop_column("is_excluded")
