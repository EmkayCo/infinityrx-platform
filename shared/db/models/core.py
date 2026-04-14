"""ORM models for the ``core`` schema.

Mirrors :doc:`docs/prd/prd-core-platform.md` section 2 exactly. Every table
that holds tenant-owned data inherits from :class:`TenantScopedMixin` so that
the session-level tenant isolation loader criteria apply automatically.

Design choices
--------------
* UUID primary keys with ``gen_random_uuid()`` server default — non-guessable,
  safe for external exposure, compatible with distributed inserts.
* All timestamps are ``TIMESTAMPTZ`` with a server ``NOW()`` default — no
  client-side time drift, and DST-safe.
* ``audit_log.id`` is ``BIGSERIAL`` because it is monotonic, append-only, and
  will exceed 32-bit integers well inside the retention window at 100M
  claims/year.
* No ``Float`` anywhere — the project forbids floats for any numeric value
  that might touch money. None of the core tables hold money today, but the
  convention is enforced globally so future contributors can't slip.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.crypto.sqlalchemy_types import EncryptedString
from shared.db.base import Base
from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "core"


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


def _ts_now() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'terminated')",
            name="tenants_status_valid",
        ),
        Index("ix_tenants_slug", "slug"),
        Index("ix_tenants_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )

    logo_url: Mapped[str | None] = mapped_column(Text)
    primary_color: Mapped[str | None] = mapped_column(String(7), server_default="#0B1D3A")
    secondary_color: Mapped[str | None] = mapped_column(String(7), server_default="#FFFFFF")
    font_family: Mapped[str | None] = mapped_column(String(100), server_default="Inter")
    custom_domain: Mapped[str | None] = mapped_column(String(255))

    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(20))

    timezone: Mapped[str | None] = mapped_column(String(50), server_default="America/New_York")
    date_format: Mapped[str | None] = mapped_column(String(20), server_default="MM/DD/YYYY")
    currency: Mapped[str | None] = mapped_column(String(3), server_default="USD")

    data_retention_days: Mapped[int] = mapped_column(Integer, server_default="2555")

    # Security settings
    mfa_required: Mapped[bool] = mapped_column(Boolean, server_default="true")

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.users.id", use_alter=True, name="fk_tenants_created_by_users"),
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.users.id", use_alter=True, name="fk_tenants_updated_by_users"),
    )


# ---------------------------------------------------------------------------
# Users / roles / permissions
# ---------------------------------------------------------------------------


class User(Base, TenantScopedMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        CheckConstraint(
            "status IN ('active', 'inactive', 'locked')",
            name="users_status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.tenants.id"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    azure_ad_oid: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, server_default="0")

    # MFA fields (HIPAA 2026 — application-level encryption on secrets)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    mfa_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "totp" | "fido2"
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    mfa_backup_codes_encrypted: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    mfa_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = _ts_now()
    updated_at: Mapped[datetime] = _ts_now()


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.tenants.id"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_at: Mapped[datetime] = _ts_now()


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
        {"schema": SCHEMA},
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=False
    )
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.roles.id"), nullable=False
    )
    granted_at: Mapped[datetime] = _ts_now()
    granted_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id")
    )


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("module", "action", name="uq_permissions_module_action"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    module: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
        {"schema": SCHEMA},
    )

    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.roles.id"), nullable=False
    )
    permission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.permissions.id"), nullable=False
    )


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditLog(Base, TenantScopedMixin):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_entity", "tenant_id", "entity_type", "entity_id"),
        Index("ix_audit_user", "tenant_id", "user_id", "created_at"),
        Index("ix_audit_action", "tenant_id", "action", "created_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.tenants.id"),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    module: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(255))
    before_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    # Tamper-evident hash chain (HIPAA 2026 — added by audit-hash-chain agent)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class Notification(Base, TenantScopedMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="notifications_severity_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenants.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=False
    )
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), server_default="info")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "notification_type", name="uq_notification_prefs_user_type"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"), nullable=False
    )
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    sms_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'disabled')",
            name="jobs_status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenants.id")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    schedule: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _ts_now()


class JobRun(Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'cancelled')",
            name="job_runs_status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.jobs.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = _ts_now()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    items_processed: Mapped[int] = mapped_column(Integer, server_default="0")
    items_failed: Mapped[int] = mapped_column(Integer, server_default="0")


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


class File(Base, TenantScopedMixin):
    __tablename__ = "files"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenants.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    module: Mapped[str | None] = mapped_column(String(100))
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(255))
    uploaded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id")
    )
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Government exclusion screening
# ---------------------------------------------------------------------------


class ExclusionList(Base):
    __tablename__ = "exclusion_list"
    __table_args__ = (
        CheckConstraint("source IN ('OIG', 'SAM')", name="exclusion_list_source_valid"),
        CheckConstraint(
            "entity_type IN ('individual', 'organization')",
            name="exclusion_list_entity_type_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    npi: Mapped[str | None] = mapped_column(String(10))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    organization_name: Mapped[str | None] = mapped_column(String(500))
    state: Mapped[str | None] = mapped_column(String(2))
    exclusion_type: Mapped[str | None] = mapped_column(String(100))
    exclusion_date: Mapped[date | None] = mapped_column(Date)
    reinstate_date: Mapped[date | None] = mapped_column(Date)
    last_updated: Mapped[datetime] = _ts_now()


class ExclusionMatch(Base, TenantScopedMixin):
    __tablename__ = "exclusion_matches"
    __table_args__ = (
        CheckConstraint(
            "match_confidence IN ('exact', 'probable', 'possible')",
            name="exclusion_matches_confidence_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'dismissed')",
            name="exclusion_matches_status_valid",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.tenants.id"), nullable=False
    )
    exclusion_list_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey(f"{SCHEMA}.exclusion_list.id")
    )
    matched_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    match_confidence: Mapped[str] = mapped_column(String(20), server_default="exact")
    status: Mapped[str] = mapped_column(String(20), server_default="pending")
    reviewed_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# FIDO2 / WebAuthn credentials
# ---------------------------------------------------------------------------


class UserFido2Credential(Base):
    """Stores a registered FIDO2 / WebAuthn credential for a user.

    One user may have multiple hardware keys. credential_id is the
    unique identifier returned by the authenticator during registration.
    """

    __tablename__ = "user_fido2_credentials"
    __table_args__ = (
        Index("ix_fido2_user", "user_id"),
        UniqueConstraint("credential_id", name="uq_fido2_credential_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.users.id"),
        nullable=False,
        index=True,
    )
    credential_id: Mapped[bytes] = mapped_column(nullable=False, unique=True)
    public_key: Mapped[bytes] = mapped_column(nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    created_at: Mapped[datetime] = _ts_now()


__all__ = [
    "Tenant",
    "User",
    "UserFido2Credential",
    "Role",
    "UserRole",
    "Permission",
    "RolePermission",
    "AuditLog",
    "Notification",
    "NotificationPreference",
    "Job",
    "JobRun",
    "File",
    "ExclusionList",
    "ExclusionMatch",
]
