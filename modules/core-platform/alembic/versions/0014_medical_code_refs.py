"""ICD-10-CM and HCPCS Level II code reference tables.

Creates:
  shared.icd10_cm_codes   — one row per diagnosis code per publication cycle
  shared.hcpcs_codes      — one row per HCPCS code per quarterly publication

Revision ID: 0014_medical_code_refs
Revises: 0013_drop_part_d_schema
Create Date: 2026-04-17

Both tables are keyed on (code, <version>) so retrospective claim
adjudication can look up the description that was valid at the date of
service, not just the current quarter's. ICD-10-CM uses ``effective_date``
(annual October release + April mid-year update). HCPCS uses
``publication_quarter`` (e.g. ``"2026Q2"`` for the April 2026 release).

LESSON-011: Global reference tables — no tenant_id, no TenantScopedMixin.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0014_medical_code_refs"
down_revision: Union[str, None] = "0013_drop_part_d_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "shared"


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')

    # ── icd10_cm_codes ──────────────────────────────────────────────────────
    op.create_table(
        "icd10_cm_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(7), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("is_billable", sa.Boolean(), nullable=False),
        sa.Column("short_description", sa.String(80), nullable=True),
        sa.Column("long_description", sa.Text(), nullable=True),
        sa.Column("ordinal_num", sa.Integer(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_icd10_cm_codes"),
        sa.UniqueConstraint(
            "code", "effective_date", name="uq_icd10_cm_codes_code_effective"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_icd10_cm_codes_effective_date",
        "icd10_cm_codes",
        ["effective_date"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_icd10_cm_codes_code",
        "icd10_cm_codes",
        ["code"],
        schema=SCHEMA,
    )

    # ── hcpcs_codes ─────────────────────────────────────────────────────────
    op.create_table(
        "hcpcs_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(5), nullable=False),
        sa.Column("is_modifier", sa.Boolean(), nullable=False),
        # publication_quarter is "YYYYQN" (e.g. "2026Q2" for Apr 2026 release).
        sa.Column("publication_quarter", sa.String(6), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("long_description", sa.Text(), nullable=True),
        sa.Column("short_description", sa.String(28), nullable=True),
        sa.Column("pricing_indicator", sa.String(2), nullable=True),
        sa.Column("coverage_code", sa.String(1), nullable=True),
        sa.Column("anesthesia_base_units", sa.Integer(), nullable=True),
        sa.Column("action_code", sa.String(1), nullable=True),
        sa.Column("added_date", sa.Date(), nullable=True),
        sa.Column("action_effective_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_hcpcs_codes"),
        sa.UniqueConstraint(
            "code",
            "is_modifier",
            "publication_quarter",
            name="uq_hcpcs_codes_code_modifier_quarter",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_hcpcs_codes_code_quarter",
        "hcpcs_codes",
        ["code", "publication_quarter"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_hcpcs_codes_publication_quarter",
        "hcpcs_codes",
        ["publication_quarter"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hcpcs_codes_publication_quarter",
        table_name="hcpcs_codes",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_hcpcs_codes_code_quarter",
        table_name="hcpcs_codes",
        schema=SCHEMA,
    )
    op.drop_table("hcpcs_codes", schema=SCHEMA)

    op.drop_index(
        "ix_icd10_cm_codes_code",
        table_name="icd10_cm_codes",
        schema=SCHEMA,
    )
    op.drop_index(
        "ix_icd10_cm_codes_effective_date",
        table_name="icd10_cm_codes",
        schema=SCHEMA,
    )
    op.drop_table("icd10_cm_codes", schema=SCHEMA)
