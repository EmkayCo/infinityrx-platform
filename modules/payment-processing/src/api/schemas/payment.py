"""Pydantic schemas for payment-processing API."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class VendorAdapterCreate(BaseModel):
    vendor_type: str
    name: str
    connection_type: str
    settlement_method: str
    api_endpoint: str | None = None
    api_version: str | None = None
    sftp_host: str | None = None
    sftp_port: int = 22
    sftp_username: str | None = None
    sftp_remote_path: str | None = None
    credentials_vault_ref: str | None = None
    file_format: str | None = None
    file_naming_pattern: str | None = None
    settlement_poll_interval_minutes: int = 60
    expected_settlement_days: int = 2
    supports_ach: bool = False
    supports_eft: bool = False
    supports_virtual_card: bool = False
    supports_check: bool = False
    supports_same_day_ach: bool = False
    failover_chain: list[str] | None = None


class VendorAdapterUpdate(BaseModel):
    name: str | None = None
    connection_type: str | None = None
    settlement_method: str | None = None
    api_endpoint: str | None = None
    sftp_host: str | None = None
    sftp_port: int | None = None
    sftp_username: str | None = None
    sftp_remote_path: str | None = None
    credentials_vault_ref: str | None = None
    file_format: str | None = None
    file_naming_pattern: str | None = None
    settlement_poll_interval_minutes: int | None = None
    expected_settlement_days: int | None = None
    supports_ach: bool | None = None
    supports_eft: bool | None = None
    supports_virtual_card: bool | None = None
    supports_check: bool | None = None
    supports_same_day_ach: bool | None = None
    is_active: bool | None = None
    failover_chain: list[str] | None = None


class VendorAdapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    vendor_type: str
    name: str
    connection_type: str
    settlement_method: str
    status: str
    is_active: bool
    supports_ach: bool
    supports_eft: bool
    supports_virtual_card: bool
    supports_check: bool
    supports_same_day_ach: bool
    error_count_24h: int
    last_submission_at: datetime | None = None
    last_submission_status: str | None = None
    created_at: datetime
    updated_at: datetime


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    vendor_adapter_id: str
    billing_payment_batch_id: str
    submission_type: str
    file_name: str | None = None
    file_format: str | None = None
    payment_count: int
    total_amount: Decimal
    status: str
    submitted_at: datetime | None = None
    acknowledged_at: datetime | None = None
    completed_at: datetime | None = None
    vendor_reference: str | None = None
    error_message: str | None = None
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None = None
    ofac_screened: bool
    fraud_monitoring_logged: bool
    created_at: datetime
    updated_at: datetime


class SettlementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    submission_id: str
    billing_payment_id: str
    pay_to_entity_id: str
    pay_to_npi: str | None = None
    amount: Decimal
    status: str
    settlement_date: date | None = None
    settlement_reference: str | None = None
    payment_method_used: str | None = None
    check_number: str | None = None
    trace_number: str | None = None
    return_code: str | None = None
    return_reason: str | None = None
    return_date: date | None = None
    vendor_payment_id: str | None = None
    is_held: bool
    hold_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class AchReturnCodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    description: str
    category: str
    is_retryable: bool
    default_action: str
    retry_delay_days: int | None = None
    triggers_fwa_alert: bool


class VendorHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vendor_adapter_id: str
    check_type: str
    status: str
    response_time_ms: int | None = None
    error_message: str | None = None
    checked_at: datetime


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    vendor_adapter_id: str
    pay_to_entity_id: str
    pay_to_npi: str | None = None
    pay_to_name: str | None = None
    enrollment_status: str
    preferred_payment_method: str | None = None
    enrolled_at: datetime | None = None
    last_payment_at: datetime | None = None


class ReconciliationRow(BaseModel):
    submission_id: str
    billing_payment_id: str
    expected_amount: Decimal
    actual_amount: Decimal | None = None
    status: str
    discrepancy: Decimal | None = None
    days_outstanding: int | None = None


class PaymentDashboard(BaseModel):
    total_submitted_30d: Decimal
    total_settled_30d: Decimal
    total_returned_30d: Decimal
    submission_count_30d: int
    settlement_rate_pct: Decimal
    pending_settlement_count: int
    pending_settlement_amount: Decimal
    vendor_statuses: list[dict]


class PaymentHoldRequest(BaseModel):
    entity_id: str
    reason: str = Field(..., min_length=1)


class ManualSettlementRequest(BaseModel):
    settlement_date: date
    settlement_reference: str = Field(..., min_length=1)
    payment_method_used: str
    check_number: str | None = None


class ReturnRecordRequest(BaseModel):
    billing_payment_id: str
    return_code: str = Field(..., min_length=1, max_length=10)
    return_date: date
    return_reason: str | None = None
    amount: Decimal
