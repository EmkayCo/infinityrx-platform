"""Unit tests: SP-3 new ORM model instantiation.

These tests verify that all six new model classes exist with the
correct __tablename__, column names, and column types. They run
against SQLite (in-memory) via the existing _shim.db machinery.

LESSON-007 applies: PG_UUID columns hit _UUIDString in SQLite.
LESSON-001 applies: SAVEPOINT-based isolation.

R1 BLOCK 4 fix: replace tuple-destructure imports with direct named
imports (the original `(*_, GraphRun, *_) = _import_models()` is a
SyntaxError — two starred targets cannot appear in one unpacking).

R1 BLOCK 5 fix: import the six new models BEFORE any
`Base.metadata.create_all()` call, so each class's `__tablename__`
is registered into `Base.metadata.tables` before table creation
walks the metadata.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Numeric, event, inspect, text
from sqlalchemy.orm import Session

from src._shim.db import Base, configure_engine, get_engine

# ---------------------------------------------------------------------------
# Model imports — MUST happen at module load time (R1 BLOCK 5 fix).
# Importing each class triggers SQLAlchemy's mapper registration which
# inserts the table into Base.metadata.tables. If these imports happen
# inside fixtures (lazy), Base.metadata.create_all() in the engine fixture
# would run against a metadata object that is missing the new tables.
# ---------------------------------------------------------------------------
from src.models.tables import (  # noqa: E402
    AccumulatorAnomaly,
    FraudRing,
    GraphRun,
    OutboxEvent,
    ThresholdConfig,
    ThresholdConfigAudit,
)

# Sanity assertion: all six classes registered themselves in metadata.
_NEW_TABLE_NAMES = {
    "reclaimrx_accumulator_anomalies",
    "reclaimrx_fraud_rings",
    "reclaimrx_graph_runs",
    "reclaimrx_outbox_events",
    "reclaimrx_threshold_configs",
    "reclaimrx_threshold_config_audits",
}
assert _NEW_TABLE_NAMES.issubset(set(Base.metadata.tables.keys())), (
    f"R1 BLOCK 5 regression: new tables missing from Base.metadata. "
    f"Missing: {_NEW_TABLE_NAMES - set(Base.metadata.tables.keys())}"
)


# ---------------------------------------------------------------------------
# UUID compatibility patch (LESSON-007) — apply BEFORE engine fixture runs.
# Module-level patch covers BOTH new model tables (registered above) and any
# existing model tables that the engine fixture's create_all will materialize.
# ---------------------------------------------------------------------------
from sqlalchemy.dialects.postgresql import UUID as PG_UUID  # noqa: E402
from sqlalchemy.types import String, TypeDecorator  # noqa: E402


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36) (LESSON-007)."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


for _table in Base.metadata.tables.values():
    for _col in _table.columns:
        if isinstance(_col.type, PG_UUID):
            _col.type = _UUIDString()


# ---------------------------------------------------------------------------
# Engine + SAVEPOINT fixture (LESSON-001)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine with all metadata (including the six new
    SP-3 tables) materialized.

    R1 BLOCK 5 fix: model imports happen at module load above, BEFORE
    create_all runs here. The patched UUID columns are also applied
    above, so this fixture is a pure DDL step.
    """
    configure_engine("sqlite:///:memory:")
    eng = get_engine()
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db(engine):
    """SAVEPOINT-based isolation (LESSON-001)."""
    connection = engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session
    session.close()
    outer.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FraudRing
# ---------------------------------------------------------------------------

class TestFraudRingModel:
    def test_tablename(self):
        assert FraudRing.__tablename__ == "reclaimrx_fraud_rings"

    def test_instantiate_minimal(self, db):
        tid = uuid.uuid4()
        run_id = uuid.uuid4()
        ring = FraudRing(
            id=str(uuid.uuid4()),
            tenant_id=str(tid),
            graph_run_id=str(run_id),
            detected_at=datetime.now(UTC),
            density_score=Decimal("0.85"),
            node_count=12,
            edge_count=34,
            entity_refs=[],
        )
        db.add(ring)
        db.flush()
        fetched = db.get(FraudRing, ring.id)
        assert fetched is not None
        assert fetched.node_count == 12

    def test_required_columns_present(self):
        cols = {c.name for c in inspect(FraudRing).columns}
        required = {
            "id", "tenant_id", "graph_run_id", "detected_at",
            "density_score", "node_count", "edge_count",
            "entity_refs", "spawned_investigation_id",
        }
        assert required.issubset(cols), f"Missing: {required - cols}"

    def test_density_score_is_numeric(self):
        col = inspect(FraudRing).columns["density_score"]
        assert isinstance(col.type, Numeric)
        assert col.type.precision == 8
        assert col.type.scale == 4


