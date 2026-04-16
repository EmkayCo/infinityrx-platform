"""PA lifecycle management service.

Manages the complete lifecycle of a prior authorization request:
create -> evaluate -> decide/auto-approve -> appeal -> expire.

All database operations use the session passed in -- no module-local
session factory. Money amounts use Decimal with ROUND_HALF_UP.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.utils.money import ZERO, TWO_PLACES, money

from src.models.tables import (
    CopayEPARecord,
    PAAppeal,
    PACriteriaSet,
    PADecision,
    PARequest,
)
from src.services.criteria_engine import CriteriaResult, evaluate_criteria

logger = logging.getLogger(__name__)

# Valid state transitions
VALID_SOURCES = frozenset({"pharmacy_reject", "epa", "manual", "phone", "fhir"})
VALID_PRIORITIES = frozenset({"routine", "urgent"})
VALID_DECISIONS = frozenset({"approved", "denied", "pend", "request_info"})
VALID_APPEAL_TYPES = frozenset({"clinical_reviewer", "medical_director", "external"})

# Configurable PA expiration
PA_EXPIRATION_DAYS = 365
URGENT_REVIEW_DEADLINE_HOURS = 24
ROUTINE_REVIEW_DEADLINE_HOURS = 72


class PALifecycleError(Exception):
    """Raised when a PA lifecycle operation fails a business rule."""


def create_pa(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    member_id: uuid.UUID,
    prescriber_npi: str,
    drug_ndc: str,
    drug_name: str,
    source: str,
    plan_id: uuid.UUID,
    priority: str = "routine",
    program_id: uuid.UUID | None = None,
    clinical_data: dict | None = None,
) -> PARequest:
    """Create a new PA request.

    Raises PALifecycleError on invalid source or duplicate detection.
    """
    if source not in VALID_SOURCES:
        raise PALifecycleError(f"Invalid PA source: {source}")
    if priority not in VALID_PRIORITIES:
        raise PALifecycleError(f"Invalid priority: {priority}")

    # Duplicate detection: active PA for same member+drug
    existing = db.execute(
        select(PARequest).where(
            PARequest.tenant_id == tenant_id,
            PARequest.member_id == member_id,
            PARequest.drug_ndc == drug_ndc,
            PARequest.status.in_(["submitted", "in_review", "approved"]),
        )
    ).scalar_one_or_none()

    if existing is not None:
        raise PALifecycleError(
            f"Active PA already exists for member {member_id} and drug {drug_ndc}: {existing.id}"
        )

    # Find applicable criteria set version
    criteria_version = _find_criteria_version(db, tenant_id, drug_ndc, plan_id)

    pa = PARequest(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        member_id=member_id,
        prescriber_npi=prescriber_npi,
        drug_ndc=drug_ndc,
        drug_name=drug_name,
        source=source,
        status="submitted",
        priority=priority,
        plan_id=plan_id,
        program_id=program_id,
        clinical_data=clinical_data,
        criteria_set_version=criteria_version,
    )
    db.add(pa)
    db.flush()

    logger.info(
        "PA request created",
        extra={
            "pa_request_id": str(pa.id),
            "pa_source": source,
            "pa_priority": priority,
            "pa_tenant_id": str(tenant_id),
        },
    )
    return pa


def evaluate_pa(
    db: Session,
    pa_request_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    member_age: int | None = None,
    member_diagnoses: list[str] | None = None,
    step_therapy_history: list[dict] | None = None,
    lab_results: dict[str, float] | None = None,
    member_bmi: float | None = None,
    member_comorbidities: list[str] | None = None,
    lifestyle_intervention_date: date | None = None,
) -> CriteriaResult:
    """Evaluate a PA request against clinical criteria.

    If auto-approved, transitions the PA to 'approved' and creates a PADecision.
    Otherwise, transitions to 'in_review'.
    """
    pa = _get_pa(db, pa_request_id, tenant_id)
    criteria_set = _find_criteria_set(
        db, tenant_id, pa.drug_ndc, pa.plan_id, pa.criteria_set_version
    )

    if criteria_set is None:
        # No criteria means manual review required
        pa.status = "in_review"
        db.flush()
        return CriteriaResult(
            auto_approve=False,
            reasons=["No criteria set found for drug; manual review required"],
            missing_info=[],
        )

    result = evaluate_criteria(
        pa,
        criteria_set,
        member_age=member_age,
        member_diagnoses=member_diagnoses,
        step_therapy_history=step_therapy_history,
        lab_results=lab_results,
        member_bmi=member_bmi,
        member_comorbidities=member_comorbidities,
        lifestyle_intervention_date=lifestyle_intervention_date,
    )

    if result.auto_approve:
        pa.status = "approved"
        decision = PADecision(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            pa_request_id=pa.id,
            decision="approved",
            approved_duration_days=PA_EXPIRATION_DAYS,
            reviewed_by=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # system
            review_notes="Auto-approved by criteria engine",
        )
        db.add(decision)
    elif result.missing_info:
        pa.status = "in_review"
    else:
        pa.status = "in_review"

    db.flush()
    return result


def decide_pa(
    db: Session,
    pa_request_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    decision: str,
    reviewer_id: uuid.UUID,
    approved_duration_days: int | None = None,
    approved_quantity: Decimal | None = None,
    review_notes: str | None = None,
) -> PADecision:
    """Record a clinical reviewer's decision on a PA request."""
    if decision not in VALID_DECISIONS:
        raise PALifecycleError(f"Invalid decision: {decision}")

    pa = _get_pa(db, pa_request_id, tenant_id)
    if pa.status not in ("submitted", "in_review"):
        raise PALifecycleError(
            f"Cannot decide PA in status '{pa.status}'. Must be submitted or in_review."
        )

    quantity = None
    if approved_quantity is not None:
        quantity = approved_quantity.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    pa_decision = PADecision(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        pa_request_id=pa.id,
        decision=decision,
        approved_duration_days=approved_duration_days,
        approved_quantity=quantity,
        reviewed_by=reviewer_id,
        review_notes=review_notes,
    )
    db.add(pa_decision)

    # Update PA status based on decision
    status_map = {
        "approved": "approved",
        "denied": "denied",
        "pend": "in_review",
        "request_info": "in_review",
    }
    pa.status = status_map[decision]
    db.flush()

    logger.info(
        "PA decision recorded",
        extra={
            "pa_request_id": str(pa.id),
            "pa_decision": decision,
            "pa_reviewer_id": str(reviewer_id),
        },
    )
    return pa_decision


