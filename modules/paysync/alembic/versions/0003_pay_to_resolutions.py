"""paysync Wave 36: pay_to_resolutions snapshot + banking_discrepancy_reviews.

Adds:
  - paysync.pay_to_resolutions   — per-claim resolution snapshot so
    later changes to network_mgmt don't retroactively alter
    historical claims.
  - paysync.banking_discrepancy_reviews — operator review queue for
    imported banking that disagrees with network_mgmt's record.

Plus: paysync.claims.pay_to_resolution_id (nullable FK so legacy
rows can stay).

Revision ID: 0003_pay_to_resolutions
Revises: 0002_paysync_rls
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_pay_to_resolutions"
down_revision: Union[str, None] = "0002_paysync_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TABLES = ("pay_to_resolutions", "banking_discrepancy_reviews")


def upgrade() -> None:
    # ── pay_to_resolutions ──
    op.create_table(
        "pay_to_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pay_to_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pay_to_entity_type", sa.String(32), nullable=True),
        sa.Column("pay_to_external_id", sa.String(64), nullable=True),
        sa.Column("banking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_statement_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "eight_thirty_five_destination_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column("matched_via", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "claim_id", name="uq_paysync_resolution_claim"),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_resolution_claim", "pay_to_resolutions", ["claim_id"], schema=_SCHEMA
    )
    op.create_index(
        "ix_paysync_resolution_entity", "pay_to_resolutions",
        ["tenant_id", "pay_to_entity_id"], schema=_SCHEMA,
    )

    # claims.pay_to_resolution_id
    op.add_column(
        "claims",
        sa.Column(
            "pay_to_resolution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.pay_to_resolutions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_claims_resolution", "claims",
        ["pay_to_resolution_id"], schema=_SCHEMA,
    )

    # ── banking_discrepancy_reviews ──
    op.create_table(
        "banking_discrepancy_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.claims.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pay_to_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("imported_routing_last_four", sa.String(4), nullable=False),
        sa.Column("imported_account_last_four", sa.String(4), nullable=False),
        sa.Column("network_routing_last_four", sa.String(4), nullable=True),
        sa.Column("network_account_last_four", sa.String(4), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_action", sa.String(64), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'resolved', 'dismissed')",
            name="ck_paysync_discrep_status",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_discrep_status", "banking_discrepancy_reviews",
        ["tenant_id", "status"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_discrep_entity", "banking_discrepancy_reviews",
        ["tenant_id", "pay_to_entity_id"], schema=_SCHEMA,
    )

    # RLS for the two new tables
    for table in _TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
              FOR ALL
              TO ifx_dev_app, {_APP_ROLE}
              USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
            """
        )

    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.pay_to_resolutions, "
        f"{_SCHEMA}.banking_discrepancy_reviews "
        f"TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    op.drop_index("ix_paysync_claims_resolution", table_name="claims", schema=_SCHEMA)
    op.drop_column("claims", "pay_to_resolution_id", schema=_SCHEMA)
    op.drop_table("banking_discrepancy_reviews", schema=_SCHEMA)
    op.drop_table("pay_to_resolutions", schema=_SCHEMA)
