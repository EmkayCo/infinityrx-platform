"""Pydantic schemas for regulatory submissions and actuarial models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from src.utils.constants import (
    REG_CAA_TRANSPARENCY,
    REG_CMS_QUALITY,
    REG_CUSTOM,
    REG_DIR,
    REG_PDE,
    REG_STAR_RATINGS,
    REG_STATE,
    REG_STATUS_ACCEPTED,
    REG_STATUS_APPROVED,
    REG_STATUS_DRAFT,
    REG_STATUS_REJECTED,
    REG_STATUS_REVIEW,
    REG_STATUS_SUBMITTED,
)

VALID_REG_TYPES = [
    REG_CAA_TRANSPARENCY,
    REG_CMS_QUALITY,
    REG_STAR_RATINGS,
    REG_STATE,
    REG_DIR,
    REG_PDE,
    REG_CUSTOM,
]
VALID_REG_STATUSES = [
    REG_STATUS_DRAFT,
    REG_STATUS_REVIEW,
    REG_STATUS_APPROVED,
    REG_STATUS_SUBMITTED,
    REG_STATUS_ACCEPTED,
    REG_STATUS_REJECTED,
]


class RegulatorySubmissionCreate(BaseModel):
    report_type: str
    period_start: date
    period_end: date
    due_date: date

    def model_post_init(self, __context: Any) -> None:
        if self.report_type not in VALID_REG_TYPES:
            raise ValueError(f"report_type must be one of {VALID_REG_TYPES}")


class RegulatorySubmissionRead(BaseModel):
    id: str
    tenant_id: str
    report_type: str
    period_start: Any
    period_end: Any
    status: str
    due_date: Any
    submitted_at: datetime | None
    accepted_at: datetime | None
    file_id: str | None
    submission_reference: str | None
    reviewed_by: str | None
    approved_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RegulatoryStatusUpdate(BaseModel):
    status: str

    def model_post_init(self, __context: Any) -> None:
        if self.status not in VALID_REG_STATUSES:
            raise ValueError(f"status must be one of {VALID_REG_STATUSES}")


class ActuarialModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    model_type: str
    input_parameters: dict[str, Any] | None = None
    methodology: str | None = None


class ActuarialModelRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    model_type: str
    results: dict[str, Any] | None
    confidence_interval: Decimal | None
    methodology: str | None
    status: str
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StarRatingsResponse(BaseModel):
    tenant_id: str
    measurement_period: str
    measures: list[dict[str, Any]]
    overall_status: str
    data_as_of: datetime


class PdcAdherenceResponse(BaseModel):
    measure_id: str
    measure_name: str
    current_pdc: Decimal
    target_pdc: Decimal
    adherent_members: int
    total_members: int
    rate: Decimal
    status: str
    data_as_of: datetime


class AdherenceGapMember(BaseModel):
    member_id: str
    member_name: str | None
    current_pdc: Decimal
    gap_days: int
    last_fill_date: date | None
    next_fill_due: date | None
