"""SLA monitoring for EDI submission turnaround and acknowledgment tracking.

Tracks:
  - Submission-to-acknowledgment elapsed time
  - Per-partner SLA compliance
  - Breach detection and alert generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class SlaStatus(str, Enum):
    WITHIN_SLA = "within_sla"
    AT_RISK = "at_risk"          # >75% of SLA window consumed
    BREACHED = "breached"
    ACKNOWLEDGED = "acknowledged"


class TransactionDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


@dataclass
class SlaConfig:
    """SLA window configuration for a trading partner."""
    trading_partner_id: str
    acknowledgment_sla_minutes: int = 60      # 999/TA1 expected within N minutes
    response_sla_minutes: int = 1440          # 271/277/278 response within N minutes
    at_risk_threshold_pct: float = 0.75       # fraction of SLA window before "at_risk"


@dataclass
class SubmissionEvent:
    submission_id: str
    trading_partner_id: str
    transaction_type: str          # 837, 270, 276, 278, etc.
    direction: TransactionDirection
    submitted_at: datetime
    acknowledged_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    status: SlaStatus = SlaStatus.WITHIN_SLA
    control_number: str = ""


@dataclass
class SlaBreachEvent:
    submission_id: str
    trading_partner_id: str
    transaction_type: str
    sla_type: str          # "acknowledgment" | "response"
    submitted_at: datetime
    sla_deadline: datetime
    elapsed_minutes: float
    sla_minutes: int


@dataclass
class PartnerSlaReport:
    trading_partner_id: str
    period_start: str
    period_end: str
    total_submissions: int
    acknowledged_within_sla: int
    responded_within_sla: int
    breaches: List[SlaBreachEvent] = field(default_factory=list)
    acknowledgment_compliance_pct: float = 0.0
    response_compliance_pct: float = 0.0


def compute_elapsed_minutes(start: datetime, end: datetime) -> float:
    """Return elapsed time in minutes between two UTC datetimes."""
    delta = end - start
    return delta.total_seconds() / 60.0


def evaluate_submission_status(
    event: SubmissionEvent,
    sla_config: SlaConfig,
    now: Optional[datetime] = None,
) -> SlaStatus:
    """Compute current SLA status for a submission."""
    if now is None:
        now = datetime.now(timezone.utc)

    if event.acknowledged_at is not None:
        elapsed = compute_elapsed_minutes(event.submitted_at, event.acknowledged_at)
        if elapsed <= sla_config.acknowledgment_sla_minutes:
            return SlaStatus.ACKNOWLEDGED
        return SlaStatus.BREACHED

    elapsed = compute_elapsed_minutes(event.submitted_at, now)
    sla_minutes = sla_config.acknowledgment_sla_minutes

    if elapsed > sla_minutes:
        return SlaStatus.BREACHED

    at_risk_minutes = sla_minutes * sla_config.at_risk_threshold_pct
    if elapsed >= at_risk_minutes:
        return SlaStatus.AT_RISK

    return SlaStatus.WITHIN_SLA


def detect_breaches(
    events: List[SubmissionEvent],
    configs: Dict[str, SlaConfig],
    now: Optional[datetime] = None,
) -> List[SlaBreachEvent]:
    """Scan submission events and return all SLA breaches."""
    if now is None:
        now = datetime.now(timezone.utc)

    breaches: List[SlaBreachEvent] = []
    default_config = SlaConfig(trading_partner_id="default")

    for event in events:
        cfg = configs.get(event.trading_partner_id, default_config)

        ack_elapsed = compute_elapsed_minutes(event.submitted_at, event.acknowledged_at or now)
        if ack_elapsed > cfg.acknowledgment_sla_minutes and event.acknowledged_at is None:
            from datetime import timedelta
            deadline = event.submitted_at + timedelta(minutes=cfg.acknowledgment_sla_minutes)
            breaches.append(SlaBreachEvent(
                submission_id=event.submission_id,
                trading_partner_id=event.trading_partner_id,
                transaction_type=event.transaction_type,
                sla_type="acknowledgment",
                submitted_at=event.submitted_at,
                sla_deadline=deadline,
                elapsed_minutes=ack_elapsed,
                sla_minutes=cfg.acknowledgment_sla_minutes,
            ))

    return breaches


def build_partner_sla_report(
    partner_id: str,
    events: List[SubmissionEvent],
    sla_config: SlaConfig,
    period_start: datetime,
    period_end: datetime,
) -> PartnerSlaReport:
    """Build a compliance report for a single trading partner over a time window."""
    in_period = [
        e for e in events
        if e.trading_partner_id == partner_id
        and period_start <= e.submitted_at <= period_end
    ]

    total = len(in_period)
    ack_within = 0
    resp_within = 0
    breaches: List[SlaBreachEvent] = []

    for event in in_period:
        if event.acknowledged_at is not None:
            elapsed = compute_elapsed_minutes(event.submitted_at, event.acknowledged_at)
            if elapsed <= sla_config.acknowledgment_sla_minutes:
                ack_within += 1
            else:
                from datetime import timedelta
                deadline = event.submitted_at + timedelta(minutes=sla_config.acknowledgment_sla_minutes)
                breaches.append(SlaBreachEvent(
                    submission_id=event.submission_id,
                    trading_partner_id=partner_id,
                    transaction_type=event.transaction_type,
                    sla_type="acknowledgment",
                    submitted_at=event.submitted_at,
                    sla_deadline=deadline,
                    elapsed_minutes=elapsed,
                    sla_minutes=sla_config.acknowledgment_sla_minutes,
                ))

        if event.responded_at is not None:
            elapsed = compute_elapsed_minutes(event.submitted_at, event.responded_at)
            if elapsed <= sla_config.response_sla_minutes:
                resp_within += 1

    ack_pct = (ack_within / total * 100.0) if total > 0 else 0.0
    resp_denominator = sum(1 for e in in_period if e.responded_at is not None)
    resp_pct = (resp_within / resp_denominator * 100.0) if resp_denominator > 0 else 0.0

    return PartnerSlaReport(
        trading_partner_id=partner_id,
        period_start=period_start.strftime("%Y%m%dT%H%M%SZ"),
        period_end=period_end.strftime("%Y%m%dT%H%M%SZ"),
        total_submissions=total,
        acknowledged_within_sla=ack_within,
        responded_within_sla=resp_within,
        breaches=breaches,
        acknowledgment_compliance_pct=round(ack_pct, 2),
        response_compliance_pct=round(resp_pct, 2),
    )


def record_acknowledgment(
    event: SubmissionEvent,
    ack_time: datetime,
    sla_config: SlaConfig,
) -> SubmissionEvent:
    """Record acknowledgment receipt and update event status."""
    event.acknowledged_at = ack_time
    elapsed = compute_elapsed_minutes(event.submitted_at, ack_time)
    if elapsed <= sla_config.acknowledgment_sla_minutes:
        event.status = SlaStatus.ACKNOWLEDGED
    else:
        event.status = SlaStatus.BREACHED
    return event


def summarize_sla_dashboard(
    events: List[SubmissionEvent],
    configs: Dict[str, SlaConfig],
    now: Optional[datetime] = None,
) -> Dict[str, object]:
    """Return a high-level SLA dashboard summary across all partners."""
    if now is None:
        now = datetime.now(timezone.utc)

    total = len(events)
    within = 0
    at_risk = 0
    breached = 0
    acknowledged = 0
    default_cfg = SlaConfig(trading_partner_id="default")

    for event in events:
        cfg = configs.get(event.trading_partner_id, default_cfg)
        status = evaluate_submission_status(event, cfg, now)
        event.status = status
        if status == SlaStatus.WITHIN_SLA:
            within += 1
        elif status == SlaStatus.AT_RISK:
            at_risk += 1
        elif status == SlaStatus.BREACHED:
            breached += 1
        elif status == SlaStatus.ACKNOWLEDGED:
            acknowledged += 1

    return {
        "as_of": now.strftime("%Y%m%dT%H%M%SZ"),
        "total_submissions": total,
        "within_sla": within,
        "at_risk": at_risk,
        "breached": breached,
        "acknowledged": acknowledged,
        "breach_rate_pct": round(breached / total * 100.0, 2) if total > 0 else 0.0,
    }
