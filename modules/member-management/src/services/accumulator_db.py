"""DB-integrated accumulator service.

Wires AccumulatorService math to Accumulator + AccumulatorLedger ORM rows.
Every apply/reverse/reset writes a ledger row with running_total.

Financial precision: all amounts Decimal + ROUND_HALF_UP. Zero floats.
100% branch coverage required on all financial paths.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from shared.utils.money import TWO_PLACES, ZERO
from src.models.tables import Accumulator, AccumulatorLedger
from src.services.accumulator import AccumulatorService


class AccumulatorNotFoundError(LookupError):
    pass


class LedgerInvariantError(RuntimeError):
    pass


_svc = AccumulatorService()


def _d(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class AccumulatorDbService:
    """Stateless DB service — applies accumulator math and persists results."""

    def _get_accumulator(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        accumulator_id: uuid.UUID,
    ) -> Accumulator:
        acc = (
            db.query(Accumulator)
            .filter_by(id=accumulator_id, tenant_id=tenant_id)
            .first()
        )
        if acc is None:
            raise AccumulatorNotFoundError(
                f"Accumulator {accumulator_id} not found for tenant {tenant_id}"
            )
        return acc

    def _write_ledger(
        self,
        db: Session,
        *,
        accumulator_id: uuid.UUID,
        tenant_id: uuid.UUID,
        transaction_type: str,
        amount: Decimal,
        running_total: Decimal,
        claim_id: uuid.UUID | None = None,
        claim_auth_number: str | None = None,
        description: str | None = None,
    ) -> AccumulatorLedger:
        row = AccumulatorLedger(
            id=uuid.uuid4(),
            accumulator_id=accumulator_id,
            tenant_id=tenant_id,
            transaction_type=transaction_type,
            amount=_d(amount),
            running_total=_d(running_total),
            claim_id=claim_id,
            claim_auth_number=claim_auth_number,
            description=description,
        )
        db.add(row)
        db.flush()
        return row

    def apply_claim(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        accumulator_id: uuid.UUID,
        amount: Decimal,
        claim_id: uuid.UUID | None = None,
        claim_auth_number: str | None = None,
    ) -> AccumulatorLedger:
        """Apply amount toward accumulator. Writes ledger row. Returns the row."""
        acc = self._get_accumulator(db, tenant_id, accumulator_id)

        result = _svc.apply_claim(
            accumulated=_d(acc.accumulated_amount),
            limit=_d(acc.limit_amount),
            amount=_d(amount),
        )

        acc.accumulated_amount = result.new_accumulated
        acc.remaining_amount = _d(acc.limit_amount - result.new_accumulated)
        acc.last_updated_claim_id = claim_id
        acc.last_updated_at = datetime.now(UTC)
        db.flush()

        return self._write_ledger(
            db,
            accumulator_id=accumulator_id,
            tenant_id=tenant_id,
            transaction_type="claim_applied",
            amount=result.applied,
            running_total=result.new_accumulated,
            claim_id=claim_id,
            claim_auth_number=claim_auth_number,
        )

    def reverse_claim(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        accumulator_id: uuid.UUID,
        amount: Decimal,
        claim_id: uuid.UUID | None = None,
        claim_auth_number: str | None = None,
    ) -> AccumulatorLedger:
        """Reverse amount from accumulator. Writes ledger row of type claim_reversed."""
        acc = self._get_accumulator(db, tenant_id, accumulator_id)

        result = _svc.reverse_claim(
            accumulated=_d(acc.accumulated_amount),
            amount=_d(amount),
        )

        acc.accumulated_amount = result.new_accumulated
        acc.remaining_amount = _d(acc.limit_amount - result.new_accumulated)
        acc.last_updated_claim_id = claim_id
        acc.last_updated_at = datetime.now(UTC)
        db.flush()

        return self._write_ledger(
            db,
            accumulator_id=accumulator_id,
            tenant_id=tenant_id,
            transaction_type="claim_reversed",
            amount=_d(-result.reversed),
            running_total=result.new_accumulated,
            claim_id=claim_id,
            claim_auth_number=claim_auth_number,
        )

    def reset_benefit_year(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        accumulator_id: uuid.UUID,
        carryover_amount: Decimal = ZERO,
        description: str | None = None,
    ) -> AccumulatorLedger:
        """Reset accumulator at benefit year boundary. Writes benefit_year_reset ledger row."""
        acc = self._get_accumulator(db, tenant_id, accumulator_id)

        result = _svc.reset_for_benefit_year(
            accumulated=_d(acc.accumulated_amount),
            carryover_amount=_d(carryover_amount),
        )

        delta = _d(result.new_accumulated - acc.accumulated_amount)
        acc.accumulated_amount = result.new_accumulated
        acc.remaining_amount = _d(acc.limit_amount - result.new_accumulated)
        acc.last_updated_at = datetime.now(UTC)
        db.flush()

        return self._write_ledger(
            db,
            accumulator_id=accumulator_id,
            tenant_id=tenant_id,
            transaction_type="benefit_year_reset",
            amount=delta,
            running_total=result.new_accumulated,
            description=description or "benefit year reset",
        )

    def verify_ledger_invariant(
        self,
        db: Session,
        accumulator_id: uuid.UUID,
    ) -> None:
        """Verify running_total == cumulative sum of amounts. Raises on corruption."""
        rows = (
            db.query(AccumulatorLedger)
            .filter_by(accumulator_id=accumulator_id)
            .order_by(AccumulatorLedger.created_at)
            .all()
        )
        cumulative = ZERO
        for row in rows:
            cumulative = _d(cumulative + row.amount)
            if row.running_total != cumulative:
                raise LedgerInvariantError(
                    f"Ledger invariant violated for accumulator {accumulator_id}: "
                    f"running_total={row.running_total} != cumulative={cumulative}"
                )
