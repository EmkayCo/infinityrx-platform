"""ORM models for ingestion run tracking and scheduling.

Schema: ``shared``. These are GLOBAL reference-registry tables, not
tenant-owned. Per LESSON-011 (docs/lessons-learned.md), reference registries
are shared cross-tenant and MUST NOT inherit TenantScopedMixin. A comment
on each model cites LESSON-011.
"""

from __future__ import annotations

import uuid as _uuid_module
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base

SCHEMA = "shared"


class IngestionRun(Base):
    """Tracks a single execution of a reference-data ingestion pipeline.

    Global reference table — NOT tenant-scoped. See LESSON-011: reference
    registries (NDC, NPI, NADAC, etc.) are shared cross-tenant and MUST NOT
    use TenantScopedMixin.
    """

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_source_started", "source", "started_at"),
        Index("ix_ingestion_runs_status", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=_uuid_module.uuid4,
        server_default=func.gen_random_uuid(),
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    run_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # auto_scheduled | manual_trigger | file_upload
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="running"
    )  # running | completed | failed | skipped_unchanged | cancelled
    source_url: Mapped[str | None] = mapped_column(Text)
    source_file_name: Mapped[str | None] = mapped_column(String(500))
    source_file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    source_file_checksum: Mapped[str | None] = mapped_column(String(128))
    records_in_source: Mapped[int | None] = mapped_column(Integer)
    records_processed: Mapped[int] = mapped_column(Integer, server_default="0")
    records_inserted: Mapped[int] = mapped_column(Integer, server_default="0")
    records_updated: Mapped[int] = mapped_column(Integer, server_default="0")
    records_skipped: Mapped[int] = mapped_column(Integer, server_default="0")
    records_errored: Mapped[int] = mapped_column(Integer, server_default="0")
    error_samples: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    download_seconds: Mapped[int | None] = mapped_column(Integer)
    parse_seconds: Mapped[int | None] = mapped_column(Integer)
    load_seconds: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IngestionSchedule(Base):
    """Persists the schedule configuration for each reference-data source.

    Global reference table — NOT tenant-scoped. See LESSON-011: reference
    registries are shared cross-tenant and MUST NOT use TenantScopedMixin.
    """

    __tablename__ = "ingestion_schedules"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=_uuid_module.uuid4,
        server_default=func.gen_random_uuid(),
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    cron_expression: Mapped[str | None] = mapped_column(String(100))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.true())
    last_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.ingestion_runs.id"),
        nullable=True,
    )
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


__all__ = ["IngestionRun", "IngestionSchedule"]
