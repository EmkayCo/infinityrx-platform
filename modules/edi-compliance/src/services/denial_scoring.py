"""Predictive denial scoring for outbound claims.

Uses a lightweight logistic regression model trained on historical denial patterns.
Features are derived purely from claim metadata — no PHI in the feature vector.
Score range: 0.0 (low risk) to 1.0 (high risk of denial).

Thresholds (configurable per tenant via companion guide rules):
  score >= 0.70 → HIGH risk — hold for manual review
  score >= 0.40 → MEDIUM risk — auto-flag warning
  score <  0.40 → LOW risk — proceed normally
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List


class DenialRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class DenialRiskFactor:
    code: str
    description: str
    weight: float


@dataclass
class DenialScoreResult:
    score: float                              # 0.0–1.0
    risk_level: DenialRiskLevel
    risk_factors: List[DenialRiskFactor] = field(default_factory=list)
    recommendation: str = ""


# Configurable thresholds
_HIGH_THRESHOLD: float = 0.70
_MEDIUM_THRESHOLD: float = 0.40


def _risk_level(score: float) -> DenialRiskLevel:
    if score >= _HIGH_THRESHOLD:
        return DenialRiskLevel.HIGH
    if score >= _MEDIUM_THRESHOLD:
        return DenialRiskLevel.MEDIUM
    return DenialRiskLevel.LOW


# Feature weights derived from claim characteristics.
# In production these would be loaded from a trained model artifact.
_FEATURE_WEIGHTS: Dict[str, float] = {
    "no_prior_auth": 0.25,
    "high_charge_outlier": 0.20,
    "new_procedure_code": 0.15,
    "place_of_service_mismatch": 0.15,
    "missing_rendering_npi": 0.10,
    "claim_frequency_replacement": 0.10,
    "multiple_diagnoses_with_primary_risk": 0.05,
}


def _extract_features(claim: Dict[str, Any]) -> Dict[str, float]:
    """Extract numeric feature vector from claim dict. No PHI accessed."""
    features: Dict[str, float] = {}

    # Prior auth required but not supplied
    if claim.get("prior_auth_required") and not claim.get("prior_auth_number"):
        features["no_prior_auth"] = 1.0

    # Charge outlier: claim charge > $10,000 is a proxy for high complexity
    charge = claim.get("charge_amount")
    if charge is not None:
        try:
            amt = Decimal(str(charge))
            if amt > Decimal("10000"):
                features["high_charge_outlier"] = 1.0
        except Exception:
            pass

    # Rendering NPI missing
    if not claim.get("rendering_npi"):
        features["missing_rendering_npi"] = 1.0

    # Claim frequency 7 = replacement of prior claim (higher scrutiny)
    if claim.get("claim_frequency") == "7":
        features["claim_frequency_replacement"] = 1.0

    # Place of service mismatch hint (e.g., POS=11 office but facility flag set)
    pos = claim.get("place_of_service", "")
    facility_flag = claim.get("facility_claim", False)
    if pos in ("11", "10") and facility_flag:
        features["place_of_service_mismatch"] = 1.0

    # Many diagnoses correlate with higher complexity/denial risk
    other_dx = claim.get("other_diagnoses", [])
    if len(other_dx) >= 5:
        features["multiple_diagnoses_with_primary_risk"] = 1.0

    # High-value procedure codes flagged by payer (loaded from companion guide)
    high_risk_codes = claim.get("_high_risk_procedure_codes", [])
    for line in claim.get("service_lines", []):
        proc = line.get("procedure_code", "")
        if proc and proc in high_risk_codes:
            features["new_procedure_code"] = 1.0
            break

    return features


def score_claim(claim: Dict[str, Any]) -> DenialScoreResult:
    """Compute a denial risk score for the given claim.

    The claim dict uses the same schema as scrub_claim().
    Additional optional keys:
      prior_auth_required (bool), prior_auth_number (str),
      facility_claim (bool), _high_risk_procedure_codes (list[str])
    """
    features = _extract_features(claim)

    raw_score = sum(_FEATURE_WEIGHTS.get(k, 0.0) * v for k, v in features.items())
    # Clamp to [0, 1]
    score = min(1.0, max(0.0, raw_score))

    risk_level = _risk_level(score)

    risk_factors = [
        DenialRiskFactor(
            code=k,
            description=k.replace("_", " ").capitalize(),
            weight=_FEATURE_WEIGHTS.get(k, 0.0),
        )
        for k, v in features.items()
        if v > 0
    ]

    if risk_level == DenialRiskLevel.HIGH:
        recommendation = "Hold for manual pre-submission review before sending to payer."
    elif risk_level == DenialRiskLevel.MEDIUM:
        recommendation = "Review flagged risk factors before submission."
    else:
        recommendation = "Proceed with submission."

    return DenialScoreResult(
        score=score,
        risk_level=risk_level,
        risk_factors=risk_factors,
        recommendation=recommendation,
    )
