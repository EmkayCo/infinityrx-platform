"""Pharmacy exclusion cross-reference table.

Creates:
  pharmacy_dir.pharmacy_exclusion_xref

Revision ID: 0002_pharmacy_exclusion_xref
Revises: 0001_ncpdp_tables
Create Date: 2026-04-14

LESSON-010: NPI plaintext — public identifier, do NOT encrypt.
LESSON-011: Global reference table — no tenant_id, no TenantScopedMixin.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_pharmacy_exclusion_xref"
down_revision: Union[str, None] = "0001_ncpdp_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "pharmacy_dir"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ── pharmacy_exclusion_xref ──────────────────────────────────────────────
    op.create_table(
        "pharmacy_exclusion_xref",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pharmacy_npi", sa.String(10), nullable=False),
        sa.Column("exclusion_source", sa.String(50), nullable=False),
        sa.Column("exclusion_date", sa.Date(), nullable=True),
        sa.Column("reinstatement_date", sa.Date(), nullable=True),
        sa.Column("exclusion_type", sa.String(100), nullable=True),
        sa.Column("uei_sam", sa.String(12), nullable=True),
        sa.Column("source_record_id", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pharmacy_exclusion_xref"),
        sa.UniqueConstraint(
            "pharmacy_npi", "exclusion_source", "exclusion_date",
            name="uq_pharmacy_exclusion_npi_source_date",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_pharmacy_xref_npi",
        "pharmacy_exclusion_xref",
        ["pharmacy_npi"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_pharmacy_xref_source",
        "pharmacy_exclusion_xref",
        ["exclusion_source"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_pharmacy_xref_uei_sam",
        "pharmacy_exclusion_xref",
        ["uei_sam"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("pharmacy_exclusion_xref", schema=_SCHEMA)
