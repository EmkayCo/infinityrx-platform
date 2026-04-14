"""MFA fields for users + FIDO2 credentials table + tenant mfa_required

Revision ID: 0004_mfa_fields
Revises: 0003_event_bus_reliability
Create Date: 2026-04-12 00:00:00.000000

HIPAA 2026: adds application-level encrypted MFA columns to core.users,
a FIDO2 credential table, and a mfa_required flag on core.tenants.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_mfa_fields"
down_revision: Union[str, None] = "0003_event_bus_reliability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # core.tenants — add mfa_required
    # -----------------------------------------------------------------------
    op.add_column(
        "tenants",
        sa.Column(
            "mfa_required",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        schema="core",
    )

    # -----------------------------------------------------------------------
    # core.users — add MFA columns
    # -----------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        schema="core",
    )
    op.add_column(
        "users",
        sa.Column("mfa_method", sa.String(length=50), nullable=True),
        schema="core",
    )
    # Encrypted bytes columns (LargeBinary) — encrypted by EncryptedString at ORM layer
    op.add_column(
        "users",
        sa.Column("mfa_secret_encrypted", sa.LargeBinary(), nullable=True),
        schema="core",
    )
    op.add_column(
        "users",
        sa.Column("mfa_backup_codes_encrypted", sa.LargeBinary(), nullable=True),
        schema="core",
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_enrolled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="core",
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="core",
    )

    # -----------------------------------------------------------------------
    # core.user_fido2_credentials — new table
    # -----------------------------------------------------------------------
    op.create_table(
        "user_fido2_credentials",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column(
            "sign_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            name=op.f("fk_user_fido2_credentials_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_fido2_credentials")),
        sa.UniqueConstraint("credential_id", name="uq_fido2_credential_id"),
        schema="core",
    )
    op.create_index(
        "ix_fido2_user",
        "user_fido2_credentials",
        ["user_id"],
        schema="core",
    )


def downgrade() -> None:
    # -----------------------------------------------------------------------
    # Drop FIDO2 credentials table
    # -----------------------------------------------------------------------
    op.drop_index("ix_fido2_user", table_name="user_fido2_credentials", schema="core")
    op.drop_table("user_fido2_credentials", schema="core")

    # -----------------------------------------------------------------------
    # core.users — remove MFA columns
    # -----------------------------------------------------------------------
    op.drop_column("users", "mfa_last_used_at", schema="core")
    op.drop_column("users", "mfa_enrolled_at", schema="core")
    op.drop_column("users", "mfa_backup_codes_encrypted", schema="core")
    op.drop_column("users", "mfa_secret_encrypted", schema="core")
    op.drop_column("users", "mfa_method", schema="core")
    op.drop_column("users", "mfa_enabled", schema="core")

    # -----------------------------------------------------------------------
    # core.tenants — remove mfa_required
    # -----------------------------------------------------------------------
    op.drop_column("tenants", "mfa_required", schema="core")
