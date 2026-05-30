"""Reflection tests for World-A ORM models (Task 1.1).

Strategy: connect to the live dev Postgres DB (read-only) and reflect each
table's actual column names, then assert exact equality with the ORM model's
mapped column set.

== assertion ==
set(orm_column_names) == set(db_column_names)

This is an EXACT equality check — it catches:
  - columns present in DB but missing from the ORM (would cause silent data loss)
  - columns in ORM but absent from the DB (would raise on INSERT/SELECT)

Run with:
    pytest modules/reclaimrx/tests/detection/test_models_reflect.py -v
"""
from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import class_mapper

# ---------------------------------------------------------------------------
# Import all World-A ORM classes.  This also registers them on the Base
# metadata so the module is fully loaded before any reflection.
# ---------------------------------------------------------------------------
from src.models.detection_run_models import (  # noqa: E402
    Anomaly,
    AnomalyAuditLog,
    BaselineCache,
    CaseAnomalyLink,
    CaseAssignment,
    CaseNumberSequence,
    CsvUploadRow,
    DetectionRuleEvaluationLog,
    DetectionRuleInstance,
    DetectionRuleType,
    DetectionRun,
    FlaggedNpi,
    MlDetectorRegistry,
    MlTrainingRun,
    RecoupCase,
)

_PG_URL = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_dev"
_SCHEMA = "reclaimrx"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _orm_column_names(model_class) -> set[str]:
    """Return the set of DB column names mapped by a SQLAlchemy ORM class."""
    mapper = class_mapper(model_class)
    return {col.key for col in mapper.columns}


def _db_column_names(insp: sa.engine.Inspector, table_name: str) -> set[str]:
    """Return the set of column names as reflected from the live database."""
    cols = insp.get_columns(table_name, schema=_SCHEMA)
    return {c["name"] for c in cols}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pg_inspector():
    """One-shot Postgres connection for the whole module; read-only."""
    engine = sa.create_engine(_PG_URL, future=True)
    insp = sa.inspect(engine)
    yield insp
    engine.dispose()


# ---------------------------------------------------------------------------
# Per-table reflection tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_class,table_name",
    [
        (DetectionRun, "detection_runs"),
        (CsvUploadRow, "csv_upload_rows"),
        (Anomaly, "anomalies"),
        (AnomalyAuditLog, "anomaly_audit_log"),
        (DetectionRuleType, "detection_rule_types"),
        (DetectionRuleInstance, "detection_rule_instances"),
        (DetectionRuleEvaluationLog, "detection_rule_evaluation_log"),
        (BaselineCache, "baseline_cache"),
        (MlDetectorRegistry, "ml_detector_registry"),
        (MlTrainingRun, "ml_training_runs"),
        (FlaggedNpi, "flagged_npis"),
        (RecoupCase, "recoup_cases"),
        (CaseAssignment, "case_assignments"),
        (CaseAnomalyLink, "case_anomaly_links"),
        (CaseNumberSequence, "case_number_sequences"),
    ],
)
def test_orm_columns_exactly_match_db(pg_inspector, model_class, table_name):
    """ORM column set must equal DB column set — no extras, no missing."""
    orm_cols = _orm_column_names(model_class)
    db_cols = _db_column_names(pg_inspector, table_name)

    missing_from_orm = db_cols - orm_cols
    extra_in_orm = orm_cols - db_cols

    assert not missing_from_orm, (
        f"{model_class.__name__}: DB has columns not in ORM: {missing_from_orm}"
    )
    assert not extra_in_orm, (
        f"{model_class.__name__}: ORM has columns not in DB: {extra_in_orm}"
    )
    # Exact equality: both sides are empty simultaneously
    assert orm_cols == db_cols


def test_global_tables_have_no_tenant_id_column():
    """detection_rule_types and ml_detector_registry are global; no tenant_id."""
    for model_class in (DetectionRuleType, MlDetectorRegistry):
        cols = _orm_column_names(model_class)
        assert "tenant_id" not in cols, (
            f"{model_class.__name__} is a global table but has tenant_id"
        )


def test_tenant_tables_have_tenant_id_column():
    """All tenant-scoped tables must expose tenant_id in their ORM mapping."""
    tenant_models = [
        DetectionRun,
        CsvUploadRow,
        Anomaly,
        AnomalyAuditLog,
        DetectionRuleInstance,
        DetectionRuleEvaluationLog,
        BaselineCache,
        MlTrainingRun,
        FlaggedNpi,
        RecoupCase,
        CaseAssignment,
        CaseAnomalyLink,
        CaseNumberSequence,
    ]
    for model_class in tenant_models:
        cols = _orm_column_names(model_class)
        assert "tenant_id" in cols, (
            f"{model_class.__name__} is tenant-scoped but lacks tenant_id"
        )


def test_money_columns_are_numeric_not_float():
    """Financial-precision rule: money columns must be Numeric, never Float."""
    money_checks = [
        (RecoupCase, "total_amount_at_risk"),
        (RecoupCase, "total_recovered"),
        (Anomaly, "amount_paid"),
        (Anomaly, "amount_billed"),
        (Anomaly, "confidence"),
        (Anomaly, "recovery_amount"),
        (BaselineCache, "mean"),
        (BaselineCache, "stddev"),
    ]
    for model_class, col_name in money_checks:
        mapper = class_mapper(model_class)
        col = next((c for c in mapper.columns if c.key == col_name), None)
        assert col is not None, f"{model_class.__name__}.{col_name} not found in ORM"
        assert isinstance(col.type, sa.Numeric), (
            f"{model_class.__name__}.{col_name} is {type(col.type).__name__}, expected Numeric"
        )


def test_schema_is_reclaimrx_on_all_models():
    """All models must declare schema='reclaimrx' in __table_args__.

    Reads schema from class.__table_args__ rather than the live SQLAlchemy
    table object, which may have been mutated to None by the SQLite compat
    fixture (_sqlite_compat_swap zeroes schemas for SQLite compatibility).
    """
    all_models = [
        DetectionRun, CsvUploadRow, Anomaly, AnomalyAuditLog,
        DetectionRuleType, DetectionRuleInstance, DetectionRuleEvaluationLog,
        BaselineCache, MlDetectorRegistry, MlTrainingRun,
        FlaggedNpi, RecoupCase, CaseAssignment, CaseAnomalyLink,
        CaseNumberSequence,
    ]
    for model_class in all_models:
        # Read schema from the class-level __table_args__ dict, which is not
        # mutated by _sqlite_compat_swap (unlike table.schema which is zeroed
        # out so SQLite create_all works without named schemas).
        table_args = getattr(model_class, "__table_args__", {})
        schema = table_args.get("schema") if isinstance(table_args, dict) else None
        assert schema == _SCHEMA, (
            f"{model_class.__name__} has __table_args__ schema={schema!r}, expected {_SCHEMA!r}"
        )
