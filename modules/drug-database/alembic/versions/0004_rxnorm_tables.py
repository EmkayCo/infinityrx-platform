"""Create drug_database RxNorm tables: concepts, relationships, attributes,
semantic types, NDC crosswalk, ATC crosswalk.

This is the FOURTH migration for the drug-database module.

Revision chain:
  0001_ndc_tables    — drugs, packages, ingredients, pharm classes
  0002_pricing       — NADAC + ASP current + history tables
  0003_orange_book   — Orange Book tables
  0004_rxnorm_tables (this file) — RxNorm tables

Revision ID: 0004_rxnorm_tables
Revises: 0003_orange_book
Create Date: 2026-04-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_rxnorm_tables"
down_revision = "0003_orange_book"
branch_labels = None
depends_on = None

_SCHEMA = "drug_database"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        "rxnorm_concepts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("rxcui", sa.String(20), nullable=False),
        sa.Column("lat", sa.String(3), nullable=True),
        sa.Column("ts", sa.String(3), nullable=True),
        sa.Column("lui", sa.String(20), nullable=True),
        sa.Column("stt", sa.String(3), nullable=True),
        sa.Column("sui", sa.String(20), nullable=True),
        sa.Column("ispref", sa.String(1), nullable=True),
        sa.Column("rxaui", sa.String(20), nullable=False),
        sa.Column("saui", sa.String(50), nullable=True),
        sa.Column("scui", sa.String(100), nullable=True),
        sa.Column("sdui", sa.String(100), nullable=True),
        sa.Column("sab", sa.String(40), nullable=True),
        sa.Column("tty", sa.String(20), nullable=True),
        sa.Column("code", sa.String(100), nullable=True),
        sa.Column("str", sa.Text(), nullable=True),
        sa.Column("srl", sa.String(10), nullable=True),
        sa.Column("suppress", sa.String(1), nullable=True),
        sa.Column("cvf", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rxcui", "rxaui", name="uq_rxnorm_concepts_rxcui_rxaui"),
        schema=_SCHEMA,
    )
    op.create_index("ix_rxnorm_concepts_rxcui", "rxnorm_concepts", ["rxcui"], schema=_SCHEMA)
    op.create_index("ix_rxnorm_concepts_tty", "rxnorm_concepts", ["tty"], schema=_SCHEMA)
    op.create_index("ix_rxnorm_concepts_sab", "rxnorm_concepts", ["sab"], schema=_SCHEMA)

    op.create_table(
        "rxnorm_relationships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("rxcui1", sa.String(20), nullable=True),
        sa.Column("rxaui1", sa.String(20), nullable=True),
        sa.Column("stype1", sa.String(50), nullable=True),
        sa.Column("rel", sa.String(4), nullable=True),
        sa.Column("rxcui2", sa.String(20), nullable=True),
        sa.Column("rxaui2", sa.String(20), nullable=True),
        sa.Column("stype2", sa.String(50), nullable=True),
        sa.Column("rela", sa.String(100), nullable=True),
        sa.Column("rui", sa.String(20), nullable=True, unique=True),
        sa.Column("srui", sa.String(50), nullable=True),
        sa.Column("sab", sa.String(40), nullable=True),
        sa.Column("sl", sa.String(1000), nullable=True),
        sa.Column("rg", sa.String(10), nullable=True),
        sa.Column("dir", sa.String(1), nullable=True),
        sa.Column("suppress", sa.String(1), nullable=True),
        sa.Column("cvf", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_rxnorm_relationships_rxcui1", "rxnorm_relationships", ["rxcui1"], schema=_SCHEMA)
    op.create_index("ix_rxnorm_relationships_rxcui2", "rxnorm_relationships", ["rxcui2"], schema=_SCHEMA)
    op.create_index("ix_rxnorm_relationships_rel", "rxnorm_relationships", ["rel"], schema=_SCHEMA)

    op.create_table(
        "rxnorm_attributes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("rxcui", sa.String(20), nullable=True),
        sa.Column("lui", sa.String(20), nullable=True),
        sa.Column("sui", sa.String(20), nullable=True),
        sa.Column("rxaui", sa.String(20), nullable=True),
        sa.Column("stype", sa.String(50), nullable=True),
        sa.Column("code", sa.String(100), nullable=True),
        sa.Column("atui", sa.String(20), nullable=True, unique=True),
        sa.Column("satui", sa.String(50), nullable=True),
        sa.Column("atn", sa.String(100), nullable=True),
        sa.Column("sab", sa.String(40), nullable=True),
        sa.Column("atv", sa.Text(), nullable=True),
        sa.Column("suppress", sa.String(1), nullable=True),
        sa.Column("cvf", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_rxnorm_attributes_rxcui_atn", "rxnorm_attributes", ["rxcui", "atn"], schema=_SCHEMA)
    op.create_index("ix_rxnorm_attributes_rxaui", "rxnorm_attributes", ["rxaui"], schema=_SCHEMA)
    op.create_index("ix_rxnorm_attributes_atn", "rxnorm_attributes", ["atn"], schema=_SCHEMA)

    op.create_table(
        "rxnorm_semantic_types",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("rxcui", sa.String(20), nullable=True),
        sa.Column("tui", sa.String(10), nullable=True),
        sa.Column("stn", sa.String(100), nullable=True),
        sa.Column("sty", sa.String(100), nullable=True),
        sa.Column("atui", sa.String(20), nullable=True, unique=True),
        sa.Column("cvf", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_rxnorm_semantic_types_rxcui", "rxnorm_semantic_types", ["rxcui"], schema=_SCHEMA)
    op.create_index("ix_rxnorm_semantic_types_tui", "rxnorm_semantic_types", ["tui"], schema=_SCHEMA)

    op.create_table(
        "rxnorm_ndc_crosswalk",
        sa.Column("ndc_11", sa.String(11), nullable=False),
        sa.Column("rxcui", sa.String(20), nullable=True),
        sa.Column("drug_name", sa.Text(), nullable=True),
        sa.Column("tty", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("ndc_11"),
        schema=_SCHEMA,
    )

    op.create_table(
        "rxnorm_atc_crosswalk",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rxcui", sa.String(20), nullable=False),
        sa.Column("atc_code", sa.String(10), nullable=False),
        sa.Column("atc_level", sa.String(10), nullable=True),
        sa.Column("atc_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rxcui", "atc_code", name="uq_rxnorm_atc_crosswalk"),
        schema=_SCHEMA,
    )
    op.create_index("ix_rxnorm_atc_crosswalk_atc_code", "rxnorm_atc_crosswalk", ["atc_code"], schema=_SCHEMA)


def downgrade() -> None:
    op.drop_table("rxnorm_atc_crosswalk", schema=_SCHEMA)
    op.drop_table("rxnorm_ndc_crosswalk", schema=_SCHEMA)
    op.drop_table("rxnorm_semantic_types", schema=_SCHEMA)
    op.drop_table("rxnorm_attributes", schema=_SCHEMA)
    op.drop_table("rxnorm_relationships", schema=_SCHEMA)
    op.drop_table("rxnorm_concepts", schema=_SCHEMA)
