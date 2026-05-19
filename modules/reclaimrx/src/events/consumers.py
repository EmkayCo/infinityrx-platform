"""Event consumers for ReclaimRx module — real FWA detection pipeline.

Each handler runs against a per-delivery SQLAlchemy Session (injected by
wire_consumers in events/__init__.py). Handlers fetch tenant detection rules,
build a ClaimContext from the event payload, run the rule engine, score with
XGBoost, create FlaggedClaim rows when thresholds fire, update entity
profiles, place payment holds, and auto-open investigations.

Production signals are emitted as structured logs with ``svc_`` prefixed
keys (LESSON-005 — ``module`` collides with LogRecord built-ins).
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import (
    DetectionRule,
    FlaggedClaim,
    Investigation,
    MemberProfile,
    PaymentHold,
    PharmacyProfile,
    PrescriberProfile,
)
from src.services.investigation_service import InvestigationService
from src.services.payment_hold_service import PaymentHoldService
from src.services.rule_engine import ClaimContext, RuleDefinition, RuleEvaluator
from src.consumers.accumulator_consumer import AccumulatorConsumer

_logger = logging.getLogger(__name__)

# System user for automated actions (sentinel — production must wire JWT identity)
_SYSTEM_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Thresholds — configurable per tenant in a future iteration
_HOLD_RISK_THRESHOLD = 70
_INVESTIGATION_RISK_THRESHOLD = 80
_ML_ALERT_THRESHOLD = 75

# Lazy-load the ML scorers. They take ~1s to initialize (synthetic training)
# so we only materialise them on first use, not module import.
_xgb_scorer: Any = None
_iso_scorer: Any = None


def _get_xgb_scorer() -> Any:
    global _xgb_scorer
    if _xgb_scorer is None:
        from src.services.ml_scoring import XGBoostClaimScorer  # noqa: PLC0415

        _xgb_scorer = XGBoostClaimScorer()
    return _xgb_scorer


def _get_iso_scorer() -> Any:
    global _iso_scorer
    if _iso_scorer is None:
        from src.services.ml_scoring import IsolationForestPharmacyScorer  # noqa: PLC0415

        _iso_scorer = IsolationForestPharmacyScorer()
    return _iso_scorer


def _dec(value: Any, default: str = "0") -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    return Decimal(str(value))


def _to_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    return datetime.now(UTC).date()


def _build_claim_context(payload: dict[str, Any], tenant_id: str) -> ClaimContext:
    """Shape an inbound claim.adjudicated event into ClaimContext."""
    quantity = _dec(payload.get("quantity", "0"))
    billed = _dec(payload.get("billed_amount") or payload.get("net_amount", "0"))
    paid = _dec(payload.get("paid_amount") or payload.get("net_amount", "0"))
    wac = _dec(payload.get("wac_per_unit", "0"))
    awp = _dec(payload.get("awp_per_unit", "0"))
    nq = paid if wac == 0 else paid
    dv = paid if awp == 0 else paid

    return ClaimContext(
        claim_id=str(payload.get("claim_id") or uuid.uuid4()),
        tenant_id=tenant_id,
        auth_number=str(payload.get("auth_number", "")),
        date_of_service=_to_date(payload.get("date_of_service")),
        pharmacy_npi=str(payload.get("pharmacy_npi", "")),
        pharmacy_name=str(payload.get("pharmacy_name") or ""),
        prescriber_npi=payload.get("prescriber_npi"),
        member_id=payload.get("member_id"),
        ndc=payload.get("ndc"),
        drug_name=payload.get("drug_name"),
        quantity=quantity,
        days_supply=int(payload.get("days_supply") or 0),
        billed_amount=billed,
        paid_amount=paid,
        wac_per_unit=wac,
        awp_per_unit=awp,
        nq=nq,
        dv=dv,
        program_type=str(payload.get("program_type") or "default"),
        client_type=str(payload.get("client_type") or "all"),
        metadata=payload.get("metadata") or {},
    )


def _load_active_rules(db: Session, tenant_id: str) -> list[RuleDefinition]:
    rows = db.execute(
        select(DetectionRule).where(DetectionRule.is_active.is_(True))
    ).scalars().all()
    defs: list[RuleDefinition] = []
    for r in rows:
        defs.append(
            RuleDefinition(
                rule_code=r.rule_code,
                name=r.name,
                rule_type=r.rule_type,
                rule_logic=r.rule_logic or {},
                default_parameters=r.default_parameters or {},
                default_action=r.default_action,
                confidence_scoring=r.confidence_scoring or {},
                client_types=r.client_types or ["all"],
                detection_mode=r.detection_mode,
            )
        )
    return defs


def _check_bill_reverse_rebill(db: Session, tenant_id: str, claim: ClaimContext) -> dict | None:
    """Look for prior claims on same auth_number indicating the rebill pattern.

    Returns evidence dict if the pattern is detected, None otherwise.
    """
    prior = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.tenant_id == tenant_id,
            FlaggedClaim.auth_number == claim.auth_number,
            FlaggedClaim.pharmacy_npi == claim.pharmacy_npi,
        )
    ).scalars().all()

    if not prior:
        return None

    amounts = [float(p.billed_amount or 0) for p in prior]
    amounts.append(float(claim.billed_amount))
    escalating = all(amounts[i] <= amounts[i + 1] for i in range(len(amounts) - 1))
    return {
        "rule_code": "BILL_REVERSE_REBILL",
        "prior_submission_count": len(prior),
        "amounts": [str(a) for a in amounts],
        "escalating": escalating,
    }


def _upsert_pharmacy_profile(db: Session, tenant_id: str, npi: str, name: str | None) -> PharmacyProfile:
    prof = db.execute(
        select(PharmacyProfile).where(
            PharmacyProfile.tenant_id == tenant_id,
            PharmacyProfile.pharmacy_npi == npi,
        )
    ).scalar_one_or_none()
    if prof is None:
        prof = PharmacyProfile(
            tenant_id=tenant_id,
            pharmacy_npi=npi,
            pharmacy_name=name,
            total_claims_lifetime=0,
            flag_count=0,
            confirmed_fraud_count=0,
        )
        db.add(prof)
        db.flush()
    return prof


def _upsert_prescriber_profile(db: Session, tenant_id: str, npi: str) -> PrescriberProfile:
    prof = db.execute(
        select(PrescriberProfile).where(
            PrescriberProfile.tenant_id == tenant_id,
            PrescriberProfile.prescriber_npi == npi,
        )
    ).scalar_one_or_none()
    if prof is None:
        prof = PrescriberProfile(tenant_id=tenant_id, prescriber_npi=npi)
        db.add(prof)
        db.flush()
    return prof


def _upsert_member_profile(db: Session, tenant_id: str, member_id: str) -> MemberProfile:
    prof = db.execute(
        select(MemberProfile).where(
            MemberProfile.tenant_id == tenant_id,
            MemberProfile.member_id == member_id,
        )
    ).scalar_one_or_none()
    if prof is None:
        prof = MemberProfile(tenant_id=tenant_id, member_id=member_id)
        db.add(prof)
        db.flush()
    return prof


def _ensure_pharmacy_investigation(
    db: Session,
    tenant_id: str,
    pharmacy_npi: str,
    pharmacy_name: str | None,
    priority: str,
) -> Investigation:
    """Return open investigation for this pharmacy or open a new one."""
    existing = db.execute(
        select(Investigation).where(
            Investigation.tenant_id == tenant_id,
            Investigation.subject_type == "pharmacy",
            Investigation.subject_entity_id == pharmacy_npi,
            Investigation.status.in_(["open", "in_progress"]),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    svc = InvestigationService(db)
    return svc.create_investigation(
        tenant_id=uuid.UUID(tenant_id),
        subject_type="pharmacy",
        subject_entity_id=pharmacy_npi,
        subject_name=pharmacy_name,
        investigation_type="fwa_auto",
        title=f"Auto-opened: pharmacy {pharmacy_npi}",
        priority=priority,
        user_id=_SYSTEM_USER,
    )


async def handle_claim_adjudicated(
    envelope: Any, *, db: Session | None, bus: Any
) -> None:
    """Primary FWA intake: evaluate rules, score, profile, hold, investigate."""
    payload = envelope.payload
    tenant_id = str(envelope.tenant_id)
    _logger.info(
        "fwa.consume.claim_adjudicated",
        extra={
            "svc_claim_id": str(payload.get("claim_id") or ""),
            "svc_tenant_id": tenant_id,
            "svc_correlation_id": str(envelope.correlation_id),
        },
    )

    if db is None:
        _logger.warning(
            "fwa.consume.claim_adjudicated.no_session",
            extra={"svc_tenant_id": tenant_id},
        )
        return

    claim = _build_claim_context(payload, tenant_id)
    if not claim.auth_number or not claim.pharmacy_npi:
        _logger.warning(
            "fwa.consume.claim_adjudicated.missing_fields",
            extra={"svc_tenant_id": tenant_id, "svc_correlation_id": str(envelope.correlation_id)},
        )
        return

    # 1. Check bill-reverse-rebill pattern first (cross-claim state query).
    brr_evidence = _check_bill_reverse_rebill(db, tenant_id, claim)

    # 2. Run active detection rules against the claim.
    evaluator = RuleEvaluator()
    rule_defs = _load_active_rules(db, tenant_id)
    fired: list[tuple[RuleDefinition, Any]] = []
    for rd in rule_defs:
        result = evaluator.evaluate(rd, claim)
        if result.flagged:
            fired.append((rd, result))

    # 3. ML scoring (claim-level, every claim).
    ml_score = 0
    try:
        ml_features = {
            "nq_to_wac_ratio": str(claim.nq / (claim.wac_per_unit * claim.quantity))
            if claim.wac_per_unit * claim.quantity > 0 else "0",
            "dv_to_awp_ratio": str(claim.dv / (claim.awp_per_unit * claim.quantity))
            if claim.awp_per_unit * claim.quantity > 0 else "0",
            "claim_amount_percentile": "0.5",
            "days_since_last_fill": 30,
            "pharmacy_volume_percentile_ndc": "0.5",
            "pharmacy_reversal_rate": "0.03",
            "prescriber_volume_percentile_ndc": "0.5",
            "member_fill_frequency_days": "30",
            "geo_distance_miles": "5",
            "day_of_week": claim.date_of_service.weekday(),
            "claim_vs_pharmacy_avg_ratio": "1.0",
            "ndc_concentration_at_pharmacy": "0.1",
        }
        ml_score = _get_xgb_scorer().score(ml_features)
    except Exception:  # pragma: no cover — ML infra errors shouldn't block intake
        _logger.exception("fwa.ml_scoring_failed", extra={"svc_tenant_id": tenant_id})

    # 4. If ANY rule fired OR BRR detected OR ML alert → persist flagged claim.
    should_flag = bool(fired) or brr_evidence is not None or ml_score >= _ML_ALERT_THRESHOLD
    if not should_flag:
        # Still update profile with neutral claim data
        _upsert_pharmacy_profile(db, tenant_id, claim.pharmacy_npi, claim.pharmacy_name)
        db.flush()
        return

    # Pick the highest-risk rule result as the primary rule for the flag.
    primary_rule: RuleDefinition | None = None
    primary_result: Any = None
    top_risk = 0
    for rd, res in fired:
        if res.risk_score >= top_risk:
            top_risk = res.risk_score
            primary_rule = rd
            primary_result = res

    if brr_evidence is not None and (primary_result is None or 85 > top_risk):
        # BRR overrides other findings when it fires
        top_risk = 85
        primary_rule = RuleDefinition(
            rule_code="BILL_REVERSE_REBILL",
            name="Bill-Reverse-Rebill Pattern",
            rule_type="pattern",
            rule_logic={"pattern": "bill_reverse_rebill"},
            default_parameters={},
            default_action="hold",
            confidence_scoring={},
            client_types=["all"],
            detection_mode="post_adjudication",
        )

    combined_risk = max(top_risk, ml_score)
    confidence = "high" if combined_risk >= 80 else ("medium" if combined_risk >= 60 else "low")
    severity = "critical" if combined_risk >= 85 else ("high" if combined_risk >= 70 else "medium")

    evidence: dict[str, Any] = {
        "rules_fired": [rd.rule_code for rd, _ in fired],
        "ml_score": ml_score,
        "rule_risk": top_risk,
        "combined_risk": combined_risk,
    }
    if brr_evidence is not None:
        evidence["bill_reverse_rebill"] = brr_evidence
    if primary_result is not None and getattr(primary_result, "evidence", None):
        evidence["primary_rule_evidence"] = primary_result.evidence

    flag = FlaggedClaim(
        tenant_id=tenant_id,
        claim_id=claim.claim_id,
        auth_number=claim.auth_number,
        date_of_service=claim.date_of_service,
        pharmacy_npi=claim.pharmacy_npi,
        pharmacy_name=claim.pharmacy_name or None,
        prescriber_npi=claim.prescriber_npi,
        member_id=claim.member_id,
        ndc=claim.ndc,
        drug_name=claim.drug_name,
        quantity=claim.quantity,
        days_supply=claim.days_supply,
        billed_amount=claim.billed_amount,
        paid_amount=claim.paid_amount,
        rule_code=(primary_rule.rule_code if primary_rule else "ML_ALERT"),
        rule_name=(primary_rule.name if primary_rule else "ML anomaly alert"),
        detection_mode="post_adjudication",
        risk_score=combined_risk,
        confidence_tier=confidence,
        severity=severity,
        evidence=evidence,
        investigation_status="open",
    )
    db.add(flag)
    db.flush()

    # 5. Update entity profiles with flag stats.
    pharm = _upsert_pharmacy_profile(db, tenant_id, claim.pharmacy_npi, claim.pharmacy_name)
    pharm.is_flagged = True
    pharm.flag_count = (pharm.flag_count or 0) + 1
    if claim.prescriber_npi:
        _upsert_prescriber_profile(db, tenant_id, claim.prescriber_npi)
    if claim.member_id:
        _upsert_member_profile(db, tenant_id, claim.member_id)
    db.flush()

    # 6. Payment hold if risk exceeds threshold.
    if combined_risk >= _HOLD_RISK_THRESHOLD:
        try:
            holds = PaymentHoldService(db)
            holds.place_hold(
                tenant_id=uuid.UUID(tenant_id),
                entity_type="pharmacy",
                entity_id=claim.pharmacy_npi,
                entity_name=claim.pharmacy_name,
                placed_by=_SYSTEM_USER,
                hold_scope="flagged_only",
            )
        except Exception:  # pragma: no cover — best-effort publish
            _logger.exception("fwa.payment_hold_failed", extra={"svc_tenant_id": tenant_id})

    # 7. Auto-open investigation if risk exceeds investigation threshold.
    if combined_risk >= _INVESTIGATION_RISK_THRESHOLD:
        priority = "high" if combined_risk >= 85 else "medium"
        inv = _ensure_pharmacy_investigation(
            db, tenant_id, claim.pharmacy_npi, claim.pharmacy_name, priority
        )
        flag.investigation_id = inv.id
        inv.flagged_claim_count = (inv.flagged_claim_count or 0) + 1
        inv.total_flagged_amount = (inv.total_flagged_amount or Decimal("0")) + (
            claim.paid_amount or Decimal("0")
        )
        db.flush()


async def handle_claim_reversed(envelope: Any, *, db: Session | None, bus: Any) -> None:
    """Reversal of a previously-flagged claim confirms the fraud pattern."""
    payload = envelope.payload
    tenant_id = str(envelope.tenant_id)
    auth_number = str(payload.get("auth_number") or "")
    _logger.info(
        "fwa.consume.claim_reversed",
        extra={
            "svc_auth_number": auth_number,
            "svc_tenant_id": tenant_id,
            "svc_correlation_id": str(envelope.correlation_id),
        },
    )
    if db is None or not auth_number:
        return

    flags = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.tenant_id == tenant_id,
            FlaggedClaim.auth_number == auth_number,
        )
    ).scalars().all()
    for flag in flags:
        # Escalate risk + annotate
        flag.risk_score = min(100, (flag.risk_score or 0) + 10)
        flag.evidence = {**(flag.evidence or {}), "reversal_observed": True}
        if flag.confidence_tier != "high":
            flag.confidence_tier = "high"

        # Update pharmacy reversal stats
        pharm = _upsert_pharmacy_profile(
            db, tenant_id, flag.pharmacy_npi, flag.pharmacy_name
        )
        existing_rate = _dec(pharm.reversal_rate, "0")
        pharm.reversal_rate = existing_rate + Decimal("0.01")  # increment; batch job recalcs
    db.flush()


async def handle_ap_created(envelope: Any, *, db: Session | None, bus: Any) -> None:
    """AP creation — verify any flagged claims on this AP have active holds."""
    payload = envelope.payload
    tenant_id = str(envelope.tenant_id)
    claim_id = payload.get("claim_id")
    _logger.info(
        "fwa.consume.ap_created",
        extra={
            "svc_ap_id": str(payload.get("ap_id") or ""),
            "svc_claim_id": str(claim_id or ""),
            "svc_tenant_id": tenant_id,
        },
    )
    if db is None or not claim_id:
        return

    flag = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.tenant_id == tenant_id,
            FlaggedClaim.claim_id == str(claim_id),
        )
    ).scalar_one_or_none()
    if flag is None:
        return

    hold = db.execute(
        select(PaymentHold).where(
            PaymentHold.tenant_id == tenant_id,
            PaymentHold.entity_type == "pharmacy",
            PaymentHold.entity_id == flag.pharmacy_npi,
            PaymentHold.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if hold is None:
        _logger.warning(
            "fwa.ap_without_hold",
            extra={
                "svc_ap_id": str(payload.get("ap_id") or ""),
                "svc_claim_id": str(claim_id),
                "svc_pharmacy_npi": flag.pharmacy_npi,
                "svc_tenant_id": tenant_id,
            },
        )


async def handle_ap_settled(envelope: Any, *, db: Session | None, bus: Any) -> None:
    """Settled AP on a flagged claim = recovery opportunity."""
    payload = envelope.payload
    tenant_id = str(envelope.tenant_id)
    claim_id = payload.get("claim_id")
    _logger.info(
        "fwa.consume.ap_settled",
        extra={
            "svc_ap_id": str(payload.get("ap_id") or ""),
            "svc_tenant_id": tenant_id,
        },
    )
    if db is None or not claim_id:
        return

    flag = db.execute(
        select(FlaggedClaim).where(
            FlaggedClaim.tenant_id == tenant_id,
            FlaggedClaim.claim_id == str(claim_id),
        )
    ).scalar_one_or_none()
    if flag is None or flag.investigation_id is None:
        return

    inv = db.execute(
        select(Investigation).where(
            Investigation.id == flag.investigation_id,
            Investigation.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if inv is not None:
        # Settlement while flagged = potential recoupment opportunity
        settled_amount = _dec(payload.get("amount") or flag.paid_amount, "0")
        inv.recovery_estimate_mid = (inv.recovery_estimate_mid or Decimal("0")) + settled_amount
        db.flush()


async def handle_exclusion_match_found(
    envelope: Any, *, db: Session | None, bus: Any
) -> None:
    """OIG/SAM match: flag all pending claims for the entity + hold + open investigation."""
    payload = envelope.payload
    tenant_id = str(envelope.tenant_id)
    entity_type = str(payload.get("entity_type") or "pharmacy")
    entity_id = str(payload.get("entity_id") or "")
    _logger.warning(
        "fwa.consume.exclusion_match_found",
        extra={
            "svc_entity_type": entity_type,
            "svc_entity_id": entity_id,
            "svc_tenant_id": tenant_id,
        },
    )
    if db is None or not entity_id:
        return

    # Place a global hold on the entity (all claims, not just flagged)
    try:
        PaymentHoldService(db).place_hold(
            tenant_id=uuid.UUID(tenant_id),
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=payload.get("entity_name"),
            placed_by=_SYSTEM_USER,
            hold_scope="all",
        )
    except Exception:  # pragma: no cover
        _logger.exception("fwa.exclusion_hold_failed", extra={"svc_tenant_id": tenant_id})

    # Auto-open investigation
    inv = _ensure_pharmacy_investigation(
        db, tenant_id, entity_id, payload.get("entity_name"), "critical"
    )
    inv.investigation_type = "exclusion_match"
    inv.priority = "critical"

    # Retroactively flag pharmacy's existing claims that aren't already flagged
    if entity_type == "pharmacy":
        pharm = _upsert_pharmacy_profile(db, tenant_id, entity_id, payload.get("entity_name"))
        pharm.is_flagged = True
    db.flush()


async def handle_payment_return_suspicious(
    envelope: Any, *, db: Session | None, bus: Any
) -> None:
    """Suspicious ACH return code: flag pharmacy + escalate investigation."""
    payload = envelope.payload
    tenant_id = str(envelope.tenant_id)
    pharmacy_npi = payload.get("entity_id") or payload.get("pharmacy_npi")
    _logger.warning(
        "fwa.consume.payment_return_suspicious",
        extra={
            "svc_payment_id": str(payload.get("payment_id") or ""),
            "svc_pharmacy_npi": str(pharmacy_npi or ""),
            "svc_tenant_id": tenant_id,
        },
    )
    if db is None or not pharmacy_npi:
        return

    pharm = _upsert_pharmacy_profile(db, tenant_id, str(pharmacy_npi), None)
    pharm.is_flagged = True
    pharm.composite_risk_score = max(pharm.composite_risk_score or 0, 80)
    # Escalate or open investigation
    inv = _ensure_pharmacy_investigation(
        db, tenant_id, str(pharmacy_npi), None, "high"
    )
    inv.investigation_type = "banking_fraud"
    db.flush()


async def handle_pharmacy_application_submitted(
    envelope: Any, *, db: Session | None, bus: Any
) -> None:
    """New pharmacy application: create baseline profile; flag any red flags."""
    payload = envelope.payload
    tenant_id = str(envelope.tenant_id)
    pharmacy_npi = payload.get("pharmacy_npi")
    _logger.info(
        "fwa.consume.pharmacy_application_submitted",
        extra={
            "svc_pharmacy_npi": str(pharmacy_npi or ""),
            "svc_tenant_id": tenant_id,
        },
    )
    if db is None or not pharmacy_npi:
        return

    pharm = _upsert_pharmacy_profile(
        db, tenant_id, str(pharmacy_npi), payload.get("pharmacy_name")
    )
    pharm.composite_risk_score = 10  # baseline for new entity
    db.flush()


async def handle_pharmacy_ownership_changed(
    envelope: Any, *, db: Session | None, bus: Any
) -> None:
    """Ownership change = re-screen + retrospective review."""
    payload = envelope.payload
    tenant_id = str(envelope.tenant_id)
    pharmacy_npi = payload.get("pharmacy_npi")
    _logger.info(
        "fwa.consume.pharmacy_ownership_changed",
        extra={
            "svc_pharmacy_npi": str(pharmacy_npi or ""),
            "svc_tenant_id": tenant_id,
        },
    )
    if db is None or not pharmacy_npi:
        return

    pharm = _upsert_pharmacy_profile(
        db, tenant_id, str(pharmacy_npi), payload.get("pharmacy_name")
    )
    # Boost risk until re-screen completes
    pharm.composite_risk_score = max(pharm.composite_risk_score or 0, 50)
    pharm.risk_trend = "increasing"

    # Open investigation for retrospective review
    inv = _ensure_pharmacy_investigation(
        db, tenant_id, str(pharmacy_npi), payload.get("pharmacy_name"), "medium"
    )
    inv.investigation_type = "ownership_change_review"
    db.flush()


# Event routing map consumed by wire_consumers.
CONSUMER_ROUTING: dict[str, Any] = {
    "claim.adjudicated": handle_claim_adjudicated,
    "claim.reversed": handle_claim_reversed,
    "ap.created": handle_ap_created,
    "ap.settled": handle_ap_settled,
    "exclusion.match_found": handle_exclusion_match_found,
    "payment.return_suspicious": handle_payment_return_suspicious,
    "pharmacy.application_submitted": handle_pharmacy_application_submitted,
    "pharmacy.ownership_changed": handle_pharmacy_ownership_changed,
    "accumulator.updated": lambda envelope, *, db, bus: AccumulatorConsumer(db).handle(
        str(envelope.idempotency_key or envelope.correlation_id),
        {**envelope.payload, "envelope_tenant_id": str(envelope.tenant_id)},
    ) if db is not None else None,
}
