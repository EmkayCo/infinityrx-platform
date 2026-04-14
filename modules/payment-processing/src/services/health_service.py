"""Vendor health monitoring service.

Tracks vendor status: healthy / degraded / down.
Updates vendor_adapters.status based on health log history.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .._shim import events as event_bus
from .._shim.notifications import NotificationService
from ..models import VendorAdapter, VendorHealthLog
from ..utils.constants import (
    EVENT_VENDOR_STATUS_CHANGED,
    HEALTH_DEGRADED_MS,
    HEALTH_DOWN_ERROR_COUNT,
    VH_DEGRADED,
    VH_DOWN,
    VH_HEALTHY,
)
from .vendor_adapter import HealthCheckResult, PaymentVendorAdapter

logger = logging.getLogger("payment.health")


class VendorHealthService:
    """Runs health checks and updates vendor status."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def run_health_check(
        self,
        vendor_adapter_id: str,
        tenant_id: str,
        adapter: PaymentVendorAdapter,
    ) -> VendorHealthLog:
        """Execute one health check and persist the result."""
        result = adapter.health_check()

        log = VendorHealthLog(
            vendor_adapter_id=vendor_adapter_id,
            tenant_id=tenant_id,
            check_type=result.check_type,
            status=result.status,
            response_time_ms=result.response_time_ms,
            error_message=result.error_message,
        )
        self._session.add(log)
        self._session.flush()

        # Compute new overall vendor status
        new_status = self._compute_status(vendor_adapter_id, result)
        vendor = self._session.get(VendorAdapter, vendor_adapter_id)
        if vendor and vendor.status != new_status:
            old_status = vendor.status
            vendor.status = new_status
            logger.info(
                "Vendor %s status: %s -> %s", vendor_adapter_id, old_status, new_status
            )
            event_bus.publish(
                EVENT_VENDOR_STATUS_CHANGED,
                {
                    "tenant_id": tenant_id,
                    "vendor_adapter_id": vendor_adapter_id,
                    "old_status": old_status,
                    "new_status": new_status,
                },
            )
            NotificationService.create(
                tenant_id=tenant_id,  # type: ignore[arg-type]
                notification_type="vendor.status_changed",
                title=f"Vendor status changed: {new_status}",
                message=f"Vendor {vendor_adapter_id} changed from {old_status} to {new_status}",
                severity="warning" if new_status == VH_DEGRADED else "critical",
            )

        self._session.commit()
        return log

    def _compute_status(
        self, vendor_adapter_id: str, latest_result: HealthCheckResult
    ) -> str:
        """Determine status from latest result."""
        if latest_result.status == VH_DOWN:
            return VH_DOWN
        if latest_result.response_time_ms and latest_result.response_time_ms > HEALTH_DEGRADED_MS:
            return VH_DEGRADED
        # Check recent error count
        one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
        error_logs = self._session.execute(
            select(VendorHealthLog).where(
                VendorHealthLog.vendor_adapter_id == vendor_adapter_id,
                VendorHealthLog.status.in_([VH_DEGRADED, VH_DOWN]),
                VendorHealthLog.checked_at >= one_hour_ago,
            )
        ).scalars().all()
        if len(error_logs) >= HEALTH_DOWN_ERROR_COUNT:
            return VH_DOWN
        if len(error_logs) >= 1:
            return VH_DEGRADED
        return VH_HEALTHY
