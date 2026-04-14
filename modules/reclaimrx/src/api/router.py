"""ReclaimRx FastAPI router — thin API layer; all logic in services."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src._shim.auth import CurrentUser
from src.api.dependencies import get_current_user, get_db, require_investigator
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
    Investigation,
    InvestigationActivity,
    MemberProfile,
    PaymentHold,
    PharmacyProfile,
    PrescriberProfile,
    Recovery,
    TipRecord,
)
from src.services.investigation_service import InvestigationService
from src.services.payment_hold_service import PaymentHoldService
from src.services.rule_engine import ClaimContext, RuleDefinition, RuleEvaluator
from src.utils.money import money

router = APIRouter(prefix="/api/v1/reclaimrx", tags=["reclaimrx"])


# ── Real-time Evaluation ──────────────────────────────────────────────────────

@router.post("/evaluate", response_model=ClaimEvaluateResponse)
async def evaluate_claim(
    req: ClaimEvaluateRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ClaimEvaluateResponse:
    """Evaluate a claim against all active detection rules (real-time path)."""
    tenant_id = user.tenant_id

    # Load active rules applicable to real-time mode
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

            # Persist flagged claim record
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

    from src.api.schemas.schemas import RuleResultSchema
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


# ── Detection Rules ───────────────────────────────────────────────────────────

@router.get("/rules", response_model=list[DetectionRuleRead])
async def list_rules(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    rules = db.execute(
        select(DetectionRule).where(DetectionRule.is_active.is_(True))
    ).scalars().all()
    return list(rules)


@router.get("/rules/{rule_id}", response_model=DetectionRuleRead)
async def get_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DetectionRule:
    rule = db.execute(
        select(DetectionRule).where(DetectionRule.id == rule_id)
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Rule not found"})
    return rule


# ── Flagged Claims ────────────────────────────────────────────────────────────

@router.get("/flags", response_model=PaginatedResponse[FlaggedClaimRead])
async def list_flags(
    severity: str | None = Query(None),
    rule_code: str | None = Query(None),
    investigation_status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse:
    stmt = select(FlaggedClaim).where(FlaggedClaim.tenant_id == str(user.tenant_id))
    if severity:
        stmt = stmt.where(FlaggedClaim.severity == severity)
    if rule_code:
        stmt = stmt.where(FlaggedClaim.rule_code == rule_code)
    if investigation_status:
        stmt = stmt.where(FlaggedClaim.investigation_status == investigation_status)
    stmt = stmt.order_by(FlaggedClaim.created_at.desc())

    from sqlalchemy import func
    from sqlalchemy import select as sa_select
    total = db.execute(
        sa_select(func.count()).select_from(
            select(FlaggedClaim).where(FlaggedClaim.tenant_id == str(user.tenant_id)).subquery()
        )
    ).scalar_one()

    items = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return PaginatedResponse(items=list(items), total=total, limit=limit, offset=offset)


@router.get("/flags/{flag_id}", response_model=FlaggedClaimRead)
async def get_flag(
    flag_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> FlaggedClaim:
    flag = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.id == flag_id,
            FlaggedClaim.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if flag is None:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Flag not found"})
    return flag


@router.put("/flags/{flag_id}", response_model=FlaggedClaimRead)
async def update_flag(
    flag_id: str,
    body: FlaggedClaimUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
) -> FlaggedClaim:
    flag = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.id == flag_id,
            FlaggedClaim.tenant_id == str(user.tenant_id),
        )
    ).scalar_one_or_none()
    if flag is None:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Flag not found"})
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


# ── Investigations ────────────────────────────────────────────────────────────

@router.get("/investigations", response_model=list[InvestigationRead])
async def list_investigations(
    status: str | None = Query(None),
    subject_type: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
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
    user: CurrentUser = Depends(require_investigator),
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
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Investigation:
    svc = InvestigationService(db)
    inv = svc.get(tenant_id=user.tenant_id, investigation_id=investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Investigation not found"})
    return inv


@router.put("/investigations/{investigation_id}", response_model=InvestigationRead)
async def update_investigation(
    investigation_id: str,
    body: InvestigationUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
) -> Investigation:
    svc = InvestigationService(db)
    try:
        if body.status is not None:
            svc.update_status(
                tenant_id=user.tenant_id,
                investigation_id=investigation_id,
                new_status=body.status,
                user_id=user.id,
                notes=body.notes,
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": str(exc)}) from exc
    inv = svc.get(tenant_id=user.tenant_id, investigation_id=investigation_id)
    if inv is None:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})
    db.commit()
    return inv


@router.get("/investigations/{investigation_id}/timeline", response_model=list[ActivityRead])
async def get_investigation_timeline(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    svc = InvestigationService(db)
    return svc.get_timeline(tenant_id=user.tenant_id, investigation_id=investigation_id)


@router.post("/investigations/{investigation_id}/activity", response_model=ActivityRead, status_code=201)
async def add_investigation_activity(
    investigation_id: str,
    body: ActivityCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
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


# ── Recoveries ────────────────────────────────────────────────────────────────

@router.get("/recoveries", response_model=list[RecoveryRead])
async def list_recoveries(
    investigation_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    stmt = select(Recovery).where(Recovery.tenant_id == str(user.tenant_id))
    if investigation_id:
        stmt = stmt.where(Recovery.investigation_id == investigation_id)
    return list(db.execute(stmt).scalars())


@router.post("/recoveries", response_model=RecoveryRead, status_code=201)
async def create_recovery(
    body: RecoveryCreate,
    investigation_id: str = Query(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
) -> Recovery:
    svc = InvestigationService(db)
    recovery = svc.create_recovery(
        tenant_id=user.tenant_id,
        investigation_id=investigation_id,
        recovery_method=body.recovery_method,
        amount=body.amount,
        confidence_tier=body.confidence_tier,
        methodology_tag=body.methodology_tag,
        user_id=user.id,
    )
    db.commit()
    return recovery


# ── Payment Holds ─────────────────────────────────────────────────────────────

@router.post("/holds", response_model=PaymentHoldRead, status_code=201)
async def create_hold(
    body: PaymentHoldCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
) -> PaymentHold:
    svc = PaymentHoldService(db)
    hold = svc.place_hold(
        tenant_id=user.tenant_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        entity_name=body.entity_name,
        placed_by=user.id,
        hold_scope=body.hold_scope,
        investigation_id=body.investigation_id,
        rule_filter=body.rule_filter,
        amount_threshold=body.amount_threshold,
        expires_at=body.expires_at,
    )
    db.commit()
    return hold


@router.get("/holds", response_model=list[PaymentHoldRead])
async def list_holds(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    svc = PaymentHoldService(db)
    return svc.list_active_holds(
        tenant_id=user.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )


@router.delete("/holds/{hold_id}", response_model=PaymentHoldRead)
async def release_hold(
    hold_id: str,
    reason: str = Query(default="Released"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
) -> PaymentHold:
    svc = PaymentHoldService(db)
    try:
        hold = svc.release_hold(
            tenant_id=user.tenant_id,
            hold_id=hold_id,
            released_by=user.id,
            reason=reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": str(exc)}) from exc
    db.commit()
    return hold


# ── Entity Profiles ───────────────────────────────────────────────────────────

@router.get("/pharmacy-profiles", response_model=list[PharmacyProfileRead])
async def list_pharmacy_profiles(
    min_risk_score: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    stmt = (
        select(PharmacyProfile)
        .where(
            PharmacyProfile.tenant_id == str(user.tenant_id),
            PharmacyProfile.composite_risk_score >= min_risk_score,
        )
        .order_by(PharmacyProfile.composite_risk_score.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())


@router.get("/pharmacy-profiles/{npi}", response_model=PharmacyProfileRead)
async def get_pharmacy_profile(
    npi: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PharmacyProfile:
    profile = db.execute(
        select(PharmacyProfile).where(
            PharmacyProfile.tenant_id == str(user.tenant_id),
            PharmacyProfile.pharmacy_npi == npi,
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})
    return profile


@router.get("/prescriber-profiles", response_model=list[PrescriberProfileRead])
async def list_prescriber_profiles(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return list(
        db.execute(
            select(PrescriberProfile)
            .where(PrescriberProfile.tenant_id == str(user.tenant_id))
            .order_by(PrescriberProfile.composite_risk_score.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )


@router.get("/member-profiles", response_model=list[MemberProfileRead])
async def list_member_profiles(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return list(
        db.execute(
            select(MemberProfile)
            .where(MemberProfile.tenant_id == str(user.tenant_id))
            .order_by(MemberProfile.composite_risk_score.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )


# ── Accumulator ───────────────────────────────────────────────────────────────

@router.get("/accumulator/detections", response_model=list[AccumulatorDetectionRead])
async def list_accumulator_detections(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list:
    return list(
        db.execute(
            select(AccumulatorDetection)
            .where(AccumulatorDetection.tenant_id == str(user.tenant_id))
            .order_by(AccumulatorDetection.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )


# ── Tips ─────────────────────────────────────────────────────────────────────

@router.post("/tips", response_model=TipRead, status_code=201)
async def submit_tip(
    body: TipCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TipRecord:
    from src.events.publishers import publish_tip_received
    tip = TipRecord(
        tenant_id=str(user.tenant_id),
        tip_type=body.tip_type,
        subject_description=body.subject_description,
        detail_text=body.detail_text,
        reporter_name=body.reporter_name,
        reporter_contact=body.reporter_contact,
        is_anonymous=body.is_anonymous,
        status="new",
    )
    db.add(tip)
    db.flush()
    publish_tip_received(
        tenant_id=user.tenant_id,
        tip_id=tip.id,
        tip_type=tip.tip_type,
        is_anonymous=tip.is_anonymous,
    )
    db.commit()
    return tip


@router.get("/tips", response_model=list[TipRead])
async def list_tips(
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_investigator),
) -> list:
    stmt = select(TipRecord).where(TipRecord.tenant_id == str(user.tenant_id))
    if status:
        stmt = stmt.where(TipRecord.status == status)
    stmt = stmt.order_by(TipRecord.created_at.desc()).limit(limit)
    return list(db.execute(stmt).scalars())
