"""Unit tests for ReconciliationService — dashboard and reconciliation rows."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal


from src.models.tables import Settlement, Submission
from src.services.reconciliation_service import ReconciliationService
from tests.conftest import TENANT_ID


def _add_submission(db_session, vendor_adapter, amount: Decimal = Decimal("500.00")) -> Submission:
    sub = Submission(
        tenant_id=TENANT_ID,
        vendor_adapter_id=vendor_adapter.id,
        billing_payment_batch_id=str(uuid.uuid4()),
        idempotency_key=str(uuid.uuid4()),
        submission_type="file",
        payment_count=1,
        total_amount=amount,
        status="submitted",
    )
    db_session.add(sub)
    db_session.flush()
    return sub


def _add_settlement(db_session, sub: Submission, status: str = "pending", amount: Decimal = Decimal("500.00")) -> Settlement:
    settle = Settlement(
        tenant_id=TENANT_ID,
        submission_id=sub.id,
        billing_payment_id=str(uuid.uuid4()),
        pay_to_entity_id=str(uuid.uuid4()),
        amount=amount,
        status=status,
    )
    db_session.add(settle)
    db_session.flush()
    return settle


class TestGetReconciliationRows:
    def test_empty_returns_empty_list(self, db_session, vendor_adapter):
        svc = ReconciliationService(db_session)
        rows = svc.get_reconciliation_rows(TENANT_ID)
        assert rows == []

    def test_pending_settlement_has_no_actual_amount(self, db_session, vendor_adapter):
        sub = _add_submission(db_session, vendor_adapter)
        _add_settlement(db_session, sub, status="pending")
        svc = ReconciliationService(db_session)
        rows = svc.get_reconciliation_rows(TENANT_ID)
        assert len(rows) == 1
        assert rows[0].actual_amount is None
        assert rows[0].discrepancy is None

    def test_settled_settlement_has_actual_amount(self, db_session, vendor_adapter):
        sub = _add_submission(db_session, vendor_adapter)
        _add_settlement(db_session, sub, status="settled", amount=Decimal("500.00"))
        svc = ReconciliationService(db_session)
        rows = svc.get_reconciliation_rows(TENANT_ID)
        assert rows[0].actual_amount == Decimal("500.00")
        assert rows[0].discrepancy == Decimal("0.00")

    def test_days_outstanding_computed_for_pending(self, db_session, vendor_adapter):
        sub = _add_submission(db_session, vendor_adapter)
        settle = _add_settlement(db_session, sub, status="pending")
        settle.created_at = datetime.now(UTC) - timedelta(days=5)
        db_session.flush()
        svc = ReconciliationService(db_session)
        rows = svc.get_reconciliation_rows(TENANT_ID)
        assert rows[0].days_outstanding is not None
        assert rows[0].days_outstanding >= 0

    def test_filter_by_submission_ids(self, db_session, vendor_adapter):
        sub1 = _add_submission(db_session, vendor_adapter)
        sub2 = _add_submission(db_session, vendor_adapter)
        _add_settlement(db_session, sub1)
        _add_settlement(db_session, sub2)
        svc = ReconciliationService(db_session)
        rows = svc.get_reconciliation_rows(TENANT_ID, submission_ids=[sub1.id])
        assert len(rows) == 1
        assert rows[0].submission_id == sub1.id


class TestGetDashboardSummary:
    def test_empty_db_returns_zeros(self, db_session, vendor_adapter):
        svc = ReconciliationService(db_session)
        summary = svc.get_dashboard_summary(TENANT_ID)
        assert summary["total_submitted_30d"] == Decimal("0.00")
        assert summary["total_settled_30d"] == Decimal("0.00")
        assert summary["settlement_rate_pct"] == Decimal("0.00")

    def test_summary_with_data(self, db_session, vendor_adapter):
        sub = _add_submission(db_session, vendor_adapter, Decimal("1000.00"))
        _add_settlement(db_session, sub, status="settled", amount=Decimal("1000.00"))
        svc = ReconciliationService(db_session)
        summary = svc.get_dashboard_summary(TENANT_ID)
        assert summary["total_submitted_30d"] == Decimal("1000.00")
        assert summary["total_settled_30d"] == Decimal("1000.00")

    def test_returned_settlements_counted(self, db_session, vendor_adapter):
        sub = _add_submission(db_session, vendor_adapter, Decimal("200.00"))
        _add_settlement(db_session, sub, status="returned", amount=Decimal("200.00"))
        svc = ReconciliationService(db_session)
        summary = svc.get_dashboard_summary(TENANT_ID)
        assert summary["total_returned_30d"] == Decimal("200.00")

    def test_pending_count_and_amount(self, db_session, vendor_adapter):
        sub = _add_submission(db_session, vendor_adapter, Decimal("300.00"))
        _add_settlement(db_session, sub, status="pending", amount=Decimal("300.00"))
        svc = ReconciliationService(db_session)
        summary = svc.get_dashboard_summary(TENANT_ID)
        assert summary["pending_settlement_count"] == 1
        assert summary["pending_settlement_amount"] == Decimal("300.00")


