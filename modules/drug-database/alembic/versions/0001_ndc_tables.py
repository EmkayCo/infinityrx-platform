"""Create drug_database NDC tables: drugs, drug_packages, drug_active_ingredients, drug_pharm_classes.

This is the FIRST migration for the drug-database module.  It creates the
``drug_database`` schema and the four core NDC reference tables populated by
the FDANDCIngester pipeline.

Revision chain:
  0001_ndc  (this file)     — drugs, packages, ingredients, pharm classes
  0002      (Teammate 4)    — RESERVED: pricing tables (NADAC, WAC, etc.)
  0003      (Teammate 5)    — RESERVED: Orange Book therapeutic equivalence overlay

Teammate 4 instructions:
  Set down_revision = "0001_ndc" in your 0002 migration.
  The application_number column on drugs is indexed for your Orange Book cross-ref.

Teammate 5 instructions:
  Set down_revision = "0002" (or "0001_ndc" if T4 runs after you) in your 0003 migration.
  The application_number column on drug_database.drugs contains NDA/ANDA numbers
  for Orange Book joins.

Revision ID: 0001_ndc
Revises: None
Create Date: 2026-04-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0001_ndc"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "drug_database"


def upgrade() -> None:
    # ------------------------------------------------------------------ schema
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ------------------------------------------------------------------ drugs
    op.create_table(
        "drugs",
        sa.Column("product_id", sa.String(50), primary_key=True,
                  comment="PRODUCTID from FDA (labeler-product)"),
        sa.Column("product_ndc", sa.String(20), nullable=False,
                  comment="PRODUCTNDC in 5-4 format"),
        sa.Column("ndc_11", sa.String(11), nullable=False,
                  comment="11-digit normalized NDC (5-4-2)"),
        sa.Column("product_type_name", sa.String(100), nullable=True),
        sa.Column("proprietary_name", sa.String(500), nullable=True),
        sa.Column("proprietary_name_suffix", sa.String(255), nullable=True),
        sa.Column("non_proprietary_name", sa.String(500), nullable=True),
        sa.Column("dosage_form_name", sa.String(100), nullable=True),
        sa.Column("route_name", sa.String(255), nullable=True),
        sa.Column("start_marketing_date", sa.Date, nullable=True),
        sa.Column("end_marketing_date", sa.Date, nullable=True),
        sa.Column("marketing_category_name", sa.String(255), nullable=True),
        sa.Column("application_number", sa.String(20), nullable=True,
                  comment="Orange Book NDA/ANDA — cross-ref for T5"),
        sa.Column("labeler_name", sa.String(500), nullable=True),
        sa.Column("substance_name", sa.Text, nullable=True),
        sa.Column("active_numerator_strength", sa.Text, nullable=True),
        sa.Column("active_ingred_unit", sa.Text, nullable=True),
        sa.Column("pharm_classes", sa.Text, nullable=True),
        sa.Column("dea_schedule", sa.String(5), nullable=True),
        sa.Column("ndc_exclude_flag", sa.String(1), nullable=True),
        sa.Column("listing_record_certified_through", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        schema=_SCHEMA,
    )
    op.create_index("ix_drugs_product_ndc", "drugs", ["product_ndc"], schema=_SCHEMA)
    op.create_index("ix_drugs_ndc_11", "drugs", ["ndc_11"], schema=_SCHEMA)
    op.create_index("ix_drugs_application_number", "drugs", ["application_number"],
                    schema=_SCHEMA)
    op.create_index("ix_drugs_dea_schedule", "drugs", ["dea_schedule"], schema=_SCHEMA)
    op.create_unique_constraint("uq_drugs_ndc_11", "drugs", ["ndc_11"], schema=_SCHEMA)

    # ------------------------------------------------------------------ drug_packages
    op.create_table(
        "drug_packages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("product_id", sa.String(50),
                  sa.ForeignKey(f"{_SCHEMA}.drugs.product_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("product_ndc", sa.String(20), nullable=True,
                  comment="Denormalized PRODUCTNDC for convenience"),
        sa.Column("ndc_package_code", sa.String(20), nullable=False,
                  comment="Raw NDCPACKAGECODE from FDA"),
        sa.Column("ndc_package_code_11", sa.String(11), nullable=False,
                  comment="Normalized 11-digit NDC (5-4-2)"),
        sa.Column("package_description", sa.Text, nullable=True),
        sa.Column("start_marketing_date", sa.Date, nullable=True),
        sa.Column("end_marketing_date", sa.Date, nullable=True),
        sa.Column("ndc_exclude_flag", sa.String(1), nullable=True),
        sa.Column("sample_package", sa.String(1), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        schema=_SCHEMA,
    )
    op.create_index("ix_drug_packages_product_ndc", "drug_packages", ["product_ndc"],
                    schema=_SCHEMA)
    op.create_index("ix_drug_packages_ndc_package_code", "drug_packages",
                    ["ndc_package_code"], schema=_SCHEMA)
    op.create_index("ix_drug_packages_ndc_package_code_11", "drug_packages",
                    ["ndc_package_code_11"], schema=_SCHEMA)
    op.create_unique_constraint("uq_drug_packages_ndc_11", "drug_packages",
                                ["ndc_package_code_11"], schema=_SCHEMA)

    # ------------------------------------------------------------------ drug_active_ingredients
    op.create_table(
        "drug_active_ingredients",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("drug_id", sa.String(50),
                  sa.ForeignKey(f"{_SCHEMA}.drugs.product_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False,
                  comment="0-indexed position within the drug ingredient list"),
        sa.Column("substance_name", sa.String(500), nullable=False),
        sa.Column("numerator_strength", sa.Numeric(18, 6), nullable=True,
                  comment="Decimal(18,6); NULL for non-numeric values like q.s."),
        sa.Column("unit", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        schema=_SCHEMA,
    )
    op.create_index("ix_drug_active_ingredients_drug_id", "drug_active_ingredients",
                    ["drug_id"], schema=_SCHEMA)
    op.create_index("ix_drug_active_ingredients_substance_name",
                    "drug_active_ingredients", ["substance_name"], schema=_SCHEMA)

    # ------------------------------------------------------------------ drug_pharm_classes
    op.create_table(
        "drug_pharm_classes",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("drug_id", sa.String(50),
                  sa.ForeignKey(f"{_SCHEMA}.drugs.product_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False,
                  comment="0-indexed position within the pharm class list"),
        sa.Column("pharm_class", sa.Text, nullable=False),
        sa.Column("class_type", sa.String(10), nullable=True,
                  comment="EPC, MoA, PE, CS — extracted from [TYPE] marker"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        schema=_SCHEMA,
    )
    op.create_index("ix_drug_pharm_classes_drug_id", "drug_pharm_classes",
                    ["drug_id"], schema=_SCHEMA)
    op.create_index("ix_drug_pharm_classes_class_type", "drug_pharm_classes",
                    ["class_type"], schema=_SCHEMA)


def downgrade() -> None:
    op.drop_table("drug_pharm_classes", schema=_SCHEMA)
    op.drop_table("drug_active_ingredients", schema=_SCHEMA)
    op.drop_table("drug_packages", schema=_SCHEMA)
    op.drop_table("drugs", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA}")
