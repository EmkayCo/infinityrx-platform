"""Drug trend decomposition service.

Decomposes total spend change into utilization, price, and mix effects.
The three components must EXACTLY sum to total_delta (Decimal arithmetic).

Paired-period decomposition formulas:
  Utilization effect = (Q_new - Q_old) * P_old
  Price effect       = (P_new - P_old) * Q_old
  Mix effect         = (Q_new - Q_old) * (P_new - P_old)
  Total delta        = (Q_new * P_new) - (Q_old * P_old)
  Invariant          = util + price + mix == total_delta  (always exact)
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DecompositionResult:
    utilization_effect: Decimal
    price_effect: Decimal
    mix_effect: Decimal
    total_delta: Decimal
    old_spend: Decimal
    new_spend: Decimal


def decompose_drug_trend(
    q_old: Decimal,
    q_new: Decimal,
    p_old: Decimal,
    p_new: Decimal,
) -> DecompositionResult:
    """Decompose drug spend change into utilization, price, and mix effects.

    Args:
        q_old: Claim quantity in the prior period.
        q_new: Claim quantity in the current period.
        p_old: Average per-unit cost in the prior period.
        p_new: Average per-unit cost in the current period.

    Returns:
        DecompositionResult where util + price + mix == total_delta exactly.
    """
    delta_q = q_new - q_old
    delta_p = p_new - p_old

    utilization_effect = delta_q * p_old
    price_effect = delta_p * q_old
    mix_effect = delta_q * delta_p

    old_spend = q_old * p_old
    new_spend = q_new * p_new
    total_delta = new_spend - old_spend

    return DecompositionResult(
        utilization_effect=utilization_effect,
        price_effect=price_effect,
        mix_effect=mix_effect,
        total_delta=total_delta,
        old_spend=old_spend,
        new_spend=new_spend,
    )
