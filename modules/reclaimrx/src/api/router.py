"""ReclaimRx FastAPI router -- thin API layer; all logic in services."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shared.auth.dependencies import CurrentUser, get_current_user  # noqa: F401

from src.api.dependencies import (
    RECLAIMRX_ADMIN_DEP,
    RECLAIMRX_INVESTIGATOR_DEP,
    RECLAIMRX_VIEWER_DEP,
    get_db,
    require_mfa_elevated,
    require_tenant_match,
)
from src.api.errors import build_error_envelope
from src.api.schemas import (
    AccumulatorDetectionRead,
    ActivityCreate,
    ActivityRead,
    ClaimEvaluateRequest,
    ClaimEvaluateResponse,
    DetectionRuleRead,
    FlaggedClaimRead,
    FlaggedClaimUpdate,
    InvestigationCreate,
    InvestigationRead,
    InvestigationUpdate,
    MemberProfileRead,
    PaginatedResponse,
    PaymentHoldCreate,
    PaymentHoldRead,
    PaymentHoldRelease,
    PharmacyProfileRead,
    PrescriberProfileRead,
    RecoveryCreate,
    RecoveryRead,
    TipCreate,
    TipRead,
)
from src.models.tables import (
    AccumulatorDetection,
    DetectionRule,
    FlaggedClaim,
    FraudRing,
    GraphRun,
    Investigation,
    InvestigationActivity,
    MemberProfile,
    MlPrediction,
    PaymentHold,
    PharmacyProfile,
    PrescriberProfile,
    Recovery,
    ThresholdConfig,
    ThresholdConfigAudit,
    TipRecord,
)
from src.services.investigation_service import InvestigationService
from src.services.payment_hold_service import HoldInvestigationMismatchError, PaymentHoldService
from src.services.rule_engine import ClaimContext, RuleDefinition, RuleEvaluator
from src.utils.constants import InvalidTransitionError
from src.utils.money import money

router = APIRouter(prefix="/api/v1/reclaimrx", tags=["reclaimrx"])


# -- Inline response schemas for A4 new endpoints ---------------------------


class MlScoreRead(BaseModel):
    id: str
    tenant_id: str
    claim_id: str | None = None
    model_id: str
    score: str
    threshold_at_time: str | None = None
    feature_importance: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GraphRunRead(BaseModel):
    id: str
    tenant_id: str
    status: str
    trigger: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    rings_detected: int
    investigations_opened: int
    records_scanned: int
    error_code: str | None = None

    model_config = {"from_attributes": True}


class FraudRingRead(BaseModel):
    id: str
    tenant_id: str
    graph_run_id: str
    density_score: Decimal
    node_count: int
    edge_count: int
    status: str
    entity_refs: list | None = None

    model_config = {"from_attributes": True}


class ThresholdConfigRead(BaseModel):
    id: str
    tenant_id: str
    config_key: str
    value: Any
    version: int
    updated_at: datetime | None = None
    updated_by: str | None = None

    model_config = {"from_attributes": True}


class RuleFiringRead(BaseModel):
    id: str
    tenant_id: str
    claim_id: str | None = None
    rule_code: str
    rule_name: str
    severity: str
    risk_score: int
    created_at: datetime


class InvestigationActivityRead(BaseModel):
    id: str
    investigation_id: str
    tenant_id: str
    activity_type: str
    description: str
    performed_by: str | None
    file_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NoteCreate(BaseModel):
    note: str
    idempotency_key: str | None = None


class TransitionRequest(BaseModel):
    to_state: str
    reason: str
    outcome_label: str | None = None
    recovered_amount: Decimal | None = None


class HoldReleaseRequest(BaseModel):
    reason: str
    investigation_id: str | None = None


class HoldReleaseResponse(BaseModel):
    id: str
    status: str
    released_by: str
    released_at: str | None = None
    idempotent_replay: bool = False


class ThresholdUpsert(BaseModel):
    config_key: str
    value: Any
    description: str | None = None


# -- Helpers ----------------------------------------------------------------


def _emit_phi_audit(
    request: Request | None,
    user: CurrentUser,
    entity_type: str,
    entity_id: str,
) -> None:
    """Emit a structured PHI access audit log entry. Never logs PHI values."""
    import logging  # noqa: PLC0415

    _logger = logging.getLogger("reclaimrx.phi_audit")
    _logger.info(
        "PHI access",
        extra={
            "audit_action": "phi_access",
            "auth_user_id": str(user.id),
            "auth_tenant_id": str(user.tenant_id),
            "svc_entity_type": entity_type,
            "svc_entity_id": entity_id,
        },
    )


def _not_found(msg: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=build_error_envelope("NOT_FOUND", msg),
    )


# -- Real-time Evaluation ---------------------------------------------------


@router.post("/evaluate", response_model=ClaimEvaluateResponse)
async def evaluate_claim(
    req: ClaimEvaluateRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> ClaimEvaluateResponse:
    """Evaluate a claim against all active detection rules (real-time path)."""
    tenant_id = user.tenant_id

    rules = db.execute(
        select(DetectionRule).where(
            DetectionRule.is_active.is_(True),
            DetectionRule.detection_mode.in_(["real_time", "both"]),
        )
    ).scalars().all()

    claim_ctx = ClaimContext(
        claim_id=req.claim_id or "",
        tenant_id=str(tenant_id),
        auth_number=req.auth_number,
        date_of_service=req.date_of_service,
        pharmacy_npi=req.pharmacy_npi,
        pharmacy_name=req.pharmacy_name or "",
        prescriber_npi=req.prescriber_npi,
        member_id=req.member_id,
        ndc=req.ndc,
        drug_name=req.drug_name,
        quantity=req.quantity,
        days_supply=req.days_supply,
        billed_amount=req.billed_amount,
        paid_amount=req.paid_amount,
        wac_per_unit=req.wac_per_unit or Decimal("0"),
        awp_per_unit=req.awp_per_unit or Decimal("0"),
        nq=req.nq or Decimal("0"),
        dv=req.dv or Decimal("0"),
        program_type=req.program_type,
        client_type=req.client_type,
        metadata=req.metadata,
    )

    evaluator = RuleEvaluator()
    flags = []
    flagged_claim_ids: list[str] = []

    for rule in rules:
        rule_def = RuleDefinition(
            rule_code=rule.rule_code,
            name=rule.name,
            rule_type=rule.rule_type,
            rule_logic=rule.rule_logic,
            default_parameters=rule.default_parameters,
            default_action=rule.default_action,
            confidence_scoring=rule.confidence_scoring or {},
            client_types=rule.client_types if isinstance(rule.client_types, list) else ["all"],
            detection_mode=rule.detection_mode,
        )
        result = evaluator.evaluate(rule_def, claim_ctx)
        if result.flagged:
            flags.append(result)
            flagged = FlaggedClaim(
                tenant_id=str(tenant_id),
                claim_id=req.claim_id,
                auth_number=req.auth_number,
                date_of_service=req.date_of_service,
                pharmacy_npi=req.pharmacy_npi,
                pharmacy_name=req.pharmacy_name,
                prescriber_npi=req.prescriber_npi,
                member_id=req.member_id,
                ndc=req.ndc,
                drug_name=req.drug_name,
                quantity=req.quantity,
                days_supply=req.days_supply,
                billed_amount=money(req.billed_amount),
                paid_amount=money(req.paid_amount),
                detection_rule_id=rule.id,
                rule_code=rule.rule_code,
                rule_name=rule.name,
                detection_mode="real_time",
                risk_score=result.risk_score,
                confidence_tier=result.confidence_tier or "low",
                severity=result.severity or "low",
                evidence=result.evidence,
                action_taken=result.action,
                investigation_status="open",
            )
            db.add(flagged)
            db.flush()
            flagged_claim_ids.append(flagged.id)

    overall_score = max((f.risk_score for f in flags), default=0)
    action_required = None
    if flags:
        actions = [f.action for f in flags if f.action in ("block", "alert")]
        action_required = "block" if "block" in actions else ("alert" if "alert" in actions else "flag")

    from src.api.schemas.schemas import RuleResultSchema  # noqa: PLC0415

    return ClaimEvaluateResponse(
        claim_id=req.claim_id,
        auth_number=req.auth_number,
        overall_risk_score=overall_score,
        rules_evaluated=len(rules),
        flags=[
            RuleResultSchema(
                flagged=f.flagged,
                rule_code=f.rule_code,
                action=f.action,
                confidence_tier=f.confidence_tier,
                risk_score=f.risk_score,
                evidence=f.evidence,
                severity=f.severity,
            )
            for f in flags
        ],
        action_required=action_required,
        flagged_claim_ids=flagged_claim_ids,
    )


# -- Detection Rules --------------------------------------------------------


@router.get("/rules", response_model=list[DetectionRuleRead])
async def list_rules(
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    rules = db.execute(
        select(DetectionRule).where(DetectionRule.is_active.is_(True))
    ).scalars().all()
    return list(rules)


@router.get("/rules/{rule_id}", response_model=DetectionRuleRead)
async def get_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> DetectionRule:
    rule = db.execute(
        select(DetectionRule).where(DetectionRule.id == rule_id)
    ).scalar_one_or_none()
    if rule is None:
        raise _not_found("Rule not found.")
    return rule


# -- Rule Firings -----------------------------------------------------------


@router.get("/rule-firings", response_model=list[RuleFiringRead])
async def list_rule_firings(
    rule_code: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(FlaggedClaim).where(FlaggedClaim.tenant_id == str(user.tenant_id))
    if rule_code:
        stmt = stmt.where(FlaggedClaim.rule_code == rule_code)
    if severity:
        stmt = stmt.where(FlaggedClaim.severity == severity)
    stmt = stmt.order_by(FlaggedClaim.created_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return [
        RuleFiringRead(
            id=r.id,
            tenant_id=r.tenant_id,
            claim_id=r.claim_id,
            rule_code=r.rule_code,
            rule_name=r.rule_name,
            severity=r.severity,
            risk_score=r.risk_score,
            created_at=r.created_at,
        )
        for r in rows
    ]


# -- Flagged Claims ---------------------------------------------------------


@router.get("/flags", response_model=PaginatedResponse[FlaggedClaimRead])
async def list_flags(
    severity: str | None = Query(None),
    rule_code: str | None = Query(None),
    investigation_status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> PaginatedResponse:
    stmt = select(FlaggedClaim).where(FlaggedClaim.tenant_id == str(user.tenant_id))
    if severity:
        stmt = stmt.where(FlaggedClaim.severity == severity)
    if rule_code:
        stmt = stmt.where(FlaggedClaim.rule_code == rule_code)
    if investigation_status:
        stmt = stmt.where(FlaggedClaim.investigation_status == investigation_status)
    total = db.execute(
        select(func.count()).select_from(
            select(FlaggedClaim).where(FlaggedClaim.tenant_id == str(user.tenant_id)).subquery()
        )
    ).scalar_one()
    items = db.execute(
        stmt.order_by(FlaggedClaim.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return PaginatedResponse(items=list(items), total=total, limit=limit, offset=offset)


@router.get("/flags/{flag_id}", response_model=FlaggedClaimRead)
async def get_flag(
    flag_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> FlaggedClaim:
    flag = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.id == flag_id,
            FlaggedClaim.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if flag is None:
        raise _not_found("Flag not found.")
    return flag


@router.put("/flags/{flag_id}", response_model=FlaggedClaimRead)
async def update_flag(
    flag_id: str,
    body: FlaggedClaimUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> FlaggedClaim:
    flag = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.id == flag_id,
            FlaggedClaim.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if flag is None:
        raise _not_found("Flag not found.")
    if body.investigation_status is not None:
        flag.investigation_status = body.investigation_status
    if body.assigned_to is not None:
        flag.assigned_to = str(body.assigned_to)
    if body.review_notes is not None:
        flag.review_notes = body.review_notes
    if body.resolution is not None:
        flag.resolution = body.resolution
    flag.updated_at = datetime.now(UTC)
    db.flush()
    return flag


# -- Investigations ---------------------------------------------------------


@router.get("/investigations", response_model=list[InvestigationRead])
async def list_investigations(
    status: str | None = Query(None),
    subject_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    request: Request = None,
    response: Response = None,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
) -> list:
    if response is not None:
        response.headers["Cache-Control"] = "no-store"
    _emit_phi_audit(request, user, "investigation_list", "*")
    svc = InvestigationService(db)
    return svc.list_investigations(
        tenant_id=user.tenant_id,
        status=status,
        subject_type=subject_type,
        limit=limit,
        offset=offset,
    )


@router.post("/investigations", response_model=InvestigationRead, status_code=201)
async def create_investigation(
    body: InvestigationCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> Investigation:
    svc = InvestigationService(db)
    inv = svc.create_investigation(
        tenant_id=user.tenant_id,
        subject_type=body.subject_type,
        subject_entity_id=body.subject_entity_id,
        subject_name=body.subject_name,
        investigation_type=body.investigation_type,
        title=body.title,
        priority=body.priority,
        user_id=user.id,
        client_id=body.client_id,
        program_id=body.program_id,
        date_range_start=body.date_range_start,
        date_range_end=body.date_range_end,
    )
    db.commit()
    return inv


@router.get("/investigations/{investigation_id}", response_model=InvestigationRead)
async def get_investigation(
    investigation_id: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
) -> Investigation:
    response.headers["Cache-Control"] = "no-store"
    _emit_phi_audit(request, user, "investigation", investigation_id)
    svc = InvestigationService(db)
    inv = svc.get(tenant_id=user.tenant_id, investigation_id=investigation_id)
    if inv is None:
        raise _not_found("Investigation not found.")
    return inv


@router.patch("/investigations/{investigation_id}", response_model=InvestigationRead)
async def update_investigation(
    investigation_id: str,
    body: InvestigationUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
) -> Investigation:
    svc = InvestigationService(db)
    inv = svc.get(tenant_id=user.tenant_id, investigation_id=investigation_id)
    if inv is None:
        raise _not_found("Investigation not found.")
    updates = body.model_dump(exclude_unset=True)
    for field, val in updates.items():
        if hasattr(inv, field):
            setattr(inv, field, str(val) if isinstance(val, uuid.UUID) else val)
    inv.updated_at = datetime.now(UTC)
    db.flush()
    db.commit()
    return inv


@router.get(
    "/investigations/{investigation_id}/timeline",
    response_model=list[InvestigationActivityRead],
)
async def get_investigation_timeline(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
) -> list:
    svc = InvestigationService(db)
    return svc.get_timeline(
        tenant_id=user.tenant_id,
        investigation_id=investigation_id,
    )


@router.post(
    "/investigations/{investigation_id}/activities",
    response_model=InvestigationActivityRead,
    status_code=201,
)
async def add_investigation_activity(
    investigation_id: str,
    body: ActivityCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
) -> InvestigationActivity:
    svc = InvestigationService(db)
    activity = svc.add_activity(
        tenant_id=user.tenant_id,
        investigation_id=investigation_id,
        activity_type=body.activity_type,
        description=body.description,
        user_id=user.id,
        file_id=body.file_id,
    )
    db.commit()
    return activity


@router.post(
    "/investigations/{investigation_id}/notes",
    response_model=InvestigationActivityRead,
    status_code=201,
)
async def add_investigation_note(
    investigation_id: str,
    body: NoteCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
) -> InvestigationActivity:
    svc = InvestigationService(db)
    activity = svc.add_activity(
        tenant_id=user.tenant_id,
        investigation_id=investigation_id,
        activity_type="note",
        description=body.note,
        user_id=user.id,
    )
    db.commit()
    return activity


@router.post(
    "/investigations/{investigation_id}/transitions",
    response_model=InvestigationRead,
)
async def transition_investigation_status(
    investigation_id: str,
    body: TransitionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
) -> Investigation:
    svc = InvestigationService(db)
    role = next((r for r in user.roles if r.startswith("reclaimrx.")), "reclaimrx.viewer")
    try:
        inv = svc.transition(
            tenant_id=user.tenant_id,
            investigation_id=investigation_id,
            to_state=body.to_state,
            role=role,
            user_id=user.id,
            reason=body.reason,
            outcome_label=body.outcome_label,
            recovered_amount=body.recovered_amount,
        )
    except InvalidTransitionError as exc:
        field_val = ", ".join(exc.allowed_next) if exc.allowed_next else investigation_id
        raise HTTPException(
            status_code=422,
            detail=build_error_envelope(exc.code, str(exc), field=field_val),
        ) from exc
    except ValueError as exc:
        if str(exc) == "NOT_FOUND":
            raise _not_found("Investigation not found.")
        raise HTTPException(
            status_code=422,
            detail=build_error_envelope("TRANSITION_ERROR", str(exc)),
        ) from exc
    db.commit()
    return inv


# -- Recoveries -------------------------------------------------------------


@router.get(
    "/investigations/{investigation_id}/recoveries",
    response_model=list[RecoveryRead],
)
async def list_recoveries(
    investigation_id: str,
    methodology_tag: str | None = Query(None),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(Recovery).where(
        Recovery.investigation_id == investigation_id,
        Recovery.tenant_id == str(user.tenant_id),
    )
    if methodology_tag:
        stmt = stmt.where(Recovery.methodology_tag == methodology_tag)
    return list(db.execute(stmt.order_by(Recovery.created_at.desc())).scalars())


@router.post(
    "/investigations/{investigation_id}/recoveries",
    response_model=RecoveryRead,
    status_code=201,
)
async def create_recovery(
    investigation_id: str,
    body: RecoveryCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> Recovery:
    svc = InvestigationService(db)
    rec = svc.create_recovery(
        tenant_id=user.tenant_id,
        investigation_id=investigation_id,
        recovery_method=body.recovery_method,
        amount=body.amount,
        confidence_tier=body.confidence_tier,
        methodology_tag=body.methodology_tag,
        user_id=user.id,
    )
    db.commit()
    return rec


# -- Payment Holds ----------------------------------------------------------


@router.post("/holds", response_model=PaymentHoldRead, status_code=201)
async def create_hold(
    body: PaymentHoldCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> PaymentHold:
    svc = PaymentHoldService(db)
    hold = svc.place_hold(
        tenant_id=user.tenant_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        entity_name=body.entity_name,
        investigation_id=body.investigation_id,
        hold_scope=body.hold_scope,
        rule_filter=body.rule_filter,
        amount_threshold=body.amount_threshold,
        expires_at=body.expires_at,
        placed_by=user.id,
    )
    db.commit()
    return hold


@router.get("/holds", response_model=list[PaymentHoldRead])
async def list_holds(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(PaymentHold).where(PaymentHold.tenant_id == str(user.tenant_id))
    if entity_type:
        stmt = stmt.where(PaymentHold.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(PaymentHold.entity_id == entity_id)
    if status == "active":
        stmt = stmt.where(PaymentHold.is_active.is_(True))
    elif status == "released":
        stmt = stmt.where(PaymentHold.is_active.is_(False))
    return list(
        db.execute(stmt.order_by(PaymentHold.placed_at.desc()).limit(limit).offset(offset)).scalars()
    )


@router.post("/holds/{hold_id}/release", response_model=HoldReleaseResponse)
async def release_hold_v2(
    hold_id: str,
    body: HoldReleaseRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> dict:
    if not body.reason or not body.reason.strip():
        raise HTTPException(
            status_code=422,
            detail=build_error_envelope("REASON_REQUIRED", "Release reason is required.", field="reason"),
        )
    svc = PaymentHoldService(db)
    try:
        result_dict, is_replay = svc.release_hold(
            tenant_id=user.tenant_id,
            hold_id=hold_id,
            released_by=user.id,
            reason=body.reason,
            investigation_id=body.investigation_id,
        )
    except HoldInvestigationMismatchError as exc:
        raise HTTPException(
            status_code=403,
            detail=build_error_envelope("HOLD_INVESTIGATION_MISMATCH", str(exc)),
        ) from exc
    except ValueError as exc:
        msg = str(exc)
        if msg == "NOT_FOUND":
            raise _not_found("Hold not found.")
        if msg.startswith("HOLD_NOT_ACTIVE:"):
            status_val = msg.split(":", 1)[1]
            raise HTTPException(
                status_code=422,
                detail=build_error_envelope(
                    "HOLD_NOT_ACTIVE",
                    f"Hold is not active (status: {status_val}).",
                    field=status_val,
                ),
            ) from exc
        if msg.startswith("ALREADY_RELEASED:"):
            parts = msg.split(":", 2)
            released_by_val = parts[1] if len(parts) > 1 else ""
            released_at_val = parts[2] if len(parts) > 2 else ""
            envelope = build_error_envelope("ALREADY_RELEASED", "Hold was already released by a different actor.")
            envelope["error"]["released_at"] = released_at_val
            envelope["error"]["released_by"] = released_by_val
            raise HTTPException(status_code=409, detail=envelope) from exc
        raise HTTPException(
            status_code=409,
            detail=build_error_envelope("HOLD_CONFLICT", msg),
        ) from exc
    if not is_replay:
        db.commit()
    return result_dict


# -- Graph Runs -------------------------------------------------------------


@router.post("/graph-runs/trigger", response_model=GraphRunRead, status_code=202)
async def trigger_graph_run(
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_ADMIN_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> GraphRun:
    from datetime import timedelta  # noqa: PLC0415
    now = datetime.now(UTC)
    run = GraphRun(
        tenant_id=str(user.tenant_id),
        status="running",
        trigger="on_demand",
        started_at=now,
        rings_detected=0,
        investigations_opened=0,
        records_scanned=0,
        correlation_id=str(uuid.uuid4()),
        stale_timeout_at=now + timedelta(hours=2),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/graph-runs", response_model=list[GraphRunRead])
async def list_graph_runs(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = (
        select(GraphRun)
        .where(GraphRun.tenant_id == str(user.tenant_id))
        .order_by(GraphRun.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())


@router.get("/graph-runs/{run_id}", response_model=GraphRunRead)
async def get_graph_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> GraphRun:
    run = db.execute(
        select(GraphRun).where(
            GraphRun.id == run_id,
            GraphRun.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if run is None:
        raise _not_found("Graph run not found.")
    return run


# -- Fraud Rings ------------------------------------------------------------


@router.get("/fraud-rings", response_model=list[FraudRingRead])
async def list_fraud_rings(
    run_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(FraudRing).where(FraudRing.tenant_id == str(user.tenant_id))
    if run_id:
        stmt = stmt.where(FraudRing.graph_run_id == run_id)
    return list(
        db.execute(stmt.order_by(FraudRing.density_score.desc()).limit(limit).offset(offset)).scalars()
    )


@router.get("/fraud-rings/{ring_id}", response_model=FraudRingRead)
async def get_fraud_ring(
    ring_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> FraudRing:
    ring = db.execute(
        select(FraudRing).where(
            FraudRing.id == ring_id,
            FraudRing.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if ring is None:
        raise _not_found("Fraud ring not found.")
    return ring


# -- ML Scores --------------------------------------------------------------


@router.get("/ml-scores", response_model=list[MlScoreRead])
async def list_ml_scores(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    min_score: float | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(MlPrediction).where(MlPrediction.tenant_id == str(user.tenant_id))
    if entity_type:
        stmt = stmt.where(MlPrediction.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(MlPrediction.entity_id == entity_id)
    rows = list(
        db.execute(stmt.order_by(MlPrediction.predicted_at.desc()).limit(limit).offset(offset)).scalars()
    )
    result = []
    for r in rows:
        score_val = getattr(r, "risk_score", getattr(r, "score", 0))
        if min_score is not None and float(score_val) < min_score:
            continue
        result.append(
            MlScoreRead(
                id=str(r.id),
                tenant_id=str(r.tenant_id),
                claim_id=str(r.claim_id) if getattr(r, "claim_id", None) else None,
                model_id=str(r.model_id) if getattr(r, "model_id", None) else "",
                score=str(score_val),
                feature_importance=getattr(r, "feature_importance", None),
                created_at=getattr(r, "predicted_at", datetime.now(UTC)),
            )
        )
    return result


# -- Thresholds -------------------------------------------------------------


@router.get("/thresholds", response_model=list[ThresholdConfigRead])
async def list_thresholds(
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(ThresholdConfig).where(ThresholdConfig.tenant_id == str(user.tenant_id))
    if category:
        stmt = stmt.where(ThresholdConfig.config_key.startswith(category))
    return list(db.execute(stmt.order_by(ThresholdConfig.config_key)).scalars())


@router.put("/thresholds/{threshold_id}", response_model=ThresholdConfigRead)
async def upsert_threshold(
    threshold_id: str,
    body: ThresholdUpsert,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_ADMIN_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
) -> ThresholdConfig:
    cfg = db.execute(
        select(ThresholdConfig).where(
            ThresholdConfig.id == threshold_id,
            ThresholdConfig.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if cfg is None:
        cfg = ThresholdConfig(
            id=threshold_id,
            tenant_id=str(user.tenant_id),
            config_key=body.config_key,
            value=body.value,
            version=1,
            updated_by=str(user.id),
            updated_at=datetime.now(UTC),
        )
        db.add(cfg)
    else:
        cfg.value = body.value
        cfg.version = (cfg.version or 0) + 1
        cfg.updated_by = str(user.id)
        cfg.updated_at = datetime.now(UTC)
    db.flush()
    db.commit()
    return cfg


# -- Accumulator Detections -------------------------------------------------


@router.get("/accumulator-detections", response_model=list[AccumulatorDetectionRead])
async def list_accumulator_detections(
    member_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(AccumulatorDetection).where(
        AccumulatorDetection.tenant_id == str(user.tenant_id)
    )
    if member_id:
        stmt = stmt.where(AccumulatorDetection.member_id == member_id)
    return list(
        db.execute(stmt.order_by(AccumulatorDetection.created_at.desc()).limit(limit).offset(offset)).scalars()
    )


# -- Entity Profiles --------------------------------------------------------


@router.get("/pharmacy-profiles", response_model=list[PharmacyProfileRead])
async def list_pharmacy_profiles(
    anomaly_candidate: bool | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(PharmacyProfile).where(PharmacyProfile.tenant_id == str(user.tenant_id))
    if anomaly_candidate is not None:
        stmt = stmt.where(PharmacyProfile.is_flagged.is_(anomaly_candidate))
    return list(
        db.execute(stmt.order_by(PharmacyProfile.composite_risk_score.desc()).limit(limit).offset(offset)).scalars()
    )


@router.get("/pharmacy-profiles/{pharmacy_npi}", response_model=PharmacyProfileRead)
async def get_pharmacy_profile(
    pharmacy_npi: str,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> PharmacyProfile:
    profile = db.execute(
        select(PharmacyProfile).where(
            PharmacyProfile.pharmacy_npi == pharmacy_npi,
            PharmacyProfile.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if profile is None:
        raise _not_found("Pharmacy profile not found.")
    return profile


@router.get("/prescriber-profiles", response_model=list[PrescriberProfileRead])
async def list_prescriber_profiles(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(PrescriberProfile).where(PrescriberProfile.tenant_id == str(user.tenant_id))
    return list(
        db.execute(stmt.order_by(PrescriberProfile.composite_risk_score.desc()).limit(limit).offset(offset)).scalars()
    )


@router.get("/member-profiles", response_model=list[MemberProfileRead])
async def list_member_profiles(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(MemberProfile).where(MemberProfile.tenant_id == str(user.tenant_id))
    return list(
        db.execute(stmt.order_by(MemberProfile.composite_risk_score.desc()).limit(limit).offset(offset)).scalars()
    )


# -- Tips -------------------------------------------------------------------


@router.post("/tips", response_model=TipRead, status_code=201)
async def submit_tip(
    body: TipCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> TipRecord:
    tip = TipRecord(
        tenant_id=str(user.tenant_id),
        tip_type=body.tip_type,
        subject_description=body.subject_description,
        detail_text=body.detail_text,
        is_anonymous=body.is_anonymous,
        reporter_name=body.reporter_name if not body.is_anonymous else None,
        reporter_contact=body.reporter_contact if not body.is_anonymous else None,
        status="received",
    )
    db.add(tip)
    db.commit()
    db.refresh(tip)
    return tip


@router.get("/tips", response_model=list[TipRead])
async def list_tips(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    stmt = select(TipRecord).where(TipRecord.tenant_id == str(user.tenant_id))
    if status:
        stmt = stmt.where(TipRecord.status == status)
    return list(
        db.execute(stmt.order_by(TipRecord.created_at.desc()).limit(limit).offset(offset)).scalars()
    )


# ---------------------------------------------------------------------------
# Detection Console: Anomalies (Foundation Slice)
# ---------------------------------------------------------------------------


def _derive_entity_type(pharmacy_npi, prescriber_npi) -> str:
    if pharmacy_npi is not None:
        return "pharmacy"
    if prescriber_npi is not None:
        return "prescriber"
    return "unknown"


def _decimal_to_str(v):
    if v is None:
        return None
    return str(v)


def _is_postgres_session(db: Session) -> bool:
    try:
        return db.bind.dialect.name == "postgresql"
    except Exception:
        return False


def _enrich_names_set_based(db: Session, rows) -> dict:
    pharm_npis = {a.pharmacy_npi for a in rows if a.pharmacy_npi}
    presc_npis = {a.prescriber_npi for a in rows if a.prescriber_npi}
    pharm_names: dict = {}
    presc_names: dict = {}
    if not _is_postgres_session(db):
        return {"pharmacy": pharm_names, "prescriber": presc_names}
    if pharm_npis:
        try:
            from sqlalchemy import text as _text
            res = db.execute(
                _text("SELECT npi, legal_business_name FROM reference.dataq_master WHERE npi = ANY(:npis)"),
                {"npis": list(pharm_npis)},
            ).fetchall()
            pharm_names = {r[0]: r[1] for r in res if r[0] and r[1]}
        except Exception:
            pass
    if presc_npis:
        try:
            from sqlalchemy import text as _text
            res = db.execute(
                _text("SELECT npi, provider_last_name FROM reference.prescribers WHERE npi = ANY(:npis)"),
                {"npis": list(presc_npis)},
            ).fetchall()
            presc_names = {r[0]: r[1] for r in res if r[0] and r[1]}
        except Exception:
            pass
    return {"pharmacy": pharm_names, "prescriber": presc_names}

@router.get("/anomalies", response_model=PaginatedResponse)
async def list_anomalies(
    response: Response,
    finding_code: list[str] = Query(default=[]),
    severity: str | None = Query(None),
    status: str | None = Query(None),
    entity_type: str | None = Query(None),
    pharmacy_npi: str | None = Query(None),
    prescriber_npi: str | None = Query(None),
    ndc: str | None = Query(None),
    data_source_run_id: str | None = Query(None),
    min_amount: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> PaginatedResponse:
    """List anomalies for the tenant with server-side AND-filters and pagination."""
    from datetime import date as _date
    from decimal import Decimal, InvalidOperation
    from src.models.detection_run_models import Anomaly as _Anomaly
    from src.api.schemas.schemas import AnomalyRead as _AnomalyRead

    response.headers["Cache-Control"] = "no-store"
    stmt = select(_Anomaly).where(_Anomaly.tenant_id == user.tenant_id)

    if finding_code:
        stmt = stmt.where(_Anomaly.finding_code.in_(finding_code))
    if severity:
        stmt = stmt.where(_Anomaly.severity == severity)
    if status:
        stmt = stmt.where(_Anomaly.status == status)
    if entity_type == "pharmacy":
        stmt = stmt.where(_Anomaly.pharmacy_npi.is_not(None))
    elif entity_type == "prescriber":
        stmt = stmt.where(_Anomaly.prescriber_npi.is_not(None), _Anomaly.pharmacy_npi.is_(None))
    elif entity_type == "unknown":
        stmt = stmt.where(_Anomaly.pharmacy_npi.is_(None), _Anomaly.prescriber_npi.is_(None))
    if pharmacy_npi:
        stmt = stmt.where(_Anomaly.pharmacy_npi == pharmacy_npi)
    if prescriber_npi:
        stmt = stmt.where(_Anomaly.prescriber_npi == prescriber_npi)
    if ndc:
        stmt = stmt.where(_Anomaly.ndc == ndc)
    if data_source_run_id:
        try:
            import uuid as _uuid
            stmt = stmt.where(_Anomaly.data_source_run_id == _uuid.UUID(data_source_run_id))
        except (ValueError, TypeError):
            pass
    if min_amount:
        try:
            stmt = stmt.where(_Anomaly.amount_paid >= Decimal(str(min_amount)))
        except InvalidOperation:
            pass
    if date_from:
        try:
            stmt = stmt.where(_Anomaly.date_of_service >= _date.fromisoformat(date_from))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            stmt = stmt.where(_Anomaly.date_of_service <= _date.fromisoformat(date_to))
        except (ValueError, TypeError):
            pass

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = db.execute(total_stmt).scalar_one()

    offset = (page - 1) * page_size
    rows = db.execute(
        stmt.order_by(_Anomaly.created_at.desc(), _Anomaly.id).limit(page_size).offset(offset)
    ).scalars().all()

    names = _enrich_names_set_based(db, rows)
    pharm_map = names["pharmacy"]
    presc_map = names["prescriber"]

    items = [
        _AnomalyRead(
            id=str(a.id),
            finding_code=a.finding_code,
            finding_summary=a.finding_summary,
            severity=a.severity,
            confidence=str(a.confidence),
            status=a.status,
            entity_type=_derive_entity_type(a.pharmacy_npi, a.prescriber_npi),
            pharmacy_npi=a.pharmacy_npi,
            pharmacy_name=pharm_map.get(a.pharmacy_npi) if a.pharmacy_npi else None,
            prescriber_npi=a.prescriber_npi,
            prescriber_name=presc_map.get(a.prescriber_npi) if a.prescriber_npi else None,
            ndc=a.ndc,
            amount_paid=_decimal_to_str(a.amount_paid),
            amount_billed=_decimal_to_str(a.amount_billed),
            recovery_amount=_decimal_to_str(a.recovery_amount),
            date_of_service=a.date_of_service,
            data_source_run_id=str(a.data_source_run_id) if a.data_source_run_id else None,
            created_at=a.created_at,
        )
        for a in rows
    ]
    return PaginatedResponse(items=items, total=total, limit=page_size, offset=offset)


# ---------------------------------------------------------------------------
# Detection Console: Detection Runs
# ---------------------------------------------------------------------------


def _run_to_dict(run) -> dict:
    stats = run.resolution_stats or {}
    return {
        "id": str(run.id),
        "run_label": run.run_label,
        "status": run.status,
        "data_source": run.data_source,
        "source_filename": run.source_filename,
        "record_count": run.record_count,
        "anomaly_count": run.anomaly_count,
        "period_start": run.period_start.isoformat() if run.period_start else None,
        "period_end": run.period_end.isoformat() if run.period_end else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "failure_reason": run.failure_reason,
        "data_quality": stats.get("data_quality"),
    }


@router.get("/detection-runs")
async def list_detection_runs(
    response: Response,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    """List detection runs for the tenant, newest first."""
    from src.models.detection_run_models import DetectionRun as _DR
    response.headers["Cache-Control"] = "no-store"
    runs = db.execute(
        select(_DR).where(_DR.tenant_id == user.tenant_id).order_by(_DR.started_at.desc())
    ).scalars().all()
    return [_run_to_dict(r) for r in runs]


@router.get("/detection-runs/{run_id}")
async def get_detection_run(
    run_id: str,
    response: Response,
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> dict:
    """Get a single detection run with per-rule breakdown (tenant-scoped GROUP BY)."""
    import uuid as _uuid
    from src.models.detection_run_models import Anomaly as _Anomaly, DetectionRun as _DR
    response.headers["Cache-Control"] = "no-store"
    try:
        run_uuid = _uuid.UUID(run_id)
    except (ValueError, TypeError):
        raise _not_found("Detection run not found.")
    run = db.execute(
        select(_DR).where(_DR.id == run_uuid, _DR.tenant_id == user.tenant_id)
    ).scalar_one_or_none()
    if run is None:
        raise _not_found("Detection run not found.")
    breakdown_rows = db.execute(
        select(
            _Anomaly.finding_code,
            _Anomaly.severity,
            func.count(_Anomaly.id).label("cnt"),
        ).where(
            _Anomaly.data_source_run_id == run_uuid,
            _Anomaly.tenant_id == user.tenant_id,
        ).group_by(_Anomaly.finding_code, _Anomaly.severity)
        .order_by(func.count(_Anomaly.id).desc())
    ).all()
    result = _run_to_dict(run)
    result["per_rule_breakdown"] = [
        {"finding_code": r.finding_code, "severity": r.severity, "count": r.cnt}
        for r in breakdown_rows
    ]
    return result


# ---------------------------------------------------------------------------
# Detection Console: Ingest
# ---------------------------------------------------------------------------


@router.post("/detection-runs", status_code=201)
async def ingest_detection_run(
    response: Response,
    file: UploadFile = File(...),
    run_label: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> dict:
    """Upload a CSV and run full ingest+detection pipeline synchronously.

    Configurable max-rows guard via RECLAIMRX_MAX_UPLOAD_ROWS env var.
    Returns HTTP 413 for oversized files (no hardcoded magic number).
    """
    import csv as _csv
    import os as _os
    import shutil as _shutil
    import uuid as _uuid
    from pathlib import Path as _Path
    from src.detection.batch_engine import run_detection as _run_detection
    from src.detection.csv_ingest import create_or_resume_run as _create_run, load_csv as _load_csv

    response.headers["Cache-Control"] = "no-store"

    max_rows_env = _os.environ.get("RECLAIMRX_MAX_UPLOAD_ROWS", "500000")
    try:
        max_rows = int(max_rows_env)
    except (ValueError, TypeError):
        max_rows = 500_000

    tenant_id = user.tenant_id
    upload_run_id = _uuid.uuid4()
    upload_dir = _Path("data") / "uploads" / str(tenant_id) / str(upload_run_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "upload.csv"
    dest_path = upload_dir / filename

    with dest_path.open("wb") as fh:
        _shutil.copyfileobj(file.file, fh)

    row_count = 0
    with dest_path.open(newline="", encoding="utf-8") as fh:
        for _ in _csv.reader(fh):
            row_count += 1
    data_rows = max(0, row_count - 1)

    if data_rows > max_rows:
        _shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(
            status_code=413,
            detail=build_error_envelope(
                "FILE_TOO_LARGE",
                f"File has {data_rows} rows which exceeds the synchronous limit of {max_rows}. Use the CLI for large files.",
                field="file",
            ),
        )

    try:
        run = _create_run(
            db,
            tenant_id=tenant_id,
            path=str(dest_path),
            created_by=user.id,
            resume=False,
            force=False,
        )
        if run_label:
            run.run_label = run_label
            db.flush()
        _load_csv(db, run)
        _run_detection(db, run)
        db.commit()
        db.refresh(run)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=build_error_envelope(
                "INGEST_ERROR",
                f"Ingest failed: {type(exc).__name__}: {exc}",
            ),
        ) from exc

    return _run_to_dict(run)