"""Pydantic schemas for the data-ingestion API.

All request/response types are defined here. Route handlers use these
exclusively — no raw dict returns or untyped JSON.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class TriggerRunRequest(BaseModel):
    """Body for ``POST /{source}/trigger``."""

    triggered_by: UUID | None = Field(
        default=None,
        description="UUID of the user initiating the run.",
    )
    run_type: str = Field(
        default="manual_trigger",
        description="One of: auto_scheduled, manual_trigger, file_upload.",
    )


class CancelRunRequest(BaseModel):
    """Body for ``POST /{source}/cancel``."""

    reason: str | None = Field(
        default=None,
        description="Optional human-readable reason for cancellation.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RunSummary(BaseModel):
    """Abbreviated run information used in status and history lists."""

    id: UUID
    source: str
    run_type: str
    status: str
    records_processed: int
    records_inserted: int
    records_updated: int
    records_skipped: int
    records_errored: int
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    error_message: str | None = None


class RunDetail(RunSummary):
    """Full run detail including file metadata and error samples."""

    source_url: str | None = None
    source_file_name: str | None = None
    source_file_size_bytes: int | None = None
    source_file_checksum: str | None = None
    records_in_source: int | None = None
    download_seconds: int | None = None
    parse_seconds: int | None = None
    load_seconds: int | None = None
    error_samples: list[dict[str, Any]] | None = None
    triggered_by: UUID | None = None
    created_at: datetime


class SourceStatus(BaseModel):
    """Current state of a single source pipeline."""

    source: str
    cron_expression: str | None
    enabled: bool
    last_run: RunSummary | None = None
    last_success_at: datetime | None = None
    next_run_at: datetime | None = None


class TriggerResponse(BaseModel):
    """Response body for ``POST /{source}/trigger``."""

    run_id: UUID
    source: str
    status: str
    message: str


class CancelResponse(BaseModel):
    """Response body for ``POST /{source}/cancel``."""

    run_id: UUID
    source: str
    status: str
    message: str


class FieldCatalogEntry(BaseModel):
    """Single entry in the field catalog."""

    source: str
    table: str
    column: str
    description: str
    source_file: str
    source_position: str
    data_type: str


class FieldCatalogResponse(BaseModel):
    """Response for ``GET /field-catalog``."""

    total: int
    fields: list[FieldCatalogEntry]


class ErrorDetail(BaseModel):
    """Standard error payload."""

    code: str
    message: str
    correlation_id: str


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    error: ErrorDetail


__all__ = [
    "CancelResponse",
    "CancelRunRequest",
    "ErrorDetail",
    "ErrorResponse",
    "FieldCatalogEntry",
    "FieldCatalogResponse",
    "RunDetail",
    "RunSummary",
    "SourceStatus",
    "TriggerResponse",
    "TriggerRunRequest",
]
