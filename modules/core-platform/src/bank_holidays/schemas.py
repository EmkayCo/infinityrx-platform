"""Pydantic schemas for the bank holidays REST API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HolidayRead(BaseModel):
    """Response schema for a bank holiday row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    holiday_date: date
    name: str
    country: str
    is_federal: bool
    is_bank_holiday: bool
    created_at: datetime


class HolidayCreate(BaseModel):
    """Request body for creating a custom holiday."""

    holiday_date: date = Field(..., description="ISO 8601 date, e.g. 2026-08-15")
    name: str = Field(..., min_length=1, max_length=255)
    country: str = Field(default="US", min_length=2, max_length=2)
    is_bank_holiday: bool = Field(default=True)

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, v: str) -> str:
        return v.upper()


class BusinessDayResponse(BaseModel):
    """Response for is-business-day check."""

    date: date
    is_business_day: bool
    reason: str | None = None  # Name of holiday blocking it, or None


class NextBusinessDayResponse(BaseModel):
    """Response for next-business-day lookup."""

    from_date: date = Field(..., alias="from")
    next_business_day: date

    model_config = ConfigDict(populate_by_name=True)


__all__ = [
    "HolidayRead",
    "HolidayCreate",
    "BusinessDayResponse",
    "NextBusinessDayResponse",
]
