"""Create drug_database Orange Book tables: drug_orange_book, drug_patents, drug_exclusivity.

Also creates the v_drug_orange_book cross-reference view that joins
drug_database.drugs to drug_database.drug_orange_book on application_number.

This is the THIRD migration for the drug-database module.

Revision chain:
  0001_ndc      (T3) — drugs, packages, ingredients, pharm classes
  0002_pricing  (T4) — NADAC + ASP current + history tables
  0003_orange_book (this file, T5) — Orange Book therapeutic equivalence overlay

Cross-reference design:
  drug_database.drugs.application_number (indexed at ix_drugs_application_number)
  contains values like "NDA019787" from the FDA NDC Directory.

  drug_database.drug_orange_book.application_number is a computed column
  built as "{appl_type_prefix}{appl_no:0>6}", e.g.:
    appl_type="N", appl_no="019787" → "NDA019787"
    appl_type="A", appl_no="020503" → "ANDA020503"

  The view v_drug_orange_book joins on this column to provide a single
  query surface over matched Orange Book products and their NDC records.

Upgrade: creates schema (idempotent), 3 tables, indexes, unique constraints, view.
Downgrade: drops view first, then tables in reverse dependency order.

Revision ID: 0003_orange_book
Revises: 0002_pricing
Create Date: 2026-04-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0003_orange_book"
down_revision: Union[str, None] = "0002_pricing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "drug_database"


def upgrade() -> None:
    # Schema already created by 0001_ndc; CREATE IF NOT EXISTS is safe.
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ------------------------------------------------------------------ drug_orange_book
    op.create_table(
        "drug_orange_book",
        sa.Column(
            "id", sa.BigInteger, primary_key=True, autoincrement=True
        ),
        sa.Column("ingredient", sa.String(500), nullable=True,
                  comment="Active ingredient(s)"),
        sa.Column("dosage_form", sa.String(200), nullable=True,
                  comment="Dosage form — split from 'DF;Route' on semicolon"),
        sa.Column("route", sa.String(200), nullable=True,
                  comment="Route of administration — split from 'DF;Route' on semicolon"),
        sa.Column("trade_name", sa.String(500), nullable=True),
        sa.Column("applicant", sa.String(100), nullable=True,
                  comment="Short applicant code"),
        sa.Column("strength", sa.String(500), nullable=True),
        sa.Column("appl_type", sa.String(5), nullable=False,
                  comment="N=NDA, A=ANDA, BLA"),
        sa.Column("appl_no", sa.String(10), nullable=False,
                  comment="Application number digits, e.g. '019787'"),
        sa.Column("application_number", sa.String(20), nullable=True,
                  comment="Computed '{appl_type_prefix}{appl_no:0>6}' — e.g. 'NDA019787'"),
        sa.Column("product_no", sa.String(10), nullable=False,
                  comment="Product number within the application"),
        sa.Column("te_code", sa.String(10), nullable=True,
                  comment="Therapeutic equivalence code: AA, AB, AB1..AB3, AP, AT, BC, BD, BE, BN, BP, BS, BT, BX"),
        sa.Column("approval_date", sa.Date, nullable=True,
                  comment="Approval date; 1982-01-01 when approved_prior_to_1982 is True"),
        sa.Column("approved_prior_to_1982", sa.Boolean, nullable=False,
                  server_default=sa.text("FALSE"),
                  comment="True when source text is 'Approved Prior to Jan 1, 1982'"),
        sa.Column("rld", sa.Boolean, nullable=True,
                  comment="Reference Listed Drug"),
        sa.Column("rs", sa.Boolean, nullable=True,
                  comment="Reference Standard"),
        sa.Column("product_type", sa.String(10), nullable=True,
                  comment="RX, OTC, DISCN"),
        sa.Column("applicant_full_name", sa.String(500), nullable=True),
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
        "uq_orange_book_appl_product",
        "drug_orange_book",
        ["appl_type", "appl_no", "product_no"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_orange_book_application_number",
        "drug_orange_book",
        ["application_number"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_orange_book_appl_type",
        "drug_orange_book",
        ["appl_type"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_orange_book_ingredient",
        "drug_orange_book",
        ["ingredient"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------ drug_patents
    op.create_table(
        "drug_patents",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("appl_type", sa.String(5), nullable=False),
        sa.Column("appl_no", sa.String(10), nullable=False),
        sa.Column("product_no", sa.String(10), nullable=False),
        sa.Column("application_number", sa.String(20), nullable=True,
                  comment="Computed '{appl_type_prefix}{appl_no:0>6}' — cross-ref"),
        sa.Column("patent_no", sa.String(50), nullable=False,
                  comment="Patent number — can contain letters"),
        sa.Column("patent_expire_date", sa.Date, nullable=True,
                  comment="Patent expiration date; nullable"),
        sa.Column("drug_substance_flag", sa.Boolean, nullable=True,
                  comment="Y→True: covers drug substance"),
        sa.Column("drug_product_flag", sa.Boolean, nullable=True,
                  comment="Y→True: covers drug product"),
        sa.Column("patent_use_code", sa.String(20), nullable=True,
                  comment="Use code (U-xxx) for method-of-use patents; null if absent"),
        sa.Column("delist_flag", sa.Boolean, nullable=True,
                  comment="Y→True: patent has been delisted"),
        sa.Column("submission_date", sa.Date, nullable=True,
                  comment="Date patent was submitted to FDA"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=_SCHEMA,
    )
    op.create_unique_constraint(
        "uq_drug_patents_appl_product_patent",
        "drug_patents",
        ["appl_type", "appl_no", "product_no", "patent_no"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_patents_application_number",
        "drug_patents",
        ["application_number"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_patents_patent_no",
        "drug_patents",
        ["patent_no"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------ drug_exclusivity
    op.create_table(
        "drug_exclusivity",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("appl_type", sa.String(5), nullable=False),
        sa.Column("appl_no", sa.String(10), nullable=False),
        sa.Column("product_no", sa.String(10), nullable=False),
        sa.Column("application_number", sa.String(20), nullable=True,
                  comment="Computed '{appl_type_prefix}{appl_no:0>6}' — cross-ref"),
        sa.Column("exclusivity_code", sa.String(20), nullable=False,
                  comment="NCE, ODE, PED, I, M, NP, NPP, PC, etc."),
        sa.Column("exclusivity_date", sa.Date, nullable=False,
                  comment="Exclusivity expiration date"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema=_SCHEMA,
    )
    op.create_unique_constraint(
        "uq_drug_exclusivity_appl_code_date",
        "drug_exclusivity",
        ["appl_type", "appl_no", "product_no", "exclusivity_code", "exclusivity_date"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_exclusivity_application_number",
        "drug_exclusivity",
        ["application_number"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_drug_exclusivity_exclusivity_code",
        "drug_exclusivity",
        ["exclusivity_code"],
        schema=_SCHEMA,
    )

    # ------------------------------------------------------------------ view
    # Cross-reference view: joins drug_orange_book ↔ drugs on application_number.
    # Dropped first on downgrade.
    op.execute(f"""
        CREATE OR REPLACE VIEW {_SCHEMA}.v_drug_orange_book AS
        SELECT
            ob.id                    AS ob_id,
            ob.ingredient,
            ob.trade_name,
            ob.strength,
            ob.appl_type,
            ob.appl_no,
            ob.application_number,
            ob.product_no,
            ob.te_code,
            ob.approval_date,
            ob.approved_prior_to_1982,
            ob.rld,
            ob.rs,
            ob.product_type,
            ob.applicant,
            ob.applicant_full_name,
            d.product_id             AS ndc_product_id,
            d.product_ndc,
            d.ndc_11,
            d.proprietary_name,
            d.non_proprietary_name,
            d.dosage_form_name       AS ndc_dosage_form,
            d.route_name             AS ndc_route,
            d.labeler_name
        FROM {_SCHEMA}.drug_orange_book ob
        LEFT JOIN {_SCHEMA}.drugs d
            ON ob.application_number = d.application_number
    """)


def downgrade() -> None:
    # Drop view first (depends on both tables)
    op.execute(f"DROP VIEW IF EXISTS {_SCHEMA}.v_drug_orange_book")

    # Drop tables in reverse creation order
    op.drop_table("drug_exclusivity", schema=_SCHEMA)
    op.drop_table("drug_patents", schema=_SCHEMA)
    op.drop_table("drug_orange_book", schema=_SCHEMA)
