"""AI Copay Recommender — deterministic rule-based scoring.

Implements a CopayRecommender class with configurable weights so real ML
can be plugged in later. No external API calls — pure rule-based scoring
on drug cost, payer mix, competitive signals, and GTN budget inputs.

Outputs are reproducible: identical inputs → identical recommendations.
This is required by Principle 5 (reproducible outputs) and the PRD §4.

100% coverage required — financial recommendation path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


@dataclass(frozen=True)
class CopayRecommenderWeights:
    """Configurable weights for the copay recommendation algorithm.

    All weights must sum to 1.0. Defaults are reasonable starting points.
    Externalized here so they can be tuned via config without code changes.
    """

    drug_cost_weight: Decimal = Decimal("0.35")
    payer_mix_weight: Decimal = Decimal("0.30")
    competitive_weight: Decimal = Decimal("0.20")
    gtn_budget_weight: Decimal = Decimal("0.15")

    def __post_init__(self) -> None:
        total = (
            self.drug_cost_weight
            + self.payer_mix_weight
            + self.competitive_weight
            + self.gtn_budget_weight
        )
        if total != Decimal("1.00"):
            raise ValueError(
                f"CopayRecommenderWeights must sum to 1.00, got {total}"
            )


@dataclass(frozen=True)
class CopayRecommenderInput:
    """Inputs for the copay recommendation algorithm.

    All money values as Decimal strings (serialized for event bus safety).
    """

    # WAC (wholesale acquisition cost) per 30-day supply
    drug_wac_per_30_day: str
    # Commercial payer mix as fraction [0..1] — e.g. 0.65 means 65% commercial
    commercial_payer_mix_fraction: str
    # Competitive benchmark — average competitor copay for same drug class
    competitive_benchmark_copay: str
    # GTN (gross-to-net) budget limit per patient per year
    gtn_budget_per_patient: str
    # Average fills per patient per year
    avg_fills_per_year: int = 12

    def to_decimals(self) -> dict[str, Decimal]:
        return {
            "drug_wac": Decimal(self.drug_wac_per_30_day),
            "payer_mix": Decimal(self.commercial_payer_mix_fraction),
            "competitive": Decimal(self.competitive_benchmark_copay),
            "gtn_budget": Decimal(self.gtn_budget_per_patient),
        }


@dataclass(frozen=True)
class CopayRecommendation:
    """Output of the copay recommendation algorithm."""

    # Recommended patient copay per fill
    recommended_copay: str
    # Recommended per-fill cap (manufacturer liability per fill)
    recommended_per_fill_cap: str
    # Recommended annual maximum benefit
    recommended_annual_max: str
    # Recommended accumulator strategy
    accumulator_strategy: str  # "standard" | "protected" | "maximizer_block"
    # Explanation of recommendation reasoning
    rationale: dict[str, Any]
    # Score components for each input factor [0..1]
    scores: dict[str, str]


# Accumulator strategy thresholds — configurable constants
_ACCUMULATOR_HIGH_PAYER_MIX_THRESHOLD = Decimal("0.70")
_ACCUMULATOR_LOW_PAYER_MIX_THRESHOLD = Decimal("0.40")

# Copay floor and ceiling (minimum/maximum patient copay recommended)
_COPAY_FLOOR = Decimal("0.00")
_COPAY_CEILING = Decimal("150.00")

# Per-fill cap factor: max(wac * factor, competitive benchmark)
_PER_FILL_CAP_WAC_FACTOR = Decimal("0.10")

# Annual max: budget-driven
_ANNUAL_MAX_BUDGET_FRACTION = Decimal("0.80")


class CopayRecommender:
    """Deterministic rule-based copay recommendation engine.

    Designed as a class so a real ML model can replace ``recommend()``
    without changing the calling interface.

    Weights are injected; defaults are reasonable starting points.
    """

    def __init__(self, weights: CopayRecommenderWeights | None = None) -> None:
        self._weights = weights or CopayRecommenderWeights()

    def recommend(self, inputs: CopayRecommenderInput) -> CopayRecommendation:
        """Compute copay recommendation from structured inputs.

        Algorithm:
          1. Compute a "patient affordability signal" from drug cost:
             lower WAC → lower copay recommendation (drug is affordable)
             higher WAC → allow higher copay (still affordable to manufacturer)
          2. Adjust upward for high commercial payer mix (manufacturer
             saves on rebate offsets when most patients are commercial)
          3. Anchor to competitive benchmark (don't deviate >20%)
          4. Constrain to GTN budget ceiling
          5. Round to nearest dollar (ROUND_HALF_UP)

        All math uses Decimal. Outputs serialized as strings.
        """
        vals = inputs.to_decimals()
        wac = vals["drug_wac"]
        payer_mix = vals["payer_mix"]
        competitive = vals["competitive"]
        gtn_budget = vals["gtn_budget"]
        fills = Decimal(str(inputs.avg_fills_per_year))

        # --- Component scores (normalized 0..1) ---
        # Drug cost score: WAC > $1000/month → score near 1 (high burden)
        # Linear between $0 and $2000
        _wac_ceiling = Decimal("2000.00")
        drug_cost_score = min(wac / _wac_ceiling, Decimal("1.00"))

        # Payer mix score: high commercial → score near 1 (manufacturer can afford subsidy)
        payer_mix_score = payer_mix

        # Competitive score: lower copay vs competitor → score near 1 (favorable)
        # Normalize: competitive range $0–$150
        _comp_ceiling = Decimal("150.00")
        competitive_score = Decimal("1.00") - min(competitive / _comp_ceiling, Decimal("1.00"))

        # GTN budget score: generous budget → score near 1 (can set lower copay)
        # Annual max per patient / fills = per-fill budget
        per_fill_budget = gtn_budget / fills if fills > 0 else Decimal("0")
        _budget_ceiling = Decimal("500.00")
        gtn_score = min(per_fill_budget / _budget_ceiling, Decimal("1.00"))

        w = self._weights

        # Weighted composite score
        composite = (
            drug_cost_score * w.drug_cost_weight
            + payer_mix_score * w.payer_mix_weight
            + competitive_score * w.competitive_weight
            + gtn_score * w.gtn_budget_weight
        )

        # Map composite [0..1] → copay recommendation
        # High composite (high burden drug, high payer mix, low competitor copay, generous budget)
        # → low patient copay ($0–$10)
        # Low composite → higher patient copay ($30–$150)
        # Linear interpolation: copay = ceiling - (composite * range)
        _cop_max = Decimal("75.00")
        raw_copay = _cop_max - (composite * _cop_max)
        # Anchor to competitive benchmark (don't go more than 20% above it)
        _anchor_factor = Decimal("1.20")
        anchored_copay = min(raw_copay, competitive * _anchor_factor)
        # Apply floor/ceiling
        recommended_copay = max(_COPAY_FLOOR, min(_COPAY_CEILING, anchored_copay))
        recommended_copay = recommended_copay.quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

        # Per-fill cap: 10% of WAC or competitive benchmark, whichever is higher
        per_fill_cap = max(
            wac * _PER_FILL_CAP_WAC_FACTOR,
            competitive,
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Annual max: constrained to GTN budget * 80% to leave headroom
        annual_max = (gtn_budget * _ANNUAL_MAX_BUDGET_FRACTION).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Accumulator strategy
        if payer_mix >= _ACCUMULATOR_HIGH_PAYER_MIX_THRESHOLD:
            # Mostly commercial → use standard (accumulators affect most patients)
            strategy = "standard"
        elif payer_mix <= _ACCUMULATOR_LOW_PAYER_MIX_THRESHOLD:
            # Mostly government/other → protect patients from maximizers
            strategy = "protected"
        else:
            # Mixed → block maximizer gaming
            strategy = "maximizer_block"

        rationale = {
            "drug_cost_signal": "high" if drug_cost_score > Decimal("0.5") else "low",
            "payer_mix_commercial": str(payer_mix),
            "competitive_anchor": str(competitive),
            "gtn_budget_utilized_pct": str(
                (recommended_copay * fills / gtn_budget * Decimal("100")).quantize(
                    Decimal("0.1"), rounding=ROUND_HALF_UP
                )
                if gtn_budget > 0
                else Decimal("0")
            ),
            "accumulator_basis": f"commercial_mix={payer_mix}",
        }

        scores = {
            "drug_cost_score": str(drug_cost_score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "payer_mix_score": str(payer_mix_score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "competitive_score": str(competitive_score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "gtn_score": str(gtn_score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            "composite_score": str(composite.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        }

        return CopayRecommendation(
            recommended_copay=str(recommended_copay),
            recommended_per_fill_cap=str(per_fill_cap),
            recommended_annual_max=str(annual_max),
            accumulator_strategy=strategy,
            rationale=rationale,
            scores=scores,
        )
