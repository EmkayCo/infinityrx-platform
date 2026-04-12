"""Local ORM models for core-platform Session 4 tables.

These mirror the DDL in docs/prd/prd-core-platform.md sections 2.5, 2.6, 2.7.
When T1 ships canonical models in shared.db.models.core, swap the imports
here and retire this file. Kept minimal-but-complete (YAGNI) — only the
columns needed by jobs/files/exclusions services.

Uses the shim Base (sync SQLAlchemy, SQLite-friendly) so tests run without
Docker. Uses String-based UUIDs / timestamps for portability.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import INTEGER as SQLITE_INTEGER

# BigInteger autoincrement does not work on SQLite. Use a dialect-aware
# variant so tests (SQLite) and prod (Postgres) both autoincrement the PK.
_BigIntAutoPK = BigInteger().with_variant(SQLITE_INTEGER(), "sqlite")
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._shim.db import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "core_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    schedule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    runs: Mapped[list["JobRun"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobRun(Base):
    __tablename__ = "core_job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("core_jobs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    items_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="runs")


class File(Base):
    __tablename__ = "core_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100))
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    module: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(36))
    sha256: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ExclusionListEntry(Base):
    __tablename__ = "core_exclusion_list"

    id: Mapped[int] = mapped_column(_BigIntAutoPK, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    npi: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    organization_name: Mapped[Optional[str]] = mapped_column(String(500))
    state: Mapped[Optional[str]] = mapped_column(String(2))
    exclusion_type: Mapped[Optional[str]] = mapped_column(String(100))
    exclusion_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reinstate_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class ExclusionMatch(Base):
    __tablename__ = "core_exclusion_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    exclusion_list_id: Mapped[Optional[int]] = mapped_column(
        _BigIntAutoPK, ForeignKey("core_exclusion_list.id")
    )
    matched_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    match_confidence: Mapped[str] = mapped_column(String(20), default="exact", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    review_reason: Mapped[Optional[str]] = mapped_column(Text)
    match_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
