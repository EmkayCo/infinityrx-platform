"""Pydantic schemas for audit entries and queries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEntry(BaseModel):
    """Input to ``AuditService.log``. Only ``tenant_id``/``action``/``module``
    are strictly required — middleware fills the rest."""

    model_config = ConfigDict(frozen=False)

    tenant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    module: str
    entity_type: str | None = None
    entity_id: str | None = None
    before_value: dict[str, Any] | None = None
    after_value: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: uuid.UUID | None = None


class AuditEntryRead(BaseModel):
    id: int
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    action: str
    module: str
    entity_type: str | None
    entity_id: str | None
    before_value: dict[str, Any] | None
    after_value: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    correlation_id: uuid.UUID | None
    created_at: datetime


class AuditQuery(BaseModel):
    action: str | None = None
    module: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    user_id: uuid.UUID | None = None
    correlation_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class AuditPage(BaseModel):
    items: list[AuditEntryRead]
    total: int
    limit: int
    offset: int
