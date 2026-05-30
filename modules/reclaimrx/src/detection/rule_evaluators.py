"""Rule evaluators for CSV-based FWA detection.

Pure functions -- no I/O, no DB, no side effects.
Financial precision: Decimal only, never float. ROUND_HALF_UP on every quantize.

Locked WAC/AWP-total semantics (verified by row-level reconciliation):
- extended_wac  is a TOTAL (WAC * quantity already applied). Never divide by qty.
- drug_awp      is a TOTAL.
- nq            = ingredient_cost_paid  (Decimal)
- dv            = dispensing_fee_paid   (Decimal)
- nq_to_wac_ratio = (dv + nq) / extended_wac   [None when extended_wac == 0]
- dv_to_awp_ratio = dv / drug_awp              [None when drug_awp == 0]
- Reversals (transaction_code == "B2"): abs() applied to all amounts before
  ratio computation.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from src.detection.parsing import parse_money

_ZERO = Decimal("0")


def derive_fields(row: dict[str, Any]) -> dict[str, Any]:
    is_reversal = str(row.get("transaction_code", "")).strip().upper() == "B2"

    def _parse(key: str) -> Decimal:
        raw = row.get(key)
        result = parse_money(raw)
        return result if result is not None else _ZERO

    nq: Decimal = _parse("ingredient_cost_paid")
    dv: Decimal = _parse("dispensing_fee_paid")
    extended_wac: Decimal = _parse("extended_wac")
    drug_awp: Decimal = _parse("drug_awp")

    if is_reversal:
        nq = abs(nq)
        dv = abs(dv)
        extended_wac = abs(extended_wac)
        drug_awp = abs(drug_awp)

    nq_to_wac_ratio: Optional[Decimal]
    if extended_wac == _ZERO:
        nq_to_wac_ratio = None
    else:
        nq_to_wac_ratio = (dv + nq) / extended_wac

    dv_to_awp_ratio: Optional[Decimal]
    if drug_awp == _ZERO:
        dv_to_awp_ratio = None
    else:
        dv_to_awp_ratio = dv / drug_awp

    return {
        "nq": nq,
        "dv": dv,
        "nq_to_wac_ratio": nq_to_wac_ratio,
        "dv_to_awp_ratio": dv_to_awp_ratio,
    }
