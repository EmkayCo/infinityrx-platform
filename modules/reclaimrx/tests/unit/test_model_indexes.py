"""Verify indexes declared on new ORM models match the spec requirements.

These run against SQLite so no PostgreSQL is required. They verify the
__table_args__ declarations on each new model class.

per .claude/rules/performance.md:
  - (tenant_id, status) for every table with a status column
  - (tenant_id, FK column) for every tenant-scoped FK

R2 CONCERN 5 fix — module-level imports (not function-local) so the import
side-effect of registering each model into Base.metadata happens once at
test collection, before any test runs.
"""
from __future__ import annotations

import pytest
from sqlalchemy import UniqueConstraint

from src.models.tables import (
    AccumulatorAnomaly,
    FraudRing,
    GraphRun,
    OutboxEvent,
    ThresholdConfig,
    ThresholdConfigAudit,
)


def _index_col_sets(table) -> list[tuple[str, ...]]:
    return [tuple(c.name for c in idx.columns) for idx in table.indexes]


def test_graph_run_has_tenant_status_index():
    index_col_sets = _index_col_sets(GraphRun.__table__)
    assert ("tenant_id", "status") in index_col_sets, \
        f"GraphRun missing (tenant_id, status) index. Found: {index_col_sets}"


def test_fraud_ring_has_tenant_run_index():
    index_col_sets = _index_col_sets(FraudRing.__table__)
    assert ("tenant_id", "graph_run_id") in index_col_sets, \
        f"FraudRing missing (tenant_id, graph_run_id) index. Found: {index_col_sets}"


def test_accumulator_anomaly_has_tenant_member_index():
    index_col_sets = _index_col_sets(AccumulatorAnomaly.__table__)
    assert ("tenant_id", "member_id") in index_col_sets, \
        f"AccumulatorAnomaly missing (tenant_id, member_id) index. Found: {index_col_sets}"


def test_threshold_config_audit_has_tenant_config_index():
    index_col_sets = _index_col_sets(ThresholdConfigAudit.__table__)
    assert ("tenant_id", "threshold_config_id") in index_col_sets, \
        f"ThresholdConfigAudit missing (tenant_id, threshold_config_id) index. Found: {index_col_sets}"


def test_outbox_events_has_idempotency_unique_constraint():
    table = OutboxEvent.__table__
    unique_cols = [
        frozenset(c.name for c in uc.columns)
        for uc in table.constraints
        if isinstance(uc, UniqueConstraint)
    ]
    assert frozenset({"idempotency_key"}) in unique_cols, \
        f"OutboxEvent missing UniqueConstraint on idempotency_key. Found: {unique_cols}"


def test_outbox_events_has_status_created_index():
    index_col_sets = _index_col_sets(OutboxEvent.__table__)
    assert ("status", "created_at") in index_col_sets, \
        f"OutboxEvent missing (status, created_at) index. Found: {index_col_sets}"


def test_threshold_config_has_tenant_version_index():
    index_col_sets = _index_col_sets(ThresholdConfig.__table__)
    assert ("tenant_id", "version") in index_col_sets, \
        f"ThresholdConfig missing (tenant_id, version) index. Found: {index_col_sets}"
