"""Tests for tables.py — SP-3 extension columns and new model classes.

The Werkbench enforce_test_first hook looks for `tests/test_tables.py`
(one-level nesting). Deep coverage of the six new model classes is in:

  tests/unit/test_new_models_instantiate.py
  tests/unit/test_model_indexes.py

This file covers:
1. SP-3 extensions to existing models (Investigation, PaymentHold).
2. Structural smoke tests for all six new SP-3 model classes.
"""
from __future__ import annotations

from sqlalchemy import Numeric, inspect

from src.models.tables import (
    AccumulatorAnomaly,
    CorrectiveActionItem,
    FraudRing,
    GraphRun,
    Investigation,
    OutboxEvent,
    PaymentHold,
    ThresholdConfig,
    ThresholdConfigAudit,
)


# ---------------------------------------------------------------------------
# Investigation — existing model smoke tests
# ---------------------------------------------------------------------------

def test_investigation_tablename():
    assert Investigation.__tablename__ == "reclaimrx_investigations"


def test_payment_hold_tablename():
    assert PaymentHold.__tablename__ == "reclaimrx_payment_holds"


# ---------------------------------------------------------------------------
# Investigation — SP-3 extension columns (12 new from migration 0008)
# ---------------------------------------------------------------------------

def test_investigation_sp3_columns_present():
    """All 12 new SP-3 scalar columns must be on Investigation."""
    cols = {c.name for c in inspect(Investigation).columns}
    required_new = {
        "severity", "source", "source_ref_id", "member_id",
        "opened_by", "closed_at", "closed_by", "outcome_label",
        "recovered_amount", "hold_amount",
        "threshold_config_version", "threshold_snapshot",
    }
    assert required_new.issubset(cols), f"Missing SP-3 columns: {required_new - cols}"


def test_investigation_recovered_amount_is_numeric():
    """financial-precision.md: recovered_amount must be Numeric, never Float."""
    col = next(c for c in inspect(Investigation).columns if c.name == "recovered_amount")
    assert isinstance(col.type, Numeric), "recovered_amount must be sa.Numeric"
    assert col.nullable


def test_investigation_hold_amount_is_numeric():
    """financial-precision.md: hold_amount must be Numeric, never Float."""
    col = next(c for c in inspect(Investigation).columns if c.name == "hold_amount")
    assert isinstance(col.type, Numeric), "hold_amount must be sa.Numeric"
    assert col.nullable


def test_investigation_outcome_label_nullable():
    col = next(c for c in inspect(Investigation).columns if c.name == "outcome_label")
    assert col.nullable, "outcome_label is null until investigation is closed"


def test_investigation_severity_nullable():
    col = next(c for c in inspect(Investigation).columns if c.name == "severity")
    assert col.nullable, "severity is nullable (populated by detection pipeline)"


# ---------------------------------------------------------------------------
# PaymentHold — SP-3 extension column (status)
# ---------------------------------------------------------------------------

def test_payment_hold_status_column_present():
    """PaymentHold must have status column for idempotency (audit §10)."""
    cols = {c.name for c in inspect(PaymentHold).columns}
    assert "status" in cols, "PaymentHold must have status column"


def test_payment_hold_status_not_nullable():
    col = next(c for c in inspect(PaymentHold).columns if c.name == "status")
    assert not col.nullable, "PaymentHold.status must be NOT NULL"


def test_payment_hold_status_has_default():
    col = next(c for c in inspect(PaymentHold).columns if c.name == "status")
    assert col.default is not None or col.server_default is not None, \
        "PaymentHold.status must have a default of 'active'"


def test_payment_hold_existing_release_columns_preserved():
    """BLOCK 1: released_by, released_at, release_reason ALREADY EXIST — must not be removed."""
    cols = {c.name for c in inspect(PaymentHold).columns}
    for col_name in ("released_by", "released_at", "release_reason"):
        assert col_name in cols, f"Pre-existing column {col_name} must not be removed"


# ---------------------------------------------------------------------------
# New SP-3 model classes — structural smoke tests
# ---------------------------------------------------------------------------

def test_graph_run_tablename():
    assert GraphRun.__tablename__ == "reclaimrx_graph_runs"


def test_fraud_ring_tablename():
    assert FraudRing.__tablename__ == "reclaimrx_fraud_rings"


def test_accumulator_anomaly_tablename():
    assert AccumulatorAnomaly.__tablename__ == "reclaimrx_accumulator_anomalies"


def test_threshold_config_tablename():
    assert ThresholdConfig.__tablename__ == "reclaimrx_threshold_configs"


def test_threshold_config_audit_tablename():
    assert ThresholdConfigAudit.__tablename__ == "reclaimrx_threshold_config_audits"


def test_outbox_event_tablename():
    assert OutboxEvent.__tablename__ == "reclaimrx_outbox_events"


def test_fraud_ring_density_score_is_numeric():
    """financial-precision.md: density_score must be Numeric(8,4), never Float."""
    col = inspect(FraudRing).columns["density_score"]
    assert isinstance(col.type, Numeric)
    assert col.type.precision == 8
    assert col.type.scale == 4


def test_threshold_config_numeric_columns():
    """financial-precision.md: both threshold Decimal columns must be Numeric."""
    cols = {c.name: c for c in inspect(ThresholdConfig).columns}
    for col_name in ("graph_density_threshold", "accumulator_anomaly_sensitivity"):
        assert isinstance(cols[col_name].type, Numeric), f"{col_name} must be Numeric"


def test_threshold_config_audit_entry_hash_not_nullable():
    """hipaa-2026.md: MUST compute entry_hash on EVERY audit log write — NOT NULL."""
    col = next(c for c in inspect(ThresholdConfigAudit).columns if c.name == "entry_hash")
    assert not col.nullable, "entry_hash must be NOT NULL per hipaa-2026.md"


def test_outbox_event_idempotency_key_unique_constraint():
    """OutboxEvent must have UniqueConstraint on idempotency_key."""
    from sqlalchemy import UniqueConstraint
    table = OutboxEvent.__table__
    unique_cols = [
        frozenset(c.name for c in uc.columns)
        for uc in table.constraints
        if isinstance(uc, UniqueConstraint)
    ]
    assert frozenset({"idempotency_key"}) in unique_cols, \
        f"OutboxEvent missing UniqueConstraint on idempotency_key. Found: {unique_cols}"
