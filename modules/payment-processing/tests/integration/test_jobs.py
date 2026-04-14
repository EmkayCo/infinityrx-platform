"""Integration tests for scheduled jobs."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.models.tables import Submission, VendorAdapter
from src.jobs.scheduled import (
    ofac_refresh_job,
    poll_settlements,
    retry_failed_submissions,
    vendor_health_check_job,
)
from tests.conftest import TENANT_ID, VENDOR_ID


class TestPollSettlements:
    def test_polls_submitted_submissions(self, db_session: Session, vendor_adapter: VendorAdapter):
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status="submitted",
        )
        db_session.add(sub)
        db_session.flush()

        count = poll_settlements(db_session, TENANT_ID)
        assert count >= 1

    def test_ignores_pending_submissions(self, db_session: Session, vendor_adapter: VendorAdapter):
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status="pending",
        )
        db_session.add(sub)
        db_session.flush()

        count = poll_settlements(db_session, TENANT_ID)
        assert count == 0

    def test_returns_zero_when_no_submissions(self, db_session: Session):
        count = poll_settlements(db_session, str(uuid.uuid4()))
        assert count == 0


class TestVendorHealthCheckJob:
    def test_returns_list_of_checked_vendor_ids(self, db_session: Session, vendor_adapter: VendorAdapter):
        checked = vendor_health_check_job(db_session)
        assert VENDOR_ID in checked

    def test_only_checks_active_vendors(self, db_session: Session):
        inactive = VendorAdapter(
            tenant_id=TENANT_ID,
            vendor_type="echo",
            name="Inactive Vendor",
            connection_type="api",
            settlement_method="api_poll",
            is_active=False,
        )
        db_session.add(inactive)
        db_session.flush()

        checked = vendor_health_check_job(db_session)
        assert inactive.id not in checked


class TestRetryFailedSubmissions:
    def test_retries_ready_submissions(self, db_session: Session, vendor_adapter: VendorAdapter):
        past_time = datetime.now(timezone.utc) - timedelta(hours=2)
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status="failed",
            retry_count=0,
            max_retries=3,
            next_retry_at=past_time,
        )
        db_session.add(sub)
        db_session.flush()

        count = retry_failed_submissions(db_session)
        assert count >= 1

    def test_skips_future_retry(self, db_session: Session, vendor_adapter: VendorAdapter):
        future_time = datetime.now(timezone.utc) + timedelta(hours=5)
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status="failed",
            retry_count=0,
            max_retries=3,
            next_retry_at=future_time,
        )
        db_session.add(sub)
        db_session.flush()

        count = retry_failed_submissions(db_session)
        assert count == 0

    def test_skips_exhausted_retries(self, db_session: Session, vendor_adapter: VendorAdapter):
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status="failed",
            retry_count=3,
            max_retries=3,
            next_retry_at=past_time,
        )
        db_session.add(sub)
        db_session.flush()

        count = retry_failed_submissions(db_session)
        assert count == 0


class TestOfacRefreshJob:
    def test_ofac_refresh_does_not_raise(self):
        ofac_refresh_job()