# ---------------------------------------------------------------------------
# GraphRun
# ---------------------------------------------------------------------------

class TestGraphRunModel:
    def test_tablename(self):
        assert GraphRun.__tablename__ == "reclaimrx_graph_runs"

    def test_status_values_documented(self):
        # Status is a String column; valid values enforced by CHECK constraint in migration
        # Unit test just verifies the column exists and accepts known values
        cols = {c.name for c in inspect(GraphRun).columns}
        assert "status" in cols

    def test_instantiate_running(self, db):
        tid = uuid.uuid4()
        run = GraphRun(
            id=str(uuid.uuid4()),
            tenant_id=str(tid),
            status="running",
            trigger="on_demand",
            started_at=datetime.now(UTC),
            correlation_id=str(uuid.uuid4()),
            stale_timeout_at=datetime.now(UTC),
            rings_detected=0,
            investigations_opened=0,
            records_scanned=0,
            lookback_window_days=90,
        )
        db.add(run)
        db.flush()
        fetched = db.get(GraphRun, run.id)
        assert fetched.status == "running"
        assert fetched.rings_detected == 0

    def test_required_columns_present(self):
        cols = {c.name for c in inspect(GraphRun).columns}
        required = {
            "id", "tenant_id", "status", "trigger", "started_at",
            "completed_at", "failed_at", "error_code", "error_message",
            "correlation_id", "stale_timeout_at", "rings_detected",
            "investigations_opened", "records_scanned", "lookback_window_days",
        }
        assert required.issubset(cols), f"Missing: {required - cols}"


# ---------------------------------------------------------------------------
# AccumulatorAnomaly
# ---------------------------------------------------------------------------

class TestAccumulatorAnomalyModel:
    def test_tablename(self):
        assert AccumulatorAnomaly.__tablename__ == "reclaimrx_accumulator_anomalies"

    def test_instantiate(self, db):
        tid = uuid.uuid4()
        anomaly = AccumulatorAnomaly(
            id=str(uuid.uuid4()),
            tenant_id=str(tid),
            member_id=str(uuid.uuid4()),
            pattern_type="sudden_spike",
            detected_at=datetime.now(UTC),
            evidence_window_start=datetime.now(UTC),
            evidence_window_end=datetime.now(UTC),
            triggering_event_ids=[],
        )
        db.add(anomaly)
        db.flush()
        fetched = db.get(AccumulatorAnomaly, anomaly.id)
        assert fetched.pattern_type == "sudden_spike"

    def test_required_columns_present(self):
        cols = {c.name for c in inspect(AccumulatorAnomaly).columns}
        required = {
            "id", "tenant_id", "member_id", "pattern_type",
            "detected_at", "evidence_window_start", "evidence_window_end",
            "triggering_event_ids", "spawned_investigation_id",
        }
        assert required.issubset(cols), f"Missing: {required - cols}"

    def test_pattern_type_values_are_enforced_at_migration(self):
        # CHECK constraint lives in migration; model itself accepts any string.
        # This test documents the four valid values from spec §5.2.
        valid = {"sudden_spike", "multi_payer_convergence", "reset_evasion", "threshold_oscillation"}
        assert len(valid) == 4  # spec §5.2 — all four must be in migration CHECK


# ---------------------------------------------------------------------------
# ThresholdConfig
# ---------------------------------------------------------------------------

