"""Pydantic schemas for journal and budget monitoring API endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    entry_type: str
    amount: Decimal
    category: str
    description: str
    entry_date: date
    client_id: uuid.UUID | None = None
    program_id: uuid.UUID | None = None
    exported_to_accounting: bool
    export_reference: str | None = None
    created_at: datetime


class JournalQueryParams(BaseModel):
    client_id: uuid.UUID | None = None
    program_id: uuid.UUID | None = None
    category: str | None = None
    entry_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    unexported_only: bool = False
    limit: int = Field(default=500, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)


class JournalSummaryResponse(BaseModel):
    period_start: date
    period_end: date
    total_debits: Decimal
    total_credits: Decimal
    net: Decimal
    entry_count: int


class JournalExportResponse(BaseModel):
    export_reference: str
    entry_count: int
    exported_at: datetime


class PeriodCloseRequest(BaseModel):
    period_end: date
    notes: str | None = None


class ProgramBudgetCreateRequest(BaseModel):
    program_id: uuid.UUID
    client_id: uuid.UUID
    budget_type: str = "fixed"
    budget_amount: Decimal = Field(ge=Decimal("0"))
    spend_increase_alert_pct: Decimal = Field(default=Decimal("25"), ge=Decimal("0"))
    budget_remaining_alert_pct: Decimal = Field(
        default=Decimal("20"), ge=Decimal("0"), le=Decimal("100")
    )
    depletion_alert_days: int = Field(default=30, ge=0)


class ProgramBudgetUpdateRequest(BaseModel):
    budget_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    spend_increase_alert_pct: Decimal | None = None
    budget_remaining_alert_pct: Decimal | None = None
    depletion_alert_days: int | None = None


class ProgramBudgetResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    program_id: uuid.UUID
    client_id: uuid.UUID
    budget_type: str
    budget_amount: Decimal
    spent_to_date: Decimal
    burn_rate_30day_avg: Decimal
    spend_increase_alert_pct: Decimal
    budget_remaining_alert_pct: Decimal
    depletion_alert_days: int


class BudgetDashboardResponse(BaseModel):
    budget: ProgramBudgetResponse
    stats: dict
    alerts: list[dict]
    snapshots: list[dict]


class BudgetAlertResponse(BaseModel):
    id: uuid.UUID
    program_budget_id: uuid.UUID
    alert_type: str
    severity: str
    message: str
    acknowledged: bool
    created_at: datetime
