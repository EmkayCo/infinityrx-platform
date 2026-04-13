"""Pydantic schemas for report definitions, runs, and scheduling."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.utils.constants import (
    ALL_CATEGORIES,
    ALL_DELIVERY_METHODS,
    ALL_FORMATS,
    ALL_FREQUENCIES,
)


class ColumnDefinition(BaseModel):
    field: str
    label: str
    type: str = "string"
    format: str | None = None
    sortable: bool = True
    filterable: bool = True


class ReportDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    category: str
    data_source: str = Field(..., min_length=1, max_length=100)
    base_query: str | None = None
    columns: list[ColumnDefinition] = Field(..., min_length=1)
    default_filters: dict[str, Any] | None = None
    default_groupings: dict[str, Any] | None = None
    default_sort: dict[str, Any] | None = None
    calculated_fields: list[dict[str, Any]] | None = None
    summary_row: dict[str, Any] | None = None
    chart_type: str | None = None
    chart_config: dict[str, Any] | None = None
    required_permission: str | None = None
    contains_phi: bool = False

    @field_validator("category")
    @classmethod
    def _validate_category(cls, v: str) -> str:
        if v not in ALL_CATEGORIES:
            raise ValueError(f"category must be one of {ALL_CATEGORIES}")
        return v


class ReportDefinitionRead(BaseModel):
    id: str
    tenant_id: str | None
    name: str
    description: str | None
    category: str
    data_source: str
    columns: list[dict[str, Any]]
    chart_type: str | None
    required_permission: str | None
    is_system: bool
    is_active: bool
    contains_phi: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportRunRequest(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)
    output_format: str = "excel"
    priority: int | None = None

    @field_validator("output_format")
    @classmethod
    def _validate_format(cls, v: str) -> str:
        if v not in ALL_FORMATS:
            raise ValueError(f"output_format must be one of {ALL_FORMATS}")
        return v


class ReportRunRead(BaseModel):
    id: str
    tenant_id: str
    report_definition_id: str
    schedule_id: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    duration_seconds: int | None
    filters_applied: dict[str, Any] | None
    row_count: int | None
    output_format: str | None
    output_file_id: str | None
    delivered_at: datetime | None
    delivery_status: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


class ReportScheduleCreate(BaseModel):
    report_definition_id: str
    name: str = Field(..., min_length=1, max_length=255)
    frequency: str
    day_of_week: int | None = Field(None, ge=0, le=6)
    day_of_month: int | None = Field(None, ge=1, le=31)
    time_of_day: str = "06:00"
    timezone: str = "America/New_York"
    filters: dict[str, Any] | None = None
    output_format: str
    delivery_method: str
    delivery_recipients: dict[str, Any] | None = None
    sftp_config_id: str | None = None
    template_id: str | None = None
    include_cover_page: bool = False
    include_charts: bool = True

    @field_validator("frequency")
    @classmethod
    def _validate_frequency(cls, v: str) -> str:
        if v not in ALL_FREQUENCIES:
            raise ValueError(f"frequency must be one of {ALL_FREQUENCIES}")
        return v

    @field_validator("output_format")
    @classmethod
    def _validate_format(cls, v: str) -> str:
        if v not in ALL_FORMATS:
            raise ValueError(f"output_format must be one of {ALL_FORMATS}")
        return v

    @field_validator("delivery_method")
    @classmethod
    def _validate_delivery(cls, v: str) -> str:
        if v not in ALL_DELIVERY_METHODS:
            raise ValueError(f"delivery_method must be one of {ALL_DELIVERY_METHODS}")
        return v

    @model_validator(mode="after")
    def _validate_weekly_requires_dow(self) -> ReportScheduleCreate:
        if self.frequency == "weekly" and self.day_of_week is None:
            raise ValueError("day_of_week is required for weekly frequency")
        if self.frequency == "monthly" and self.day_of_month is None:
            raise ValueError("day_of_month is required for monthly frequency")
        return self


class ReportScheduleRead(BaseModel):
    id: str
    tenant_id: str
    report_definition_id: str
    name: str
    frequency: str
    day_of_week: int | None
    day_of_month: int | None
    time_of_day: Any
    timezone: str
    output_format: str
    delivery_method: str
    is_active: bool
    last_run_at: datetime | None
    last_run_status: str | None
    next_run_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
