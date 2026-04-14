"""Pydantic schemas for member management API.

Input validation uses strict string anchoring per LESSON-004 (fullmatch semantics).
"""
from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PhiAccessLevel(str, Enum):
    FULL = "full"
    PARTIAL = "partial"
    REDACTED = "redacted"


# Validation patterns — \A...\Z for strict string anchoring (LESSON-004)
_BIN_RE = re.compile(r"\A\d{6}\Z")
_SSN_RE = re.compile(r"\A\d{9}\Z")
_PERSON_CODE_RE = re.compile(r"\A\d{1,5}\Z")
_STATE_RE = re.compile(r"\A[A-Z]{2}\Z")
_ZIP_RE = re.compile(r"\A\d{5}(-\d{4})?\Z")


class MemberCreate(BaseModel):
    member_id: str = Field(..., min_length=1, max_length=100)
    person_code: str = Field(default="01", max_length=5)
    cardholder_id: str | None = None
    alternate_id: str | None = None

    first_name: str = Field(..., min_length=1, max_length=255)
    middle_name: str | None = None
    last_name: str = Field(..., min_length=1, max_length=255)
    suffix: str | None = None
    date_of_birth: str  # ISO: YYYY-MM-DD
    gender: str = Field(..., min_length=1, max_length=1)
    ssn: str | None = None

    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str = "US"

    phone: str | None = None
    email: str | None = None
    preferred_language: str = "en"

    relationship_code: str | None = None

    rx_bin: str
    rx_pcn: str | None = None
    rx_group: str | None = None

    effective_date: str  # ISO: YYYY-MM-DD

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        if v not in ("M", "F", "U"):
            raise ValueError(f"gender must be M, F, or U — got {v!r}")
        return v

    @field_validator("rx_bin")
    @classmethod
    def validate_rx_bin(cls, v: str) -> str:
        if not _BIN_RE.fullmatch(v):
            raise ValueError(f"rx_bin must be exactly 6 digits — got {v!r}")
        return v

    @field_validator("ssn")
    @classmethod
    def validate_ssn(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SSN_RE.fullmatch(v):
            raise ValueError("ssn must be exactly 9 digits (no dashes)")
        return v

    @field_validator("person_code")
    @classmethod
    def validate_person_code(cls, v: str) -> str:
        if not _PERSON_CODE_RE.fullmatch(v):
            raise ValueError("person_code must be 1-5 digits")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _STATE_RE.fullmatch(v.upper()):
            raise ValueError("state must be 2 uppercase letters")
        return v.upper()


class MemberUpdate(BaseModel):
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    suffix: str | None = None
    date_of_birth: str | None = None
    gender: str | None = None
    ssn: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    email: str | None = None
    preferred_language: str | None = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str | None) -> str | None:
        if v is not None and v not in ("M", "F", "U"):
            raise ValueError(f"gender must be M, F, or U — got {v!r}")
        return v

    @field_validator("ssn")
    @classmethod
    def validate_ssn(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SSN_RE.fullmatch(v):
            raise ValueError("ssn must be exactly 9 digits (no dashes)")
        return v


class MemberTerminate(BaseModel):
    termination_date: str  # ISO: YYYY-MM-DD
    termination_reason: str = Field(..., min_length=1)


class MemberResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    member_id: str
    person_code: str
    first_name: str | None
    last_name: str | None
    date_of_birth: str | None
    gender: str
    rx_bin: str
    rx_pcn: str | None
    rx_group: str | None
    status: str
    enrollment_date: date | None
    termination_date: date | None

    model_config = {"from_attributes": True}


class GroupCreate(BaseModel):
    group_number: str = Field(..., min_length=1, max_length=50)
    group_name: str = Field(..., min_length=1, max_length=500)
    employer_name: str | None = None
    employer_tax_id: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    billing_cycle: str = "monthly"
    payment_terms_days: int = 30
    effective_date: str  # ISO: YYYY-MM-DD
    default_plan_id: UUID | None = None


class GroupResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    group_number: str
    group_name: str
    effective_date: date
    is_active: bool

    model_config = {"from_attributes": True}


class EnrollmentPreview(BaseModel):
    total_records: int
    valid_records: int
    error_count: int
    sample_records: list[dict[str, Any]]
    errors: list[dict[str, Any]]


class EnrollmentProcessResult(BaseModel):
    added: int
    updated: int
    terminated: int
    errors: int
    enrollment_file_id: UUID


class ErrorResponse(BaseModel):
    error: dict[str, Any]