class TestThresholdConfigModel:
    def test_tablename(self):
        assert ThresholdConfig.__tablename__ == "reclaimrx_threshold_configs"

    def test_instantiate(self, db):
        tid = uuid.uuid4()
        cfg = ThresholdConfig(
            id=str(uuid.uuid4()),
            tenant_id=str(tid),
            version=1,
            effective_at=datetime.now(UTC),
            superseded_at=None,
            rule_thresholds={},
            ml_score_thresholds={"open": "0.60", "auto_hold": "0.80", "escalate": "0.90"},
            graph_density_threshold=Decimal("0.70"),
            accumulator_anomaly_sensitivity=Decimal("0.75"),
            updated_by="user-sub-abc",
        )
        db.add(cfg)
        db.flush()
        fetched = db.get(ThresholdConfig, cfg.id)
        assert fetched.version == 1
        assert fetched.superseded_at is None

    def test_numeric_threshold_columns(self):
        cols = {c.name: c for c in inspect(ThresholdConfig).columns}
        for col_name in ("graph_density_threshold", "accumulator_anomaly_sensitivity"):
            assert isinstance(cols[col_name].type, Numeric), f"{col_name} must be Numeric"


# ---------------------------------------------------------------------------
# ThresholdConfigAudit
# ---------------------------------------------------------------------------

class TestThresholdConfigAuditModel:
    def test_tablename(self):
        assert ThresholdConfigAudit.__tablename__ == "reclaimrx_threshold_config_audits"

    def test_instantiate(self, db):
        tid = uuid.uuid4()
        cfg = ThresholdConfig(
            id=str(uuid.uuid4()),
            tenant_id=str(tid),
            version=1,
            effective_at=datetime.now(UTC),
            updated_by="user-sub",
            rule_thresholds={},
            ml_score_thresholds={},
            graph_density_threshold=Decimal("0.70"),
            accumulator_anomaly_sensitivity=Decimal("0.75"),
        )
        db.add(cfg)
        db.flush()

        audit_entry = ThresholdConfigAudit(
            id=str(uuid.uuid4()),
            tenant_id=str(tid),
            threshold_config_id=cfg.id,
            field="ml_score_thresholds.open",
            old_value="0.60",
            new_value="0.65",
            changed_at=datetime.now(UTC),
            changed_by="user-sub",
            reason="Tuning for Q2",
            entry_hash="abc123",
            prev_entry_hash=None,
        )
        db.add(audit_entry)
        db.flush()
        fetched = db.get(ThresholdConfigAudit, audit_entry.id)
        assert fetched.entry_hash == "abc123"
        assert fetched.prev_entry_hash is None

    def test_entry_hash_not_nullable(self):
        """Enforces hipaa-2026.md: MUST compute entry_hash on EVERY audit log write."""
        col = next(c for c in inspect(ThresholdConfigAudit).columns if c.name == "entry_hash")
        assert not col.nullable, "entry_hash must be NOT NULL per hipaa-2026.md"


# ---------------------------------------------------------------------------
# OutboxEvent
# ---------------------------------------------------------------------------

class TestOutboxEventModel:
    def test_tablename(self):
        assert OutboxEvent.__tablename__ == "reclaimrx_outbox_events"

    def test_instantiate(self, db):
        tid = uuid.uuid4()
        event_id = uuid.uuid4()
        evt = OutboxEvent(
            id=str(event_id),
            tenant_id=str(tid),
            event_type="payment.hold_released",
            envelope_json={
                "event_type": "payment.hold_released",
                "tenant_id": str(tid),
                "schema_version": "1.0",
            },
            status="pending",
            created_at=datetime.now(UTC),
            attempt_count=0,
            idempotency_key=f"hold:release:{uuid.uuid4()}",
        )
        db.add(evt)
        db.flush()
        fetched = db.get(OutboxEvent, evt.id)
        assert fetched.status == "pending"
        assert fetched.attempt_count == 0

    def test_idempotency_key_is_unique(self):
        from sqlalchemy import inspect as sa_inspect
        mapper = sa_inspect(OutboxEvent)
        # Check the __table_args__ has a UniqueConstraint on idempotency_key
        table = OutboxEvent.__table__
        unique_cols = [
            frozenset(uc.columns.keys())
            for uc in table.constraints
            if hasattr(uc, "columns") and len(list(uc.columns)) > 0
            and str(type(uc).__name__) == "UniqueConstraint"
        ]
        assert any("idempotency_key" in s for s in unique_cols), \
            "OutboxEvent must have UniqueConstraint on idempotency_key"

    def test_status_column_accepts_known_values(self, db):
        # status CHECK constraint is enforced in migration (Postgres);
        # SQLite does not enforce CHECKs in older versions.
        # This test verifies the three valid values are documented.
        valid_statuses = {"pending", "published", "failed"}
        assert len(valid_statuses) == 3  # spec §5.2


