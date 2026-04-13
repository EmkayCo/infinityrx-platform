"""Pydantic schemas for vendor, bank, accounting, and SFTP config endpoints."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentVendorResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    vendor_name: str
    vendor_type: str
    is_active: bool
    is_default: bool


class PaymentVendorCreateRequest(BaseModel):
    vendor_name: str
    vendor_type: str
    config: dict = Field(default_factory=dict)
    is_default: bool = False


class BankAccountResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    account_name: str
    account_type: str
    routing_number: str
    account_number_last4: str
    is_active: bool
    is_default: bool


class BankAccountCreateRequest(BaseModel):
    account_name: str
    account_type: str
    routing_number: str
    account_number: str
    is_default: bool = False


class AccountingConfigResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    system_type: str
    export_format: str
    auto_export: bool
    is_active: bool


class AccountingConfigUpdateRequest(BaseModel):
    system_type: str | None = None
    export_format: str | None = None
    auto_export: bool | None = None


class RemittanceConfigResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    delivery_method: str
    format: str
    is_active: bool


class RemittanceConfigCreateRequest(BaseModel):
    client_id: uuid.UUID
    delivery_method: str = "sftp"
    format: str = "835"


class SFTPConfigResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    config_name: str
    host: str
    port: int
    username: str
    remote_path: str
    is_active: bool


class SFTPConfigCreateRequest(BaseModel):
    config_name: str
    host: str
    port: int = Field(default=22, ge=1, le=65535)
    username: str
    password: str | None = None
    private_key: str | None = None
    remote_path: str = "/"


class SFTPTestResponse(BaseModel):
    success: bool
    message: str


class FundingConfigResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    client_id: uuid.UUID
    funding_model: str
    prefund_days: int
    prefund_amount: Decimal | None = None
    auto_replenish: bool


class FundingDepositRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"))
    deposit_date: str
    reference: str | None = None


class FundingProjectionResponse(BaseModel):
    client_id: uuid.UUID
    current_balance: Decimal
    avg_daily_spend: Decimal
    projected_days_remaining: int | None = None
    projected_depletion_date: str | None = None