def submit_appeal(
    db: Session,
    pa_request_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    appeal_level: int,
    appeal_type: str,
    regulatory_deadline: date | None = None,
) -> PAAppeal:
    """Submit an appeal against a PA denial."""
    if appeal_type not in VALID_APPEAL_TYPES:
        raise PALifecycleError(f"Invalid appeal type: {appeal_type}")

    pa = _get_pa(db, pa_request_id, tenant_id)
    if pa.status not in ("denied",):
        raise PALifecycleError(
            f"Cannot appeal PA in status '{pa.status}'. Must be denied."
        )

    appeal = PAAppeal(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        pa_request_id=pa.id,
        appeal_level=appeal_level,
        appeal_type=appeal_type,
        status="submitted",
        regulatory_deadline=regulatory_deadline,
    )
    db.add(appeal)
    pa.status = "appealed"
    db.flush()

    logger.info(
        "PA appeal submitted",
        extra={
            "pa_request_id": str(pa.id),
            "pa_appeal_id": str(appeal.id),
            "pa_appeal_level": appeal_level,
        },
    )
    return appeal


def check_pa_status(
    db: Session,
    tenant_id: uuid.UUID,
    member_id: uuid.UUID,
    drug_ndc: str,
) -> dict:
    """Check current PA status for a member+drug combination.

    Consumed by the adjudication engine to determine if a PA exists and is valid.
    Returns a dict with pa_id, status, approved_until (if approved), or None if no PA.
    """
    pa = db.execute(
        select(PARequest).where(
            PARequest.tenant_id == tenant_id,
            PARequest.member_id == member_id,
            PARequest.drug_ndc == drug_ndc,
            PARequest.status.in_(["submitted", "in_review", "approved", "appealed"]),
        ).order_by(PARequest.created_at.desc())
    ).scalar_one_or_none()

    if pa is None:
        return {"pa_exists": False, "status": None}

    result: dict = {
        "pa_exists": True,
        "pa_id": str(pa.id),
        "status": pa.status,
    }

    if pa.status == "approved":
        # Find latest approval decision for duration
        latest_decision = db.execute(
            select(PADecision).where(
                PADecision.tenant_id == tenant_id,
                PADecision.pa_request_id == pa.id,
                PADecision.decision == "approved",
            ).order_by(PADecision.decided_at.desc())
        ).scalar_one_or_none()

        if latest_decision and latest_decision.approved_duration_days:
            approved_until = latest_decision.decided_at + timedelta(
                days=latest_decision.approved_duration_days
            )
            result["approved_until"] = approved_until.isoformat()

    return result


