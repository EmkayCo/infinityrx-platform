"""adjudication_engine bin_routing table — Wave 28 Sub-wave 3 M3.1.

Platform-level routing table that resolves NCPDP BIN + PCN on an
incoming wire request to a (tenant_id, program_id) pair. Replaces
the env-var single-tenant bringup fallback in
``services/tcp_listener.py`` for multi-tenant production use.

Routing semantics:
  - Exact (bin, pcn) match wins.
  - (bin, NULL pcn) row acts as a wildcard fallback for that BIN
    — used when a tenant owns an entire BIN regardless of PCN.
  - Active rows satisfy: effective_date <= today AND
    (termination_date IS NULL OR termination_date > today).

The table is NOT tenant-scoped / no RLS — the listener is trusted
BEFORE any tenant is resolved (that's the whole point of this
table). Only admin roles write routing rows; tier app roles read.

Partial unique index guarantees one active (bin, pcn) mapping at a
time — attempting to stage a second overlapping active row conflicts
cleanly, forcing operators to terminate the old row first.

Revision ID: 0007_bin_routing
Revises: 0006_claim_txn_program_id
Create Date: 2026-04-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_bin_routing"
down_revision: Union[str, None] = "0006_claim_txn_program_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "adjudication_engine"
_TABLE = "bin_routing"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("bin", sa.String(6), nullable=False),
        sa.Column("pcn", sa.String(10), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "effective_date", sa.Date, nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column("termination_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_date",
            name="ck_bin_routing_lifecycle",
        ),
        sa.CheckConstraint(
            "bin ~ '^[0-9]{6}$'",
            name="ck_bin_routing_bin_digits",
        ),
        schema=_SCHEMA,
    )

    # Lookup index — covers the common resolver query
    # (bin, pcn) exact + (bin, pcn IS NULL) wildcard.
    op.create_index(
        "idx_bin_routing_lookup", _TABLE,
        ["bin", "pcn", "effective_date"],
        schema=_SCHEMA,
    )

    # Partial unique: one active mapping per (bin, pcn-or-wildcard).
    # COALESCE(pcn, '') collapses NULL-wildcard rows into comparable
    # keys. The WHERE clause scopes uniqueness to currently-active rows
    # so historical terminated rows don't block new mappings.
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_bin_routing_active
          ON {_SCHEMA}.{_TABLE} (bin, COALESCE(pcn, ''))
          WHERE termination_date IS NULL
        """
    )

    # Platform-level table owned by the admin role (no RLS). The
    # listener runs as a tenant app role, so grant read + insert/
    # update for operational registration via the register helper.
    # DELETE is reserved for admin ops.
    for role in ("ifx_dev_app", "ifx_mock_app", _APP_ROLE):
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE ON {_SCHEMA}.{_TABLE} TO {role}"
        )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_SCHEMA}.uq_bin_routing_active")
    op.drop_index("idx_bin_routing_lookup", table_name=_TABLE, schema=_SCHEMA)
    op.drop_table(_TABLE, schema=_SCHEMA)
