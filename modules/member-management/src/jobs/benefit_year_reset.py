"""Benefit year reset scheduled job.

Iterates accumulators where benefit_year_end < as_of_date and resets them.
Honors carryover_rules: {accumulator_type: carryover_amount}.
Writes benefit_year_reset ledger entry for each reset.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from shared.utils.money import ZERO
from src.models.tables import Accumulator, CoveragePeriod
from src.services.accumulator_db import AccumulatorDbService


@dataclass
class BenefitYearResetResult:
    reset_count: int


class BenefitYearResetJob:
    """Resets all expired-benefit-year accumulators for a tenant."""

    def run(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        as_of_date: date,
        carryover_rules: dict[str, Decimal],
    ) -> BenefitYearResetResult:
        svc = AccumulatorDbService()
        reset_count = 0

        # Find coverage periods whose benefit year has ended
        expired_coverage_ids = [
            row.id
            for row in db.query(CoveragePeriod.id)
            .filter(
                CoveragePeriod.tenant_id == tenant_id,
                CoveragePeriod.benefit_year_end < as_of_date,
            )
            .all()
        ]

        if not expired_coverage_ids:
            return BenefitYearResetResult(reset_count=0)

        accumulators = (
            db.query(Accumulator)
            .filter(
                Accumulator.tenant_id == tenant_id,
                Accumulator.coverage_period_id.in_(expired_coverage_ids),
            )
            .all()
        )

        for acc in accumulators:
            carryover = carryover_rules.get(acc.accumulator_type, ZERO)
            svc.reset_benefit_year(
                db=db,
                tenant_id=tenant_id,
                accumulator_id=acc.id,
                carryover_amount=carryover,
            )
            reset_count += 1

        return BenefitYearResetResult(reset_count=reset_count)
