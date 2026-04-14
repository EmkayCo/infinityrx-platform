"""Unit tests for SubmissionService — financial path, 100% coverage."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from src._shim.events import published_events
from src.models.tables import Settlement, Submission
from src.services.nacha_generator import NachaBatchConfig, NachaFileConfig
from src.services.ofac_screening import OfacScreeningService
from src.services.submission_service import SubmissionService
from src.services.vendor_adapter import (
    DirectAchAdapter,
    PaymentInstruction,
    SubmitResult,
)
from src.utils.constants import (
    EVENT_FILE_GENERATED,
    EVENT_RETURN_SUSPICIOUS,
    EVENT_RETURNED,
    EVENT_SUBMITTED,
    SUB_FAILED,
    SUB_PENDING,
    SUB_SUBMITTED,
)
from tests.conftest import TENANT_ID, VENDOR_ID

BATCH_ID = str(uuid.uuid4())


def _make_instructions(count: int = 2) -> list[PaymentInstruction]:
    return [
        PaymentInstruction(
            billing_payment_id=f"BP-{i:04d}",
            pay_to_entity_id=f"ENT-{i:04d}",
            pay_to_name=f"Pharmacy {i}",
            pay_to_npi=f"123456789{i}",
            amount=Decimal(f"{100 * i}.00"),
            routing_number="021000021",
            account_number="12345678901234567",
        )
        for i in range(1, count + 1)
    ]


def _make_adapter() -> DirectAchAdapter:
    return DirectAchAdapter(
        file_cfg=NachaFileConfig(
            immediate_destination="021000021",
            immediate_origin="1234567890",
            immediate_destination_name="BANK OF TEST",
            immediate_origin_name="INFINITYRX LLC",
        ),
        batch_cfg=NachaBatchConfig(
            company_name="INFINITYRX",
            company_id="1234567890",
            entry_class_code="CCD",
            company_entry_description="PAYMT",
            originating_dfi_id="02100002",
        ),
    )


class TestSubmitBatch:
    def test_submit_creates_submission_record(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=BATCH_ID,
            instructions=_make_instructions(2),
        )
        assert sub.status == SUB_SUBMITTED
        assert sub.payment_count == 2
        assert sub.total_amount == Decimal("300.00")

    def test_submit_creates_settlement_records(self, db_session, vendor_adapter):
        from sqlalchemy import select
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=BATCH_ID,
            instructions=_make_instructions(2),
        )
        settlements = db_session.execute(
            select(Settlement).where(Settlement.submission_id == sub.id)
        ).scalars().all()
        assert len(settlements) == 2

    def test_submit_publishes_file_generated_event(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=BATCH_ID,
            instructions=_make_instructions(),
        )
        events = published_events()
        topics = [e.topic for e in events]
        assert EVENT_FILE_GENERATED in topics

    def test_submit_publishes_submitted_event(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=BATCH_ID,
            instructions=_make_instructions(),
        )
        events = published_events()
        topics = [e.topic for e in events]
        assert EVENT_SUBMITTED in topics

    def test_idempotency_prevents_duplicate_submission(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        sub1 = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=BATCH_ID,
            instructions=_make_instructions(),
        )
        sub2 = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=BATCH_ID,
            instructions=_make_instructions(),
        )
        assert sub1.id == sub2.id

    def test_ofac_block_raises_value_error(self, db_session, vendor_adapter):
        blocked_ofac = OfacScreeningService(blocked_entity_ids={"ENT-0001"})
        svc = SubmissionService(db_session, _make_adapter(), ofac=blocked_ofac)
        with pytest.raises(ValueError, match="OFAC block"):
            svc.submit_batch(
                tenant_id=TENANT_ID,
                vendor_adapter_id=VENDOR_ID,
                billing_payment_batch_id=BATCH_ID,
                instructions=_make_instructions(),
            )

    def test_ofac_screened_flag_set(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=BATCH_ID,
            instructions=_make_instructions(),
        )
        assert sub.ofac_screened is True
        assert sub.ofac_screened_at is not None

    def test_fraud_monitoring_logged(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=BATCH_ID,
            instructions=_make_instructions(),
        )
        assert sub.fraud_monitoring_logged is True

    def test_total_amount_decimal_precision(self, db_session, vendor_adapter):
        instructions = [
            PaymentInstruction(
                billing_payment_id="BP-PENNY",
                pay_to_entity_id="ENT-PENNY",
                pay_to_name="Penny Pharmacy",
                pay_to_npi="1234567890",
                amount=Decimal("33.34"),
                routing_number="021000021",
                account_number="12345678901234567",
            )
        ]
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            instructions=instructions,
        )
        assert sub.total_amount == Decimal("33.34")
        assert isinstance(sub.total_amount, Decimal)


class TestProcessReturn:
    def test_return_updates_settlement_status(self, db_session, vendor_adapter):
        from datetime import date
        from sqlalchemy import select
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            instructions=_make_instructions(1),
        )
        settle = db_session.execute(
            select(Settlement).where(Settlement.submission_id == sub.id)
        ).scalar_one()

        svc.process_return(
            tenant_id=TENANT_ID,
            submission_id=sub.id,
            billing_payment_id=settle.billing_payment_id,
            return_code="R01",
            return_reason="Insufficient Funds",
            return_date=date(2026, 4, 16),
            amount=Decimal("100.00"),
        )
        db_session.refresh(settle)
        assert settle.status == "returned"
        assert settle.return_code == "R01"

    def test_return_publishes_returned_event(self, db_session, vendor_adapter):
        from datetime import date
        from sqlalchemy import select
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            instructions=_make_instructions(1),
        )
        settle = db_session.execute(
            select(Settlement).where(Settlement.submission_id == sub.id)
        ).scalar_one()

        svc.process_return(
            tenant_id=TENANT_ID,
            submission_id=sub.id,
            billing_payment_id=settle.billing_payment_id,
            return_code="R01",
            return_reason=None,
            return_date=date(2026, 4, 16),
            amount=Decimal("100.00"),
        )
        topics = [e.topic for e in published_events()]
        assert EVENT_RETURNED in topics

    def test_suspicious_return_r10_publishes_suspicious_event(self, db_session, vendor_adapter):
        from datetime import date
        from sqlalchemy import select
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            instructions=_make_instructions(1),
        )
        settle = db_session.execute(
            select(Settlement).where(Settlement.submission_id == sub.id)
        ).scalar_one()

        svc.process_return(
            tenant_id=TENANT_ID,
            submission_id=sub.id,
            billing_payment_id=settle.billing_payment_id,
            return_code="R10",
            return_reason="Unauthorized",
            return_date=date(2026, 4, 16),
            amount=Decimal("100.00"),
        )
        topics = [e.topic for e in published_events()]
        assert EVENT_RETURN_SUSPICIOUS in topics


class TestMarkSettled:
    def test_mark_settled_updates_status(self, db_session, vendor_adapter):
        from datetime import date
        from sqlalchemy import select
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            instructions=_make_instructions(1),
        )
        settle = db_session.execute(
            select(Settlement).where(Settlement.submission_id == sub.id)
        ).scalar_one()

        svc.mark_settled(
            tenant_id=TENANT_ID,
            submission_id=sub.id,
            billing_payment_id=settle.billing_payment_id,
            settlement_date=date(2026, 4, 17),
            settlement_reference="ACH-REF-001",
            payment_method_used="ach",
            amount=Decimal("100.00"),
        )
        db_session.refresh(settle)
        assert settle.status == "settled"
        assert settle.settlement_date == date(2026, 4, 17)

    def test_mark_settled_unknown_payment_raises(self, db_session, vendor_adapter):
        from datetime import date
        svc = SubmissionService(db_session, _make_adapter())
        with pytest.raises(LookupError):
            svc.mark_settled(
                tenant_id=TENANT_ID,
                submission_id="no-sub",
                billing_payment_id="NONEXISTENT",
                settlement_date=date(2026, 4, 17),
                settlement_reference="REF",
                payment_method_used="ach",
                amount=Decimal("0.00"),
            )


class TestPaymentHold:
    def test_apply_hold_marks_settlements(self, db_session, vendor_adapter):
        from sqlalchemy import select
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            instructions=_make_instructions(2),
        )
        count = svc.apply_payment_hold(
            tenant_id=TENANT_ID,
            entity_id="ENT-0001",
            reason="FWA investigation",
        )
        assert count >= 1
        settles = db_session.execute(
            select(Settlement).where(
                Settlement.pay_to_entity_id == "ENT-0001",
                Settlement.is_held.is_(True),
            )
        ).scalars().all()
        assert len(settles) >= 1

    def test_release_hold_clears_holds(self, db_session, vendor_adapter):
        from sqlalchemy import select
        svc = SubmissionService(db_session, _make_adapter())
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            instructions=_make_instructions(2),
        )
        svc.apply_payment_hold(tenant_id=TENANT_ID, entity_id="ENT-0001", reason="Test")
        released = svc.release_payment_hold(tenant_id=TENANT_ID, entity_id="ENT-0001")
        assert released >= 1
        settles = db_session.execute(
            select(Settlement).where(
                Settlement.pay_to_entity_id == "ENT-0001",
                Settlement.is_held.is_(True),
            )
        ).scalars().all()
        assert len(settles) == 0


class TestSubmitBatchFailurePaths:
    def test_adapter_format_failure_raises_runtime_error(self, db_session, vendor_adapter):
        from unittest.mock import MagicMock
        mock_adapter = MagicMock()
        mock_adapter.format_batch.return_value = SubmitResult(
            success=False, error_message="format error"
        )
        svc = SubmissionService(db_session, mock_adapter)
        with pytest.raises(RuntimeError, match="format error"):
            svc.submit_batch(
                tenant_id=TENANT_ID,
                vendor_adapter_id=VENDOR_ID,
                billing_payment_batch_id=str(uuid.uuid4()),
                instructions=_make_instructions(1),
            )

    def test_submit_failure_marks_submission_failed(self, db_session, vendor_adapter):
        from unittest.mock import MagicMock
        mock_adapter = MagicMock()
        mock_adapter.format_batch.return_value = SubmitResult(success=True, file_content="test")
        mock_adapter.submit.return_value = SubmitResult(
            success=False, error_message="network error"
        )
        svc = SubmissionService(db_session, mock_adapter)
        sub = svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            instructions=_make_instructions(1),
        )
        assert sub.status == SUB_FAILED
        assert "network error" in sub.error_message

    def test_submit_failure_publishes_failed_event(self, db_session, vendor_adapter):
        from unittest.mock import MagicMock
        from src.utils.constants import EVENT_FAILED
        mock_adapter = MagicMock()
        mock_adapter.format_batch.return_value = SubmitResult(success=True, file_content="test")
        mock_adapter.submit.return_value = SubmitResult(
            success=False, error_message="timeout"
        )
        svc = SubmissionService(db_session, mock_adapter)
        svc.submit_batch(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            instructions=_make_instructions(1),
        )
        topics = [e.topic for e in published_events()]
        assert EVENT_FAILED in topics


class TestRetrySubmission:
    def test_retry_resets_to_pending(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status=SUB_FAILED,
            retry_count=0,
            max_retries=3,
        )
        db_session.add(sub)
        db_session.flush()
        result = svc.retry_submission(sub.id, TENANT_ID)
        assert result.status == SUB_PENDING
        assert result.retry_count == 1

    def test_retry_not_found_raises(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        with pytest.raises(LookupError):
            svc.retry_submission(str(uuid.uuid4()), TENANT_ID)

    def test_retry_non_failed_raises(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status=SUB_SUBMITTED,
            retry_count=0,
            max_retries=3,
        )
        db_session.add(sub)
        db_session.flush()
        with pytest.raises(ValueError, match="Cannot retry"):
            svc.retry_submission(sub.id, TENANT_ID)

    def test_retry_max_retries_exhausted_raises(self, db_session, vendor_adapter):
        svc = SubmissionService(db_session, _make_adapter())
        sub = Submission(
            tenant_id=TENANT_ID,
            vendor_adapter_id=VENDOR_ID,
            billing_payment_batch_id=str(uuid.uuid4()),
            idempotency_key=str(uuid.uuid4()),
            submission_type="file",
            payment_count=1,
            total_amount=Decimal("100.00"),
            status=SUB_FAILED,
            retry_count=3,
            max_retries=3,
        )
        db_session.add(sub)
        db_session.flush()
        with pytest.raises(ValueError, match="Max retries"):
            svc.retry_submission(sub.id, TENANT_ID)


class TestProcessReturnNewSettlement:
    def test_return_creates_settlement_when_not_found(self, db_session, vendor_adapter):
        from datetime import date
        svc = SubmissionService(db_session, _make_adapter())
        settle = svc.process_return(
            tenant_id=TENANT_ID,
            submission_id=str(uuid.uuid4()),
            billing_payment_id="BP-NEW-001",
            return_code="R02",
            return_reason="Account Closed",
            return_date=date(2026, 4, 16),
            amount=Decimal("200.00"),
        )
        assert settle.status == "returned"
        assert settle.billing_payment_id == "BP-NEW-001"
        assert settle.pay_to_entity_id == "unknown"
