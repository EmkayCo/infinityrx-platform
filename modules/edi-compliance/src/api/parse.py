"""EDI parsing API endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from ..x12.parsers.parse_271 import parse_271
from ..x12.parsers.parse_277 import parse_277
from ..x12.parsers.parse_278 import parse_278
from ..x12.parsers.parse_834 import parse_834
from ..x12.parsers.parse_835 import parse_835
from ..x12.parsers.parse_999 import parse_999, parse_ta1
from ..x12.validators.validator import validate_x12


def _require_tenant(x_tenant_id: Annotated[Optional[str], Header()] = None) -> uuid.UUID:
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail={"error": {"code": "MISSING_TENANT", "message": "x-tenant-id header required"}})
    try:
        return uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(status_code=403, detail={"error": {"code": "INVALID_TENANT", "message": "x-tenant-id must be a valid UUID"}})


router = APIRouter(prefix="/parse", tags=["parsing"])


class ParseRequest(BaseModel):
    content: str


class ParseResponse(BaseModel):
    transaction_type: str
    is_valid: bool
    errors: list[str]
    data: dict


@router.post("/835", response_model=ParseResponse)
async def api_parse_835(
    req: ParseRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
) -> ParseResponse:
    """Parse an inbound 835 remittance advice."""
    try:
        parsed = parse_835(req.content)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "PARSE_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    validation = validate_x12(req.content)
    return ParseResponse(
        transaction_type="835",
        is_valid=validation.is_valid,
        errors=[f"{e.code}: {e.message}" for e in validation.errors],
        data={
            "sender_id": parsed.sender_id,
            "receiver_id": parsed.receiver_id,
            "isa_control_number": parsed.isa_control_number,
            "payment_amount": str(parsed.payment_amount),
            "payment_date": parsed.payment_date,
            "check_eft_number": parsed.check_eft_number,
            "payer_id": parsed.payer_id,
            "claim_count": len(parsed.claims),
            "total_claim_paid": str(parsed.total_claim_paid),
            "reconciliation_ok": parsed.payment_amount == parsed.total_claim_paid,
        },
    )


@router.post("/271", response_model=ParseResponse)
async def api_parse_271(
    req: ParseRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
) -> ParseResponse:
    """Parse an inbound 271 eligibility response."""
    try:
        parsed = parse_271(req.content)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "PARSE_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return ParseResponse(
        transaction_type="271",
        is_valid=True,
        errors=[],
        data={
            "sender_id": parsed.sender_id,
            "receiver_id": parsed.receiver_id,
            "isa_control_number": parsed.isa_control_number,
            "payer_id": parsed.payer_id,
            "payer_name": parsed.payer_name,
            "subscriber_id": parsed.subscriber_id,
            "eligibility_status": parsed.eligibility_status,
            "plan_begin_date": parsed.plan_begin_date,
            "plan_end_date": parsed.plan_end_date,
            "benefit_count": len(parsed.benefits),
        },
    )


@router.post("/277", response_model=ParseResponse)
async def api_parse_277(
    req: ParseRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
) -> ParseResponse:
    """Parse an inbound 277 claim status response."""
    try:
        parsed = parse_277(req.content)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "PARSE_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return ParseResponse(
        transaction_type="277",
        is_valid=True,
        errors=[],
        data={
            "sender_id": parsed.sender_id,
            "receiver_id": parsed.receiver_id,
            "isa_control_number": parsed.isa_control_number,
            "payer_id": parsed.payer_id,
            "payer_name": parsed.payer_name,
            "claim_count": len(parsed.claim_statuses),
        },
    )


@router.post("/278", response_model=ParseResponse)
async def api_parse_278(
    req: ParseRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
) -> ParseResponse:
    """Parse an inbound 278 prior authorization request or response."""
    try:
        parsed = parse_278(req.content)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "PARSE_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return ParseResponse(
        transaction_type="278",
        is_valid=True,
        errors=[],
        data={
            "sender_id": parsed.sender_id,
            "receiver_id": parsed.receiver_id,
            "isa_control_number": parsed.isa_control_number,
            "payer_id": parsed.payer_id,
            "payer_name": parsed.payer_name,
            "provider_npi": parsed.provider_npi,
            "subscriber_id": parsed.subscriber_id,
            "service_review_count": len(parsed.service_reviews),
        },
    )


@router.post("/834", response_model=ParseResponse)
async def api_parse_834(
    req: ParseRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
) -> ParseResponse:
    """Parse an inbound 834 benefit enrollment transaction."""
    try:
        parsed = parse_834(req.content)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "PARSE_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return ParseResponse(
        transaction_type="834",
        is_valid=True,
        errors=[],
        data={
            "sender_id": parsed.sender_id,
            "receiver_id": parsed.receiver_id,
            "isa_control_number": parsed.isa_control_number,
            "payer_id": parsed.payer_id,
            "payer_name": parsed.payer_name,
            "member_count": len(parsed.members),
            "reference_number": parsed.reference_number,
        },
    )


@router.post("/999", response_model=ParseResponse)
async def api_parse_999(
    req: ParseRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
) -> ParseResponse:
    """Parse an inbound 999 functional acknowledgment."""
    try:
        parsed = parse_999(req.content)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "PARSE_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return ParseResponse(
        transaction_type="999",
        is_valid=True,
        errors=[],
        data={
            "sender_id": parsed.sender_id,
            "receiver_id": parsed.receiver_id,
            "isa_control_number": parsed.isa_control_number,
            "ack_code": parsed.ack_code,
            "original_gs_control": parsed.original_gs_control,
            "original_transaction_type": parsed.original_transaction_type,
            "error_codes": parsed.error_codes,
        },
    )


@router.post("/ta1", response_model=ParseResponse)
async def api_parse_ta1(
    req: ParseRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
) -> ParseResponse:
    """Parse an inbound TA1 interchange acknowledgment."""
    try:
        parsed = parse_ta1(req.content)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "PARSE_FAILED", "message": str(exc), "correlation_id": str(uuid.uuid4())}},
        )
    return ParseResponse(
        transaction_type="TA1",
        is_valid=True,
        errors=[],
        data={
            "ack_control_number": parsed.ack_control_number,
            "ack_date": parsed.ack_date,
            "ack_time": parsed.ack_time,
            "ack_code": parsed.ack_code,
            "error_code": parsed.error_code,
        },
    )


@router.post("/validate", response_model=ParseResponse)
async def api_validate(
    req: ParseRequest,
    tenant_id: uuid.UUID = Depends(_require_tenant),
) -> ParseResponse:
    """Validate any X12 file without processing it."""
    validation = validate_x12(req.content)
    return ParseResponse(
        transaction_type="unknown",
        is_valid=validation.is_valid,
        errors=[f"{e.code}: {e.message}" for e in validation.errors],
        data={},
    )
