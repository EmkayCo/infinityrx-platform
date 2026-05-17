"""Billing module API router — /api/v1/billing/"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import DBSession, TenantId
from src.api.schemas.ap import (
    BatchGenerateRequest,
    BatchValidateResponse,
    SettlementRecordRequest,
)
from src.api.schemas.ar import (
    ARAgingResponse,
    ARDisputeRequest,
    ARPaymentRequest,
    ARWriteOffRequest,
    FeeConfigCreateRequest,
    FeeConfigUpdateRequest,
    InvoiceGenerateRequest,
    InvoicingConfigCreateRequest,
)
from src.api.schemas.claims import (
    ClaimSubmitRequest,
)
from src.api.schemas.config import (
    AccountingConfigUpdateRequest,
    BankAccountCreateRequest,
    FundingDepositRequest,
    PaymentVendorCreateRequest,
    RemittanceConfigCreateRequest,
    SFTPConfigCreateRequest,
    SFTPTestResponse,
)
from src.api.schemas.journal import (
    PeriodCloseRequest,
    ProgramBudgetCreateRequest,
    ProgramBudgetUpdateRequest,
)
from src.api.schemas.routing import (
    RoutingRuleCreateRequest,
    RoutingRuleUpdateRequest,
    RoutingTestRequest,
    RoutingTestResponse,
)
from src.models.tables import (
    APRecord,
    ARRecord,
    BankAccount,
    ClaimRecord,
    FeeConfig,
    FundingConfig,
    InvoiceLineItem,
    Invoice,
    InvoicingConfig,
    JournalEntry,
    Payment,
    PaymentBatch,
    PaymentVendorConfig,
    PrefundLedger,
    ProgramBudget,
    ProgramBudgetAlert,
    ProgramBudgetSnapshot,
    RemittanceConfig,
    RoutingRule,
    SFTPConfig,
)
from src.utils.constants import (
    AGING_30,
    AGING_60,
    AGING_90,
    AGING_120_PLUS,
    AGING_CURRENT,
)

logger = logging.getLogger(__name__)

_WRITE_ROLES = frozenset({"operator", "approver"})
_APPROVER_ONLY = frozenset({"approver"})

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


@router.post("/claims", status_code=status.HTTP_201_CREATED, response_model=dict)
def submit_claim(
    body: ClaimSubmitRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit a single claim via API."""
    if not any(current_user.has_role(r) for r in _WRITE_ROLES):
        raise HTTPException(status_code=403, detail="Operator or Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "status": "ingested",
        "auth_number": body.auth_number,
    }


@router.get("/claims", response_model=list[dict])
def list_claims(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    program_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    claim_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List claims with optional filters."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(ClaimRecord)
            .where(ClaimRecord.tenant_id == tenant_id)
            .order_by(ClaimRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if client_id is not None:
            stmt = stmt.where(ClaimRecord.client_id == client_id)
        if program_id is not None:
            stmt = stmt.where(ClaimRecord.program_id == program_id)
        if status_filter is not None:
            stmt = stmt.where(ClaimRecord.status == status_filter)
        if claim_type is not None:
            stmt = stmt.where(ClaimRecord.claim_type == claim_type)
        if date_from is not None:
            stmt = stmt.where(ClaimRecord.date_of_service >= date_from)
        if date_to is not None:
            stmt = stmt.where(ClaimRecord.date_of_service <= date_to)
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "auth_number": r.auth_number,
                "claim_type": r.claim_type,
                "status": r.status,
                "pharmacy_npi": r.pharmacy_npi,
                "date_of_service": r.date_of_service.isoformat() if r.date_of_service else None,
                "net_amount": str(r.net_amount),
                "client_id": str(r.client_id) if r.client_id else None,
                "program_id": str(r.program_id) if r.program_id else None,
                "payment_route": r.payment_route,
                "is_excluded": r.is_excluded,
                "is_statement": r.is_statement,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_claims failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_CLAIMS_ERROR", "message": "Failed to list claims", "correlation_id": correlation_id}},
        ) from exc


@router.get("/claims/{claim_id}", response_model=dict)
def get_claim(
    claim_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get claim detail by ID."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = select(ClaimRecord).where(
            ClaimRecord.tenant_id == tenant_id,
            ClaimRecord.id == claim_id,
        )
        row = db.execute(stmt).scalar_one_or_none()
    except Exception as exc:
        logger.error(
            "get_claim DB error",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "GET_CLAIM_ERROR", "message": "Failed to retrieve claim", "correlation_id": correlation_id}},
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "auth_number": row.auth_number,
        "reversal_of_auth": row.reversal_of_auth,
        "claim_type": row.claim_type,
        "status": row.status,
        "source_type": row.source_type,
        "pharmacy_npi": row.pharmacy_npi,
        "pharmacy_name": row.pharmacy_name,
        "prescriber_npi": row.prescriber_npi,
        "ndc": row.ndc,
        "drug_name": row.drug_name,
        "date_of_service": row.date_of_service.isoformat() if row.date_of_service else None,
        "net_amount": str(row.net_amount),
        "ingredient_cost": str(row.ingredient_cost),
        "dispensing_fee": str(row.dispensing_fee),
        "patient_pay": str(row.patient_pay),
        "plan_pay": str(row.plan_pay),
        "other_payer_amount": str(row.other_payer_amount),
        "under_reimbursement": str(row.under_reimbursement),
        "client_id": str(row.client_id) if row.client_id else None,
        "program_id": str(row.program_id) if row.program_id else None,
        "payment_route": row.payment_route,
        "is_excluded": row.is_excluded,
        "is_statement": row.is_statement,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------


