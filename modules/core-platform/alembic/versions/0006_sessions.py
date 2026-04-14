"""core.sessions table — active session tracking

Revision ID: 0006_sessions
Revises: 0005_audit_hash_chain
Create Date: 2026-04-12 00:00:00.000000

HIPAA 2026: tracks active sessions for concurrent session management,
idle timeout enforcement, force-logout, and session visibility per user.
The audit agent (0005_audit_hash_chain) must be merged before this runs.
If that migration is unreachable during local integration, the Integration
Coordinator must adjust ``down_revision`` to the last known head.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_sessions"
down_revision: Union[str, None] = "0005_audit_hash_chain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("device_info", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            name=op.f("fk_sessions_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        schema="core",
    )
    op.create_index(
        "idx_sessions_user_active",
        "sessions",
        ["user_id", "is_active"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("idx_sessions_user_active", table_name="sessions", schema="core")
    op.drop_table("sessions", schema="core")
