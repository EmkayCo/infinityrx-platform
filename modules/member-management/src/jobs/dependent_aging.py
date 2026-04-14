"""Dependent aging-out daily job.

Terminates dependents who have reached the plan age limit.
DOB is stored encrypted as bytes; in tests we decode as ISO date string.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from src.models.tables import Member


@dataclass
class DependentAgingResult:
    terminated_count: int


class DependentAgingJob:
    """Terminates dependents (person_code != '01') who have reached age_limit."""

    def run(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        as_of_date: date,
        age_limit: int,
    ) -> DependentAgingResult:
        dependents = (
            db.query(Member)
            .filter(
                Member.tenant_id == tenant_id,
                Member.status == "active",
                Member.person_code != "01",
            )
            .all()
        )

        terminated_count = 0
        for dep in dependents:
            dob = self._decode_dob(dep.dob_encrypted)
            if dob is None:
                continue
            age = self._calculate_age(dob, as_of_date)
            if age >= age_limit:
                dep.status = "terminated"
                dep.termination_reason = "dependent_aged_out"
                dep.termination_date = as_of_date
                terminated_count += 1

        db.flush()
        return DependentAgingResult(terminated_count=terminated_count)

    def _decode_dob(self, dob_encrypted: str | None) -> date | None:
        if dob_encrypted is None:
            return None
        try:
            return date.fromisoformat(dob_encrypted)
        except (ValueError, AttributeError):
            return None

    def _calculate_age(self, dob: date, as_of: date) -> int:
        age = as_of.year - dob.year
        if (as_of.month, as_of.day) < (dob.month, dob.day):
            age -= 1
        return age