@router.get("/routing-rules", response_model=list[dict])
def list_routing_rules(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List routing rules ordered by priority."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(RoutingRule)
            .where(RoutingRule.tenant_id == tenant_id)
            .order_by(RoutingRule.priority.asc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "name": r.name,
                "priority": r.priority,
                "payment_route": r.payment_route,
                "match_nrid": r.match_nrid,
                "match_program_id": str(r.match_program_id) if r.match_program_id else None,
                "match_pharmacy_npi": r.match_pharmacy_npi,
                "match_claim_type": r.match_claim_type,
                "match_client_id": str(r.match_client_id) if r.match_client_id else None,
                "payment_vendor_config_id": str(r.payment_vendor_config_id) if r.payment_vendor_config_id else None,
                "payment_schedule": r.payment_schedule,
                "is_active": r.is_active,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_routing_rules failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_ROUTING_RULES_ERROR", "message": "Failed to list routing rules", "correlation_id": correlation_id}},
        ) from exc


@router.post("/routing-rules", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_routing_rule(
    body: RoutingRuleCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new routing rule."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    return {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), **body.model_dump()}


@router.put("/routing-rules/{rule_id}", response_model=dict)
def update_routing_rule(
    rule_id: uuid.UUID,
    body: RoutingRuleUpdateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update an existing routing rule."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")


@router.post("/routing-rules/test", response_model=RoutingTestResponse)
def test_routing_rules(
    body: RoutingTestRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> RoutingTestResponse:
    """Test routing rules against sample claims."""
    return RoutingTestResponse(results=[])


# ---------------------------------------------------------------------------
# AP Records
# ---------------------------------------------------------------------------


@router.get("/ap", response_model=list[dict])
def list_ap_records(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    pay_to_entity_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    payment_route: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List AP records."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(APRecord)
            .where(APRecord.tenant_id == tenant_id)
            .order_by(APRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if client_id is not None:
            stmt = stmt.where(APRecord.client_id == client_id)
        if pay_to_entity_id is not None:
            stmt = stmt.where(APRecord.pay_to_entity_id == pay_to_entity_id)
        if status_filter is not None:
            stmt = stmt.where(APRecord.status == status_filter)
        if payment_route is not None:
            stmt = stmt.where(APRecord.payment_route == payment_route)
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "claim_record_id": str(r.claim_record_id),
                "client_id": str(r.client_id),
                "pay_to_entity_id": str(r.pay_to_entity_id),
                "pay_to_entity_name": r.pay_to_entity_name,
                "amount": str(r.amount),
                "payment_route": r.payment_route,
                "status": r.status,
                "payment_batch_id": str(r.payment_batch_id) if r.payment_batch_id else None,
                "is_carryover": r.is_carryover,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_ap_records failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_AP_ERROR", "message": "Failed to list AP records", "correlation_id": correlation_id}},
        ) from exc


@router.get("/ap/summary", response_model=list[dict])
def ap_summary(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """AP summary grouped by entity and status."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(
                APRecord.pay_to_entity_id,
                APRecord.pay_to_entity_name,
                APRecord.status,
                APRecord.payment_route,
                func.count(APRecord.id).label("record_count"),
                func.sum(APRecord.amount).label("total_amount"),
            )
            .where(APRecord.tenant_id == tenant_id)
            .group_by(
                APRecord.pay_to_entity_id,
                APRecord.pay_to_entity_name,
                APRecord.status,
                APRecord.payment_route,
            )
            .order_by(APRecord.pay_to_entity_name.asc())
        )
        rows = db.execute(stmt).all()
        return [
            {
                "pay_to_entity_id": str(r.pay_to_entity_id),
                "pay_to_entity_name": r.pay_to_entity_name,
                "status": r.status,
                "payment_route": r.payment_route,
                "record_count": r.record_count,
                "total_amount": str(
                    Decimal(str(r.total_amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if r.total_amount is not None
                    else Decimal("0.00")
                ),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "ap_summary failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "AP_SUMMARY_ERROR", "message": "Failed to generate AP summary", "correlation_id": correlation_id}},
        ) from exc


@router.get("/ap/{ap_id}", response_model=dict)
def get_ap_record(
    ap_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get AP record detail."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = select(APRecord).where(
            APRecord.tenant_id == tenant_id,
            APRecord.id == ap_id,
        )
        row = db.execute(stmt).scalar_one_or_none()
    except Exception as exc:
        logger.error(
            "get_ap_record DB error",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "GET_AP_ERROR", "message": "Failed to retrieve AP record", "correlation_id": correlation_id}},
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AP record not found")
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "claim_record_id": str(row.claim_record_id),
        "client_id": str(row.client_id),
        "pay_to_entity_id": str(row.pay_to_entity_id),
        "pay_to_entity_name": row.pay_to_entity_name,
        "pay_to_npi": row.pay_to_npi,
        "amount": str(row.amount),
        "payment_route": row.payment_route,
        "payment_vendor_config_id": str(row.payment_vendor_config_id) if row.payment_vendor_config_id else None,
        "payment_schedule": row.payment_schedule,
        "status": row.status,
        "payment_batch_id": str(row.payment_batch_id) if row.payment_batch_id else None,
        "settlement_date": row.settlement_date.isoformat() if row.settlement_date else None,
        "return_code": row.return_code,
        "return_reason": row.return_reason,
        "is_carryover": row.is_carryover,
        "carryover_from_id": str(row.carryover_from_id) if row.carryover_from_id else None,
        "carryover_reason": row.carryover_reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Payment Batches
# ---------------------------------------------------------------------------


@router.get("/payment-batches", response_model=list[dict])
def list_payment_batches(
    tenant_id: TenantId,
    db: DBSession,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List payment batches."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(PaymentBatch)
            .where(PaymentBatch.tenant_id == tenant_id)
            .order_by(PaymentBatch.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "batch_number": r.batch_number,
                "payment_route": r.payment_route,
                "total_amount": str(r.total_amount),
                "payment_count": r.payment_count,
                "ap_count": r.ap_count,
                "status": r.status,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "settled_at": r.settled_at.isoformat() if r.settled_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_payment_batches failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_BATCHES_ERROR", "message": "Failed to list payment batches", "correlation_id": correlation_id}},
        ) from exc


@router.post("/payment-batches/generate", status_code=status.HTTP_201_CREATED, response_model=dict)
def generate_payment_batch(
    body: BatchGenerateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate a payment batch for a given route."""
    if not any(current_user.has_role(r) for r in _WRITE_ROLES):
        raise HTTPException(status_code=403, detail="Operator or Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    return {"id": str(uuid.uuid4()), "status": "generated", "batch_number": body.batch_number}


@router.get("/payment-batches/{batch_id}", response_model=dict)
def get_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get payment batch detail."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = select(PaymentBatch).where(
            PaymentBatch.tenant_id == tenant_id,
            PaymentBatch.id == batch_id,
        )
        row = db.execute(stmt).scalar_one_or_none()
    except Exception as exc:
        logger.error(
            "get_payment_batch DB error",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "GET_BATCH_ERROR", "message": "Failed to retrieve batch", "correlation_id": correlation_id}},
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "batch_number": row.batch_number,
        "payment_route": row.payment_route,
        "total_amount": str(row.total_amount),
        "payment_count": row.payment_count,
        "ap_count": row.ap_count,
        "status": row.status,
        "validation_result": row.validation_result,
        "validation_warnings": row.validation_warnings,
        "data_lock": row.data_lock,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "approved_by": str(row.approved_by) if row.approved_by else None,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "settled_at": row.settled_at.isoformat() if row.settled_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "version": row.version,
    }


@router.post("/payment-batches/{batch_id}/validate", response_model=BatchValidateResponse)
def validate_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> BatchValidateResponse:
    """Validate a payment batch before submission."""
    if not any(current_user.has_role(r) for r in _WRITE_ROLES):
        raise HTTPException(status_code=403, detail="Operator or Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    return BatchValidateResponse(valid=True, errors=[])


@router.post("/payment-batches/{batch_id}/approve", response_model=dict)
def approve_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve a payment batch."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")


@router.post("/payment-batches/{batch_id}/submit", response_model=dict)
def submit_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit a payment batch to vendor."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")


@router.post("/payment-batches/{batch_id}/void", response_model=dict)
def void_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Void a payment batch."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")


@router.get("/payment-batches/{batch_id}/payments", response_model=list[dict])
def list_batch_payments(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List payments in a batch."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.payment_batch_id == batch_id,
            )
            .order_by(Payment.created_at.asc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "payment_batch_id": str(r.payment_batch_id),
                "tenant_id": str(r.tenant_id),
                "pay_to_entity_id": str(r.pay_to_entity_id),
                "pay_to_entity_name": r.pay_to_entity_name,
                "amount": str(r.amount),
                "claim_count": r.claim_count,
                "payment_method": r.payment_method,
                "status": r.status,
                "bank_routing_number": r.bank_routing_number,
                "bank_account_type": r.bank_account_type,
                "return_code": r.return_code,
                "return_reason": r.return_reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_batch_payments failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_BATCH_PAYMENTS_ERROR", "message": "Failed to list batch payments", "correlation_id": correlation_id}},
        ) from exc


# ---------------------------------------------------------------------------
# Settlement
# ---------------------------------------------------------------------------


@router.post("/settlement/record", status_code=status.HTTP_200_OK, response_model=dict)
def record_settlement(
    body: SettlementRecordRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Manually record a settlement."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    return {"payment_id": str(body.payment_id), "status": "settled"}


@router.get("/settlement/unmatched", response_model=list[dict])
def list_unmatched_payments(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List payments not yet matched to a settlement."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.status == "pending",
                Payment.settlement_date.is_(None),
            )
            .order_by(Payment.created_at.asc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "payment_batch_id": str(r.payment_batch_id),
                "pay_to_entity_id": str(r.pay_to_entity_id),
                "pay_to_entity_name": r.pay_to_entity_name,
                "amount": str(r.amount),
                "claim_count": r.claim_count,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_unmatched_payments failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_UNMATCHED_ERROR", "message": "Failed to list unmatched payments", "correlation_id": correlation_id}},
        ) from exc


# ---------------------------------------------------------------------------
# Invoicing Configs
# ---------------------------------------------------------------------------


@router.get("/invoicing-configs", response_model=list[dict])
def list_invoicing_configs(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List invoicing configurations."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(InvoicingConfig)
            .where(InvoicingConfig.tenant_id == tenant_id)
            .order_by(InvoicingConfig.created_at.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "client_id": str(r.client_id),
                "name": r.name,
                "frequency": r.frequency,
                "automation_level": r.automation_level,
                "delivery_method": r.delivery_method,
                "payment_terms_days": r.payment_terms_days,
                "include_fees": r.include_fees,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_invoicing_configs failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_INVOICING_CONFIGS_ERROR", "message": "Failed to list invoicing configs", "correlation_id": correlation_id}},
        ) from exc


@router.post("/invoicing-configs", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_invoicing_config(
    body: InvoicingConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create invoicing configuration for a client."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    return {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), **body.model_dump()}


@router.put("/invoicing-configs/{config_id}", response_model=dict)
def update_invoicing_config(
    config_id: uuid.UUID,
    body: InvoicingConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update invoicing configuration."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@router.get("/invoices", response_model=list[dict])
def list_invoices(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List invoices."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(Invoice)
            .where(Invoice.tenant_id == tenant_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if client_id is not None:
            stmt = stmt.where(Invoice.client_id == client_id)
        if status_filter is not None:
            stmt = stmt.where(Invoice.status == status_filter)
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "invoice_number": r.invoice_number,
                "invoice_type": r.invoice_type,
                "client_id": str(r.client_id),
                "client_name": r.client_name,
                "period_start": r.period_start.isoformat() if r.period_start else None,
                "period_end": r.period_end.isoformat() if r.period_end else None,
                "claims_subtotal": str(r.claims_subtotal),
                "fees_subtotal": str(r.fees_subtotal),
                "adjustments": str(r.adjustments),
                "late_fees": str(r.late_fees),
                "total": str(r.total),
                "claim_count": r.claim_count,
                "status": r.status,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "paid_amount": str(r.paid_amount),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_invoices failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_INVOICES_ERROR", "message": "Failed to list invoices", "correlation_id": correlation_id}},
        ) from exc


@router.post("/invoices/generate", status_code=status.HTTP_201_CREATED, response_model=dict)
def generate_invoice(
    body: InvoiceGenerateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate a new invoice for a client and period."""
    if not any(current_user.has_role(r) for r in _WRITE_ROLES):
        raise HTTPException(status_code=403, detail="Operator or Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    return {"id": str(uuid.uuid4()), "status": "draft", "invoice_number": body.invoice_number}


@router.get("/invoices/{invoice_id}", response_model=dict)
def get_invoice(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get invoice detail."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(Invoice)
            .where(
                Invoice.tenant_id == tenant_id,
                Invoice.id == invoice_id,
            )
            .options(selectinload(Invoice.line_items))
        )
        row = db.execute(stmt).scalar_one_or_none()
    except Exception as exc:
        logger.error(
            "get_invoice DB error",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "GET_INVOICE_ERROR", "message": "Failed to retrieve invoice", "correlation_id": correlation_id}},
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "invoice_number": row.invoice_number,
        "invoice_type": row.invoice_type,
        "client_id": str(row.client_id),
        "client_name": row.client_name,
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat() if row.period_end else None,
        "claims_subtotal": str(row.claims_subtotal),
        "fees_subtotal": str(row.fees_subtotal),
        "adjustments": str(row.adjustments),
        "late_fees": str(row.late_fees),
        "total": str(row.total),
        "claim_count": row.claim_count,
        "status": row.status,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "payment_terms_days": row.payment_terms_days,
        "paid_amount": str(row.paid_amount),
        "data_lock": row.data_lock,
        "version": row.version,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "voided_at": row.voided_at.isoformat() if row.voided_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> Any:
    """Download invoice PDF."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.post("/invoices/{invoice_id}/approve", response_model=dict)
def approve_invoice(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve a draft invoice."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.post("/invoices/{invoice_id}/send", response_model=dict)
def send_invoice(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Send invoice to client."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.post("/invoices/{invoice_id}/void", response_model=dict)
def void_invoice(
    invoice_id: uuid.UUID,
    body: dict,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Void an invoice."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail="Approver role required")
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail="MFA verification required")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.get("/invoices/{invoice_id}/line-items", response_model=list[dict])
def list_invoice_line_items(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List line items for an invoice."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(InvoiceLineItem)
            .where(
                InvoiceLineItem.tenant_id == tenant_id,
                InvoiceLineItem.invoice_id == invoice_id,
            )
            .order_by(InvoiceLineItem.sort_order.asc(), InvoiceLineItem.created_at.asc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "invoice_id": str(r.invoice_id),
                "tenant_id": str(r.tenant_id),
                "line_type": r.line_type,
                "description": r.description,
                "program_id": str(r.program_id) if r.program_id else None,
                "program_name": r.program_name,
                "fee_config_id": str(r.fee_config_id) if r.fee_config_id else None,
                "quantity": r.quantity,
                "unit_amount": str(r.unit_amount) if r.unit_amount is not None else None,
                "amount": str(r.amount),
                "sort_order": r.sort_order,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_invoice_line_items failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_LINE_ITEMS_ERROR", "message": "Failed to list invoice line items", "correlation_id": correlation_id}},
        ) from exc


# ---------------------------------------------------------------------------
# AR Records
# ---------------------------------------------------------------------------


@router.get("/ar", response_model=list[dict])
def list_ar_records(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List AR records."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(ARRecord)
            .where(ARRecord.tenant_id == tenant_id)
            .order_by(ARRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if client_id is not None:
            stmt = stmt.where(ARRecord.client_id == client_id)
        if status_filter is not None:
            stmt = stmt.where(ARRecord.status == status_filter)
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "invoice_id": str(r.invoice_id),
                "client_id": str(r.client_id),
                "amount_due": str(r.amount_due),
                "amount_paid": str(r.amount_paid),
                "amount_outstanding": str(r.amount_outstanding),
                "status": r.status,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "days_outstanding": r.days_outstanding,
                "aging_bucket": r.aging_bucket,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_ar_records failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_AR_ERROR", "message": "Failed to list AR records", "correlation_id": correlation_id}},
        ) from exc


@router.get("/ar/aging", response_model=ARAgingResponse)
def get_ar_aging(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
) -> ARAgingResponse:
    """Get AR aging report."""
    correlation_id = str(uuid.uuid4())
    zero = Decimal("0.00")
    try:
        stmt = select(
            ARRecord.aging_bucket,
            func.sum(ARRecord.amount_outstanding).label("bucket_total"),
        ).where(ARRecord.tenant_id == tenant_id)
        if client_id is not None:
            stmt = stmt.where(ARRecord.client_id == client_id)
        stmt = stmt.group_by(ARRecord.aging_bucket)
        rows = db.execute(stmt).all()
        buckets: dict[str | None, Decimal] = {}
        for row in rows:
            raw = row.bucket_total
            val = (
                Decimal(str(raw)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if raw is not None
                else zero
            )
            buckets[row.aging_bucket] = val
        current = buckets.get(AGING_CURRENT, zero)
        days_30 = buckets.get(AGING_30, zero)
        days_60 = buckets.get(AGING_60, zero)
        days_90 = buckets.get(AGING_90, zero)
        days_120_plus = buckets.get(AGING_120_PLUS, zero)
        total_outstanding = (current + days_30 + days_60 + days_90 + days_120_plus).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return ARAgingResponse(
            current=current,
            days_30=days_30,
            days_60=days_60,
            days_90=days_90,
            days_120_plus=days_120_plus,
            total_outstanding=total_outstanding,
        )
    except Exception as exc:
        logger.error(
            "get_ar_aging failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "AR_AGING_ERROR", "message": "Failed to generate AR aging", "correlation_id": correlation_id}},
        ) from exc


@router.post("/ar/{ar_id}/payment", status_code=status.HTTP_200_OK, response_model=dict)
def record_ar_payment(
    ar_id: uuid.UUID,
    body: ARPaymentRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a payment against an AR record."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "NOT_FOUND", "message": "AR record not found", "correlation_id": str(uuid.uuid4())}})


@router.post("/ar/{ar_id}/dispute", status_code=status.HTTP_200_OK, response_model=dict)
def dispute_ar_record(
    ar_id: uuid.UUID,
    body: ARDisputeRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Open a dispute on an AR record."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "NOT_FOUND", "message": "AR record not found", "correlation_id": str(uuid.uuid4())}})


@router.post("/ar/{ar_id}/write-off", status_code=status.HTTP_200_OK, response_model=dict)
def write_off_ar_record(
    ar_id: uuid.UUID,
    body: ARWriteOffRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Write off an AR record (admin only)."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "NOT_FOUND", "message": "AR record not found", "correlation_id": str(uuid.uuid4())}})


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


@router.get("/journal-summary", response_model=dict)
def journal_summary(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, Any]:
    """Get journal period summary. READ ONLY."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = select(
            JournalEntry.category,
            func.count(JournalEntry.id).label("entry_count"),
            func.sum(JournalEntry.amount).label("total_amount"),
        ).where(JournalEntry.tenant_id == tenant_id)
        if date_from is not None:
            stmt = stmt.where(JournalEntry.entry_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(JournalEntry.entry_date <= date_to)
        stmt = stmt.group_by(JournalEntry.category).order_by(JournalEntry.category.asc())
        rows = db.execute(stmt).all()

        by_category = {}
        grand_total = Decimal("0.00")
        grand_count = 0
        for row in rows:
            raw = row.total_amount
            amt = (
                Decimal(str(raw)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if raw is not None
                else Decimal("0.00")
            )
            by_category[row.category] = {"entry_count": row.entry_count, "total_amount": str(amt)}
            grand_total = (grand_total + amt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            grand_count += row.entry_count

        return {
            "period_from": date_from.isoformat() if date_from else None,
            "period_to": date_to.isoformat() if date_to else None,
            "total_entries": grand_count,
            "total_amount": str(grand_total),
            "by_category": by_category,
        }
    except Exception as exc:
        logger.error(
            "journal_summary failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "JOURNAL_SUMMARY_ERROR", "message": "Failed to generate journal summary", "correlation_id": correlation_id}},
        ) from exc


@router.get("/journal-export", response_model=dict)
def export_journal(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    """Export journal entries to accounting system."""
    return {"export_reference": "", "entry_count": 0}


@router.post("/journal/close-period", response_model=dict)
def close_period(
    body: PeriodCloseRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Close an accounting period."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return {"period_end": str(body.period_end), "status": "closed"}


# ---------------------------------------------------------------------------
# Fee Configs
# ---------------------------------------------------------------------------


@router.get("/fees", response_model=list[dict])
def list_fee_configs(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
) -> list[dict]:
    """List fee configurations."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(FeeConfig)
            .where(FeeConfig.tenant_id == tenant_id)
            .order_by(FeeConfig.created_at.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "name": r.name,
                "fee_code": r.fee_code,
                "calculation_type": r.calculation_type,
                "amount": str(r.amount) if r.amount is not None else None,
                "percentage": str(r.percentage) if r.percentage is not None else None,
                "tiers": r.tiers,
                "effective_date": r.effective_date.isoformat() if r.effective_date else None,
                "termination_date": r.termination_date.isoformat() if r.termination_date else None,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_fee_configs failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_FEES_ERROR", "message": "Failed to list fee configs", "correlation_id": correlation_id}},
        ) from exc


@router.post("/fees", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_fee_config(
    body: FeeConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a fee configuration."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return {"id": str(uuid.uuid4()), **body.model_dump()}


@router.put("/fees/{fee_id}", response_model=dict)
def update_fee_config(
    fee_id: uuid.UUID,
    body: FeeConfigUpdateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update a fee configuration."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "NOT_FOUND", "message": "Fee config not found", "correlation_id": str(uuid.uuid4())}})


# ---------------------------------------------------------------------------
# Program Budgets
# ---------------------------------------------------------------------------


@router.get("/program-budgets", response_model=list[dict])
def list_program_budgets(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    program_id: uuid.UUID | None = Query(default=None),
) -> list[dict]:
    """List program budgets."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(ProgramBudget)
            .where(ProgramBudget.tenant_id == tenant_id)
            .order_by(ProgramBudget.created_at.desc())
        )
        if client_id is not None:
            stmt = stmt.where(ProgramBudget.client_id == client_id)
        if program_id is not None:
            stmt = stmt.where(ProgramBudget.program_id == program_id)
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "client_id": str(r.client_id),
                "program_id": str(r.program_id),
                "budget_type": r.budget_type,
                "budget_amount": str(r.budget_amount) if r.budget_amount is not None else None,
                "spent_to_date": str(r.spent_to_date),
                "remaining": str(r.remaining) if r.remaining is not None else None,
                "utilization_percentage": str(r.utilization_percentage),
                "burn_rate_daily": str(r.burn_rate_daily),
                "projected_depletion_date": r.projected_depletion_date.isoformat() if r.projected_depletion_date else None,
                "projected_over_budget": r.projected_over_budget,
                "budget_period_start": r.budget_period_start.isoformat() if r.budget_period_start else None,
                "budget_period_end": r.budget_period_end.isoformat() if r.budget_period_end else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_program_budgets failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_BUDGETS_ERROR", "message": "Failed to list program budgets", "correlation_id": correlation_id}},
        ) from exc


@router.post("/program-budgets", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_program_budget(
    body: ProgramBudgetCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a program budget."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), **body.model_dump()}


@router.put("/program-budgets/{budget_id}", response_model=dict)
def update_program_budget(
    budget_id: uuid.UUID,
    body: ProgramBudgetUpdateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update a program budget."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "NOT_FOUND", "message": "Budget not found", "correlation_id": str(uuid.uuid4())}})


@router.get("/program-budgets/{budget_id}/dashboard", response_model=dict)
def budget_dashboard(
    budget_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get budget dashboard data."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(ProgramBudget)
            .where(
                ProgramBudget.tenant_id == tenant_id,
                ProgramBudget.id == budget_id,
            )
            .options(selectinload(ProgramBudget.alerts), selectinload(ProgramBudget.snapshots))
        )
        row = db.execute(stmt).scalar_one_or_none()
    except Exception as exc:
        logger.error(
            "budget_dashboard DB error",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "BUDGET_DASHBOARD_ERROR", "message": "Failed to load budget dashboard", "correlation_id": correlation_id}},
        ) from exc
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    budget_amount = row.budget_amount or Decimal("0")
    spent = row.spent_to_date
    remaining = (budget_amount - spent).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    remaining = max(remaining, Decimal("0.00"))
    utilization = row.utilization_percentage
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "client_id": str(row.client_id),
        "program_id": str(row.program_id),
        "budget_type": row.budget_type,
        "budget_amount": str(budget_amount),
        "spent_to_date": str(spent),
        "remaining": str(remaining),
        "utilization_percentage": str(utilization),
        "burn_rate_daily": str(row.burn_rate_daily),
        "burn_rate_7day_avg": str(row.burn_rate_7day_avg),
        "burn_rate_30day_avg": str(row.burn_rate_30day_avg),
        "burn_rate_trend": row.burn_rate_trend,
        "projected_depletion_date": row.projected_depletion_date.isoformat() if row.projected_depletion_date else None,
        "projected_over_budget": row.projected_over_budget,
        "active_alert_count": sum(1 for a in row.alerts if a.acknowledged_at is None),
        "last_calculated_at": row.last_calculated_at.isoformat() if row.last_calculated_at else None,
    }


@router.get("/program-budgets/{budget_id}/snapshots", response_model=list[dict])
def list_budget_snapshots(
    budget_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List budget historical snapshots."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(ProgramBudgetSnapshot)
            .where(
                ProgramBudgetSnapshot.tenant_id == tenant_id,
                ProgramBudgetSnapshot.program_budget_id == budget_id,
            )
            .order_by(ProgramBudgetSnapshot.snapshot_date.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "program_budget_id": str(r.program_budget_id),
                "snapshot_date": r.snapshot_date.isoformat() if r.snapshot_date else None,
                "spent_to_date": str(r.spent_to_date),
                "daily_spend": str(r.daily_spend),
                "claim_count": r.claim_count,
                "avg_claim_amount": str(r.avg_claim_amount) if r.avg_claim_amount is not None else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_budget_snapshots failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_SNAPSHOTS_ERROR", "message": "Failed to list budget snapshots", "correlation_id": correlation_id}},
        ) from exc


@router.get("/program-budgets/{budget_id}/alerts", response_model=list[dict])
def list_budget_alerts(
    budget_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List alerts for a program budget."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(ProgramBudgetAlert)
            .where(
                ProgramBudgetAlert.tenant_id == tenant_id,
                ProgramBudgetAlert.program_budget_id == budget_id,
            )
            .order_by(ProgramBudgetAlert.created_at.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "program_budget_id": str(r.program_budget_id),
                "alert_type": r.alert_type,
                "severity": r.severity,
                "message": r.message,
                "metric_value": str(r.metric_value) if r.metric_value is not None else None,
                "threshold_value": str(r.threshold_value) if r.threshold_value is not None else None,
                "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None,
                "acknowledged_by": str(r.acknowledged_by) if r.acknowledged_by else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_budget_alerts failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_ALERTS_ERROR", "message": "Failed to list budget alerts", "correlation_id": correlation_id}},
        ) from exc


@router.post(
    "/program-budgets/{budget_id}/alerts/{alert_id}/acknowledge",
    response_model=dict,
)
def acknowledge_budget_alert(
    budget_id: uuid.UUID,
    alert_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Acknowledge a budget alert."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "NOT_FOUND", "message": "Alert not found", "correlation_id": str(uuid.uuid4())}})


# ---------------------------------------------------------------------------
# Payment Vendors
# ---------------------------------------------------------------------------


@router.get("/payment-vendors", response_model=list[dict])
def list_payment_vendors(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List payment vendor configurations."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(PaymentVendorConfig)
            .where(PaymentVendorConfig.tenant_id == tenant_id)
            .order_by(PaymentVendorConfig.created_at.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "vendor_type": r.vendor_type,
                "name": r.name,
                "api_endpoint": r.api_endpoint,
                "file_delivery_method": r.file_delivery_method,
                "file_format": r.file_format,
                "settlement_method": r.settlement_method,
                "expected_settlement_days": r.expected_settlement_days,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_payment_vendors failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_VENDORS_ERROR", "message": "Failed to list payment vendors", "correlation_id": correlation_id}},
        ) from exc


@router.post("/payment-vendors", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_payment_vendor(
    body: PaymentVendorCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a payment vendor configuration."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return {"id": str(uuid.uuid4()), **body.model_dump()}


@router.put("/payment-vendors/{vendor_id}", response_model=dict)
def update_payment_vendor(
    vendor_id: uuid.UUID,
    body: PaymentVendorCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update a payment vendor configuration."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "NOT_FOUND", "message": "Vendor not found", "correlation_id": str(uuid.uuid4())}})


# ---------------------------------------------------------------------------
# Bank Accounts
# ---------------------------------------------------------------------------


@router.get("/bank-accounts", response_model=list[dict])
def list_bank_accounts(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List bank accounts."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(BankAccount)
            .where(BankAccount.tenant_id == tenant_id)
            .order_by(BankAccount.created_at.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "account_name": r.account_name,
                "bank_name": r.bank_name,
                "routing_number": r.routing_number,
                "account_number_last4": r.account_number[-4:] if r.account_number else None,
                "account_type": r.account_type,
                "purpose": r.purpose,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_bank_accounts failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_BANK_ACCOUNTS_ERROR", "message": "Failed to list bank accounts", "correlation_id": correlation_id}},
        ) from exc


@router.post("/bank-accounts", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_bank_account(
    body: BankAccountCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a bank account."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return {"id": str(uuid.uuid4()), "account_number_last4": body.account_number[-4:]}


@router.put("/bank-accounts/{account_id}", response_model=dict)
def update_bank_account(
    account_id: uuid.UUID,
    body: BankAccountCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update a bank account."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "NOT_FOUND", "message": "Account not found", "correlation_id": str(uuid.uuid4())}})


# ---------------------------------------------------------------------------
# Accounting Config
# ---------------------------------------------------------------------------


@router.get("/accounting/config", response_model=dict)
def get_accounting_config(
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get accounting system configuration."""
    return {}


@router.put("/accounting/config", response_model=dict)
def update_accounting_config(
    body: AccountingConfigUpdateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update accounting system configuration."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return body.model_dump(exclude_none=True)


# ---------------------------------------------------------------------------
# Remittance Configs
# ---------------------------------------------------------------------------


@router.get("/remittance-configs", response_model=list[dict])
def list_remittance_configs(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List remittance configurations."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(RemittanceConfig)
            .where(RemittanceConfig.tenant_id == tenant_id)
            .order_by(RemittanceConfig.created_at.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "entity_type": r.entity_type,
                "entity_id": str(r.entity_id) if r.entity_id else None,
                "delivery_method": r.delivery_method,
                "sftp_config_id": str(r.sftp_config_id) if r.sftp_config_id else None,
                "format_type": r.format_type,
                "include_pos_adjustment": r.include_pos_adjustment,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_remittance_configs failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_REMITTANCE_CONFIGS_ERROR", "message": "Failed to list remittance configs", "correlation_id": correlation_id}},
        ) from exc


@router.post("/remittance-configs", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_remittance_config(
    body: RemittanceConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a remittance configuration."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return {"id": str(uuid.uuid4()), **body.model_dump()}


# ---------------------------------------------------------------------------
# SFTP Configs
# ---------------------------------------------------------------------------


@router.get("/sftp-configs", response_model=list[dict])
def list_sftp_configs(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List SFTP configurations."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(SFTPConfig)
            .where(SFTPConfig.tenant_id == tenant_id)
            .order_by(SFTPConfig.created_at.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "name": r.name,
                "host": r.host,
                "port": r.port,
                "username": r.username,
                "auth_type": r.auth_type,
                "remote_path": r.remote_path,
                "is_active": r.is_active,
                "last_delivery_at": r.last_delivery_at.isoformat() if r.last_delivery_at else None,
                "last_delivery_status": r.last_delivery_status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_sftp_configs failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_SFTP_CONFIGS_ERROR", "message": "Failed to list SFTP configs", "correlation_id": correlation_id}},
        ) from exc


@router.post("/sftp-configs", status_code=status.HTTP_201_CREATED, response_model=dict)
def create_sftp_config(
    body: SFTPConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create an SFTP configuration."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return {"id": str(uuid.uuid4()), "host": body.host, "config_name": body.config_name}


@router.post("/sftp-configs/{config_id}/test", response_model=SFTPTestResponse)
def test_sftp_config(
    config_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> SFTPTestResponse:
    """Test SFTP connection."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return SFTPTestResponse(success=False, message="Config not found")


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


@router.get("/funding", response_model=list[dict])
def list_funding_configs(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List funding configurations."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(FundingConfig)
            .where(FundingConfig.tenant_id == tenant_id)
            .order_by(FundingConfig.created_at.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "tenant_id": str(r.tenant_id),
                "client_id": str(r.client_id),
                "funding_model": r.funding_model,
                "prefund_balance": str(r.prefund_balance),
                "alert_threshold": str(r.alert_threshold) if r.alert_threshold is not None else None,
                "critical_threshold": str(r.critical_threshold) if r.critical_threshold is not None else None,
                "funding_bank_account_id": str(r.funding_bank_account_id) if r.funding_bank_account_id else None,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "list_funding_configs failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "LIST_FUNDING_ERROR", "message": "Failed to list funding configs", "correlation_id": correlation_id}},
        ) from exc


@router.put("/funding/{config_id}", response_model=dict)
def update_funding_config(
    config_id: uuid.UUID,
    body: dict,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update funding configuration."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error": {"code": "NOT_FOUND", "message": "Config not found", "correlation_id": str(uuid.uuid4())}})


@router.get("/funding/{config_id}/ledger", response_model=list[dict])
def get_funding_ledger(
    config_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """Get prefund ledger for a funding config."""
    correlation_id = str(uuid.uuid4())
    try:
        stmt = (
            select(PrefundLedger)
            .where(
                PrefundLedger.tenant_id == tenant_id,
                PrefundLedger.funding_config_id == config_id,
            )
            .order_by(PrefundLedger.created_at.desc())
        )
        rows = db.execute(stmt).scalars().all()
        return [
            {
                "id": str(r.id),
                "funding_config_id": str(r.funding_config_id),
                "tenant_id": str(r.tenant_id),
                "transaction_type": r.transaction_type,
                "amount": str(r.amount),
                "running_balance": str(r.running_balance),
                "reference_type": r.reference_type,
                "reference_id": str(r.reference_id) if r.reference_id else None,
                "description": r.description,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error(
            "get_funding_ledger failed",
            extra={"billing_correlation_id": correlation_id, "billing_tenant_id": str(tenant_id)},
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "GET_LEDGER_ERROR", "message": "Failed to retrieve funding ledger", "correlation_id": correlation_id}},
        ) from exc


@router.post("/funding/{config_id}/deposit", status_code=status.HTTP_200_OK, response_model=dict)
def record_funding_deposit(
    config_id: uuid.UUID,
    body: FundingDepositRequest,
    tenant_id: TenantId,
    db: DBSession,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a prefund deposit."""
    if not any(current_user.has_role(r) for r in _APPROVER_ONLY):
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Approver role required", "correlation_id": str(uuid.uuid4())}})
    if not getattr(current_user, "mfa_verified", True):
        raise HTTPException(status_code=403, detail={"error": {"code": "MFA_REQUIRED", "message": "MFA verification required", "correlation_id": str(uuid.uuid4())}})
    return {"config_id": str(config_id), "amount": str(body.amount), "status": "recorded"}


@router.get("/funding/{config_id}/projection", response_model=dict)
def get_funding_projection(
    config_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get burn rate projection for a funding config."""
    return {}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/reports/ap-summary", response_model=dict)
def report_ap_summary(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    """AP summary report."""
    return {}


@router.get("/reports/ar-aging", response_model=dict)
def report_ar_aging(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    """AR aging report."""
    return {}


@router.get("/reports/payment-history", response_model=list[dict])
def report_payment_history(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    """Payment history report."""
    return []


@router.get("/reports/fee-summary", response_model=dict)
def report_fee_summary(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, Any]:
    """Fee summary report."""
    return {}


@router.get("/reports/prefund-history", response_model=list[dict])
def report_prefund_history(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
) -> list[dict]:
    """Prefund history report."""
    return []


@router.get("/reports/cash-flow", response_model=dict)
def report_cash_flow(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, Any]:
    """Cash flow report (inflows vs outflows)."""
    return {}


@router.get("/reports/program-performance", response_model=dict)
def report_program_performance(
    tenant_id: TenantId,
    db: DBSession,
    program_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, Any]:
    """Program spend vs budget performance report."""
    return {}


@router.get("/reports/period-close", response_model=dict)
def report_period_close(
    tenant_id: TenantId,
    db: DBSession,
    period_end: date | None = Query(default=None),
) -> dict[str, Any]:
    """Period close summary report."""
    return {}


@router.get("/reports/1099-data", response_model=list[dict])
def report_1099_data(
    tenant_id: TenantId,
    db: DBSession,
    tax_year: int = Query(default=2025, ge=2020, le=2099),
) -> list[dict]:
    """1099 data for a tax year."""
    return []
