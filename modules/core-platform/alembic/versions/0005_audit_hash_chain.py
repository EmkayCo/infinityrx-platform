"""audit_hash_chain: add previous_hash and entry_hash columns to audit_log

Revision ID: 0005_audit_hash_chain
Revises: 0004_mfa_fields
Create Date: 2026-04-12 00:00:00.000000

Adds tamper-evident hash chain columns to core.audit_log per HIPAA 2026
requirement for immutable, tamper-evident audit logs (PRD section 4.4).

Backfill strategy:
  - For any existing rows, compute the chain in created_at, id order per
    tenant using a PL/pgSQL loop so we never load the whole table into
    application memory.
  - The SHA-256 canonical format is:
        {tenant_id}|{action}|{entity_type or ''}|{entity_id or ''}|
        {created_at ISO}|{previous_hash or ''}
  - First entry per tenant uses previous_hash = '0' * 64 (GENESIS_HASH).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_audit_hash_chain"
down_revision: Union[str, None] = "0004_mfa_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GENESIS_HASH = "0" * 64

# PL/pgSQL block that backfills entry_hash/previous_hash for existing rows.
# Uses encode(digest(...), 'hex') from pgcrypto.  If the extension is not
# available the block raises an informative error.
_BACKFILL_SQL = """\
DO $$
DECLARE
    r           RECORD;
    prev_tid    UUID  := NULL;
    prev_hash   TEXT  := '{genesis}';
    canonical   TEXT;
    computed    TEXT;
BEGIN
    FOR r IN
        SELECT id, tenant_id, action,
               COALESCE(entity_type, '') AS entity_type,
               COALESCE(entity_id, '')   AS entity_id,
               created_at
        FROM   core.audit_log
        ORDER  BY tenant_id, created_at, id
    LOOP
        IF prev_tid IS DISTINCT FROM r.tenant_id THEN
            prev_hash := '{genesis}';
            prev_tid  := r.tenant_id;
        END IF;

        canonical := r.tenant_id::TEXT
            || '|' || r.action
            || '|' || r.entity_type
            || '|' || r.entity_id
            || '|' || to_char(r.created_at AT TIME ZONE 'UTC',
                              'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"')
            || '|' || prev_hash;

        computed := encode(digest(convert_to(canonical, 'UTF8'), 'sha256'), 'hex');

        UPDATE core.audit_log
        SET    previous_hash = CASE WHEN prev_hash = '{genesis}' AND
                                         NOT EXISTS (
                                             SELECT 1 FROM core.audit_log
                                             WHERE  tenant_id = r.tenant_id
                                             AND    id < r.id
                                         )
                                    THEN NULL
                                    ELSE prev_hash
                               END,
               entry_hash    = computed
        WHERE  id = r.id;

        prev_hash := computed;
    END LOOP;
END;
$$;
""".format(genesis=GENESIS_HASH)


def upgrade(conn: sa.engine.Connection | None = None) -> None:
    """Add previous_hash and entry_hash columns, backfill existing rows."""
    if conn is not None:
        # Called via AsyncConnection.run_sync() in tests
        conn.execute(
            sa.text(
                "ALTER TABLE core.audit_log "
                "ADD COLUMN IF NOT EXISTS previous_hash VARCHAR(64),"
                "ADD COLUMN IF NOT EXISTS entry_hash    VARCHAR(64)"
            )
        )
        # Backfill existing rows — only needed if any rows exist
        result = conn.execute(sa.text("SELECT COUNT(*) FROM core.audit_log"))
        count = result.scalar()
        if count and count > 0:
            conn.execute(sa.text(_BACKFILL_SQL))
        # Now enforce NOT NULL on entry_hash (all rows have a value)
        conn.execute(
            sa.text(
                "ALTER TABLE core.audit_log "
                "ALTER COLUMN entry_hash SET NOT NULL"
            )
        )
        # Index on (tenant_id, created_at) — may already exist from baseline
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_audit_tenant_created "
                "ON core.audit_log (tenant_id, created_at)"
            )
        )
        return

    # Called by Alembic normally
    op.add_column(
        "audit_log",
        sa.Column("previous_hash", sa.String(64), nullable=True),
        schema="core",
    )
    op.add_column(
        "audit_log",
        sa.Column("entry_hash", sa.String(64), nullable=True),
        schema="core",
    )

    # Backfill existing rows
    bind = op.get_bind()
    result = bind.execute(sa.text("SELECT COUNT(*) FROM core.audit_log"))
    count = result.scalar()
    if count and count > 0:
        bind.execute(sa.text(_BACKFILL_SQL))

    # Enforce NOT NULL
    op.alter_column("audit_log", "entry_hash", nullable=False, schema="core")

    op.create_index(
        "ix_audit_tenant_created",
        "audit_log",
        ["tenant_id", "created_at"],
        schema="core",
        if_not_exists=True,
    )


def downgrade(conn: sa.engine.Connection | None = None) -> None:
    """Drop previous_hash and entry_hash columns."""
    if conn is not None:
        conn.execute(
            sa.text(
                "ALTER TABLE core.audit_log "
                "DROP COLUMN IF EXISTS previous_hash,"
                "DROP COLUMN IF EXISTS entry_hash"
            )
        )
        return

    op.drop_index("ix_audit_tenant_created", table_name="audit_log", schema="core")
    op.drop_column("audit_log", "entry_hash", schema="core")
    op.drop_column("audit_log", "previous_hash", schema="core")
