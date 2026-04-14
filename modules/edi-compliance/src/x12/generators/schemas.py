"""Pydantic input schemas for X12 generators."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CasAdjustment(BaseModel):
    group_code: str          # CO, OA, PI, PR
    reason_code: str
    amount: Decimal

    @field_validator("amount")
    @classmethod
    def amount_is_decimal(cls, v: Decimal) -> Decimal:
        if not isinstance(v, Decimal):
            raise ValueError("amount must be Decimal")
        return v


class SvcLine(BaseModel):
    procedure_code: str
    procedure_qualifier: str = "HC"
    charge_amount: Decimal
    paid_amount: Decimal
    quantity: Decimal = Decimal("1")
    ndc: Optional[str] = None
    rx_number: Optional[str] = None
    adjustments: List[CasAdjustment] = Field(default_factory=list)
    original_units: Optional[Decimal] = None


class ClpClaim(BaseModel):
    claim_id: str
    status_code: str = "1"
    charge_amount: Decimal
    paid_amount: Decimal
    patient_responsibility: Decimal = Decimal("0")
    claim_filing_indicator: str = "HM"
    payer_claim_ref: str = ""
    adjustments: List[CasAdjustment] = Field(default_factory=list)
    service_lines: List[SvcLine] = Field(default_factory=list)
    pharmacy_npi: Optional[str] = None
    bin_number: Optional[str] = None
    ncpdp_number: Optional[str] = None
    chain_code: Optional[str] = None
    patient_control_number: str = ""


class N1Party(BaseModel):
    entity_qualifier: str
    name: str
    id_qualifier: Optional[str] = None
    id_code: Optional[str] = None


class TrnTrace(BaseModel):
    check_eft_number: str
    payer_id: str
    originating_company_id: Optional[str] = None


class Generate835Request(BaseModel):
    tenant_id: UUID
    trading_partner_id: UUID
    isa_control_number: int
    gs_control_number: int
    st_control_number: int = 1
    payment_date: str
    payment_amount: Decimal
    credit_debit_flag: str = "C"
    payment_method: str = "ACH"
    check_eft_number: str
    payer: N1Party
    payee: N1Party
    trace: TrnTrace
    claims: List[ClpClaim] = Field(default_factory=list)
    sender_qualifier: str = "ZZ"
    sender_id: str = "INFINITYRX     "
    receiver_qualifier: str = "ZZ"
    receiver_id: str = "RECEIVER       "
    test_mode: bool = True
    implementation_guide: str = "005010X221A1"
    metadata: dict = Field(default_factory=dict)


class Generate837PRequest(BaseModel):
    tenant_id: UUID
    trading_partner_id: UUID
    isa_control_number: int
    gs_control_number: int
    st_control_number: int = 1
    sender_qualifier: str = "ZZ"
    sender_id: str = "INFINITYRX     "
    receiver_qualifier: str = "ZZ"
    receiver_id: str
    test_mode: bool = True
    implementation_guide: str = "005010X222A2"
    billing_provider_npi: str
    billing_provider_name: str
    billing_provider_ein: Optional[str] = None
    subscriber_id: str
    subscriber_last_name: str
    subscriber_first_name: str
    subscriber_dob: str
    subscriber_gender: str
    payer_id: str
    payer_name: str
    claims: List[Any] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class Generate270Request(BaseModel):
    tenant_id: UUID
    trading_partner_id: UUID
    isa_control_number: int
    gs_control_number: int
    st_control_number: int = 1
    sender_qualifier: str = "ZZ"
    sender_id: str = "INFINITYRX     "
    receiver_qualifier: str = "ZZ"
    receiver_id: str
    test_mode: bool = True
    implementation_guide: str = "005010X279A1"
    payer_id: str
    payer_name: str
    receiver_id_qualifier: str = "XX"
    receiver_npi: str
    subscriber_id: str
    subscriber_last_name: str
    subscriber_first_name: str
    subscriber_dob: Optional[str] = None
    service_type_codes: List[str] = Field(default_factory=lambda: ["30"])
    date_of_service: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