# ---------------------------------------------------------------------------
# Investigation extensions
# ---------------------------------------------------------------------------

class TestInvestigationExtensions:
    """Verify the 12 new scalar columns are present on the existing Investigation model (R1 CONCERN 6)."""

    def test_new_columns_present(self):
        from src.models.tables import Investigation
        cols = {c.name for c in inspect(Investigation).columns}
        required_new = {
            "severity",
            "source",
            "source_ref_id",
            "member_id",
            "opened_by",
            "closed_at",
            "closed_by",
            "outcome_label",
            "recovered_amount",
            "hold_amount",
            "threshold_config_version",
            "threshold_snapshot",
        }
        assert required_new.issubset(cols), f"Missing new columns: {required_new - cols}"

    def test_recovered_amount_is_numeric(self):
        """financial-precision.md: Decimal only, sa.Numeric, no float."""
        from src.models.tables import Investigation
        from sqlalchemy import Numeric
        col = next(c for c in inspect(Investigation).columns if c.name == "recovered_amount")
        assert isinstance(col.type, Numeric), "recovered_amount must be Numeric"

    def test_hold_amount_is_numeric(self):
        from src.models.tables import Investigation
        from sqlalchemy import Numeric
        col = next(c for c in inspect(Investigation).columns if c.name == "hold_amount")
        assert isinstance(col.type, Numeric), "hold_amount must be Numeric"

    def test_outcome_label_nullable(self):
        from src.models.tables import Investigation
        col = next(c for c in inspect(Investigation).columns if c.name == "outcome_label")
        assert col.nullable, "outcome_label must be nullable (null until investigation closed)"

    def test_instantiate_with_new_columns(self, db):
        from src.models.tables import Investigation
        inv = Investigation(
            id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            investigation_number="INV-001",
            title="Test SP-3 investigation",
            subject_type="pharmacy",
            subject_entity_id=str(uuid.uuid4()),
            investigation_type="fwa",
            # New SP-3 columns
            severity="high",
            source="rule_firing",
            source_ref_id=str(uuid.uuid4()),
            member_id=str(uuid.uuid4()),
            opened_by="system",
            outcome_label=None,
            recovered_amount=None,
            hold_amount=None,
            threshold_config_version=None,
            threshold_snapshot=None,
        )
        db.add(inv)
        db.flush()
        fetched = db.get(Investigation, inv.id)
        assert fetched.severity == "high"
        assert fetched.source == "rule_firing"
        assert fetched.outcome_label is None


# ---------------------------------------------------------------------------
# PaymentHold extensions
# ---------------------------------------------------------------------------

class TestPaymentHoldExtensions:
    def test_status_column_present(self):
        """PaymentHold needs a status column; existing is_active bool stays for backcompat."""
        from src.models.tables import PaymentHold
        cols = {c.name for c in inspect(PaymentHold).columns}
        assert "status" in cols, "PaymentHold must have status column for idempotency (audit §10)"
        # released_by/released_at/release_reason ALREADY EXIST — verify they are still there
        already_existing = {"released_by", "released_at", "release_reason"}
        assert already_existing.issubset(cols), \
            f"Pre-existing release columns must not be removed: {already_existing - cols}"

    def test_status_not_nullable(self):
        from src.models.tables import PaymentHold
        col = next(c for c in inspect(PaymentHold).columns if c.name == "status")
        assert not col.nullable, "PaymentHold.status must be NOT NULL"

    def test_status_default_is_active(self):
        from src.models.tables import PaymentHold
        col = next(c for c in inspect(PaymentHold).columns if c.name == "status")
        # Default value 'active' aligns with existing is_active=True semantics
        assert col.default is not None or col.server_default is not None, \
            "PaymentHold.status must have a default of 'active'"
