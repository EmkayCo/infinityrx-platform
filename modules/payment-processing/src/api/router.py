"""Payment-processing FastAPI router.

Thin routes — all business logic lives in services.
Every endpoint: tenant-scoped, auth-required, mutating endpoints audit-logged.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .._shim.auth import CurrentUser
from ..models import (
    AchReturnCode,
    PayeeEnrollment,
    Settlement,
    Submission,
    VendorAdapter,
    VendorHealthLog,
)
from ..services.ach_return_codes import ACH_RETURN_CODES, get_return_code
from ..services.reconciliation_service import ReconciliationService
from ..utils.constants import (
    ENROLL_NOT_ENROLLED,
    ENROLL_PENDING,
    SETTLE_SETTLED,
    SUB_FAILED,
    SUB_PENDING,
)
from .dependencies import get_db, require_payment_role, require_readonly
from .schemas import (
    AchReturnCodeRead,
    EnrollmentRead,
    ManualSettlementRequest,
    ReconciliationRow,
    ReturnRecordRequest,
    SettlementRead,
    SubmissionRead,
    VendorAdapterCreate,
    VendorAdapterRead,
    VendorAdapterUpdate,
    VendorHealthRead,
)

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


def _tenant(user: CurrentUser) -> str:
    return str(user.tenant_id)


# ---------------------------------------------------------------------------
# Vendor Adapters
# ---------------------------------------------------------------------------


@router.get("/vendors", response_model=list[VendorAdapterRead])
async def list_vendors(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> list[VendorAdapterRead]:
    rows = db.execute(
        select(VendorAdapter).where(
            VendorAdapter.tenant_id == _tenant(user),
            VendorAdapter.is_active.is_(True),
        )
    ).scalars().all()
    return [VendorAdapterRead.model_validate(r) for r in rows]


@router.post("/vendors", response_model=VendorAdapterRead, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    body: VendorAdapterCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_payment_role),
) -> VendorAdapterRead:
    row = VendorAdapter(
        tenant_id=_tenant(user),
        vendor_type=body.vendor_type,
        name=body.name,
        connection_type=body.connection_type,
        settlement_method=body.settlement_method,
        api_endpoint=body.api_endpoint,
        api_version=body.api_version,
        sftp_host=body.sftp_host,
        sftp_port=body.sftp_port,
        sftp_username=body.sftp_username,
        sftp_remote_path=body.sftp_remote_path,
        credentials_vault_ref=body.credentials_vault_ref,
        file_format=body.file_format,
        file_naming_pattern=body.file_naming_pattern,
        settlement_poll_interval_minutes=body.settlement_poll_interval_minutes,
        expected_settlement_days=body.expected_settlement_days,
        supports_ach=body.supports_ach,
        supports_eft=body.supports_eft,
        supports_virtual_card=body.supports_virtual_card,
        supports_check=body.supports_check,
        supports_same_day_ach=body.supports_same_day_ach,
        failover_chain=json.dumps(body.failover_chain) if body.failover_chain else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return VendorAdapterRead.model_validate(row)


@router.put("/vendors/{vendor_id}", response_model=VendorAdapterRead)
async def update_vendor(
    vendor_id: str,
    body: VendorAdapterUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_payment_role),
) -> VendorAdapterRead:
    row = db.get(VendorAdapter, vendor_id)
    if row is None or row.tenant_id != _tenant(user):
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Vendor not found"})
    for field, val in body.model_dump(exclude_none=True).items():
        if field == "failover_chain" and val is not None:
            setattr(row, field, json.dumps(val))
        else:
            setattr(row, field, val)
    db.commit()
    db.refresh(row)
    return VendorAdapterRead.model_validate(row)


@router.get("/vendors/{vendor_id}/health", response_model=list[VendorHealthRead])
async def vendor_health(
    vendor_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> list[VendorHealthRead]:
    rows = db.execute(
        select(VendorHealthLog).where(
            VendorHealthLog.vendor_adapter_id == vendor_id,
            VendorHealthLog.tenant_id == _tenant(user),
        ).order_by(VendorHealthLog.checked_at.desc()).limit(100)
    ).scalars().all()
    return [VendorHealthRead.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------


@router.get("/submissions", response_model=list[SubmissionRead])
async def list_submissions(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> list[SubmissionRead]:
    query = select(Submission).where(Submission.tenant_id == _tenant(user))
    if status_filter:
        query = query.where(Submission.status == status_filter)
    rows = db.execute(query.order_by(Submission.created_at.desc()).limit(200)).scalars().all()
    return [SubmissionRead.model_validate(r) for r in rows]


@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
async def get_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> SubmissionRead:
    row = db.get(Submission, submission_id)
    if row is None or row.tenant_id != _tenant(user):
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Submission not found"})
    return SubmissionRead.model_validate(row)


@router.post("/submissions/{submission_id}/retry", response_model=SubmissionRead)
async def retry_submission(
    submission_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_payment_role),
) -> SubmissionRead:
    row = db.get(Submission, submission_id)
    if row is None or row.tenant_id != _tenant(user):
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Submission not found"})
    if row.status != SUB_FAILED:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_STATE", "message": f"Cannot retry submission in status {row.status}"},
        )
    if row.retry_count >= row.max_retries:
        raise HTTPException(
            status_code=422,
            detail={"error": "MAX_RETRIES", "message": "Max retries exhausted"},
        )
    row.retry_count += 1
    row.status = SUB_PENDING
    db.commit()
    db.refresh(row)
    return SubmissionRead.model_validate(row)


# ---------------------------------------------------------------------------
# Settlements
# ---------------------------------------------------------------------------


@router.get("/settlements", response_model=list[SettlementRead])
async def list_settlements(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> list[SettlementRead]:
    query = select(Settlement).where(Settlement.tenant_id == _tenant(user))
    if status_filter:
        query = query.where(Settlement.status == status_filter)
    rows = db.execute(query.order_by(Settlement.created_at.desc()).limit(500)).scalars().all()
    return [SettlementRead.model_validate(r) for r in rows]


@router.get("/settlements/pending", response_model=list[SettlementRead])
async def pending_settlements(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> list[SettlementRead]:
    rows = db.execute(
        select(Settlement).where(
            Settlement.tenant_id == _tenant(user),
            Settlement.status == "pending",
        ).order_by(Settlement.created_at.asc()).limit(500)
    ).scalars().all()
    return [SettlementRead.model_validate(r) for r in rows]


@router.post("/settlements/{settlement_id}/manual", response_model=SettlementRead)
async def manual_settlement(
    settlement_id: str,
    body: ManualSettlementRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_payment_role),
) -> SettlementRead:
    row = db.get(Settlement, settlement_id)
    if row is None or row.tenant_id != _tenant(user):
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Settlement not found"})
    row.status = SETTLE_SETTLED
    row.settlement_date = body.settlement_date
    row.settlement_reference = body.settlement_reference
    row.payment_method_used = body.payment_method_used
    row.check_number = body.check_number
    db.commit()
    db.refresh(row)
    return SettlementRead.model_validate(row)


# ---------------------------------------------------------------------------
# ACH Returns
# ---------------------------------------------------------------------------


@router.get("/returns", response_model=list[SettlementRead])
async def list_returns(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> list[SettlementRead]:
    rows = db.execute(
        select(Settlement).where(
            Settlement.tenant_id == _tenant(user),
            Settlement.status == "returned",
        ).order_by(Settlement.return_date.desc().nulls_last()).limit(500)
    ).scalars().all()
    return [SettlementRead.model_validate(r) for r in rows]


@router.post("/returns", response_model=SettlementRead, status_code=status.HTTP_201_CREATED)
async def record_return(
    body: ReturnRecordRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_payment_role),
) -> SettlementRead:
    rc = get_return_code(body.return_code)
    if rc is None:
        raise HTTPException(
            status_code=422,
            detail={"error": "INVALID_RETURN_CODE", "message": f"Unknown ACH return code: {body.return_code}"},
        )
    settle = db.execute(
        select(Settlement).where(
            Settlement.tenant_id == _tenant(user),
            Settlement.billing_payment_id == body.billing_payment_id,
        )
    ).scalar_one_or_none()

    if settle is None:
        settle = Settlement(
            tenant_id=_tenant(user),
            submission_id="manual",
            billing_payment_id=body.billing_payment_id,
            pay_to_entity_id="manual",
            amount=body.amount,
            status="returned",
            return_code=body.return_code,
            return_reason=body.return_reason,
            return_date=body.return_date,
        )
        db.add(settle)
    else:
        settle.status = "returned"
        settle.return_code = body.return_code
        settle.return_reason = body.return_reason
        settle.return_date = body.return_date

    db.commit()
    db.refresh(settle)
    return SettlementRead.model_validate(settle)


@router.get("/returns/codes", response_model=list[AchReturnCodeRead])
async def list_return_codes(
    user: CurrentUser = Depends(require_readonly),
    db: Session = Depends(get_db),
) -> list[AchReturnCodeRead]:
    # Try DB first (pre-loaded), fall back to in-memory definitions
    rows = db.execute(select(AchReturnCode)).scalars().all()
    if rows:
        return [AchReturnCodeRead.model_validate(r) for r in rows]
    # In-memory fallback
    return [
        AchReturnCodeRead(
            code=rc.code,
            description=rc.description,
            category=rc.category,
            is_retryable=rc.is_retryable,
            default_action=rc.default_action,
            retry_delay_days=rc.retry_delay_days,
            triggers_fwa_alert=rc.triggers_fwa_alert,
        )
        for rc in ACH_RETURN_CODES
    ]


# ---------------------------------------------------------------------------
# Payee Enrollment
# ---------------------------------------------------------------------------


@router.get("/enrollments", response_model=list[EnrollmentRead])
async def list_enrollments(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> list[EnrollmentRead]:
    rows = db.execute(
        select(PayeeEnrollment).where(PayeeEnrollment.tenant_id == _tenant(user))
    ).scalars().all()
    return [EnrollmentRead.model_validate(r) for r in rows]


@router.post(
    "/enrollments/{entity_id}/enroll",
    response_model=EnrollmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_enrollment(
    entity_id: str,
    vendor_adapter_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_payment_role),
) -> EnrollmentRead:
    existing = db.execute(
        select(PayeeEnrollment).where(
            PayeeEnrollment.tenant_id == _tenant(user),
            PayeeEnrollment.vendor_adapter_id == vendor_adapter_id,
            PayeeEnrollment.pay_to_entity_id == entity_id,
        )
    ).scalar_one_or_none()

    if existing:
        existing.enrollment_status = ENROLL_PENDING
        db.commit()
        db.refresh(existing)
        return EnrollmentRead.model_validate(existing)

    row = PayeeEnrollment(
        tenant_id=_tenant(user),
        vendor_adapter_id=vendor_adapter_id,
        pay_to_entity_id=entity_id,
        enrollment_status=ENROLL_PENDING,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return EnrollmentRead.model_validate(row)


@router.get("/enrollments/unenrolled", response_model=list[EnrollmentRead])
async def unenrolled_pharmacies(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> list[EnrollmentRead]:
    rows = db.execute(
        select(PayeeEnrollment).where(
            PayeeEnrollment.tenant_id == _tenant(user),
            PayeeEnrollment.enrollment_status == ENROLL_NOT_ENROLLED,
        )
    ).scalars().all()
    return [EnrollmentRead.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Dashboard & Reconciliation
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def dashboard(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> dict:
    svc = ReconciliationService(db)
    summary = svc.get_dashboard_summary(_tenant(user))
    # Add vendor statuses
    vendors = db.execute(
        select(VendorAdapter).where(
            VendorAdapter.tenant_id == _tenant(user),
            VendorAdapter.is_active.is_(True),
        )
    ).scalars().all()
    summary["vendor_statuses"] = [
        {"id": v.id, "name": v.name, "status": v.status} for v in vendors
    ]
    return summary


@router.get("/dashboard/reconciliation", response_model=list[ReconciliationRow])
async def reconciliation(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_readonly),
) -> list[ReconciliationRow]:
    svc = ReconciliationService(db)
    return svc.get_reconciliation_rows(_tenant(user))
