"""DEA registrations and prescriber exclusion cross-reference tables.

Creates:
  prescriber_dir.dea_registrations
  prescriber_dir.prescriber_exclusion_xref

Revision ID: 0003_dea_compliance_tables
Revises: 0002_medicare_tables
Create Date: 2026-04-14

LESSON-010: NPI plaintext — public identifier, do NOT encrypt.
LESSON-011: Global reference tables — no tenant_id, no TenantScopedMixin.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003_dea_compliance_tables"
down_revision: Union[str, None] = "0002_medicare_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "prescriber_dir"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ── dea_registrations ────────────────────────────────────────────────────
    op.create_table(
        "dea_registrations",
        sa.Column("dea_number", sa.String(9), nullable=False),
        sa.Column("registrant_name", sa.String(255), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("zip", sa.String(10), nullable=True),
        sa.Column("business_activity", sa.String(100), nullable=True),
        sa.Column("drug_schedules_authorized", JSONB(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("registration_status", sa.String(50), nullable=True),
        sa.Column("npi", sa.String(10), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("dea_number", name="pk_dea_registrations"),
        schema=_SCHEMA,
    )
    op.create_index("idx_dea_npi", "dea_registrations", ["npi"], schema=_SCHEMA)
    op.create_index(
        "idx_dea_activity_status",
        "dea_registrations",
        ["business_activity", "registration_status"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_dea_expiration_date",
        "dea_registrations",
        ["expiration_date"],
        schema=_SCHEMA,
    )

    # ── prescriber_exclusion_xref ────────────────────────────────────────────
    op.create_table(
        "prescriber_exclusion_xref",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prescriber_npi", sa.String(10), nullable=False),
        sa.Column("exclusion_source", sa.String(50), nullable=False),
        sa.Column("exclusion_date", sa.Date(), nullable=True),
        sa.Column("reinstatement_date", sa.Date(), nullable=True),
        sa.Column("exclusion_type", sa.String(100), nullable=True),
        sa.Column("source_record_id", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_prescriber_exclusion_xref"),
        sa.UniqueConstraint(
            "prescriber_npi", "exclusion_source", "exclusion_date",
            name="uq_prescriber_exclusion_npi_source_date",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_prescriber_xref_npi",
        "prescriber_exclusion_xref",
        ["prescriber_npi"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_prescriber_xref_source",
        "prescriber_exclusion_xref",
        ["exclusion_source"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("prescriber_exclusion_xref", schema=_SCHEMA)
    op.drop_table("dea_registrations", schema=_SCHEMA)
