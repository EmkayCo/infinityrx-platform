"""Government program BIN/PCN reference table for Anti-Kickback Statute compliance.

Creates:
  shared.government_program_bins

Revision ID: 0009_government_program_bins
Revises: 0008_compliance_reference_tables
Create Date: 2026-04-14

LESSON-011: Global reference table — no tenant_id, no TenantScopedMixin.
Government program BINs are federal/state reference data shared across all tenants.
Anti-Kickback Statute (AKS) requires blocking copay assistance cards when the
payer is a government program (Medicare, Medicaid, TRICARE, VA, FEP, IHS, CHAMPVA).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_government_program_bins"
down_revision: Union[str, None] = "0008_compliance_reference_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "shared"


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')

    op.create_table(
        "government_program_bins",
        sa.Column(
            "id",
            sa.String(36),
            nullable=False,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("bin", sa.String(6), nullable=False),
        sa.Column("pcn", sa.String(20), nullable=True),
        sa.Column("group_number", sa.String(20), nullable=True),
        sa.Column("plan_type", sa.String(50), nullable=False),
        sa.Column("plan_subtype", sa.String(100), nullable=True),
        sa.Column("pbm_name", sa.String(200), nullable=True),
        sa.Column("plan_name", sa.String(500), nullable=True),
        sa.Column("mco_name", sa.String(300), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column(
            "government_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("occ_codes", sa.Text(), nullable=True),
        sa.Column(
            "confidence",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'HIGH'"),
        ),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_government_program_bins"),
        # COALESCE(pcn,'') and COALESCE(group_number,'') handled in application layer;
        # unique constraint covers the three columns together.
        sa.UniqueConstraint(
            "bin",
            "pcn",
            "group_number",
            name="uq_gov_bins_bin_pcn_group",
        ),
        schema=SCHEMA,
    )

    op.create_index(
        "idx_gov_bins_bin",
        "government_program_bins",
        ["bin"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_gov_bins_bin_pcn",
        "government_program_bins",
        ["bin", "pcn"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_gov_bins_plan_type",
        "government_program_bins",
        ["plan_type"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_gov_bins_state",
        "government_program_bins",
        ["state"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("idx_gov_bins_state", table_name="government_program_bins", schema=SCHEMA)
    op.drop_index("idx_gov_bins_plan_type", table_name="government_program_bins", schema=SCHEMA)
    op.drop_index("idx_gov_bins_bin_pcn", table_name="government_program_bins", schema=SCHEMA)
    op.drop_index("idx_gov_bins_bin", table_name="government_program_bins", schema=SCHEMA)
    op.drop_table("government_program_bins", schema=SCHEMA)
