"""Pydantic schemas for dashboards and filter presets."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WidgetConfig(BaseModel):
    widget_type: str
    position: dict[str, int]  # x, y, w, h
    config: dict[str, Any]


class DashboardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    role_target: str | None = None
    layout: list[WidgetConfig] = Field(default_factory=list)


class DashboardRead(BaseModel):
    id: str
    tenant_id: str | None
    name: str
    description: str | None
    role_target: str | None
    layout: list[dict[str, Any]]
    is_default: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardUpdate(BaseModel):
    name: str | None = None
    layout: list[WidgetConfig] | None = None


class UserDashboardUpdate(BaseModel):
    custom_layout: list[dict[str, Any]] | None = None
    pinned_filters: dict[str, Any] | None = None


class FilterPresetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    filters: dict[str, Any]
    applies_to: dict[str, Any] | None = None
    shared: bool = False


class FilterPresetRead(BaseModel):
    id: str
    tenant_id: str
    user_id: str | None
    name: str
    filters: dict[str, Any]
    applies_to: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WidgetDataResponse(BaseModel):
    widget_id: str
    widget_type: str
    data: list[dict[str, Any]]
    metadata: dict[str, Any] = Field(default_factory=dict)
    data_as_of: datetime | None = None
    refresh_interval_seconds: int = 300
