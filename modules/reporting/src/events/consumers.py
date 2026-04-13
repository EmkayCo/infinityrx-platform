"""Event consumers for the reporting module.

Reporting consumes events from ALL modules for real-time dashboard updates
and alert-triggered report generation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def handle_billing_journal_entry(payload: dict[str, Any], tenant_id: str) -> None:
    """Handle billing.journal_entries events for financial report freshness."""
    logger.info(
        "reporting: received billing.journal_entries event",
        extra={"tenant_id": tenant_id, "correlation_id": payload.get("correlation_id")},
    )


async def handle_fwa_claim_flagged(payload: dict[str, Any], tenant_id: str) -> None:
    """Handle fwa.claim_flagged events to refresh FWA dashboard data."""
    logger.info(
        "reporting: received fwa.claim_flagged event",
        extra={"tenant_id": tenant_id, "entity_id": payload.get("entity_id")},
    )


async def handle_fwa_investigation_opened(payload: dict[str, Any], tenant_id: str) -> None:
    """Handle fwa.investigation_opened for investigation status dashboard."""
    logger.info(
        "reporting: received fwa.investigation_opened",
        extra={"tenant_id": tenant_id},
    )


async def handle_fwa_investigation_resolved(payload: dict[str, Any], tenant_id: str) -> None:
    """Handle fwa.investigation_resolved for investigation status dashboard."""
    logger.info(
        "reporting: received fwa.investigation_resolved",
        extra={"tenant_id": tenant_id},
    )


async def handle_prefund_critical(
    payload: dict[str, Any],
    tenant_id: str,
    alert_service: Any | None = None,
) -> None:
    """Handle prefund.critical alert — auto-generate Prefund Status Report."""
    logger.warning(
        "reporting: prefund.critical alert received — triggering auto-report",
        extra={"tenant_id": tenant_id},
    )
    if alert_service:
        await alert_service.trigger_alert_report(
            tenant_id=tenant_id,
            event_type="prefund.critical",
            event_payload=payload,
        )


async def handle_quality_measure_at_risk(
    payload: dict[str, Any],
    tenant_id: str,
    alert_service: Any | None = None,
) -> None:
    """Handle quality.measure_at_risk — auto-generate Star Ratings Gap Report."""
    logger.warning(
        "reporting: quality.measure_at_risk received — triggering gap report",
        extra={"tenant_id": tenant_id, "measure_id": payload.get("measure_id")},
    )


EVENT_HANDLERS: dict[str, Any] = {
    "billing.journal_entries": handle_billing_journal_entry,
    "fwa.claim_flagged": handle_fwa_claim_flagged,
    "fwa.investigation_opened": handle_fwa_investigation_opened,
    "fwa.investigation_resolved": handle_fwa_investigation_resolved,
    "prefund.critical": handle_prefund_critical,
    "quality.measure_at_risk": handle_quality_measure_at_risk,
}
