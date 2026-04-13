"""event_bus_reliability: add core.event_dlq and core.processed_events tables

Revision ID: 0003_event_bus_reliability
Revises: 0002_bank_holidays
Create Date: 2026-04-12 00:00:00.000000

These tables support Phase 2 event bus reliability:
  - event_dlq: dead-letter queue entries for failed messages after retry exhaustion
  - processed_events: idempotency tracking per consumer (composite PK)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_event_bus_reliability"
down_revision: Union[str, None] = "0002_bank_holidays"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade(conn: sa.engine.Connection | None = None) -> None:
    """Create event_dlq and processed_events tables in the core schema.

    When called via alembic directly, ``conn`` is None and the standard
    ``op`` context is used.  When called via ``conn.run_sync(upgrade)``
    in tests, ``conn`` is the synchronous connection and we use raw DDL.
    """
    if conn is not None:
        # Called via AsyncConnection.run_sync() in tests
        conn.execute(
            sa.text(
                """
                CREATE TABLE IF NOT EXISTS core.event_dlq (
                    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
                    event_id        UUID        NOT NULL,
                    tenant_id       UUID        NOT NULL,
                    event_type      VARCHAR(200) NOT NULL,
                    envelope        JSONB       NOT NULL,
                    failure_reason  TEXT        NOT NULL,
                    attempt_count   INTEGER     NOT NULL DEFAULT 1,
                    first_failed_at TIMESTAMPTZ NOT NULL,
                    last_failed_at  TIMESTAMPTZ NOT NULL,
                    dlq_topic       VARCHAR(200) NOT NULL,
                    replayed_at     TIMESTAMPTZ,
                    status          VARCHAR(20)  NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued','replayed','dropped')),
                    CONSTRAINT pk_event_dlq PRIMARY KEY (id)
                )
                """
            )
        )
        conn.execute(
            sa.text("CREATE INDEX IF NOT EXISTS ix_event_dlq_event_id ON core.event_dlq (event_id)")
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_event_dlq_tenant_id ON core.event_dlq (tenant_id)"
            )
        )
        conn.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_event_dlq_event_type ON core.event_dlq (event_type)"
            )
        )
        conn.execute(
            sa.text("CREATE INDEX IF NOT EXISTS ix_event_dlq_status ON core.event_dlq (status)")
        )
        conn.execute(
            sa.text(
                """
                CREATE TABLE IF NOT EXISTS core.processed_events (
                    idempotency_key TEXT        NOT NULL,
                    consumer_name   TEXT        NOT NULL DEFAULT '',
                    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT pk_processed_events PRIMARY KEY (idempotency_key, consumer_name)
                )
                """
            )
        )
        return

    # Called by Alembic normally
    op.create_table(
        "event_dlq",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(200), nullable=False),
        sa.Column("envelope", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dlq_topic", sa.String(200), nullable=False),
        sa.Column("replayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.CheckConstraint(
            "status IN ('queued','replayed','dropped')",
            name=op.f("ck_event_dlq_event_dlq_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_dlq")),
        schema="core",
    )
    op.create_index("ix_event_dlq_event_id", "event_dlq", ["event_id"], schema="core")
    op.create_index("ix_event_dlq_tenant_id", "event_dlq", ["tenant_id"], schema="core")
    op.create_index("ix_event_dlq_event_type", "event_dlq", ["event_type"], schema="core")
    op.create_index("ix_event_dlq_status", "event_dlq", ["status"], schema="core")

    op.create_table(
        "processed_events",
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("consumer_name", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint(
            "idempotency_key", "consumer_name", name=op.f("pk_processed_events")
        ),
        schema="core",
    )


def downgrade(conn: sa.engine.Connection | None = None) -> None:
    """Drop event_dlq and processed_events tables."""
    if conn is not None:
        # Called via AsyncConnection.run_sync() in tests
        conn.execute(sa.text("DROP TABLE IF EXISTS core.processed_events"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_event_dlq_status"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_event_dlq_event_type"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_event_dlq_tenant_id"))
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_event_dlq_event_id"))
        conn.execute(sa.text("DROP TABLE IF EXISTS core.event_dlq"))
        return

    # Called by Alembic normally
    op.drop_table("processed_events", schema="core")
    op.drop_index("ix_event_dlq_status", table_name="event_dlq", schema="core")
    op.drop_index("ix_event_dlq_event_type", table_name="event_dlq", schema="core")
    op.drop_index("ix_event_dlq_tenant_id", table_name="event_dlq", schema="core")
    op.drop_index("ix_event_dlq_event_id", table_name="event_dlq", schema="core")
    op.drop_table("event_dlq", schema="core")
