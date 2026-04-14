"""Medicare Part D utilization and Opt-Out affidavit tables.

Creates:
  prescriber_dir.medicare_part_d_utilization
  prescriber_dir.medicare_opt_out

Revision ID: 0002_medicare_tables
Revises: 0001_nppes
Create Date: 2026-04-14

LESSON-010: NPI plaintext — public identifier, do NOT encrypt.
LESSON-011: Global reference tables — no tenant_id, no TenantScopedMixin.
financial-precision.md: All money columns are Numeric — NEVER Float.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002_medicare_tables"
down_revision: Union[str, None] = "0001_nppes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "prescriber_dir"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ── medicare_part_d_utilization ─────────────────────────────────────────
    op.create_table(
        "medicare_part_d_utilization",
        # Identity / PK
        sa.Column("npi", sa.String(10), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("prscrbr_last_org_name", sa.String(255), nullable=True),
        sa.Column("prscrbr_first_name", sa.String(100), nullable=True),
        sa.Column("prscrbr_city", sa.String(100), nullable=True),
        sa.Column("prscrbr_state_abrvtn", sa.String(2), nullable=True),
        sa.Column("prscrbr_state_fips", sa.String(5), nullable=True),
        sa.Column("prscrbr_zip5", sa.String(5), nullable=True),
        sa.Column("prscrbr_ruca", sa.String(10), nullable=True),
        sa.Column("prscrbr_cntry", sa.String(100), nullable=True),
        sa.Column("prscrbr_type", sa.String(100), nullable=True),
        sa.Column("prscrbr_type_src", sa.String(50), nullable=True),
        # Utilization totals
        sa.Column("tot_clms", sa.Integer(), nullable=True),
        sa.Column("tot_30day_fills", sa.Integer(), nullable=True),
        sa.Column("tot_day_suply", sa.Integer(), nullable=True),
        sa.Column("tot_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("tot_benes", sa.Integer(), nullable=True),
        # Brand/Generic split
        sa.Column("brnd_clms", sa.Integer(), nullable=True),
        sa.Column("brnd_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("gnrc_clms", sa.Integer(), nullable=True),
        sa.Column("gnrc_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("othr_clms", sa.Integer(), nullable=True),
        sa.Column("othr_drug_cst", sa.Numeric(18, 2), nullable=True),
        # Plan split
        sa.Column("mapd_clms", sa.Integer(), nullable=True),
        sa.Column("mapd_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("pdp_clms", sa.Integer(), nullable=True),
        sa.Column("pdp_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("lis_clms", sa.Integer(), nullable=True),
        sa.Column("lis_drug_cst", sa.Numeric(18, 2), nullable=True),
        # Drug classes
        sa.Column("opioid_clms", sa.Integer(), nullable=True),
        sa.Column("opioid_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("opioid_prscrbr_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("opioid_la_clms", sa.Integer(), nullable=True),
        sa.Column("opioid_la_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("antbtc_clms", sa.Integer(), nullable=True),
        sa.Column("antbtc_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("antpsycht_ge65_clms", sa.Integer(), nullable=True),
        sa.Column("antpsycht_ge65_drug_cst", sa.Numeric(18, 2), nullable=True),
        # Beneficiary demographics
        sa.Column("bene_avg_age", sa.Integer(), nullable=True),
        sa.Column("bene_avg_risk_scre", sa.Numeric(6, 4), nullable=True),
        sa.Column("bene_race_wht_cnt", sa.Integer(), nullable=True),
        sa.Column("bene_race_black_cnt", sa.Integer(), nullable=True),
        sa.Column("bene_race_api_cnt", sa.Integer(), nullable=True),
        sa.Column("bene_race_hspnc_cnt", sa.Integer(), nullable=True),
        sa.Column("bene_race_natind_cnt", sa.Integer(), nullable=True),
        sa.Column("bene_race_othr_cnt", sa.Integer(), nullable=True),
        sa.Column("bene_dual_cnt", sa.Integer(), nullable=True),
        sa.Column("bene_ndual_cnt", sa.Integer(), nullable=True),
        # 65+ subset
        sa.Column("ge65_tot_clms", sa.Integer(), nullable=True),
        sa.Column("ge65_tot_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("ge65_brnd_clms", sa.Integer(), nullable=True),
        sa.Column("ge65_brnd_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("ge65_gnrc_clms", sa.Integer(), nullable=True),
        sa.Column("ge65_gnrc_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("ge65_othr_clms", sa.Integer(), nullable=True),
        sa.Column("ge65_othr_drug_cst", sa.Numeric(18, 2), nullable=True),
        # Raw payload
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("npi", "year", name="pk_part_d_npi_year"),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_part_d_year", "medicare_part_d_utilization", ["year"], schema=_SCHEMA
    )
    op.create_index(
        "idx_part_d_prscrbr_type",
        "medicare_part_d_utilization",
        ["prscrbr_type"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_part_d_state",
        "medicare_part_d_utilization",
        ["prscrbr_state_abrvtn"],
        schema=_SCHEMA,
    )

    # ── medicare_opt_out ─────────────────────────────────────────────────────
    op.create_table(
        "medicare_opt_out",
        sa.Column("npi", sa.String(10), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("middle_name", sa.String(100), nullable=True),
        sa.Column("specialty", sa.String(255), nullable=True),
        sa.Column("opt_out_effective_date", sa.Date(), nullable=True),
        sa.Column("opt_out_end_date", sa.Date(), nullable=True),
        sa.Column("order_referring", sa.Boolean(), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("zip", sa.String(10), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("npi"),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_opt_out_end_date", "medicare_opt_out", ["opt_out_end_date"], schema=_SCHEMA
    )
    op.create_index(
        "idx_opt_out_state", "medicare_opt_out", ["state"], schema=_SCHEMA
    )


def downgrade() -> None:
    op.drop_table("medicare_opt_out", schema=_SCHEMA)
    op.drop_table("medicare_part_d_utilization", schema=_SCHEMA)
