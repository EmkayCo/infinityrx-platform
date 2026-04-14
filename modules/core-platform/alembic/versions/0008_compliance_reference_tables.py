"""OIG LEIE exclusions and SAM.gov exclusions reference tables.

Creates:
  shared.oig_leie_exclusions
  shared.sam_exclusions

Revision ID: 0008_compliance_reference_tables
Revises: 0007_ingestion_tracking
Create Date: 2026-04-14

LESSON-010: NPI plaintext — public identifier, do NOT encrypt.
LESSON-011: Global reference tables — no tenant_id, no TenantScopedMixin.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0008_compliance_reference_tables"
down_revision: Union[str, None] = "0007_ingestion_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "shared"


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')

    # ── oig_leie_exclusions ──────────────────────────────────────────────────
    op.create_table(
        "oig_leie_exclusions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lastname", sa.String(255), nullable=True),
        sa.Column("firstname", sa.String(255), nullable=True),
        sa.Column("midname", sa.String(255), nullable=True),
        sa.Column("busname", sa.String(500), nullable=True),
        sa.Column("general", sa.String(255), nullable=True),
        sa.Column("specialty", sa.String(255), nullable=True),
        sa.Column("upin", sa.String(20), nullable=True),
        sa.Column("npi", sa.String(10), nullable=True),
        sa.Column("dob", sa.String(10), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("zip", sa.String(10), nullable=True),
        sa.Column("excltype", sa.String(50), nullable=True),
        sa.Column("excldate", sa.Date(), nullable=True),
        sa.Column("reindate", sa.Date(), nullable=True),
        sa.Column("waiverdate", sa.Date(), nullable=True),
        sa.Column("waiverstate", sa.String(2), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_oig_leie_exclusions"),
        sa.UniqueConstraint(
            "lastname", "firstname", "busname", "excldate",
            name="uq_oig_leie_natural_key",
        ),
        schema=SCHEMA,
    )
    op.create_index("idx_leie_npi", "oig_leie_exclusions", ["npi"], schema=SCHEMA)
    op.create_index(
        "idx_leie_name_dob",
        "oig_leie_exclusions",
        ["lastname", "firstname", "dob"],
        schema=SCHEMA,
    )
    op.create_index("idx_leie_excldate", "oig_leie_exclusions", ["excldate"], schema=SCHEMA)
    op.create_index("idx_leie_reindate", "oig_leie_exclusions", ["reindate"], schema=SCHEMA)

    # ── sam_exclusions ───────────────────────────────────────────────────────
    op.create_table(
        "sam_exclusions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("classification_type", sa.String(100), nullable=True),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("address_line_1", sa.String(255), nullable=True),
        sa.Column("address_line_2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state_province", sa.String(100), nullable=True),
        sa.Column("zip_postal_code", sa.String(20), nullable=True),
        sa.Column("country_code", sa.String(3), nullable=True),
        sa.Column("duns_number", sa.String(20), nullable=True),
        sa.Column("uei_sam", sa.String(12), nullable=True),
        sa.Column("cage_code", sa.String(10), nullable=True),
        sa.Column("npi", sa.String(10), nullable=True),
        sa.Column("exclusion_type", sa.String(100), nullable=True),
        sa.Column("exclusion_program", sa.String(100), nullable=True),
        sa.Column("agency", sa.String(255), nullable=True),
        sa.Column("active_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("ct_code", sa.String(20), nullable=True),
        sa.Column("additional_comments", sa.Text(), nullable=True),
        sa.Column("affiliations", JSONB(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sam_exclusions"),
        sa.UniqueConstraint(
            "classification_type", "name", "exclusion_type", "active_date",
            name="uq_sam_exclusions_natural_key",
        ),
        schema=SCHEMA,
    )
    op.create_index("idx_sam_npi", "sam_exclusions", ["npi"], schema=SCHEMA)
    op.create_index("idx_sam_uei_sam", "sam_exclusions", ["uei_sam"], schema=SCHEMA)
    op.create_index(
        "idx_sam_active_date", "sam_exclusions", ["active_date"], schema=SCHEMA
    )
    op.create_index(
        "idx_sam_termination_date", "sam_exclusions", ["termination_date"], schema=SCHEMA
    )
    op.create_index(
        "idx_sam_classification_type",
        "sam_exclusions",
        ["classification_type"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("sam_exclusions", schema=SCHEMA)
    op.drop_table("oig_leie_exclusions", schema=SCHEMA)
