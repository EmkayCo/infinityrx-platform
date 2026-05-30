"""Seed ML detector placeholder rows for Wave 44b detectors.

Revision ID: 0008_ml_detector_seed
Revises: 0007_flagged_npis
Create Date: 2026-04-30
"""
from __future__ import annotations
from alembic import op

revision = "0008_ml_detector_seed"
down_revision = "0007_flagged_npis"
branch_labels = None
depends_on = None

# (detector_name, feature_schema_class, notes) — exact values from dev.
_DETECTORS = [
    ("pharmacy_behavioral_baseline", "reclaimrx.detection.ml.sklearn_detector.PharmacyFeatures",
     "Pharmacy behavioral drift detector (Wave 44b BEHAV-001). Isolation Forest on pharmacy fill-volume, reversal-rate, NDC-mix metrics. Train via POST /admin/reclaimrx/ml/train."),
    ("member_cohort_outlier", "reclaimrx.detection.ml.sklearn_detector.MemberFeatures",
     "Member cohort outlier detector (Wave 44b BEHAV-002). Isolation Forest on member doctor-shopping, quantity-trajectory and drug-mix within cohort. Train via POST /admin/reclaimrx/ml/train."),
    ("prescriber_baseline", "reclaimrx.detection.ml.sklearn_detector.PrescriberFeatures",
     "Prescriber behavioral baseline detector (Wave 44b BEHAV-003). Isolation Forest on prescriber volume, drug-mix and member-count relative to specialty baseline. Train via POST /admin/reclaimrx/ml/train."),
    ("nq_target_clustering", "reclaimrx.detection.ml.sklearn_detector.NqClusterFeatures",
     "NQ target-cluster ML detector (Wave 44b NQ-008). XGBoost classifier identifying claims whose NQ pattern matches a learned maximizer cluster signature. Train via POST /admin/reclaimrx/ml/train."),
    ("reject_resubmit_pattern", "reclaimrx.detection.ml.sklearn_detector.RejectResubmitFeatures",
     "Reject-resubmit pattern ML detector (Wave 44b REJ-003). XGBoost classifier on pharmacy reject-code cycling sequences to identify artificial override attempts. Train via POST /admin/reclaimrx/ml/train."),
]


def upgrade() -> None:
    for name, fclass, notes in _DETECTORS:
        op.execute(
            "INSERT INTO reclaimrx.ml_detector_registry "
            "(detector_name, detector_version, model_artifact_path, feature_schema_class, "
            " is_placeholder, training_metadata, registered_at, updated_at, notes) "
            f"VALUES ('{name}', '0', NULL, '{fclass}', TRUE, '{{}}', now(), now(), "
            f"'{notes.replace(chr(39), chr(39)+chr(39))}') "
            "ON CONFLICT (detector_name) DO NOTHING"
        )


def downgrade() -> None:
    for name, _f, _n in _DETECTORS:
        op.execute(
            f"DELETE FROM reclaimrx.ml_detector_registry WHERE detector_name = '{name}' "
            "AND is_placeholder = TRUE AND model_artifact_path IS NULL"
        )
