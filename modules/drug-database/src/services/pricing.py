"""Drug pricing service — effective date resolution and price change detection.

All monetary values use Decimal with ROUND_HALF_UP. No floats.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


class PricingService:
    """Pure-function pricing utilities (stateless — no DB access)."""

    @staticmethod
    def select_effective_price(
        prices: list[dict[str, Any]],
        requested_date: date,
    ) -> dict[str, Any] | None:
        """Return the most recent price effective on or before requested_date.

        Excludes prices whose termination_date <= requested_date.
        Returns None if no qualifying price exists.
        """
        candidates = [
            p
            for p in prices
            if p["effective_date"] <= requested_date
            and (p.get("termination_date") is None or p["termination_date"] > requested_date)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p["effective_date"])

    @staticmethod
    def resolve_price(
        standard_prices: list[dict[str, Any]],
        override_prices: list[dict[str, Any]],
        requested_date: date,
    ) -> dict[str, Any] | None:
        """Resolve effective price: tenant override first, then standard."""
        if override_prices:
            result = PricingService.select_effective_price(override_prices, requested_date)
            if result is not None:
                return result
        return PricingService.select_effective_price(standard_prices, requested_date)


@dataclass(frozen=True)
class PriceChangeResult:
    old_price: Decimal
    new_price: Decimal
    change_pct: Decimal
    is_significant: bool


class PriceChangeDetector:
    """Detects significant drug price changes."""

    @staticmethod
    def compute_change(
        old_price: Decimal,
        new_price: Decimal,
        threshold_pct: Decimal,
    ) -> PriceChangeResult:
        """Compute price change percentage and significance.

        A change is significant if abs(change_pct) > threshold_pct.
        Returns is_significant=False if old_price is zero to avoid division error.
        """
        if old_price == Decimal("0"):
            return PriceChangeResult(
                old_price=old_price,
                new_price=new_price,
                change_pct=Decimal("0"),
                is_significant=False,
            )

        raw_pct = (new_price - old_price) / old_price * Decimal("100")
        change_pct = raw_pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        is_significant = abs(change_pct) > threshold_pct

        return PriceChangeResult(
            old_price=old_price,
            new_price=new_price,
            change_pct=change_pct,
            is_significant=is_significant,
        )
