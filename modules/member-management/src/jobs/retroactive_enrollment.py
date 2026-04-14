"""Retroactive enrollment detection.

Checks if an enrollment's effective_date is in the past relative to
the enrollment_date. Flags it as retroactive and whether it exceeds
the configurable max_retroactive_days.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RetroactiveCheckResult:
    is_retroactive: bool
    retroactive_days: int
    exceeds_max: bool


class RetroactiveEnrollmentDetector:
    def __init__(self, max_retroactive_days: int = 90) -> None:
        self._max_days = max_retroactive_days

    def check(
        self,
        effective_date: date,
        enrollment_date: date,
    ) -> RetroactiveCheckResult:
        delta = (enrollment_date - effective_date).days
        is_retroactive = delta > 0
        exceeds_max = delta > self._max_days if is_retroactive else False
        return RetroactiveCheckResult(
            is_retroactive=is_retroactive,
            retroactive_days=delta if is_retroactive else 0,
            exceeds_max=exceeds_max,
        )
