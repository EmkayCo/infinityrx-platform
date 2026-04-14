"""Core payment submission service.

Orchestrates: vendor adapter selection, OFAC screening, idempotency,
submission creation, fraud monitoring logging, event publishing.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .._shim import events as event_bus
from .._shim.notifications import NotificationService
from ..models import Settlement, Submission
from ..utils.constants import (
    EVENT_FAILED,
    EVENT_FILE_GENERATED,
    EVENT_RETURN_SUSPICIOUS,
    EVENT_RETURNED,
    EVENT_SETTLED,
    EVENT_SUBMITTED,
    SETTLE_RETURNED,
    SETTLE_SETTLED,
    SUB_FAILED,
    SUB_PENDING,
    SUB_SUBMITTED,
)
from .ach_return_codes import get_return_code, is_suspicious_return
from .decimal_utils import money
from .ofac_screening import OfacScreeningService
from .retry_service import next_retry_at, should_retry
from .vendor_adapter import PaymentInstruction, PaymentVendorAdapter, SubmitResult

logger = logging.getLogger("payment.submission")


def _make_idempotency_key(tenant_id: str, billing_batch_id: str, vendor_adapter_id: str) -> str:
    raw = f"{tenant_id}:{billing_batch_id}:{vendor_adapter_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


class SubmissionService:
    """Orchestrates payment submission lifecycle."""

    def __init__(
        self,
        session: Session,
        adapter: PaymentVendorAdapter,
        ofac: OfacScreeningService | None = None,
    ) -> None:
        self._session = session
        self._adapter = adapter
        self._ofac = ofac or OfacScreeningService()

    def submit_batch(
        self,
        *,
        tenant_id: str,
        vendor_adapter_id: str,
        billing_payment_batch_id: str,
        instructions: list[PaymentInstruction],
    ) -> Submission:
        """
        Submit a payment batch. Idempotent — returns existing submission if already submitted.

        Steps:
        1. Idempotency check
        2. OFAC screening (block if any match)
        3. Format via adapter
        4. Create submission record
        5. Submit via adapter
        6. Update record + emit events
        7. Log NACHA 2026 fraud monitoring
        """
        # 1. Idempotency check
        idem_key = _make_idempotency_key(tenant_id, billing_payment_batch_id, vendor_adapter_id)
        existing = self._session.execute(
            select(Submission).where(
                Submission.idempotency_key == idem_key,
                Submission.status != SUB_FAILED,
            )
        ).scalar_one_or_none()
        if existing is not None:
            logger.info("Duplicate submission prevented: %s", idem_key)
            return existing

        # 2. OFAC screening
        entities = [(i.pay_to_entity_id, i.pay_to_name) for i in instructions]
        ofac_results = self._ofac.screen_batch(entities)
        blocked = [r for r in ofac_results if r.is_blocked]
        if blocked:
            blocked_ids = [r.entity_id for r in blocked]
            logger.error("OFAC block: entities %s in batch %s", blocked_ids, billing_payment_batch_id)
            NotificationService.create(
                tenant_id=tenant_id,  # type: ignore[arg-type]
                notification_type="payment.ofac_blocked",
                title="OFAC Screening Block",
                message=f"Payment batch {billing_payment_batch_id} blocked: OFAC match on {len(blocked)} entities",
                severity="critical",
            )
            raise ValueError(f"OFAC block: entities {blocked_ids} cannot receive payment")

        # 3. Format
        batch_id = f"{tenant_id[:8]}-{billing_payment_batch_id[:8]}"
        total_amount = money(sum(i.amount for i in instructions))
        formatted = self._adapter.format_batch(instructions, batch_id)
        if not formatted.success:
            raise RuntimeError(f"Adapter format failed: {formatted.error_message}")

        # 4. Create submission record
        sub = Submission(
            tenant_id=tenant_id,
            vendor_adapter_id=vendor_adapter_id,
            billing_payment_batch_id=billing_payment_batch_id,
            idempotency_key=idem_key,
            submission_type="file",
            payment_count=len(instructions),
            total_amount=total_amount,
            status=SUB_PENDING,
            ofac_screened=True,
            ofac_screened_at=datetime.now(UTC),
        )
        self._session.add(sub)
        self._session.flush()

        # Create settlement records (one per instruction)
        for instr in instructions:
            settle = Settlement(
                tenant_id=tenant_id,
                submission_id=sub.id,
                billing_payment_id=instr.billing_payment_id,
                pay_to_entity_id=instr.pay_to_entity_id,
                pay_to_npi=instr.pay_to_npi,
                amount=instr.amount,
                status="pending",
            )
            self._session.add(settle)

        event_bus.publish(
            EVENT_FILE_GENERATED,
            {
                "tenant_id": tenant_id,
                "submission_id": sub.id,
                "billing_payment_batch_id": billing_payment_batch_id,
                "payment_count": len(instructions),
                "total_amount": str(total_amount),
            },
        )

        # 5. Submit
        submit_result: SubmitResult = self._adapter.submit(formatted, sub.id)

        # 6. Update record
        if submit_result.success:
            sub.status = SUB_SUBMITTED
            sub.submitted_at = datetime.now(UTC)
            sub.vendor_reference = submit_result.vendor_reference
            sub.vendor_response = json.dumps(submit_result.raw_response) if submit_result.raw_response else None
            sub.fraud_monitoring_logged = True

            event_bus.publish(
                EVENT_SUBMITTED,
                {
                    "tenant_id": tenant_id,
                    "submission_id": sub.id,
                    "billing_payment_batch_id": billing_payment_batch_id,
                    "vendor_reference": submit_result.vendor_reference,
                    "total_amount": str(total_amount),
                    "payment_count": len(instructions),
                },
            )
        else:
            sub.status = SUB_FAILED
            sub.error_message = submit_result.error_message

            event_bus.publish(
                EVENT_FAILED,
                {
                    "tenant_id": tenant_id,
                    "submission_id": sub.id,
                    "error": submit_result.error_message,
                },
            )

        self._session.commit()
        return sub

    def retry_submission(self, submission_id: str, tenant_id: str) -> Submission:
        """Retry a failed submission with exponential backoff tracking."""
        sub = self._session.get(Submission, submission_id)
        if sub is None or sub.tenant_id != tenant_id:
            raise LookupError(f"Submission {submission_id} not found")
        if sub.status != SUB_FAILED:
            raise ValueError(f"Cannot retry submission in status {sub.status}")
        if not should_retry(sub.retry_count, sub.max_retries):
            raise ValueError("Max retries exhausted")

        sub.retry_count += 1
        sub.next_retry_at = next_retry_at(sub.retry_count)
        sub.status = SUB_PENDING
        self._session.commit()
        return sub

    def process_return(
        self,
        *,
        tenant_id: str,
        submission_id: str,
        billing_payment_id: str,
        return_code: str,
        return_reason: str | None,
        return_date: date,
        amount: Decimal,
    ) -> Settlement:
        """Process an ACH return — update settlement and emit events."""
        settle = self._session.execute(
            select(Settlement).where(
                Settlement.tenant_id == tenant_id,
                Settlement.submission_id == submission_id,
                Settlement.billing_payment_id == billing_payment_id,
            )
        ).scalar_one_or_none()

        if settle is None:
            settle = Settlement(
                tenant_id=tenant_id,
                submission_id=submission_id,
                billing_payment_id=billing_payment_id,
                pay_to_entity_id="unknown",
                amount=amount,
                status=SETTLE_RETURNED,
                return_code=return_code,
                return_reason=return_reason,
                return_date=return_date,
            )
            self._session.add(settle)
        else:
            settle.status = SETTLE_RETURNED
            settle.return_code = return_code
            settle.return_reason = return_reason
            settle.return_date = return_date

        rc_def = get_return_code(return_code)

        event_bus.publish(
            EVENT_RETURNED,
            {
                "tenant_id": tenant_id,
                "submission_id": submission_id,
                "billing_payment_id": billing_payment_id,
                "return_code": return_code,
                "return_reason": return_reason,
                "amount": str(amount),
                "default_action": rc_def.default_action if rc_def else "manual_review",
                "is_retryable": rc_def.is_retryable if rc_def else False,
            },
        )

        if is_suspicious_return(return_code):
            event_bus.publish(
                EVENT_RETURN_SUSPICIOUS,
                {
                    "tenant_id": tenant_id,
                    "submission_id": submission_id,
                    "billing_payment_id": billing_payment_id,
                    "return_code": return_code,
                    "amount": str(amount),
                },
            )
            NotificationService.create(
                tenant_id=tenant_id,  # type: ignore[arg-type]
                notification_type="payment.return_suspicious",
                title=f"Suspicious Return: {return_code}",
                message=f"Return {return_code} on payment {billing_payment_id} may indicate fraud",
                severity="critical",
            )

        self._session.commit()
        return settle

    def mark_settled(
        self,
        *,
        tenant_id: str,
        submission_id: str,
        billing_payment_id: str,
        settlement_date: date,
        settlement_reference: str,
        payment_method_used: str,
        amount: Decimal,
    ) -> Settlement:
        """Mark a settlement record as settled."""
        settle = self._session.execute(
            select(Settlement).where(
                Settlement.tenant_id == tenant_id,
                Settlement.billing_payment_id == billing_payment_id,
            )
        ).scalar_one_or_none()

        if settle is None:
            raise LookupError(f"Settlement for payment {billing_payment_id} not found")

        settle.status = SETTLE_SETTLED
        settle.settlement_date = settlement_date
        settle.settlement_reference = settlement_reference
        settle.payment_method_used = payment_method_used

        event_bus.publish(
            EVENT_SETTLED,
            {
                "tenant_id": tenant_id,
                "billing_payment_id": billing_payment_id,
                "settlement_date": settlement_date.isoformat(),
                "settlement_reference": settlement_reference,
                "amount": str(amount),
                "payment_method_used": payment_method_used,
            },
        )
        self._session.commit()
        return settle

    def apply_payment_hold(
        self, *, tenant_id: str, entity_id: str, reason: str
    ) -> int:
        """Place a hold on all pending settlements for an entity. Returns count held."""
        settlements = self._session.execute(
            select(Settlement).where(
                Settlement.tenant_id == tenant_id,
                Settlement.pay_to_entity_id == entity_id,
                Settlement.status == "pending",
            )
        ).scalars().all()

        for s in settlements:
            s.is_held = True
            s.hold_reason = reason

        self._session.commit()
        return len(settlements)

    def release_payment_hold(
        self, *, tenant_id: str, entity_id: str
    ) -> int:
        """Release holds for an entity. Returns count released."""
        settlements = self._session.execute(
            select(Settlement).where(
                Settlement.tenant_id == tenant_id,
                Settlement.pay_to_entity_id == entity_id,
                Settlement.is_held.is_(True),
            )
        ).scalars().all()

        for s in settlements:
            s.is_held = False
            s.hold_reason = None

        self._session.commit()
        return len(settlements)
