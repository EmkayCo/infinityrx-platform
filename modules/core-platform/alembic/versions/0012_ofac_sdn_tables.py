"""OFAC SDN (Specially Designated Nationals) reference tables.

Creates four tables in the shared schema to hold the raw OFAC SDN CSV
distribution — one parent plus three child tables that mirror the
ent_num-keyed relational structure of the source files:

  shared.ofac_sdn            — parent, PK ent_num (from sdn.csv)
  shared.ofac_sdn_addresses  — child, FK ent_num (from add.csv)
  shared.ofac_sdn_aliases    — child, FK ent_num (from alt.csv)
  shared.ofac_sdn_comments   — child, FK ent_num (from sdn_comments.csv)

All four tables get a raw_payload jsonb column so the loader can preserve
the full source row even when columns get sanitized / "-0- " sentinels
normalized to NULL during ingestion. This leaves a per-row escape hatch
for any source-data oddity that surfaces later.

Leaves payment_proc.payment_proc_ofac_sdn (the payment-processing
module's flattened screening table) untouched — that's a different
consumer with different row shape.

Revision ID: 0012_ofac_sdn_tables
Revises: 0011_gpb_id_to_uuid
Create Date: 2026-04-16

LESSON-011: Global reference tables — no tenant_id, no TenantScopedMixin.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0012_ofac_sdn_tables"
down_revision: Union[str, None] = "0011_gpb_id_to_uuid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "shared"


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')

    # ── ofac_sdn (parent) ────────────────────────────────────────────────────
    op.create_table(
        "ofac_sdn",
        sa.Column("ent_num", sa.Integer(), nullable=False),
        sa.Column("sdn_name", sa.Text(), nullable=True),
        sa.Column("sdn_type", sa.String(50), nullable=True),
        sa.Column("program", sa.String(500), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("call_sign", sa.String(100), nullable=True),
        sa.Column("vess_type", sa.String(100), nullable=True),
        sa.Column("tonnage", sa.String(50), nullable=True),
        sa.Column("grt", sa.String(50), nullable=True),
        sa.Column("vess_flag", sa.String(100), nullable=True),
        sa.Column("vess_owner", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("ent_num", name="pk_ofac_sdn"),
        schema=SCHEMA,
    )
    op.create_index("idx_ofac_sdn_name", "ofac_sdn", ["sdn_name"], schema=SCHEMA)
    op.create_index("idx_ofac_sdn_type", "ofac_sdn", ["sdn_type"], schema=SCHEMA)
    op.create_index("idx_ofac_sdn_program", "ofac_sdn", ["program"], schema=SCHEMA)

    # ── ofac_sdn_addresses ───────────────────────────────────────────────────
    op.create_table(
        "ofac_sdn_addresses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ent_num", sa.Integer(), nullable=False),
        sa.Column("add_num", sa.Integer(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city_state_zip", sa.Text(), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("add_remarks", sa.Text(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ofac_sdn_addresses"),
        sa.ForeignKeyConstraint(
            ["ent_num"],
            [f"{SCHEMA}.ofac_sdn.ent_num"],
            name="fk_ofac_sdn_addresses_ent_num",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("ent_num", "add_num",
                             name="uq_ofac_sdn_addresses_ent_add"),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_ofac_sdn_addresses_ent_num", "ofac_sdn_addresses",
        ["ent_num"], schema=SCHEMA,
    )
    op.create_index(
        "idx_ofac_sdn_addresses_country", "ofac_sdn_addresses",
        ["country"], schema=SCHEMA,
    )

    # ── ofac_sdn_aliases ─────────────────────────────────────────────────────
    op.create_table(
        "ofac_sdn_aliases",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ent_num", sa.Integer(), nullable=False),
        sa.Column("alt_num", sa.Integer(), nullable=False),
        sa.Column("alt_type", sa.String(20), nullable=True),
        sa.Column("alt_name", sa.Text(), nullable=True),
        sa.Column("alt_remarks", sa.Text(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ofac_sdn_aliases"),
        sa.ForeignKeyConstraint(
            ["ent_num"],
            [f"{SCHEMA}.ofac_sdn.ent_num"],
            name="fk_ofac_sdn_aliases_ent_num",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("ent_num", "alt_num",
                             name="uq_ofac_sdn_aliases_ent_alt"),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_ofac_sdn_aliases_ent_num", "ofac_sdn_aliases",
        ["ent_num"], schema=SCHEMA,
    )
    op.create_index(
        "idx_ofac_sdn_aliases_name", "ofac_sdn_aliases",
        ["alt_name"], schema=SCHEMA,
    )
    op.create_index(
        "idx_ofac_sdn_aliases_type", "ofac_sdn_aliases",
        ["alt_type"], schema=SCHEMA,
    )

    # ── ofac_sdn_comments ────────────────────────────────────────────────────
    # sdn_comments is a "Remarks3" continuation file — there's one row per
    # ent_num whose remarks field overflowed sdn.csv's Remarks column.
    op.create_table(
        "ofac_sdn_comments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ent_num", sa.Integer(), nullable=False),
        sa.Column("remarks3", sa.Text(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ofac_sdn_comments"),
        sa.ForeignKeyConstraint(
            ["ent_num"],
            [f"{SCHEMA}.ofac_sdn.ent_num"],
            name="fk_ofac_sdn_comments_ent_num",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("ent_num",
                             name="uq_ofac_sdn_comments_ent_num"),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_ofac_sdn_comments_ent_num", "ofac_sdn_comments",
        ["ent_num"], schema=SCHEMA,
    )


def downgrade() -> None:
    # Children first (FK dependency).
    op.drop_table("ofac_sdn_comments", schema=SCHEMA)
    op.drop_table("ofac_sdn_aliases", schema=SCHEMA)
    op.drop_table("ofac_sdn_addresses", schema=SCHEMA)
    op.drop_table("ofac_sdn", schema=SCHEMA)
