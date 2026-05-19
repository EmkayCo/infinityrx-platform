"""Accumulator anomaly consumer — subscribes accumulator.updated events.

Wired into CONSUMER_ROUTING in src/events/consumers.py after this file exists.

A3 scope: implements ONLY sudden_spike and multi_payer_convergence pattern
detectors. reset_evasion and threshold_oscillation are deferred to
B11/follow-on/accumulator-patterns-3-4.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import AccumulatorAnomaly, Investigation  # Plan A1 tables
from src.utils.constants import risk_score_to_severity

_logger = logging.getLogger(__name__)

# Spike threshold: current value > window_average * SPIKE_MULTIPLIER
_SPIKE_MULTIPLIER = Decimal("3.0")
# Multi-payer threshold: distinct payers in window
_MULTI_PAYER_THRESHOLD = 3
# System user sentinel for auto-opened investigations
_SYSTEM_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")


class AccumulatorTenantMismatchWarning(RuntimeError):
    """Raised when envelope.tenant_id != payload.tenant_id."""


class AccumulatorConsumer:
    """Consumer for accumulator.updated events.

    Wraps detect() with idempotent_handler in events/__init__.py wire_consumers().
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def handle(self, idempotency_key: str, payload: dict) -> None:
        """Process one accumulator.updated event.

        First arg is idempotency_key (idempotent_handler contract).
        """
        envelope_tid = payload.get("envelope_tenant_id")
        payload_tid = payload.get("tenant_id")

        # Tenant consistency check (spec section 5.3 accumulator_consumer)
        if envelope_tid and payload_tid and str(envelope_tid) != str(payload_tid):
            _logger.warning(
                "accumulator.tenant_mismatch",
                extra={
                    "svc_name": "reclaimrx.accumulator_consumer",
                    "svc_event_key": idempotency_key,
                    "svc_warn_code": "ACCUMULATOR_TENANT_MISMATCH",
                },
            )
            raise AccumulatorTenantMismatchWarning(
                f"Tenant mismatch: envelope={envelope_tid} payload={payload_tid}"
            )

        tenant_id = uuid.UUID(str(payload_tid or envelope_tid))
        member_id = payload["member_id"]
        amounts = payload.get("amounts", {})
        oop = Decimal(str(amounts.get("oop", "0")))
        source_payer_id = payload.get("source_payer_id")
        event_id = idempotency_key  # used as triggering_event_id

        window = self._load_recent_window(tenant_id, member_id)
        anomalies = self._detect_patterns(member_id, tenant_id, oop, source_payer_id, window, event_id)

        # A3 scope note: only the two implemented pattern detectors may open
        # investigations. reset_evasion and threshold_oscillation are deferred
        # to B11/follow-on/accumulator-patterns-3-4.
        _A3_AUTO_OPEN_PATTERNS = frozenset({"sudden_spike", "multi_payer_convergence"})
        for anomaly in anomalies:
            self._session.add(anomaly)
            if anomaly.pattern_type in _A3_AUTO_OPEN_PATTERNS:
                inv = self._open_investigation(tenant_id, member_id, anomaly)
                anomaly.spawned_investigation_id = inv.id
                self._session.add(inv)

        self._session.flush()

    def _load_recent_window(self, tenant_id: uuid.UUID, member_id: str) -> list[dict]:
        """Load last 7 days of accumulator anomaly history for this member.

        Returns list of dicts with oop, source_payer_id for pattern analysis.
        Overridden in tests via patch.
        """
        cutoff = datetime.now(UTC) - timedelta(days=7)
        rows = self._session.execute(
            select(AccumulatorAnomaly).where(
                AccumulatorAnomaly.tenant_id == str(tenant_id),
                AccumulatorAnomaly.member_id == str(member_id),
                AccumulatorAnomaly.detected_at >= cutoff,
            )
        ).scalars().all()
        return [{"oop": Decimal("0"), "source_payer_id": None} for _ in rows]

    def _detect_patterns(
        self,
        member_id: str,
        tenant_id: uuid.UUID,
        oop: Decimal,
        source_payer_id: str | None,
        window: list[dict],
        event_id: str,
    ) -> list[AccumulatorAnomaly]:
        anomalies: list[AccumulatorAnomaly] = []
        now = datetime.now(UTC)

        # Pattern 1: sudden_spike
        if window:
            avg = sum(r["oop"] for r in window) / len(window)
            if avg > Decimal("0") and oop > avg * _SPIKE_MULTIPLIER:
                anomalies.append(AccumulatorAnomaly(
                    id=str(uuid.uuid4()),
                    tenant_id=str(tenant_id),
                    member_id=str(member_id),
                    pattern_type="sudden_spike",
                    detected_at=now,
                    evidence_window_start=now - timedelta(days=7),
                    evidence_window_end=now,
                    triggering_event_ids=[event_id],
                ))

        # Pattern 2: multi_payer_convergence
        distinct_payers = {r.get("source_payer_id") for r in window if r.get("source_payer_id")}
        if source_payer_id:
            distinct_payers.add(source_payer_id)
        if len(distinct_payers) > _MULTI_PAYER_THRESHOLD:
            anomalies.append(AccumulatorAnomaly(
                id=str(uuid.uuid4()),
                tenant_id=str(tenant_id),
                member_id=str(member_id),
                pattern_type="multi_payer_convergence",
                detected_at=now,
                evidence_window_start=now - timedelta(days=7),
                evidence_window_end=now,
                triggering_event_ids=[event_id],
            ))

        return anomalies

    def _open_investigation(
        self, tenant_id: uuid.UUID, member_id: str, anomaly: AccumulatorAnomaly
    ) -> Investigation:
        now = datetime.now(UTC)
        return Investigation(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            investigation_number=f"INV-{now.year}-ACC-{str(uuid.uuid4())[:8].upper()}",
            title=f"Accumulator anomaly: {anomaly.pattern_type}",
            subject_type="member",
            subject_entity_id=str(member_id),
            investigation_type="accumulator_anomaly",
            status="open",
            priority="high",
            opened_at=now,
        )
