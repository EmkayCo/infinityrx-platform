"""Integration tests for VendorHealthService."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src._shim.events import published_events
from src.models.tables import VendorAdapter
from src.services.health_service import VendorHealthService
from src.services.vendor_adapter import HealthCheckResult, PaymentVendorAdapter
from src.utils.constants import EVENT_VENDOR_STATUS_CHANGED, VH_DEGRADED, VH_DOWN, VH_HEALTHY
from tests.conftest import TENANT_ID, VENDOR_ID


class _MockAdapter(PaymentVendorAdapter):
    def __init__(self, result: HealthCheckResult) -> None:
        self._result = result

    def format_batch(self, instructions, batch_id, effective_date=None):
        raise NotImplementedError

    def submit(self, formatted, submission_id):
        raise NotImplementedError

    def poll_settlement(self, vendor_reference, billing_payment_ids):
        return []

    def parse_return(self, raw_data):
        return []

    def health_check(self) -> HealthCheckResult:
        return self._result


class TestVendorHealthService:
    def test_healthy_check_creates_log(self, db_session: Session, vendor_adapter: VendorAdapter):
        svc = VendorHealthService(db_session)
        adapter = _MockAdapter(HealthCheckResult(status=VH_HEALTHY, response_time_ms=120))
        log = svc.run_health_check(VENDOR_ID, TENANT_ID, adapter)
        assert log.status == VH_HEALTHY
        assert log.response_time_ms == 120

    def test_status_change_publishes_event(self, db_session: Session, vendor_adapter: VendorAdapter):
        svc = VendorHealthService(db_session)
        # First set to down to trigger status change from "active"
        adapter = _MockAdapter(HealthCheckResult(status=VH_DOWN, error_message="timeout"))
        svc.run_health_check(VENDOR_ID, TENANT_ID, adapter)
        events = published_events()
        assert any(e.topic == EVENT_VENDOR_STATUS_CHANGED for e in events)

    def test_healthy_after_down_emits_change(self, db_session: Session, vendor_adapter: VendorAdapter):
        vendor_adapter.status = VH_DOWN
        db_session.flush()

        svc = VendorHealthService(db_session)
        adapter = _MockAdapter(HealthCheckResult(status=VH_HEALTHY, response_time_ms=100))
        svc.run_health_check(VENDOR_ID, TENANT_ID, adapter)

        events = published_events()
        status_events = [e for e in events if e.topic == EVENT_VENDOR_STATUS_CHANGED]
        assert len(status_events) >= 1

    def test_slow_response_marks_degraded(self, db_session: Session, vendor_adapter: VendorAdapter):
        svc = VendorHealthService(db_session)
        adapter = _MockAdapter(HealthCheckResult(status=VH_HEALTHY, response_time_ms=600))
        log = svc.run_health_check(VENDOR_ID, TENANT_ID, adapter)
        db_session.refresh(vendor_adapter)
        assert vendor_adapter.status == VH_DEGRADED

    def test_down_check_marks_down(self, db_session: Session, vendor_adapter: VendorAdapter):
        svc = VendorHealthService(db_session)
        adapter = _MockAdapter(HealthCheckResult(status=VH_DOWN, error_message="no connection"))
        svc.run_health_check(VENDOR_ID, TENANT_ID, adapter)
        db_session.refresh(vendor_adapter)
        assert vendor_adapter.status == VH_DOWN

    def test_status_same_no_event_emitted(self, db_session: Session, vendor_adapter: VendorAdapter):
        vendor_adapter.status = VH_HEALTHY
        db_session.flush()
        svc = VendorHealthService(db_session)
        adapter = _MockAdapter(HealthCheckResult(status=VH_HEALTHY, response_time_ms=50))
        svc.run_health_check(VENDOR_ID, TENANT_ID, adapter)
        events = published_events()
        status_events = [e for e in events if e.topic == EVENT_VENDOR_STATUS_CHANGED]
        assert len(status_events) == 0

    def test_multiple_errors_within_hour_marks_down(self, db_session: Session, vendor_adapter: VendorAdapter):
        from src.models.tables import VendorHealthLog
        from datetime import datetime, timezone
        for _ in range(3):
            db_session.add(VendorHealthLog(
                vendor_adapter_id=VENDOR_ID,
                tenant_id=TENANT_ID,
                check_type="sftp_connect",
                status=VH_DOWN,
                checked_at=datetime.now(timezone.utc),
            ))
        db_session.flush()

        svc = VendorHealthService(db_session)
        adapter = _MockAdapter(HealthCheckResult(status=VH_HEALTHY, response_time_ms=50))
        svc.run_health_check(VENDOR_ID, TENANT_ID, adapter)
        db_session.refresh(vendor_adapter)
        assert vendor_adapter.status == VH_DOWN

    def test_one_error_within_hour_marks_degraded(self, db_session: Session, vendor_adapter: VendorAdapter):
        from src.models.tables import VendorHealthLog
        from datetime import datetime, timezone
        db_session.add(VendorHealthLog(
            vendor_adapter_id=VENDOR_ID,
            tenant_id=TENANT_ID,
            check_type="sftp_connect",
            status=VH_DOWN,
            checked_at=datetime.now(timezone.utc),
        ))
        db_session.flush()
        vendor_adapter.status = VH_HEALTHY
        db_session.flush()

        svc = VendorHealthService(db_session)
        adapter = _MockAdapter(HealthCheckResult(status=VH_HEALTHY, response_time_ms=50))
        svc.run_health_check(VENDOR_ID, TENANT_ID, adapter)
        db_session.refresh(vendor_adapter)
        assert vendor_adapter.status == VH_DEGRADED