def expire_pas(db: Session, tenant_id: uuid.UUID) -> int:
    """Batch expire overdue PA requests.

    Returns the count of PAs expired.
    """
    now = datetime.now(UTC)
    expiration_cutoff = now - timedelta(days=PA_EXPIRATION_DAYS)

    pas = db.execute(
        select(PARequest).where(
            PARequest.tenant_id == tenant_id,
            PARequest.status.in_(["submitted", "in_review"]),
            PARequest.created_at < expiration_cutoff,
        )
    ).scalars().all()

    count = 0
    for pa in pas:
        pa.status = "expired"
        count += 1

    if count > 0:
        db.flush()
        logger.info(
            "PAs expired in batch",
            extra={
                "pa_expired_count": count,
                "pa_tenant_id": str(tenant_id),
            },
        )

    return count


def create_copay_epa_first_fill(
    db: Session,
    pa_request_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    manufacturer_program_id: str,
    first_fill_amount: Decimal,
    first_fill_date: date,
) -> CopayEPARecord:
    """Create a copay ePA first-fill record for manufacturer-funded programs.

    When a PA is pending but the manufacturer program allows first-fill
    coverage, this record tracks the funded amount for reconciliation.
    """
    pa = _get_pa(db, pa_request_id, tenant_id)

    record = CopayEPARecord(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        pa_request_id=pa.id,
        manufacturer_program_id=manufacturer_program_id,
        first_fill_amount=money(first_fill_amount),
        first_fill_date=first_fill_date,
        pa_outcome=pa.status,
        manufacturer_absorbed_cost=ZERO,
    )
    db.add(record)
    db.flush()

    logger.info(
        "Copay ePA first-fill record created",
        extra={
            "pa_request_id": str(pa.id),
            "pa_copay_program": manufacturer_program_id,
            "pa_first_fill_amount": str(money(first_fill_amount)),
        },
    )
    return record


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_pa(db: Session, pa_request_id: uuid.UUID, tenant_id: uuid.UUID) -> PARequest:
    """Fetch a PA request or raise PALifecycleError."""
    pa = db.execute(
        select(PARequest).where(
            PARequest.id == pa_request_id,
            PARequest.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()

    if pa is None:
        raise PALifecycleError(f"PA request {pa_request_id} not found for tenant {tenant_id}")
    return pa


def _find_criteria_version(
    db: Session,
    tenant_id: uuid.UUID,
    drug_ndc: str,
    plan_id: uuid.UUID,
) -> int | None:
    """Find the latest criteria set version for a drug+plan combination."""
    cs = db.execute(
        select(PACriteriaSet).where(
            PACriteriaSet.tenant_id == tenant_id,
            PACriteriaSet.drug_ndc == drug_ndc,
            (PACriteriaSet.plan_id == plan_id) | (PACriteriaSet.plan_id.is_(None)),
        ).order_by(PACriteriaSet.version.desc())
    ).scalar_one_or_none()

    return cs.version if cs is not None else None


def _find_criteria_set(
    db: Session,
    tenant_id: uuid.UUID,
    drug_ndc: str,
    plan_id: uuid.UUID,
    version: int | None,
) -> PACriteriaSet | None:
    """Find a criteria set, preferring plan-specific over global.

    If version is specified, returns that exact version (criteria locked at
    submission time). Otherwise returns the latest.
    """
    query = select(PACriteriaSet).where(
        PACriteriaSet.tenant_id == tenant_id,
        PACriteriaSet.drug_ndc == drug_ndc,
        (PACriteriaSet.plan_id == plan_id) | (PACriteriaSet.plan_id.is_(None)),
    )

    if version is not None:
        query = query.where(PACriteriaSet.version == version)

    query = query.order_by(
        PACriteriaSet.plan_id.isnot(None).desc(),  # plan-specific first
        PACriteriaSet.version.desc(),
    )

    return db.execute(query).scalar_one_or_none()
