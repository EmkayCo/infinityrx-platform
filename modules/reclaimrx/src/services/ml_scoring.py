"""ML scoring services for ReclaimRx.

- XGBoostClaimScorer: claim-level fraud risk scoring
- IsolationForestPharmacyScorer: pharmacy anomaly detection (unsupervised)

Money fields NEVER use float. numpy arrays used ONLY for ML feature vectors.
All Decimal inputs are converted to float ONLY at the boundary (to_numpy()),
and results are returned as int (risk scores 0-100).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from xgboost import XGBClassifier


@dataclass
class ClaimFeatures:
    """Claim feature set for XGBoost scoring. All stored as Decimal for precision."""

    nq_to_wac_ratio: Decimal
    dv_to_awp_ratio: Decimal
    claim_amount_percentile: Decimal
    days_since_last_fill: int
    pharmacy_volume_percentile_ndc: Decimal
    pharmacy_reversal_rate: Decimal
    prescriber_volume_percentile_ndc: Decimal
    member_fill_frequency_days: Decimal
    geo_distance_miles: Decimal
    day_of_week: int
    claim_vs_pharmacy_avg_ratio: Decimal
    ndc_concentration_at_pharmacy: Decimal

    def to_numpy(self) -> np.ndarray:
        """Convert to float numpy array for ML inference. ONLY allowed use of float."""
        return np.array([
            float(self.nq_to_wac_ratio),
            float(self.dv_to_awp_ratio),
            float(self.claim_amount_percentile),
            float(self.days_since_last_fill),
            float(self.pharmacy_volume_percentile_ndc),
            float(self.pharmacy_reversal_rate),
            float(self.prescriber_volume_percentile_ndc),
            float(self.member_fill_frequency_days),
            float(self.geo_distance_miles),
            float(self.day_of_week),
            float(self.claim_vs_pharmacy_avg_ratio),
            float(self.ndc_concentration_at_pharmacy),
        ], dtype=np.float32)


@dataclass
class PharmacyFeatures:
    """Pharmacy feature set for Isolation Forest scoring."""

    avg_daily_claims: Decimal
    reversal_rate: Decimal
    weekend_holiday_rate: Decimal
    ndc_diversity_score: Decimal
    avg_nq_to_wac_ratio: Decimal
    controlled_substance_rate: Decimal
    new_patient_rate: Decimal
    avg_claim_amount: Decimal
    rejection_rate: Decimal
    percentile_rank_volume: int
    percentile_rank_claim_value: int
    percentile_rank_reversal_rate: int

    def to_numpy(self) -> np.ndarray:
        return np.array([
            float(self.avg_daily_claims),
            float(self.reversal_rate),
            float(self.weekend_holiday_rate),
            float(self.ndc_diversity_score),
            float(self.avg_nq_to_wac_ratio),
            float(self.controlled_substance_rate),
            float(self.new_patient_rate),
            float(self.avg_claim_amount),
            float(self.rejection_rate),
            float(self.percentile_rank_volume),
            float(self.percentile_rank_claim_value),
            float(self.percentile_rank_reversal_rate),
        ], dtype=np.float32)


CLAIM_FEATURE_NAMES = [
    "nq_to_wac_ratio",
    "dv_to_awp_ratio",
    "claim_amount_percentile",
    "days_since_last_fill",
    "pharmacy_volume_percentile_ndc",
    "pharmacy_reversal_rate",
    "prescriber_volume_percentile_ndc",
    "member_fill_frequency_days",
    "geo_distance_miles",
    "day_of_week",
    "claim_vs_pharmacy_avg_ratio",
    "ndc_concentration_at_pharmacy",
]

PHARMACY_FEATURE_NAMES = [
    "avg_daily_claims",
    "reversal_rate",
    "weekend_holiday_rate",
    "ndc_diversity_score",
    "avg_nq_to_wac_ratio",
    "controlled_substance_rate",
    "new_patient_rate",
    "avg_claim_amount",
    "rejection_rate",
    "percentile_rank_volume",
    "percentile_rank_claim_value",
    "percentile_rank_reversal_rate",
]


class ClaimFeatureExtractor:
    """Extracts ClaimFeatures from a raw claim dict."""

    FEATURE_COUNT = len(CLAIM_FEATURE_NAMES)

    def extract(self, data: dict[str, Any]) -> ClaimFeatures:
        def dec(key: str, default: Any = "0") -> Decimal:
            val = data.get(key, default)
            return Decimal(str(val))

        def int_val(key: str, default: int = 0) -> int:
            val = data.get(key, default)
            return int(val)

        return ClaimFeatures(
            nq_to_wac_ratio=dec("nq_to_wac_ratio"),
            dv_to_awp_ratio=dec("dv_to_awp_ratio"),
            claim_amount_percentile=dec("claim_amount_percentile"),
            days_since_last_fill=int_val("days_since_last_fill"),
            pharmacy_volume_percentile_ndc=dec("pharmacy_volume_percentile_ndc"),
            pharmacy_reversal_rate=dec("pharmacy_reversal_rate"),
            prescriber_volume_percentile_ndc=dec("prescriber_volume_percentile_ndc"),
            member_fill_frequency_days=dec("member_fill_frequency_days"),
            geo_distance_miles=dec("geo_distance_miles"),
            day_of_week=int_val("day_of_week"),
            claim_vs_pharmacy_avg_ratio=dec("claim_vs_pharmacy_avg_ratio"),
            ndc_concentration_at_pharmacy=dec("ndc_concentration_at_pharmacy"),
        )


def _generate_training_data(n_samples: int, random_seed: int, fraud_rate: float = 0.05) -> tuple[np.ndarray, np.ndarray]:
    """Generate synthetic training data for base model. Deterministic via seed."""
    rng = np.random.default_rng(random_seed)
    X = rng.standard_normal((n_samples, len(CLAIM_FEATURE_NAMES))).astype(np.float32)
    # Clip features to realistic ranges
    X[:, 0] = np.clip(X[:, 0] * 0.2 + 1.0, 0.5, 3.0)  # nq_to_wac_ratio
    X[:, 1] = np.clip(X[:, 1] * 0.1 + 0.85, 0.5, 1.5)  # dv_to_awp_ratio
    X[:, 2] = np.clip(X[:, 2] * 0.2 + 0.5, 0.0, 1.0)   # claim_amount_percentile

    # Label: fraud when nq_to_wac_ratio > 1.5 (simplistic base rule)
    y = (X[:, 0] > 1.5).astype(np.int32)
    # Add random fraud labels
    random_fraud = rng.random(n_samples) < fraud_rate
    y = np.logical_or(y, random_fraud).astype(np.int32)
    return X, y


class XGBoostClaimScorer:
    """XGBoost classifier for claim fraud risk scoring.

    Ships with a base model trained on synthetic data.
    Per-tenant retraining happens when labeled outcomes are available.
    Deterministic via random_seed.
    """

    def __init__(self, random_seed: int = 42, n_training_samples: int = 5000) -> None:
        self._seed = random_seed
        self._model = XGBClassifier(
            n_estimators=50,
            max_depth=4,
            learning_rate=0.1,
            random_state=random_seed,
            eval_metric="logloss",
            verbosity=0,
        )
        self._extractor = ClaimFeatureExtractor()
        self._trained = False
        self._fit_base_model(n_training_samples)

    def _fit_base_model(self, n_samples: int) -> None:
        X, y = _generate_training_data(n_samples, self._seed)
        self._model.fit(X, y)
        self._trained = True

    def score(self, claim_data: dict[str, Any]) -> int:
        """Return integer risk score 0-100."""
        features = self._extractor.extract(claim_data)
        arr = features.to_numpy().reshape(1, -1)
        prob = float(self._model.predict_proba(arr)[0][1])
        return min(100, max(0, round(prob * 100)))

    def score_with_importance(
        self, claim_data: dict[str, Any]
    ) -> tuple[int, dict[str, float]]:
        """Return (score, feature_importance_dict) for explainability."""
        score = self.score(claim_data)
        importances = self._model.feature_importances_
        importance_dict = {
            CLAIM_FEATURE_NAMES[i]: float(importances[i])
            for i in range(len(CLAIM_FEATURE_NAMES))
        }
        return score, importance_dict

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Retrain model on labeled outcome data."""
        self._model.fit(X, y)
        self._trained = True


