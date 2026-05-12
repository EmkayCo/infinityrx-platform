"""program_config Wave 26 Phase C.7-PRE-B + PRE-C tables.

Adds 5 new tables to program_config:
  PRE-B (Network Tier):
    1. program_networks
    2. program_network_pharmacies
    3. program_hub_spoke_pairs
  PRE-C (Member-Drug Accumulator):
    4. member_drug_program_accumulators
    5. member_program_flags

All 5 are tenant-scoped (TenantScopedMixin in ORM). Includes:
  - Check constraints for non-negative counts/dollars and
    effective-dating sanity (end_date >= effective_date when set)
  - RLS policies (FORCE + NULLIF-wrapped tenant predicate) on all 5
  - Partial unique index for "one active membership per
    (program, pharmacy)" on program_network_pharmacies

Revision ID: 0004_pre_b_pre_c_tables
Revises: 0003_pc_rls
Create Date: 2026-04-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_pre_b_pre_c_tables"
down_revision: Union[str, None] = "0003_pc_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "program_config"
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"
_TENANT_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)
_NEW_TABLES = (
    "program_networks",
    "program_network_pharmacies",
    "program_hub_spoke_pairs",
    "member_drug_program_accumulators",
    "member_program_flags",
)


def upgrade() -> None:
    # ── 1. program_networks ──
    op.create_table(
        "program_networks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "program_id", "name", name="uq_program_network_name"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_program_networks_tenant_id", "program_networks", ["tenant_id"], schema=_SCHEMA
    )
    op.create_index(
        "idx_program_network_program",
        "program_networks", ["tenant_id", "program_id"], schema=_SCHEMA,
    )

    # ── 2. program_network_pharmacies ──
    op.create_table(
        "program_network_pharmacies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("network_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pharmacy_npi", sa.String(10), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= effective_date",
            name="ck_pnp_dates_lifecycle",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_program_network_pharmacies_tenant_id",
        "program_network_pharmacies", ["tenant_id"], schema=_SCHEMA,
    )
    op.create_index(
        "idx_program_network_pharmacy_lookup",
        "program_network_pharmacies",
        ["tenant_id", "program_id", "pharmacy_npi"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_program_network_pharmacy_network",
        "program_network_pharmacies",
        ["tenant_id", "network_id"],
        schema=_SCHEMA,
    )
    # Partial unique: at most one active (end_date IS NULL) membership
    # per (tenant, program, pharmacy_npi). Allows historical inactive
    # rows to coexist for audit/effective-date reconstruction.
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_program_network_pharmacy_active
          ON {_SCHEMA}.program_network_pharmacies
            (tenant_id, program_id, pharmacy_npi)
          WHERE end_date IS NULL;
        """
    )

    # ── 3. program_hub_spoke_pairs ──
    op.create_table(
        "program_hub_spoke_pairs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hub_pharmacy_npi", sa.String(10), nullable=False),
        sa.Column("spoke_pharmacy_npi", sa.String(10), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "program_id", "spoke_pharmacy_npi",
            name="uq_program_spoke_unique",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= effective_date",
            name="ck_hub_spoke_dates_lifecycle",
        ),
        sa.CheckConstraint(
            "hub_pharmacy_npi <> spoke_pharmacy_npi",
            name="ck_hub_spoke_distinct",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_program_hub_spoke_pairs_tenant_id",
        "program_hub_spoke_pairs", ["tenant_id"], schema=_SCHEMA,
    )
    op.create_index(
        "idx_program_hub_spoke_lookup",
        "program_hub_spoke_pairs",
        ["tenant_id", "program_id", "spoke_pharmacy_npi"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_program_hub_spoke_hub",
        "program_hub_spoke_pairs",
        ["tenant_id", "program_id", "hub_pharmacy_npi"],
        schema=_SCHEMA,
    )

    # ── 4. member_drug_program_accumulators ──
    op.create_table(
        "member_drug_program_accumulators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", sa.String(50), nullable=False),
        sa.Column("drug_brand", sa.String(100), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_year", sa.Integer(), nullable=False),
        sa.Column("fills_used", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "dollars_used", sa.Numeric(12, 2), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "scc_overrides_used", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "member_id", "drug_brand", "program_id", "calendar_year",
            name="uq_member_drug_program_year",
        ),
        sa.CheckConstraint("fills_used >= 0", name="ck_accumulator_fills_nonnegative"),
        sa.CheckConstraint("dollars_used >= 0", name="ck_accumulator_dollars_nonnegative"),
        sa.CheckConstraint(
            "scc_overrides_used >= 0", name="ck_accumulator_scc_nonnegative"
        ),
        sa.CheckConstraint(
            "calendar_year >= 2020 AND calendar_year <= 2099",
            name="ck_accumulator_year_sane",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_member_drug_program_accumulators_tenant_id",
        "member_drug_program_accumulators", ["tenant_id"], schema=_SCHEMA,
    )
    op.create_index(
        "idx_accumulator_lookup",
        "member_drug_program_accumulators",
        ["tenant_id", "member_id", "drug_brand", "program_id", "calendar_year"],
        schema=_SCHEMA,
    )

    # ── 5. member_program_flags ──
    op.create_table(
        "member_program_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", sa.String(50), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flag_type", sa.String(100), nullable=False),
        sa.Column("flag_value", postgresql.JSONB(), nullable=False),
        sa.Column(
            "effective_from", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_member_flag_dates_lifecycle",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_member_program_flags_tenant_id",
        "member_program_flags", ["tenant_id"], schema=_SCHEMA,
    )
    op.create_index(
        "idx_member_program_flag_lookup",
        "member_program_flags",
        ["tenant_id", "member_id", "program_id", "flag_type"],
        schema=_SCHEMA,
    )

    # ── RLS for all 5 new tables ──
    for table in _NEW_TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
              FOR ALL
              TO {_ROLES}
              USING      ({_TENANT_PREDICATE})
              WITH CHECK ({_TENANT_PREDICATE});
            """
        )


def downgrade() -> None:
    for table in _NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.{table};")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY;")
    op.drop_table("member_program_flags", schema=_SCHEMA)
    op.drop_table("member_drug_program_accumulators", schema=_SCHEMA)
    op.drop_table("program_hub_spoke_pairs", schema=_SCHEMA)
    op.execute(
        f"DROP INDEX IF EXISTS {_SCHEMA}.uq_program_network_pharmacy_active;"
    )
    op.drop_table("program_network_pharmacies", schema=_SCHEMA)
    op.drop_table("program_networks", schema=_SCHEMA)
