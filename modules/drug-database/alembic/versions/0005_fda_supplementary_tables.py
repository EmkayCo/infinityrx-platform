"""Create drug_database FDA supplementary tables: drug_rems, drug_rems_ndc,
drug_shortages, drug_shortages_history, drug_purple_book.

This is the FIFTH migration for the drug-database module.

Revision chain:
  0001_ndc_tables         — drugs, packages, ingredients, pharm classes
  0002_pricing            — NADAC + ASP current + history tables
  0003_orange_book        — Orange Book therapeutic equivalence
  0004_rxnorm_tables      — RxNorm tables
  0005_fda_supplementary  (this file) — REMS, Drug Shortages, Purple Book

Upgrade: creates 5 tables with indexes and unique constraints.
Downgrade: drops all 5 tables in reverse order.

Revision ID: 0005_fda_supplementary
Revises: 0004_rxnorm_tables
Create Date: 2026-04-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic
revision: str = "0005_fda_supplementary"
down_revision: Union[str, None] = "0004_rxnorm_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "drug_database"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ------------------------------------------------------------------ drug_rems
    op.create_table(
        "drug_rems",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("application_number", sa.String(20), nullable=False),
        sa.Column("rems_program_name", sa.String(255), nullable=False),
        sa.Column("drug_name_brand", sa.String(255), nullable=True),
        sa.Column("drug_name_generic", sa.String(255), nullable=True),
        sa.Column("ndc_codes", JSONB, nullable=True,
                  comment="NDC codes covered by this REMS program"),
        sa.Column("rems_type", sa.String(50), nullable=True,
                  comment="Medication Guide | Communication Plan | ETASU"),
        sa.Column("etasu_requirements", JSONB, nullable=True,
                  comment="ETASU requirements dict: prescriber_cert, pharmacy_cert, patient_enrollment, etc."),
        sa.Column("initial_approval_date", sa.Date, nullable=True),
        sa.Column("most_recent_modification_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(30), nullable=True,
                  comment="Active | Modified | Released"),
        sa.Column("shared_system_name", sa.String(255), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True,
                  comment="Full raw openFDA label payload"),
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
    op.create_unique_constraint(
        "uq_drug_rems_pk",
        "drug_rems",
        ["application_number", "rems_program_name"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_rems_app_number",
        "drug_rems",
        ["application_number"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_rems_ndc_codes_gin",
        "drug_rems",
        ["ndc_codes"],
        schema=_SCHEMA,
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------ drug_rems_ndc
    op.create_table(
        "drug_rems_ndc",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rems_id", sa.Integer, nullable=False,
                  comment="FK to drug_rems.id"),
        sa.Column("ndc_11", sa.String(11), nullable=False),
        sa.Column("application_number", sa.String(20), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_rems_ndc_ndc11",
        "drug_rems_ndc",
        ["ndc_11"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_rems_ndc_rems_id",
        "drug_rems_ndc",
        ["rems_id"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------ drug_shortages
    op.create_table(
        "drug_shortages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("drug_name_generic", sa.String(255), nullable=False),
        sa.Column("application_number", sa.String(20), nullable=True),
        sa.Column("ndc_codes", JSONB, nullable=True),
        sa.Column("status", sa.String(30), nullable=True,
                  comment="Current | Resolved | Discontinued"),
        sa.Column("shortage_reason", sa.String(50), nullable=True,
                  comment="manufacturing_delay | demand_increase | raw_material | discontinuation | other"),
        sa.Column("date_first_posted", sa.Date, nullable=True),
        sa.Column("date_last_updated", sa.Date, nullable=True),
        sa.Column("date_resolved", sa.Date, nullable=True),
        sa.Column("manufacturers", JSONB, nullable=True),
        sa.Column("therapeutic_category", sa.String(255), nullable=True),
        sa.Column("estimated_resupply_date", sa.Date, nullable=True),
        sa.Column("alternative_therapies", JSONB, nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
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
    op.create_unique_constraint(
        "uq_drug_shortages_pk",
        "drug_shortages",
        ["drug_name_generic", "application_number"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_shortages_status",
        "drug_shortages",
        ["status"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_shortages_ndc_codes_gin",
        "drug_shortages",
        ["ndc_codes"],
        schema=_SCHEMA,
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------ drug_shortages_history (append-only)
    op.create_table(
        "drug_shortages_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_date", sa.Date, nullable=False,
                  comment="Date this snapshot was taken"),
        sa.Column("drug_name_generic", sa.String(255), nullable=False),
        sa.Column("application_number", sa.String(20), nullable=True),
        sa.Column("ndc_codes", JSONB, nullable=True),
        sa.Column("status", sa.String(30), nullable=True),
        sa.Column("shortage_reason", sa.String(50), nullable=True),
        sa.Column("date_first_posted", sa.Date, nullable=True),
        sa.Column("date_last_updated", sa.Date, nullable=True),
        sa.Column("date_resolved", sa.Date, nullable=True),
        sa.Column("manufacturers", JSONB, nullable=True),
        sa.Column("therapeutic_category", sa.String(255), nullable=True),
        sa.Column("estimated_resupply_date", sa.Date, nullable=True),
        sa.Column("alternative_therapies", JSONB, nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_shortages_history_generic",
        "drug_shortages_history",
        ["drug_name_generic"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_shortages_history_snapshot",
        "drug_shortages_history",
        ["snapshot_date"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_shortages_history_status",
        "drug_shortages_history",
        ["status"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------ drug_purple_book
    op.create_table(
        "drug_purple_book",
        sa.Column("bla_number", sa.String(20), primary_key=True,
                  comment="BLA application number — PK"),
        sa.Column("proprietary_name", sa.String(255), nullable=True),
        sa.Column("proper_name", sa.String(255), nullable=True),
        sa.Column("bla_type", sa.String(10), nullable=True,
                  comment="351(a) original | 351(k) biosimilar"),
        sa.Column("applicant", sa.String(255), nullable=True),
        sa.Column("strength", sa.String(255), nullable=True),
        sa.Column("dosage_form", sa.String(100), nullable=True),
        sa.Column("route", sa.String(100), nullable=True),
        sa.Column("product_presentation", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=True,
                  comment="Active | Discontinued"),
        sa.Column("licensure_date", sa.Date, nullable=True),
        sa.Column("interchangeable", sa.Boolean, nullable=True,
                  comment="CRITICAL for formulary substitution"),
        sa.Column("reference_product_bla", sa.String(20), nullable=True,
                  comment="BLA of the reference biologic (biosimilars only)"),
        sa.Column("reference_product_proper_name", sa.String(255), nullable=True),
        sa.Column("exclusivity_expiration_date", sa.Date, nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True,
                  comment="All CSV columns preserved as JSONB"),
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
        "ix_drug_purple_book_proprietary_name",
        "drug_purple_book",
        ["proprietary_name"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_purple_book_proper_name",
        "drug_purple_book",
        ["proper_name"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_purple_book_reference_bla",
        "drug_purple_book",
        ["reference_product_bla"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_purple_book_interchangeable",
        "drug_purple_book",
        ["interchangeable"],
        schema=_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("drug_purple_book", schema=_SCHEMA)
    op.drop_index("ix_drug_shortages_history_status", table_name="drug_shortages_history", schema=_SCHEMA)
    op.drop_index("ix_drug_shortages_history_snapshot", table_name="drug_shortages_history", schema=_SCHEMA)
    op.drop_index("ix_drug_shortages_history_generic", table_name="drug_shortages_history", schema=_SCHEMA)
    op.drop_table("drug_shortages_history", schema=_SCHEMA)
    op.drop_index("ix_drug_shortages_ndc_codes_gin", table_name="drug_shortages", schema=_SCHEMA)
    op.drop_index("ix_drug_shortages_status", table_name="drug_shortages", schema=_SCHEMA)
    op.drop_table("drug_shortages", schema=_SCHEMA)
    op.drop_index("ix_drug_rems_ndc_rems_id", table_name="drug_rems_ndc", schema=_SCHEMA)
    op.drop_index("ix_drug_rems_ndc_ndc11", table_name="drug_rems_ndc", schema=_SCHEMA)
    op.drop_table("drug_rems_ndc", schema=_SCHEMA)
    op.drop_index("ix_drug_rems_ndc_codes_gin", table_name="drug_rems", schema=_SCHEMA)
    op.drop_index("ix_drug_rems_app_number", table_name="drug_rems", schema=_SCHEMA)
    op.drop_table("drug_rems", schema=_SCHEMA)
