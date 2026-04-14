"""COB (Coordination of Benefits) service.

Manages payer sequencing: primary → secondary → tertiary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class CobSequence(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


_SEQUENCE_ORDER = {
    CobSequence.PRIMARY: 0,
    CobSequence.SECONDARY: 1,
    CobSequence.TERTIARY: 2,
}


class CobServiceError(ValueError):
    pass


@dataclass
class PayerRecord:
    sequence: CobSequence
    effective_date: date
    other_payer_name: str | None = None
    other_payer_bin: str | None = None
    other_payer_pcn: str | None = None
    other_payer_group: str | None = None
    other_payer_member_id: str | None = None
    other_payer_type: str | None = None
    termination_date: date | None = None


class CobService:
    """Stateless COB helpers for payer sequencing and validation."""

    def sort_payers(self, payers: list[PayerRecord]) -> list[PayerRecord]:
        return sorted(payers, key=lambda p: _SEQUENCE_ORDER[p.sequence])

    def get_active_payers(
        self,
        payers: list[PayerRecord],
        as_of: date,
    ) -> list[PayerRecord]:
        active = []
        for p in payers:
            if p.effective_date > as_of:
                continue
            if p.termination_date is not None and as_of > p.termination_date:
                continue
            active.append(p)
        return active

    def validate_sequence(self, payers: list[PayerRecord]) -> None:
        seen: set[CobSequence] = set()
        for p in payers:
            if p.sequence in seen:
                raise CobServiceError(
                    f"duplicate payer sequence: {p.sequence.value}"
                )
            seen.add(p.sequence)