def _generate_pharmacy_training_data(n_samples: int, random_seed: int) -> np.ndarray:
    """Generate synthetic pharmacy profiles for base Isolation Forest fit."""
    rng = np.random.default_rng(random_seed)
    X = rng.standard_normal((n_samples, len(PHARMACY_FEATURE_NAMES))).astype(np.float32)
    X[:, 0] = np.clip(X[:, 0] * 20 + 50, 0, 500)      # avg_daily_claims
    X[:, 1] = np.clip(X[:, 1] * 0.05 + 0.03, 0, 1)    # reversal_rate
    X[:, 2] = np.clip(X[:, 2] * 0.05 + 0.12, 0, 1)    # weekend_holiday_rate
    return X


class IsolationForestPharmacyScorer:
    """Isolation Forest for pharmacy anomaly detection.

    Unsupervised — no labeled data required. Works from day one.
    Deterministic via random_seed.
    """

    def __init__(self, random_seed: int = 42, n_estimators: int = 100) -> None:
        self._seed = random_seed
        self._model = IsolationForest(
            n_estimators=n_estimators,
            random_state=random_seed,
            contamination=0.05,
        )
        self._fitted = False
        self._fit_base_model()

    def _fit_base_model(self) -> None:
        X = _generate_pharmacy_training_data(2000, self._seed)
        self._model.fit(X)
        self._fitted = True

    def fit(self, pharmacy_data_list: list[dict[str, Any]]) -> None:
        """Retrain on actual pharmacy profile data."""
        arrays = [self._extract(p) for p in pharmacy_data_list]
        X = np.stack(arrays)
        self._model.fit(X)
        self._fitted = True

    def score(self, pharmacy_data: dict[str, Any]) -> int:
        """Return anomaly risk score 0-100. Higher = more anomalous."""
        arr = self._extract(pharmacy_data).reshape(1, -1)
        raw_score = float(self._model.decision_function(arr)[0])
        # decision_function: positive = normal, negative = anomalous
        # Map to 0-100: anomalous → high score
        normalized = max(0.0, min(1.0, (0.5 - raw_score)))
        return round(normalized * 100)

    def score_batch(self, pharmacy_data_list: list[dict[str, Any]]) -> list[int]:
        arrays = [self._extract(p) for p in pharmacy_data_list]
        X = np.stack(arrays)
        raw_scores = self._model.decision_function(X)
        return [
            round(max(0.0, min(1.0, 0.5 - float(s))) * 100)
            for s in raw_scores
        ]

    def _extract(self, data: dict[str, Any]) -> np.ndarray:
        def fval(key: str, default: float = 0.0) -> float:
            val = data.get(key, default)
            return float(str(val))

        return np.array([
            fval("avg_daily_claims"),
            fval("reversal_rate"),
            fval("weekend_holiday_rate"),
            fval("ndc_diversity_score"),
            fval("avg_nq_to_wac_ratio"),
            fval("controlled_substance_rate"),
            fval("new_patient_rate"),
            fval("avg_claim_amount"),
            fval("rejection_rate"),
            fval("percentile_rank_volume"),
            fval("percentile_rank_claim_value"),
            fval("percentile_rank_reversal_rate"),
        ], dtype=np.float32)
