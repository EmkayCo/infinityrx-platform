"""Pass-through ledger service (CAA 2026 compliance).

100% pass-through: every rebate dollar received from manufacturer must
be passed through to the plan sponsor, tracked at NDC-11 level.

Hash chain guarantees immutability: any tamper attempt breaks the chain.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.models.tables import (
    PassThroughEntry,
    PassThroughReconciliation,
    RebateTransaction,
)
from src.utils.hash_chain import GENESIS_HASH, compute_entry_hash
from src.utils.money import ZERO, money

PASS_THROUGH_TOLERANCE = Decimal("0.00")  # must be exactly zero — CAA 2026


class PassThroughError(ValueError):
    """Raised when pass-through amounts do not balance."""


class PassThroughService:
    """Manages the dollar-for-dollar pass-through ledger."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def _get_prev_entry_hash(self, tenant_id: uuid.UUID) -> str:
        last = (
            self._db.query(PassThroughEntry)
            .filter(PassThroughEntry.tenant_id == tenant_id)
            .order_by(PassThroughEntry.created_at.desc())
            .first()
        )
        return last.entry_hash if last else GENESIS_HASH

    def record_pass_through(
        self,
        tenant_id: uuid.UUID,
        transaction_id: uuid.UUID,
        ndc11: str,
        period_month: date,
        sponsor_id: uuid.UUID,
        manufacturer_received: Decimal,
        sponsor_passed: Decimal,
        rebate_category: str,
        remittance_date: date | None = None,
    ) -> PassThroughEntry:
        """Record a pass-through entry and validate dollar-for-dollar balance.

        Raises:
            PassThroughError: if sponsor_passed != manufacturer_received
                              (CAA 2026 requires exact pass-through).
        """
        mfr_recv = money(manufacturer_received)
        spons_passed = money(sponsor_passed)

        difference = (mfr_recv - spons_passed).quantize(
            Decimal("0.01")
        )
        if difference != ZERO:
            raise PassThroughError(
                f"Pass-through imbalance: manufacturer_received={mfr_recv}, "
                f"sponsor_passed={spons_passed}, difference={difference}. "
                "CAA 2026 requires 100% pass-through (zero difference)."
            )

        prev_hash = self._get_prev_entry_hash(tenant_id)
        entry_id = uuid.uuid4()
        now = datetime.now(UTC)

        entry_fields = {
            "id": str(entry_id),
            "tenant_id": str(tenant_id),
            "transaction_id": str(transaction_id),
            "ndc11": ndc11,
            "period_month": period_month.isoformat(),
            "sponsor_id": str(sponsor_id),
            "manufacturer_received": str(mfr_recv),
            "sponsor_passed": str(spons_passed),
            "rebate_category": rebate_category,
        }
        entry_hash = compute_entry_hash(prev_hash, entry_fields)

        entry = PassThroughEntry(
            id=entry_id,
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            ndc11=ndc11,
            period_month=period_month,
            sponsor_id=sponsor_id,
            manufacturer_received=mfr_recv,
            sponsor_passed=spons_passed,
            rebate_category=rebate_category,
            remittance_date=remittance_date,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            created_at=now,
        )
        self._db.add(entry)
        self._db.flush()
        return entry

    def reconcile_month(
        self,
        tenant_id: uuid.UUID,
        sponsor_id: uuid.UUID,
        period_month: date,
        reconciled_by: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> PassThroughReconciliation:
        """Reconcile all pass-through entries for a sponsor/month.

        Aggregates all entries and verifies total_received == total_passed.
        Records the reconciliation result (is_balanced flag).
        """
        from sqlalchemy import func

        rows = (
            self._db.query(
                func.sum(PassThroughEntry.manufacturer_received).label("total_received"),
                func.sum(PassThroughEntry.sponsor_passed).label("total_passed"),
            )
            .filter(
                PassThroughEntry.tenant_id == tenant_id,
                PassThroughEntry.sponsor_id == sponsor_id,
                PassThroughEntry.period_month == period_month,
            )
            .first()
        )

        total_received = money(
            Decimal(str(rows.total_received)) if rows.total_received else ZERO
        )
        total_passed = money(
            Decimal(str(rows.total_passed)) if rows.total_passed else ZERO
        )
        difference = money(total_received - total_passed)
        is_balanced = difference == ZERO

        now = datetime.now(UTC)
        # Upsert reconciliation record
        existing = (
            self._db.query(PassThroughReconciliation)
            .filter(
                PassThroughReconciliation.tenant_id == tenant_id,
                PassThroughReconciliation.sponsor_id == sponsor_id,
                PassThroughReconciliation.period_month == period_month,
            )
            .first()
        )
        if existing:
            existing.total_received = total_received
            existing.total_passed = total_passed
            existing.difference = difference
            existing.is_balanced = is_balanced
            existing.reconciled_by = reconciled_by
            existing.reconciled_at = now
            existing.notes = notes
            self._db.flush()
            return existing

        recon = PassThroughReconciliation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            sponsor_id=sponsor_id,
            period_month=period_month,
            total_received=total_received,
            total_passed=total_passed,
            difference=difference,
            is_balanced=is_balanced,
            reconciled_by=reconciled_by,
            reconciled_at=now,
            notes=notes,
            created_at=now,
        )
        self._db.add(recon)
        self._db.flush()
        return recon

    def get_entries(
        self,
        tenant_id: uuid.UUID,
        sponsor_id: uuid.UUID | None = None,
        period_month: date | None = None,
        ndc11: str | None = None,
    ) -> list[PassThroughEntry]:
        q = self._db.query(PassThroughEntry).filter(
            PassThroughEntry.tenant_id == tenant_id
        )
        if sponsor_id:
            q = q.filter(PassThroughEntry.sponsor_id == sponsor_id)
        if period_month:
            q = q.filter(PassThroughEntry.period_month == period_month)
        if ndc11:
            q = q.filter(PassThroughEntry.ndc11 == ndc11)
        return q.order_by(PassThroughEntry.created_at).all()
