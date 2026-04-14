"""Create drug_database pricing tables: NADAC and ASP current + history.

This is the SECOND migration for the drug-database module.  It adds four
pricing tables to the ``drug_database`` schema populated by the
CMSNADACIngester and CMSASPIngester pipelines.

Revision chain:
  0001_ndc     (T3)  — drugs, packages, ingredients, pharm classes
  0002_pricing (T4, this file) — NADAC + ASP current + history tables
  0003         (T5)  — RESERVED: Orange Book therapeutic equivalence overlay

T5 instructions:
  Set down_revision = "0002_pricing" in your 0003 migration.
  The application_number column on drug_database.drugs (migration 0001_ndc)
  contains NDA/ANDA numbers for Orange Book joins.

Data rules reflected in DDL:
  - All money/price columns use NUMERIC(18, 6) — never FLOAT or REAL.
  - No float anywhere in this migration.
  - Global reference data — no tenant_id column (LESSON-011).

Revision ID: 0002_pricing
Revises: 0001_ndc
Create Date: 2026-04-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0002_pricing"
down_revision: Union[str, None] = "0001_ndc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "drug_database"


def upgrade() -> None:
    # Schema was already created by 0001_ndc; CREATE IF NOT EXISTS is safe.
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ------------------------------------------------------------------ drug_nadac_pricing
    op.create_table(
        "drug_nadac_pricing",
        sa.Column(
            "ndc_11", sa.String(11), primary_key=True,
            comment="11-digit normalized NDC (5-4-2); upsert key",
        ),
        sa.Column("ndc_description", sa.Text, nullable=True),
        sa.Column(
            "nadac_per_unit", sa.Numeric(18, 6), nullable=False,
            comment="NADAC price per unit — NUMERIC(18,6); never FLOAT",
        ),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("pricing_unit", sa.String(10), nullable=True,
                  comment="ML, GM, EA, etc."),
        sa.Column("pharmacy_type_indicator", sa.String(1), nullable=True,
                  comment="C=Chain, I=Independent, blank=combined"),
        sa.Column("otc", sa.String(1), nullable=True, comment="Y=OTC, N=Rx"),
        sa.Column("explanation_code", sa.String(10), nullable=True),
        sa.Column("classification", sa.String(10), nullable=True,
                  comment="B, G, B-BIO, B-ANDA"),
        sa.Column(
            "generic_nadac_per_unit", sa.Numeric(18, 6), nullable=True,
            comment="Corresponding generic NADAC per unit — NUMERIC(18,6); nullable",
        ),
        sa.Column("generic_effective_date", sa.Date, nullable=True),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_nadac_pricing_ndc_11", "drug_nadac_pricing", ["ndc_11"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_nadac_pricing_effective_date", "drug_nadac_pricing", ["effective_date"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_nadac_pricing_as_of_date", "drug_nadac_pricing", ["as_of_date"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------ drug_nadac_pricing_history
    op.create_table(
        "drug_nadac_pricing_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ndc_11", sa.String(11), nullable=False,
                  comment="11-digit normalized NDC (5-4-2)"),
        sa.Column("ndc_description", sa.Text, nullable=True),
        sa.Column(
            "nadac_per_unit", sa.Numeric(18, 6), nullable=False,
            comment="NADAC price per unit — NUMERIC(18,6); never FLOAT",
        ),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("pricing_unit", sa.String(10), nullable=True),
        sa.Column("pharmacy_type_indicator", sa.String(1), nullable=True),
        sa.Column("otc", sa.String(1), nullable=True),
        sa.Column("explanation_code", sa.String(10), nullable=True),
        sa.Column("classification", sa.String(10), nullable=True),
        sa.Column(
            "generic_nadac_per_unit", sa.Numeric(18, 6), nullable=True,
            comment="Corresponding generic NADAC per unit — NUMERIC(18,6); nullable",
        ),
        sa.Column("generic_effective_date", sa.Date, nullable=True),
        sa.Column("as_of_date", sa.Date, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=_SCHEMA,
    )
    op.create_unique_constraint(
        "uq_nadac_history_ndc_eff_asof",
        "drug_nadac_pricing_history",
        ["ndc_11", "effective_date", "as_of_date"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_nadac_history_ndc_11", "drug_nadac_pricing_history", ["ndc_11"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_nadac_history_effective_date", "drug_nadac_pricing_history",
        ["effective_date"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_nadac_history_as_of_date", "drug_nadac_pricing_history",
        ["as_of_date"], schema=_SCHEMA,
    )

    # ------------------------------------------------------------------ drug_asp_pricing
    op.create_table(
        "drug_asp_pricing",
        sa.Column(
            "hcpcs_code", sa.String(10), primary_key=True,
            comment="HCPCS code; upsert key",
        ),
        sa.Column("short_description", sa.Text, nullable=True),
        sa.Column("dosage", sa.String(100), nullable=True,
                  comment="HCPCS Code Dosage, e.g. '10 mg'"),
        sa.Column(
            "payment_limit", sa.Numeric(18, 6), nullable=False,
            comment="Payment limit (ASP + 6%) — NUMERIC(18,6); never FLOAT",
        ),
        sa.Column("vaccine_awp", sa.String(1), nullable=True,
                  comment="Y/N — may be absent in some quarters"),
        sa.Column(
            "effective_quarter", sa.String(7), nullable=False,
            comment="YYYYQN, e.g. '2026Q2'",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_asp_pricing_hcpcs_code", "drug_asp_pricing", ["hcpcs_code"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_asp_pricing_effective_quarter", "drug_asp_pricing", ["effective_quarter"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------ drug_asp_pricing_history
    op.create_table(
        "drug_asp_pricing_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("hcpcs_code", sa.String(10), nullable=False),
        sa.Column("short_description", sa.Text, nullable=True),
        sa.Column("dosage", sa.String(100), nullable=True),
        sa.Column(
            "payment_limit", sa.Numeric(18, 6), nullable=False,
            comment="Payment limit (ASP + 6%) — NUMERIC(18,6); never FLOAT",
        ),
        sa.Column("vaccine_awp", sa.String(1), nullable=True),
        sa.Column("effective_quarter", sa.String(7), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=_SCHEMA,
    )
    op.create_unique_constraint(
        "uq_asp_history_hcpcs_quarter",
        "drug_asp_pricing_history",
        ["hcpcs_code", "effective_quarter"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_asp_history_hcpcs_code", "drug_asp_pricing_history", ["hcpcs_code"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_asp_history_effective_quarter", "drug_asp_pricing_history",
        ["effective_quarter"], schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("drug_asp_pricing_history", schema=_SCHEMA)
    op.drop_table("drug_asp_pricing", schema=_SCHEMA)
    op.drop_table("drug_nadac_pricing_history", schema=_SCHEMA)
    op.drop_table("drug_nadac_pricing", schema=_SCHEMA)
