"""Drop Medicare Part D Prescribers PUF table.

Removes prescriber_dir.medicare_part_d_utilization (and its three indexes)
created in 0002_medicare_tables. The Part D Prescribers PUF loader is
out of scope for this platform — all other CMS/FDA/SAM reference data
loaders remain.

Sibling table prescriber_dir.medicare_opt_out (also created in 0002)
stays — it's independently useful.

Revision ID: 0005_drop_part_d_utilization
Revises: 0004_prescriber_excl_cols
Create Date: 2026-04-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005_drop_part_d_utilization"
down_revision: Union[str, None] = "0004_prescriber_excl_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "prescriber_dir"


def upgrade() -> None:
    op.drop_index(
        "idx_part_d_state",
        table_name="medicare_part_d_utilization",
        schema=_SCHEMA,
    )
    op.drop_index(
        "idx_part_d_prscrbr_type",
        table_name="medicare_part_d_utilization",
        schema=_SCHEMA,
    )
    op.drop_index(
        "idx_part_d_year",
        table_name="medicare_part_d_utilization",
        schema=_SCHEMA,
    )
    op.drop_table("medicare_part_d_utilization", schema=_SCHEMA)


def downgrade() -> None:
    # Mirror of 0002_medicare_tables upgrade() for medicare_part_d_utilization.
    # Data is not restored — downgrade only rebuilds the empty schema so a
    # re-upgrade of downstream migrations doesn't fail on a missing table.
    op.create_table(
        "medicare_part_d_utilization",
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
        sa.Column("tot_clms", sa.Integer(), nullable=True),
        sa.Column("tot_30day_fills", sa.Integer(), nullable=True),
        sa.Column("tot_day_suply", sa.Integer(), nullable=True),
        sa.Column("tot_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("tot_benes", sa.Integer(), nullable=True),
        sa.Column("brnd_clms", sa.Integer(), nullable=True),
        sa.Column("brnd_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("gnrc_clms", sa.Integer(), nullable=True),
        sa.Column("gnrc_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("othr_clms", sa.Integer(), nullable=True),
        sa.Column("othr_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("mapd_clms", sa.Integer(), nullable=True),
        sa.Column("mapd_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("pdp_clms", sa.Integer(), nullable=True),
        sa.Column("pdp_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("lis_clms", sa.Integer(), nullable=True),
        sa.Column("lis_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("opioid_clms", sa.Integer(), nullable=True),
        sa.Column("opioid_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("opioid_prscrbr_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("opioid_la_clms", sa.Integer(), nullable=True),
        sa.Column("opioid_la_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("antbtc_clms", sa.Integer(), nullable=True),
        sa.Column("antbtc_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("antpsycht_ge65_clms", sa.Integer(), nullable=True),
        sa.Column("antpsycht_ge65_drug_cst", sa.Numeric(18, 2), nullable=True),
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
        sa.Column("ge65_tot_clms", sa.Integer(), nullable=True),
        sa.Column("ge65_tot_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("ge65_brnd_clms", sa.Integer(), nullable=True),
        sa.Column("ge65_brnd_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("ge65_gnrc_clms", sa.Integer(), nullable=True),
        sa.Column("ge65_gnrc_drug_cst", sa.Numeric(18, 2), nullable=True),
        sa.Column("ge65_othr_clms", sa.Integer(), nullable=True),
        sa.Column("ge65_othr_drug_cst", sa.Numeric(18, 2), nullable=True),
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
