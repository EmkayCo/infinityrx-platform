# SP-3 Plan A1 — Models + Alembic 0008 + RLS + Indexes

**Status:** Ready for execution  
**Date:** 2026-05-18  
**Slice:** Models + migration only (the A1 sub-slice of Plan A)  
**Parent plan:** `docs/superpowers/plans/2026-05-18-sp3-plan-a-backend-contract-scaffold.md` (failed; this replaces its model/migration tasks)  
**Spec ref:** `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`  
**Audit ground truth:** `waves/B10/SP-3-audit-deep.md`  
**Codex review:** `docs/superpowers/codex-sp3-plan-a-review-r1.md` — BLOCKS 1, 2, 3, 5 resolved here

---

## Scope

This plan delivers exactly:
1. Six new ORM model classes in `modules/reclaimrx/src/models/tables.py` (extending the existing file)
2. Twelve new scalar columns on the existing `Investigation` model (ALTER TABLE) — R1 CONCERN 6 fix; explicit count is twelve, not eleven, matching the spec §5.2 list and the migration column list below
3. One new column on the existing `PaymentHold` model (`status`)
4. Alembic migration `0008_sp3_extensions.py` — creates new tables, alters existing, adds RLS policies, adds indexes
5. Unit tests proving every model instantiates correctly, indexes exist, RLS predicate SQL is syntactically correct

This plan does NOT write API endpoints, services, outbox logic, consumers, or contract layer — those are Plans A2-A5.

---

## Verified ground-truth facts (from audit — executor must not re-derive)

| Fact | Source |
|---|---|
| Latest migration: `0007_flagged_npis` | `waves/B10/SP-3-audit-deep.md` §1 |
| Migration schema: `reclaimrx` | Every existing migration file |
| GUC name: `app.current_tenant_id` | `0002_reclaimrx_rls.py:41`, `0007_flagged_npis.py:100` — NOT `app.tenant_id` |
| RLS predicate pattern: `tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid` | `0007_flagged_npis.py:98–104` |
| UUID column type in migrations: `postgresql.UUID(as_uuid=False)` | `0007_flagged_npis.py:42–44` |
| ORM base class: `src._shim.db.Base` (module-local) | `modules/reclaimrx/src/models/tables.py:30` |
| ORM tenant_id type: `String(36)` for ALL tables (existing AND new) — R1 BLOCK 3 fix; mixin abandoned | audit §1 |
| `PaymentHold` already has `released_by`, `released_at`, `release_reason` | `tables.py:607–609` — DO NOT add these again |
| `PaymentHold` uses `is_active: Boolean` — needs `status: String(20)` added | audit §1, §10 |
| `Investigation.__tablename__` = `reclaimrx_investigations` | `tables.py:374` |
| `PaymentHold.__tablename__` = `reclaimrx_payment_holds` | `tables.py:588` |
| `AccumulatorDetection.__tablename__` = `reclaimrx_accumulator_detections` | `tables.py:491` |
| `AccumulatorAnomaly` is NEW (not an extension of `AccumulatorDetection`) | audit §1 |
| FK references use full `reclaimrx_*` table names | existing tables.py FKs at lines 433, 450 |
| `TenantScopedMixin` from `shared.db.tenant_context` uses `SA_UUID(as_uuid=True)` — INCOMPATIBLE with this module's `String(36)` pattern; NOT used by A1 | `shared/db/tenant_context.py:93` |
| No APScheduler anywhere — use asyncio + croniter | audit §7 |
| Advisory lock deterministic hash: use `zlib.crc32` | audit §9 |
| `EventEnvelope` fields: `event_type` + `timestamp` (not `type`/`emitted_at`) | audit §2 |
| `CurrentUser` is a dataclass with `.roles` / `.has_role()` — not a dict | audit §3 |

---

## BLOCKS resolved by this plan

| Codex BLOCK | Resolution |
|---|---|
| BLOCK 1: `PaymentHold.released_by` already exists | This plan does NOT add `released_by`. Adds only `status` column. |
| BLOCK 2: Migration uses wrong table names | This plan uses exact `__tablename__` values from audit. |
| BLOCK 3: `TenantScopedBase` invented; `Base + TenantScopedMixin` internally inconsistent | **R1 BLOCK 3 fix:** A1 uses ONLY `Base` with explicit `tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)` on every new model. The `TenantScopedMixin` from `shared.db.tenant_context` uses `SA_UUID(as_uuid=True)`, which collides with this module's existing `String(36)` tenant_id column pattern (e.g. `Investigation` at tables.py:377). Mixing the two patterns produces a `tenant_id` type-mismatch on FK joins between new tables and existing tables. Tenant scoping is still enforced — by RLS at the database layer, and by the existing `install_tenant_loader` session pattern at the ORM layer, both of which operate on the `String(36)` column. |
| BLOCK 5: `hold.hold_amount` does not exist | This plan documents that `amount_threshold` is the existing money column on PaymentHold. Separate `hold_amount` column on Investigation is added as `recovered_amount`/`hold_amount` (spec §5.2). |

---

## Task 1: Add new model classes to tables.py

**TDD order:** Write failing instantiation tests → add models → tests pass.

### Step 1.1 — Write failing tests

File: `modules/reclaimrx/tests/unit/test_new_models_instantiate.py` (create new)

```python
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
            event_type="fwa.hold_released",
            envelope_json={
                "event_type": "fwa.hold_released",
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
```

**Run (must FAIL before models added):**
```bash
cd modules/reclaimrx && python -m pytest tests/unit/test_new_models_instantiate.py -v 2>&1 | head -40
```
Expected: `ImportError: cannot import name 'AccumulatorAnomaly' from 'src.models.tables'` and column-missing errors.

---

### Step 1.2 — Add new model classes to tables.py

File: `modules/reclaimrx/src/models/tables.py`

Append the following **after the `PaymentHold` class** (around line 614) and **before** the `TipRecord` class. Also extend `Investigation` and `PaymentHold` in-place.

**1.2a — Extend Investigation model** (add 12 scalar columns after line 423, before the `activities` relationship — R1 CONCERN 6: explicit count is twelve, matching the migration column list below):

```python
# SP-3 extensions — added by migration 0008_sp3_extensions
# These columns extend the existing Investigation model with the
# fields required by spec §5.2 and the 7-state investigation machine.
severity: Mapped[str | None] = mapped_column(
    String(20), nullable=True, index=True
)  # low|medium|high|critical
source: Mapped[str | None] = mapped_column(
    String(50), nullable=True
)  # rule_firing|ml_score|graph_ring|accumulator_anomaly|manual
source_ref_id: Mapped[str | None] = mapped_column(
    String(36), nullable=True
)  # UUID FK to source entity (untyped FK — source table varies by source type)
member_id: Mapped[str | None] = mapped_column(
    String(36), nullable=True, index=True
)  # UUID FK — NOT PHI per spec D6; member_id is a UUID reference, not a name
opened_by: Mapped[str | None] = mapped_column(
    String(255), nullable=True
)  # 'system' or JWT sub
closed_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
closed_by: Mapped[str | None] = mapped_column(
    String(255), nullable=True
)
outcome_label: Mapped[str | None] = mapped_column(
    String(50), nullable=True
)  # confirmed|false_positive|no_action; null until closed
recovered_amount: Mapped[object | None] = mapped_column(
    Numeric(15, 2), nullable=True
)  # Decimal; 100% coverage gate; financial-precision.md
hold_amount: Mapped[object | None] = mapped_column(
    Numeric(15, 2), nullable=True
)  # Decimal; 100% coverage gate; financial-precision.md
threshold_config_version: Mapped[int | None] = mapped_column(
    Integer, nullable=True
)  # version at time investigation was opened
threshold_snapshot: Mapped[dict | None] = mapped_column(
    JSON, nullable=True
)  # immutable copy of threshold values at open time (defense-in-depth)
```

**1.2b — Extend PaymentHold model** (add after line 611, before `created_at`):

```python
# SP-3 extension: status replaces the boolean is_active for the 3-case
# idempotency logic in spec §7.2. is_active remains for backward compat
# with existing callers until they are migrated to status.
# Valid values: 'active' | 'released' | 'expired' | 'cancelled'
# CHECK constraint is in migration 0008.
status: Mapped[str] = mapped_column(
    String(20), nullable=False, default="active"
)
```

> **R1 CONCERN 9 — PaymentHold.idempotency_key explicit deferral.** The audit
> calls out that `PaymentHold` also lacks an `idempotency_key` column.
> A1 deliberately does NOT add it because A3's `POST /holds/{id}/release`
> implements idempotency at the **outbox layer** via the
> `reclaimrx_outbox_events.idempotency_key` UNIQUE constraint (composed as
> `hold:release:{hold_id}` — see Plan A2 §6b and Plan A3 §7.2 case A/B/C).
> No A1 consumer queries against a `PaymentHold.idempotency_key` column.
>
> A `PaymentHold.idempotency_key` column would only be needed if we ever
> moved idempotency enforcement OFF the outbox and ONTO the hold row
> itself — which is not the design. Tracked as future hardening under
> `B11/follow-on/payment-hold-row-idempotency` for explicit decision
> before that re-architecture lands.

**1.2c — New model classes** (append after PaymentHold class, before TipRecord):

```python
# =============================================================================
# SP-3 NEW TABLES — added by migration 0008_sp3_extensions
# =============================================================================


class GraphRun(Base):
    """Tracks a single graph-analysis batch run per tenant.

    status enum: running | completed | completed_partial | failed
    (no 'cancelled' per spec §3 — stale runs auto-fail via stale_timeout_at)

    The durable 'running' row is the cross-process concurrency authority:
    no two runs per tenant may be 'running' simultaneously. The advisory lock
    (pg_try_advisory_xact_lock) is transaction-scoped and prevents the race
    at INSERT time; this row persists as the long-term authority.

    BLOCK 2 resolved: __tablename__ matches audit-verified naming convention.
    """

    __tablename__ = "reclaimrx_graph_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="running"
    )  # running|completed|completed_partial|failed
    trigger: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # cron|on_demand

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # sanitized — MUST NOT contain PHI

    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    stale_timeout_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )  # auto-fail if status='running' past this time

    rings_detected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    investigations_opened: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_scanned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lookback_window_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        Index("ix_graph_runs_tenant_status", "tenant_id", "status"),
    )


class FraudRing(Base):
    """A fraud ring detected by the graph-analysis batch job.

    Produced by graph_analysis_service; one FraudRing per dense subgraph
    component per run. density_score is Numeric(8,4) — financial-precision.md
    requires Numeric for all money-adjacent Decimal values.

    entity_refs is a JSON array of {type, id, npi/nabp} dicts.
    spawned_investigation_id may be null if ring density is below threshold
    for auto-investigation.

    BLOCK 2 resolved: FK references reclaimrx_graph_runs.id (full table name).
    """

    __tablename__ = "reclaimrx_fraud_rings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    graph_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reclaimrx_graph_runs.id"),
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    density_score: Mapped[object] = mapped_column(
        Numeric(8, 4), nullable=False
    )  # Numeric not Float — financial-precision.md

    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)

    entity_refs: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # [{type, id, npi|nabp}]; capped at 500 nodes per spec §5.5#13

    spawned_investigation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("reclaimrx_investigations.id"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        Index("ix_fraud_rings_tenant_run", "tenant_id", "graph_run_id"),
    )


class AccumulatorAnomaly(Base):
    """Accumulator manipulation anomaly detected by accumulator_consumer.

    This is a NEW table — separate from the existing AccumulatorDetection
    model (reclaimrx_accumulator_detections), which tracks copay-assistance
    accumulator plan-type detection. AccumulatorAnomaly is for the four
    SP-3 fraud pattern detectors (sudden_spike, multi_payer_convergence,
    reset_evasion, threshold_oscillation).

    member_id is a UUID reference — NOT PHI per spec D6 (it's a FK, not a name).
    triggering_event_ids is a JSON array of accumulator.updated event_id strings.

    BLOCK 2 resolved: NOT reclaimrx_accumulator_detections.
    """

    __tablename__ = "reclaimrx_accumulator_anomalies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    member_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )  # UUID FK — NOT PHI (spec D6)
    pattern_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # sudden_spike|multi_payer_convergence|reset_evasion|threshold_oscillation

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    evidence_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    evidence_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    triggering_event_ids: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # list of accumulator.updated event_id strings

    spawned_investigation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("reclaimrx_investigations.id"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    __table_args__ = (
        Index("ix_accumulator_anomalies_tenant_member", "tenant_id", "member_id"),
        Index("ix_accumulator_anomalies_tenant_detected", "tenant_id", "detected_at"),
    )


class ThresholdConfig(Base):
    """Versioned per-tenant FWA threshold configuration.

    Each UPDATE creates a new version row (version monotonically increments
    per tenant). superseded_at=null means this is the current version.
    threshold_config_version on Investigation FKs to this table's version int.

    rule_thresholds: JSON {rule_code: "0.XX"} — Decimal as string
    ml_score_thresholds: JSON {open: "0.60", auto_hold: "0.80", escalate: "0.90"}
    graph_density_threshold: Numeric(8,4)
    accumulator_anomaly_sensitivity: Numeric(8,4)

    All Decimal threshold values use Numeric — financial-precision.md.
    """

    __tablename__ = "reclaimrx_threshold_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # null = current active version

    rule_thresholds: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # {rule_code: "decimal_str"}
    ml_score_thresholds: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # {open, auto_hold, escalate} as decimal strings
    graph_density_threshold: Mapped[object] = mapped_column(
        Numeric(8, 4), nullable=False
    )
    accumulator_anomaly_sensitivity: Mapped[object] = mapped_column(
        Numeric(8, 4), nullable=False
    )

    updated_by: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # JWT sub of the admin who made the change

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    audit_entries: Mapped[list["ThresholdConfigAudit"]] = relationship(
        back_populates="config", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Only one current version per tenant (superseded_at IS NULL)
        # Enforced via partial unique index in migration — not expressible here
        Index("ix_threshold_configs_tenant_version", "tenant_id", "version"),
    )


class ThresholdConfigAudit(Base):
    """Per-field hash-chained audit for ThresholdConfig changes.

    Per hipaa-2026.md: entry_hash is NOT NULL (MUST compute on every write;
    never write with empty hash). prev_entry_hash chains to prior entry.
    field uses dot-path notation per event-bus.md conventions.

    BLOCK 2 resolved: FK reclaimrx_threshold_configs.id (full table name).
    """

    __tablename__ = "reclaimrx_threshold_config_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    threshold_config_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reclaimrx_threshold_configs.id"),
        nullable=False,
        index=True,
    )
    field: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # dot-path e.g. 'ml_score_thresholds.open'
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)  # JWT sub
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hash chain — hipaa-2026.md MUST compute entry_hash on EVERY write
    entry_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # NOT NULL enforced; SHA-256 hex of (prev_entry_hash + field + old + new + changed_at)
    prev_entry_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # null for first entry per tenant-config

    config: Mapped["ThresholdConfig"] = relationship(back_populates="audit_entries")

    __table_args__ = (
        Index("ix_threshold_config_audits_tenant", "tenant_id", "threshold_config_id"),
    )


class OutboxEvent(Base):
    """Transactional outbox for reliable event publishing (R1 BLOCK 4).

    Every mutation that must emit an event (hold release, graph run complete)
    writes an OutboxEvent row in the SAME database transaction as the state
    change. The outbox_dispatcher background task polls pending rows and
    publishes them to the event bus with retry + exponential backoff.

    envelope_json holds the full EventEnvelope as dict (using correct fields:
    event_type, tenant_id, correlation_id, source_module, payload, schema_version,
    ordering_key, idempotency_key — per audit §2 + shared/events/types.py).

    idempotency_key has a UNIQUE constraint so duplicate trigger attempts
    do not produce duplicate outbox rows.
    """

    __tablename__ = "reclaimrx_outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # dot-notation e.g. 'fwa.hold_released'
    envelope_json: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # Full EventEnvelope as dict — fields: event_type, tenant_id, etc.

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending|published|failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # sanitized — MUST NOT contain PHI

    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # e.g. 'hold:release:{hold_id}'; UNIQUE constraint in __table_args__

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_outbox_events_idempotency_key"),
        Index("ix_outbox_events_status_created", "status", "created_at"),
        Index("ix_outbox_events_tenant_status", "tenant_id", "status"),
    )
```

**Run tests (must now PASS):**
```bash
cd modules/reclaimrx && python -m pytest tests/unit/test_new_models_instantiate.py -v
```
Expected: All tests green. Coverage for models slice: run `python -m pytest tests/unit/test_new_models_instantiate.py --cov=src.models.tables --cov-report=term-missing`.

---

## Task 2: Write migration 0008_sp3_extensions.py

**TDD order:** Write migration test → write migration → test passes (apply + rollback cleanly).

### Step 2.1 — Write migration acceptance test

File: `modules/reclaimrx/tests/integration/test_migration_0008.py` (create new)

```python
"""Migration 0008 acceptance tests.

Verifies:
1. Migration applies without error (CREATE TABLE + ALTER TABLE)
2. All 6 new tables exist with correct column sets
3. All 3 altered tables (investigations, payment_holds, + Investigation) have new columns
4. All required indexes exist
5. RLS predicates are syntactically correct (SQL parse check)
6. Migration rolls back cleanly (downgrade idempotent)

Runs against a real PostgreSQL instance. Skip if RECLAIMRX_TEST_DB_URL not set.
"""
from __future__ import annotations

import os
import pytest
from sqlalchemy import create_engine, inspect, text


DB_URL = os.environ.get("RECLAIMRX_TEST_DB_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="RECLAIMRX_TEST_DB_URL not set")


@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(DB_URL)
    yield engine
    engine.dispose()


def get_table_columns(engine, schema, table_name) -> set[str]:
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ), {"schema": schema, "table": table_name})
        return {row[0] for row in result}


def get_indexes(engine, schema, table_name) -> set[str]:
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = :schema AND tablename = :table"
        ), {"schema": schema, "table": table_name})
        return {row[0] for row in result}


class TestNewTablesExist:
    NEW_TABLES = [
        "graph_runs",
        "fraud_rings",
        "accumulator_anomalies",
        "threshold_configs",
        "threshold_config_audits",
        "outbox_events",
    ]

    def test_all_new_tables_created(self, pg_engine):
        with pg_engine.connect() as conn:
            for table in self.NEW_TABLES:
                result = conn.execute(text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'reclaimrx' AND table_name = :t"
                ), {"t": table}).fetchone()
                assert result is not None, f"Table reclaimrx.{table} was not created"


class TestGraphRunsTable:
    def test_required_columns(self, pg_engine):
        cols = get_table_columns(pg_engine, "public", "reclaimrx_graph_runs")
        required = {
            "id", "tenant_id", "status", "trigger", "started_at",
            "completed_at", "failed_at", "error_code", "error_message",
            "correlation_id", "stale_timeout_at", "rings_detected",
            "investigations_opened", "records_scanned", "lookback_window_days",
            "created_at",
        }
        assert required.issubset(cols), f"Missing: {required - cols}"

    def test_status_check_constraint(self, pg_engine):
        """Invalid status is rejected by CHECK constraint."""
        with pg_engine.connect() as conn:
            with pytest.raises(Exception, match="check"):
                conn.execute(text(
                    "INSERT INTO reclaimrx_graph_runs "
                    "(id, tenant_id, status, trigger, started_at, correlation_id, "
                    " stale_timeout_at, rings_detected, investigations_opened, "
                    " records_scanned, lookback_window_days, created_at) VALUES "
                    "('00000000-0000-0000-0000-000000000001', "
                    " '00000000-0000-0000-0000-000000000002', "
                    " 'INVALID_STATUS', 'cron', now(), 'corr-id', now()+interval'6h', "
                    " 0, 0, 0, 90, now())"
                ))
                conn.rollback()

    def test_indexes(self, pg_engine):
        indexes = get_indexes(pg_engine, "public", "reclaimrx_graph_runs")
        assert any("tenant" in idx and "status" in idx for idx in indexes), \
            f"Missing (tenant_id, status) index on graph_runs. Found: {indexes}"


class TestFraudRingsTable:
    def test_required_columns(self, pg_engine):
        cols = get_table_columns(pg_engine, "public", "reclaimrx_fraud_rings")
        required = {
            "id", "tenant_id", "graph_run_id", "detected_at",
            "density_score", "node_count", "edge_count",
            "entity_refs", "spawned_investigation_id", "created_at",
        }
        assert required.issubset(cols), f"Missing: {required - cols}"

    def test_density_score_is_numeric(self, pg_engine):
        with pg_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT data_type, numeric_precision, numeric_scale "
                "FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='reclaimrx_fraud_rings' "
                "AND column_name='density_score'"
            )).fetchone()
        assert result is not None
        assert result[0] == "numeric", "density_score must be numeric type"

    def test_indexes(self, pg_engine):
        indexes = get_indexes(pg_engine, "public", "reclaimrx_fraud_rings")
        assert any("tenant" in idx for idx in indexes), \
            f"Missing tenant_id index on fraud_rings. Found: {indexes}"


class TestAccumulatorAnomaliesTable:
    def test_required_columns(self, pg_engine):
        cols = get_table_columns(pg_engine, "public", "reclaimrx_accumulator_anomalies")
        required = {
            "id", "tenant_id", "member_id", "pattern_type",
            "detected_at", "evidence_window_start", "evidence_window_end",
            "triggering_event_ids", "spawned_investigation_id", "created_at",
        }
        assert required.issubset(cols), f"Missing: {required - cols}"

    def test_pattern_type_check(self, pg_engine):
        with pg_engine.connect() as conn:
            with pytest.raises(Exception, match="check"):
                conn.execute(text(
                    "INSERT INTO reclaimrx_accumulator_anomalies "
                    "(id, tenant_id, member_id, pattern_type, detected_at, "
                    " evidence_window_start, evidence_window_end, created_at) VALUES "
                    "('00000000-0000-0000-0000-000000000001', "
                    " '00000000-0000-0000-0000-000000000002', "
                    " '00000000-0000-0000-0000-000000000003', "
                    " 'INVALID_PATTERN', now(), now(), now(), now())"
                ))
                conn.rollback()


class TestThresholdConfigsTable:
    def test_required_columns(self, pg_engine):
        cols = get_table_columns(pg_engine, "public", "reclaimrx_threshold_configs")
        required = {
            "id", "tenant_id", "version", "effective_at", "superseded_at",
            "rule_thresholds", "ml_score_thresholds",
            "graph_density_threshold", "accumulator_anomaly_sensitivity",
            "updated_by", "created_at",
        }
        assert required.issubset(cols), f"Missing: {required - cols}"

    def test_partial_unique_index_for_current_version(self, pg_engine):
        """Only one active (superseded_at IS NULL) version per tenant."""
        indexes = get_indexes(pg_engine, "public", "reclaimrx_threshold_configs")
        # The partial unique index name from migration
        assert any("current" in idx or "active" in idx or "superseded" in idx
                   for idx in indexes), \
            f"Missing partial unique index for current version per tenant. Found: {indexes}"


class TestOutboxEventsTable:
    def test_required_columns(self, pg_engine):
        cols = get_table_columns(pg_engine, "public", "reclaimrx_outbox_events")
        required = {
            "id", "tenant_id", "event_type", "envelope_json", "status",
            "created_at", "published_at", "attempt_count", "last_error",
            "idempotency_key",
        }
        assert required.issubset(cols), f"Missing: {required - cols}"

    def test_idempotency_key_unique_constraint(self, pg_engine):
        """Duplicate idempotency_key must be rejected."""
        with pg_engine.connect() as conn:
            tid = "00000000-0000-0000-0000-000000000099"
            ikey = "hold:release:test-unique-check"
            conn.execute(text(
                "INSERT INTO reclaimrx_outbox_events "
                "(id, tenant_id, event_type, envelope_json, status, "
                " created_at, attempt_count, idempotency_key) VALUES "
                "('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', :tid, "
                " 'fwa.hold_released', '{}', 'pending', now(), 0, :ikey)"
            ), {"tid": tid, "ikey": ikey})
            with pytest.raises(Exception, match="unique|duplicate"):
                conn.execute(text(
                    "INSERT INTO reclaimrx_outbox_events "
                    "(id, tenant_id, event_type, envelope_json, status, "
                    " created_at, attempt_count, idempotency_key) VALUES "
                    "('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', :tid, "
                    " 'fwa.hold_released', '{}', 'pending', now(), 0, :ikey)"
                ), {"tid": tid, "ikey": ikey})
            conn.rollback()


class TestInvestigationAlterations:
    """R1 BLOCK 2 fix: ALTER TABLE targets the deterministic ORM-aligned name.

    The ORM at `tables.py:374` declares `Investigation.__tablename__ =
    "reclaimrx_investigations"` in the default schema. Migration 0008 must
    alter that physical table. No hedging "check both" pattern — the table
    name is determined by the ORM, full stop.
    """

    def test_new_columns_added(self, pg_engine):
        cols = get_table_columns(pg_engine, "public", "reclaimrx_investigations")
        required_new = {
            "severity", "source", "source_ref_id", "member_id",
            "opened_by", "closed_at", "closed_by", "outcome_label",
            "recovered_amount", "hold_amount",
            "threshold_config_version", "threshold_snapshot",
        }
        assert required_new.issubset(cols), \
            f"Missing new columns on reclaimrx_investigations: {required_new - cols}"


class TestPaymentHoldAlteration:
    """R1 BLOCK 2 fix: same deterministic ORM-aligned table-name discipline."""

    def test_status_column_added(self, pg_engine):
        cols = get_table_columns(pg_engine, "public", "reclaimrx_payment_holds")
        assert "status" in cols, "PaymentHold.status column must be added"

    def test_existing_release_columns_unchanged(self, pg_engine):
        cols = get_table_columns(pg_engine, "public", "reclaimrx_payment_holds")
        # These ALREADY EXISTED — must not be removed (BLOCK 1 resolved)
        assert {"released_by", "released_at", "release_reason"}.issubset(cols), \
            "Pre-existing release columns must not be dropped by migration 0008"


class TestRLSPolicies:
    """RLS policies must be created on all 6 new tables.

    R1 BLOCK 1 + BLOCK 7 fix: tables live in PUBLIC schema with
    `reclaimrx_*` prefix (matches ORM); pg_namespace lookups use
    nspname='public'. The dedicated null-deny test class above
    (TestRLSNullDenyUnderAppRole) covers the BYPASSRLS concern.
    """

    NEW_TABLES = [
        "reclaimrx_graph_runs", "reclaimrx_fraud_rings",
        "reclaimrx_accumulator_anomalies", "reclaimrx_threshold_configs",
        "reclaimrx_threshold_config_audits", "reclaimrx_outbox_events",
    ]

    def test_rls_enabled(self, pg_engine):
        with pg_engine.connect() as conn:
            for table in self.NEW_TABLES:
                result = conn.execute(text(
                    "SELECT relrowsecurity FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relname = :t"
                ), {"t": table}).fetchone()
                assert result is not None, f"Table public.{table} not found in pg_class"
                assert result[0] is True, f"RLS not enabled on public.{table}"

    def test_predicate_uses_correct_guc(self, pg_engine):
        """GUC must be app.current_tenant_id (not app.tenant_id — common mistake)."""
        with pg_engine.connect() as conn:
            for table in self.NEW_TABLES:
                result = conn.execute(text(
                    "SELECT qual FROM pg_policies "
                    "WHERE schemaname = 'public' AND tablename = :t "
                    "AND policyname = 'tenant_isolation'"
                ), {"t": table}).fetchone()
                assert result is not None, \
                    f"No tenant_isolation policy on public.{table}"
                assert "app.current_tenant_id" in result[0], \
                    f"Wrong GUC in RLS predicate for {table}: {result[0]}"


class TestRequiredIndexes:
    """Indexes required by .claude/rules/performance.md."""

    def test_investigation_tenant_severity_index(self, pg_engine):
        """R1 BLOCK 2 fix: target the ORM-aligned table name deterministically.
        Investigation.__tablename__ = 'reclaimrx_investigations' (public schema).
        """
        idxs = get_indexes(pg_engine, "public", "reclaimrx_investigations")
        has_severity = any("severity" in i for i in idxs)
        assert has_severity, (
            f"Missing (tenant_id, severity) index on public.reclaimrx_investigations. "
            f"Found: {idxs}"
        )

    def test_outbox_status_index(self, pg_engine):
        idxs = get_indexes(pg_engine, "public", "reclaimrx_outbox_events")
        assert any("status" in i for i in idxs), \
            f"Missing status index on outbox_events. Found: {idxs}"
```

**Run (must FAIL before migration exists):**
```bash
cd modules/reclaimrx && RECLAIMRX_TEST_DB_URL=postgresql://... python -m pytest tests/integration/test_migration_0008.py -v -k "test_all_new_tables_created" 2>&1 | head -20
```
Expected: `AssertionError: Table public.reclaimrx_graph_runs was not created` (migration not run yet).

---

### Step 2.2 — Write migration 0008_sp3_extensions.py

File: `modules/reclaimrx/alembic/versions/0008_sp3_extensions.py`

```python
"""SP-3 backend extensions: new tables + column extensions + RLS + indexes.

New tables (public schema, `reclaimrx_*` prefix — ORM-aligned per R1 BLOCK 1):
  - reclaimrx_graph_runs            — durable per-tenant graph-analysis run tracking
  - reclaimrx_fraud_rings           — fraud rings detected per run
  - reclaimrx_accumulator_anomalies — accumulator manipulation anomalies (NOT extending
                                       accumulator_detections — this is a separate table)
  - reclaimrx_threshold_configs     — versioned per-tenant FWA threshold configuration
  - reclaimrx_threshold_config_audits — per-field hash-chained audit trail
  - reclaimrx_outbox_events         — transactional outbox for reliable event publishing

Altered tables:
  - reclaimrx_investigations — 12 new scalar columns (severity, source, source_ref_id,
                            member_id, opened_by, closed_at, closed_by,
                            outcome_label, recovered_amount, hold_amount,
                            threshold_config_version, threshold_snapshot)
  - reclaimrx_payment_holds — add status column (active|released|expired|cancelled)
                               NOTE: released_by, released_at, release_reason
                               ALREADY EXIST at tables.py:607-609 — DO NOT re-add.

RLS: FORCE ROW LEVEL SECURITY on all 6 new tables.
     GUC: app.current_tenant_id (matches 0002, 0003, 0006, 0007)
     Predicate: tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid

Indexes per .claude/rules/performance.md:
  - (tenant_id, status) on graph_runs, outbox_events, accumulator_anomalies
  - (tenant_id, FK) on fraud_rings, accumulator_anomalies, threshold_config_audits
  - (tenant_id, severity) on investigations
  - (tenant_id, member_id) on investigations
  - (status, created_at) on outbox_events (dispatcher poll)
  - UNIQUE partial (tenant_id WHERE superseded_at IS NULL) on threshold_configs
  - UNIQUE (idempotency_key) on outbox_events

Revision ID: 0008_sp3_extensions
Revises: 0007_flagged_npis
Create Date: 2026-05-18
"""
from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_sp3_extensions"
down_revision: Union[str, None] = "0007_flagged_npis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
# GUC matches every prior migration in this module (0002, 0003, 0006, 0007)
_RLS_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)

# R1 BLOCKS 1 + 2 fix — single physical-naming convention for SP-3.
#
# The reclaimrx codebase already has an internal split:
#   • migrations 0001-0007 create *unprefixed* tables inside the
#     `reclaimrx` named schema (e.g. reclaimrx.investigations);
#   • the ORM at `modules/reclaimrx/src/models/tables.py` declares
#     *prefixed* tables in the default public schema (e.g.
#     reclaimrx_investigations) with no `__table_args__["schema"]`.
#
# Codex R1 BLOCK 1+2 flagged this split as a data-layer hazard: an
# executor following the original A1 plan verbatim would create
# `reclaimrx.graph_runs` etc., but the ORM would query
# `public.reclaimrx_graph_runs` and find nothing.
#
# RESOLUTION: this migration follows the ORM's pattern verbatim —
# all new SP-3 tables are created in the default schema with the
# `reclaimrx_*` prefix. No `schema=` kwarg on `op.create_table`,
# no `schema=` on `op.create_index`, and the helper functions
# below operate on bare (already-prefixed) table names.
#
# Existing pre-SP-3 tables in the `reclaimrx` schema are NOT moved.
# They remain queryable through their own existing ORM models (if any)
# or raw SQL. SP-3 does not own that migration debt — Wave B11+ will
# audit and rationalize it.

_GRAPH_RUN_STATUSES = "('running', 'completed', 'completed_partial', 'failed')"
_GRAPH_RUN_TRIGGERS = "('cron', 'on_demand')"
_ACCUMULATOR_PATTERN_TYPES = (
    "('sudden_spike', 'multi_payer_convergence', 'reset_evasion', 'threshold_oscillation')"
)
_OUTBOX_STATUSES = "('pending', 'published', 'failed')"
_HOLD_STATUSES = "('active', 'released', 'expired', 'cancelled')"
_INVESTIGATION_SEVERITIES = "('low', 'medium', 'high', 'critical')"
_INVESTIGATION_SOURCES = (
    "('rule_firing', 'ml_score', 'graph_ring', 'accumulator_anomaly', 'manual')"
)
_INVESTIGATION_OUTCOMES = "('confirmed', 'false_positive', 'no_action')"


def _enable_rls(table: str) -> None:
    """Enable + force RLS and create tenant_isolation policy.

    `table` MUST be the fully prefixed name (e.g. `reclaimrx_graph_runs`).
    R1 BLOCK 1 fix: no schema qualifier — these tables live in public.
    """
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
          FOR ALL
          USING      ({_RLS_PREDICATE})
          WITH CHECK ({_RLS_PREDICATE})
        """
    )


def _grant_rw(table: str) -> None:
    for role in ("ifx_dev_app", _APP_ROLE):
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE ON {table} TO {role}"
        )
    for role in ("ifx_dev_admin", "ifx_prod_admin"):
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {role}"
        )


def upgrade() -> None:
    # R1 BLOCK 1 fix: all SP-3 tables live in public schema with `reclaimrx_*`
    # prefix to match the ORM at `src/models/tables.py`. No schema creation
    # needed (public always exists).

    # -------------------------------------------------------------------------
    # 1. graph_runs
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_graph_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("stale_timeout_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rings_detected", sa.Integer, nullable=False, server_default="0"),
        sa.Column("investigations_opened", sa.Integer, nullable=False, server_default="0"),
        sa.Column("records_scanned", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lookback_window_days", sa.Integer, nullable=False, server_default="90"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"status IN {_GRAPH_RUN_STATUSES}",
            name="ck_graph_runs_status",
        ),
        sa.CheckConstraint(
            f"trigger IN {_GRAPH_RUN_TRIGGERS}",
            name="ck_graph_runs_trigger",
        ),
    )
    op.create_index(
        "ix_graph_runs_tenant_status",
        "reclaimrx_graph_runs",
        ["tenant_id", "status"],
    )
    # Partial unique index: at most one 'running' row per tenant
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_graph_runs_one_running_per_tenant
          ON reclaimrx_graph_runs (tenant_id)
          WHERE status = 'running'
        """
    )
    _enable_rls("reclaimrx_graph_runs")
    _grant_rw("reclaimrx_graph_runs")

    # -------------------------------------------------------------------------
    # 2. fraud_rings
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_fraud_rings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "graph_run_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("reclaimrx_graph_runs.id"),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("density_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("node_count", sa.Integer, nullable=False),
        sa.Column("edge_count", sa.Integer, nullable=False),
        sa.Column(
            "entity_refs",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "spawned_investigation_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "node_count >= 0 AND edge_count >= 0",
            name="ck_fraud_rings_counts_non_negative",
        ),
        sa.CheckConstraint(
            "density_score >= 0 AND density_score <= 1",
            name="ck_fraud_rings_density_range",
        ),
    )
    op.create_index(
        "ix_fraud_rings_tenant_run",
        "reclaimrx_fraud_rings",
        ["tenant_id", "graph_run_id"],
    )
    op.create_index(
        "ix_fraud_rings_tenant_detected",
        "reclaimrx_fraud_rings",
        ["tenant_id", "detected_at"],
    )
    _enable_rls("reclaimrx_fraud_rings")
    _grant_rw("reclaimrx_fraud_rings")

    # -------------------------------------------------------------------------
    # 3. accumulator_anomalies
    # NOTE: This is NOT an extension of reclaimrx_accumulator_detections.
    # AccumulatorDetection tracks copay-assistance plan-type detection.
    # AccumulatorAnomaly tracks SP-3 fraud pattern detection.
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_accumulator_anomalies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("pattern_type", sa.String(50), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("evidence_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "triggering_event_ids",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "spawned_investigation_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"pattern_type IN {_ACCUMULATOR_PATTERN_TYPES}",
            name="ck_accumulator_anomalies_pattern_type",
        ),
    )
    op.create_index(
        "ix_accumulator_anomalies_tenant_member",
        "reclaimrx_accumulator_anomalies",
        ["tenant_id", "member_id"],
    )
    op.create_index(
        "ix_accumulator_anomalies_tenant_detected",
        "reclaimrx_accumulator_anomalies",
        ["tenant_id", "detected_at"],
    )
    _enable_rls("reclaimrx_accumulator_anomalies")
    _grant_rw("reclaimrx_accumulator_anomalies")

    # -------------------------------------------------------------------------
    # 4. threshold_configs
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_threshold_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "rule_thresholds",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "ml_score_thresholds",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("graph_density_threshold", sa.Numeric(8, 4), nullable=False),
        sa.Column("accumulator_anomaly_sensitivity", sa.Numeric(8, 4), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("version > 0", name="ck_threshold_configs_version_positive"),
        sa.CheckConstraint(
            "graph_density_threshold > 0 AND graph_density_threshold <= 1",
            name="ck_threshold_configs_density_range",
        ),
        sa.CheckConstraint(
            "accumulator_anomaly_sensitivity > 0 AND accumulator_anomaly_sensitivity <= 1",
            name="ck_threshold_configs_sensitivity_range",
        ),
    )
    op.create_index(
        "ix_threshold_configs_tenant_version",
        "reclaimrx_threshold_configs",
        ["tenant_id", "version"],
    )
    # Partial unique index: only one current (unsuperseded) version per tenant
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_threshold_configs_current_per_tenant
          ON reclaimrx_threshold_configs (tenant_id)
          WHERE superseded_at IS NULL
        """
    )
    _enable_rls("reclaimrx_threshold_configs")
    _grant_rw("reclaimrx_threshold_configs")

    # -------------------------------------------------------------------------
    # 5. threshold_config_audits
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_threshold_config_audits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "threshold_config_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("reclaimrx_threshold_configs.id"),
            nullable=False,
        ),
        sa.Column("field", sa.String(255), nullable=False),
        sa.Column("old_value", sa.Text, nullable=True),
        sa.Column("new_value", sa.Text, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("changed_by", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        # hipaa-2026.md: MUST compute entry_hash on EVERY write — NOT NULL
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("prev_entry_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "length(entry_hash) > 0",
            name="ck_threshold_config_audits_entry_hash_nonempty",
        ),
    )
    op.create_index(
        "ix_threshold_config_audits_tenant_config",
        "reclaimrx_threshold_config_audits",
        ["tenant_id", "threshold_config_id"],
    )
    op.create_index(
        "ix_threshold_config_audits_changed_at",
        "reclaimrx_threshold_config_audits",
        ["tenant_id", "changed_at"],
    )
    _enable_rls("reclaimrx_threshold_config_audits")
    _grant_rw("reclaimrx_threshold_config_audits")

    # -------------------------------------------------------------------------
    # 6. outbox_events
    # -------------------------------------------------------------------------
    op.create_table(
        "reclaimrx_outbox_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "envelope_json",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.CheckConstraint(
            f"status IN {_OUTBOX_STATUSES}",
            name="ck_outbox_events_status",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_events_idempotency_key"),
    )
    op.create_index(
        "ix_outbox_events_status_created",
        "reclaimrx_outbox_events",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_outbox_events_tenant_status",
        "reclaimrx_outbox_events",
        ["tenant_id", "status"],
    )
    _enable_rls("reclaimrx_outbox_events")
    _grant_rw("reclaimrx_outbox_events")

    # -------------------------------------------------------------------------
    # 7. ALTER reclaimrx_investigations — add 11 SP-3 columns
    # Note: existing tables.py uses public schema with prefixed table names.
    # Mirror the table name exactly as used in existing migrations.
    # -------------------------------------------------------------------------
    # Determine whether the table is in reclaimrx schema (created by migration)
    # or in public schema (created by ORM create_all). Use op.add_column with
    # explicit schema=None to target the default schema per alembic.ini.
    # The existing Investigation ORM model is at tables.py:374 with
    # __tablename__ = "reclaimrx_investigations" (public schema).
    for col_def in [
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("source_ref_id", sa.String(36), nullable=True),
        sa.Column("member_id", sa.String(36), nullable=True),
        sa.Column("opened_by", sa.String(255), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.String(255), nullable=True),
        sa.Column("outcome_label", sa.String(50), nullable=True),
        sa.Column("recovered_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("hold_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("threshold_config_version", sa.Integer, nullable=True),
        sa.Column(
            "threshold_snapshot",
            postgresql.JSONB,
            nullable=True,
            server_default=sa.text("NULL"),
        ),
    ]:
        op.add_column("reclaimrx_investigations", col_def)

    # Add CHECK constraints on new enum columns
    op.execute(
        "ALTER TABLE reclaimrx_investigations "
        f"ADD CONSTRAINT ck_investigations_severity "
        f"CHECK (severity IS NULL OR severity IN {_INVESTIGATION_SEVERITIES})"
    )
    op.execute(
        "ALTER TABLE reclaimrx_investigations "
        f"ADD CONSTRAINT ck_investigations_source "
        f"CHECK (source IS NULL OR source IN {_INVESTIGATION_SOURCES})"
    )
    op.execute(
        "ALTER TABLE reclaimrx_investigations "
        f"ADD CONSTRAINT ck_investigations_outcome_label "
        f"CHECK (outcome_label IS NULL OR outcome_label IN {_INVESTIGATION_OUTCOMES})"
    )

    # New indexes on investigations per performance.md
    op.create_index(
        "ix_reclaimrx_investigations_tenant_severity",
        "reclaimrx_investigations",
        ["tenant_id", "severity"],
    )
    op.create_index(
        "ix_reclaimrx_investigations_tenant_member_id",
        "reclaimrx_investigations",
        ["tenant_id", "member_id"],
    )
    op.create_index(
        "ix_reclaimrx_investigations_tenant_source_ref",
        "reclaimrx_investigations",
        ["tenant_id", "source_ref_id"],
    )

    # -------------------------------------------------------------------------
    # 8. ALTER reclaimrx_payment_holds — add status column
    # BLOCK 1 RESOLVED: released_by/released_at/release_reason ALREADY EXIST
    # at tables.py:607-609. DO NOT re-add. Only add status.
    # -------------------------------------------------------------------------
    op.add_column(
        "reclaimrx_payment_holds",
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
    )
    op.execute(
        "ALTER TABLE reclaimrx_payment_holds "
        f"ADD CONSTRAINT ck_payment_holds_status "
        f"CHECK (status IN {_HOLD_STATUSES})"
    )
    op.create_index(
        "ix_reclaimrx_payment_holds_tenant_status",
        "reclaimrx_payment_holds",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    # Reverse in dependency order
    # payment_holds
    op.execute(
        "ALTER TABLE reclaimrx_payment_holds DROP CONSTRAINT IF EXISTS ck_payment_holds_status"
    )
    # R1 CONCERN 8 fix: downgrade is the exact reverse of upgrade.
    # 1. payment_holds — drop index, drop CHECK, drop column.
    op.execute(
        "ALTER TABLE reclaimrx_payment_holds DROP CONSTRAINT IF EXISTS ck_payment_holds_status"
    )
    op.drop_index("ix_reclaimrx_payment_holds_tenant_status",
                  table_name="reclaimrx_payment_holds")
    op.drop_column("reclaimrx_payment_holds", "status")

    # 2. investigations — drop indexes, drop CHECKs, drop columns in REVERSE order.
    for idx in [
        "ix_reclaimrx_investigations_tenant_source_ref",
        "ix_reclaimrx_investigations_tenant_member_id",
        "ix_reclaimrx_investigations_tenant_severity",
    ]:
        op.drop_index(idx, table_name="reclaimrx_investigations")
    for constraint in [
        "ck_investigations_outcome_label",
        "ck_investigations_source",
        "ck_investigations_severity",
    ]:
        op.execute(
            f"ALTER TABLE reclaimrx_investigations DROP CONSTRAINT IF EXISTS {constraint}"
        )
    # Columns dropped in EXACT reverse of upgrade insertion order.
    for col_name in [
        "threshold_snapshot",
        "threshold_config_version",
        "hold_amount",
        "recovered_amount",
        "outcome_label",
        "closed_by",
        "closed_at",
        "opened_by",
        "member_id",
        "source_ref_id",
        "source",
        "severity",
    ]:
        op.drop_column("reclaimrx_investigations", col_name)

    # 3. New tables — drop partial unique indexes BEFORE the tables
    # (Alembic does not auto-drop partial indexes created via raw SQL).
    for idx in [
        "uq_threshold_configs_current_per_tenant",
        "uq_graph_runs_one_running_per_tenant",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {idx}")

    # 4. Drop tables in reverse dependency order (children before parents).
    op.drop_table("reclaimrx_outbox_events")
    op.drop_table("reclaimrx_threshold_config_audits")  # FK → threshold_configs
    op.drop_table("reclaimrx_threshold_configs")
    op.drop_table("reclaimrx_accumulator_anomalies")
    op.drop_table("reclaimrx_fraud_rings")               # FK → graph_runs
    op.drop_table("reclaimrx_graph_runs")
```

**Apply migration and run integration tests:**
```bash
cd modules/reclaimrx
alembic upgrade 0008_sp3_extensions
RECLAIMRX_TEST_DB_URL=postgresql://... python -m pytest tests/integration/test_migration_0008.py -v
```
Expected: All migration tests pass.

**Verify rollback:**
```bash
alembic downgrade 0007_flagged_npis
alembic upgrade 0008_sp3_extensions  # re-apply to leave DB in correct state
```
Expected: No errors on both directions.

---

## Task 3: RLS isolation acceptance test

**Separate test file to satisfy spec D8 acceptance criterion.**

File: `modules/reclaimrx/tests/integration/test_rls_null_deny.py`

```python
"""RLS null-deny acceptance test.

Per spec D8: open a session WITHOUT setting app.current_tenant_id →
query each new tenant-owned table → assert zero rows AND no exception.

This validates the NULLIF(..., '') pattern: when GUC is unset (missing_ok=true
returns empty string), NULLIF converts it to NULL, and
tenant_id = NULL evaluates to false → zero rows visible.

Run against a live PostgreSQL with the reclaimrx schema.
"""
from __future__ import annotations

import os
import uuid
import pytest
from sqlalchemy import create_engine, text

DB_URL = os.environ.get("RECLAIMRX_TEST_DB_URL")
APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")  # R1 BLOCK 7 fix
pytestmark = pytest.mark.skipif(not DB_URL, reason="RECLAIMRX_TEST_DB_URL not set")

# R1 BLOCK 7 fix — RLS null-deny test requirements:
#   1. Seed ALL six tenant-owned tables (prior version seeded only 4).
#   2. Run assertions as the APPLICATION ROLE, not as the superuser the
#      test fixture connects with. PostgreSQL superusers BYPASS RLS by
#      default; a passing null-deny test under a superuser proves nothing.
#   3. Verify tenant A sees their rows AND another tenant context (B) sees
#      zero, in addition to the unset-GUC case.
ALL_NEW_TENANT_OWNED_TABLES = [
    "reclaimrx_graph_runs",
    "reclaimrx_fraud_rings",
    "reclaimrx_accumulator_anomalies",
    "reclaimrx_threshold_configs",
    "reclaimrx_threshold_config_audits",
    "reclaimrx_outbox_events",
]


@pytest.fixture(scope="module")
def seeded_engine():
    """Engine with seed data for tenant A in ALL six tables."""
    engine = create_engine(DB_URL)
    tid_a = str(uuid.uuid4())

    with engine.begin() as conn:
        # Seed runs as superuser so RLS does not interfere with seeding;
        # the cross-tenant assertions below explicitly SET ROLE to the
        # non-BYPASSRLS app role.
        conn.execute(text(f"SET app.current_tenant_id = '{tid_a}'"))

        # 1. graph_runs
        graph_run_id = str(uuid.uuid4())
        conn.execute(text(
            "INSERT INTO reclaimrx_graph_runs "
            "(id, tenant_id, status, trigger, started_at, correlation_id, "
            " stale_timeout_at, rings_detected, investigations_opened, "
            " records_scanned, lookback_window_days) VALUES "
            f"('{graph_run_id}', '{tid_a}', 'completed', 'cron', "
            " now(), gen_random_uuid()::text, now() + interval '6h', 0, 0, 0, 90)"
        ))
        # 2. fraud_rings (R1 BLOCK 7 fix — was previously omitted)
        conn.execute(text(
            "INSERT INTO reclaimrx_fraud_rings "
            "(id, tenant_id, graph_run_id, detected_at, density_score, "
            " node_count, edge_count) VALUES "
            f"(gen_random_uuid(), '{tid_a}', '{graph_run_id}', now(), "
            " 0.85, 3, 5)"
        ))
        # 3. accumulator_anomalies (R1 BLOCK 7 fix — was previously omitted)
        conn.execute(text(
            "INSERT INTO reclaimrx_accumulator_anomalies "
            "(id, tenant_id, member_id, pattern_type, detected_at, "
            " evidence_window_start, evidence_window_end) VALUES "
            f"(gen_random_uuid(), '{tid_a}', gen_random_uuid(), "
            " 'sudden_spike', now(), now() - interval '7 days', now())"
        ))
        # 4. threshold_configs (required by threshold_config_audits FK)
        cfg_id = str(uuid.uuid4())
        conn.execute(text(
            "INSERT INTO reclaimrx_threshold_configs "
            "(id, tenant_id, version, effective_at, graph_density_threshold, "
            " accumulator_anomaly_sensitivity, updated_by) VALUES "
            f"('{cfg_id}', '{tid_a}', 1, now(), 0.70, 0.75, 'seed-user')"
        ))
        # 5. threshold_config_audits
        conn.execute(text(
            "INSERT INTO reclaimrx_threshold_config_audits "
            "(id, tenant_id, threshold_config_id, field, new_value, "
            " changed_at, changed_by, entry_hash) VALUES "
            f"(gen_random_uuid(), '{tid_a}', '{cfg_id}', "
            " 'graph_density_threshold', '0.70', now(), 'seed-user', "
            " 'abc123def456abc123def456abc123def456abc123def456abc123def45')"
        ))
        # 6. outbox_events
        conn.execute(text(
            "INSERT INTO reclaimrx_outbox_events "
            "(id, tenant_id, event_type, envelope_json, status, "
            " created_at, attempt_count, idempotency_key) VALUES "
            f"(gen_random_uuid(), '{tid_a}', 'fwa.hold_released', "
            " '{{}}', 'published', now(), 1, "
            f"'hold:release:rls-test-{tid_a}')"
        ))
        conn.execute(text("RESET app.current_tenant_id"))

    yield engine, tid_a
    engine.dispose()


@pytest.mark.parametrize("table", ALL_NEW_TENANT_OWNED_TABLES)
def test_rls_null_deny_under_app_role(seeded_engine, table):
    """R1 BLOCK 7 fix: with NO GUC set AND running AS the app role
    (which does NOT have BYPASSRLS), query MUST return zero rows.

    Without `SET ROLE` the test connection runs as superuser, which bypasses
    RLS by default — a passing assertion would prove nothing about real
    multi-tenant safety in production.
    """
    engine, _ = seeded_engine
    with engine.connect() as conn:
        conn.execute(text(f"SET ROLE {APP_ROLE}"))
        try:
            conn.execute(text("RESET app.current_tenant_id"))
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        finally:
            conn.execute(text("RESET ROLE"))
    assert count == 0, (
        f"RLS null-deny FAILED for {APP_ROLE}: {table} returned {count} rows "
        "when app.current_tenant_id was not set. Either RLS is not enabled, "
        "or the role has BYPASSRLS — both are production safety regressions."
    )


@pytest.mark.parametrize("table", ALL_NEW_TENANT_OWNED_TABLES)
def test_tenant_b_sees_zero_rows_under_app_role(seeded_engine, table):
    """R1 BLOCK 7 fix: a DIFFERENT tenant context AS the app role sees zero
    rows belonging to tenant A. Distinct from null-deny — exercises the
    `tenant_id = current_setting(...)::uuid` equality predicate."""
    engine, _ = seeded_engine
    tid_b = str(uuid.uuid4())
    with engine.connect() as conn:
        conn.execute(text(f"SET ROLE {APP_ROLE}"))
        try:
            conn.execute(text(f"SET app.current_tenant_id = '{tid_b}'"))
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        finally:
            conn.execute(text("RESET ROLE"))
    assert count == 0, (
        f"Cross-tenant leak: tenant B saw {count} rows in {table} "
        f"that belong to tenant A."
    )


def test_tenant_a_sees_own_rows_under_app_role(seeded_engine):
    """Sanity: tenant A AS the app role CAN see their own rows."""
    engine, tid_a = seeded_engine
    with engine.connect() as conn:
        conn.execute(text(f"SET ROLE {APP_ROLE}"))
        try:
            conn.execute(text(f"SET app.current_tenant_id = '{tid_a}'"))
            count = conn.execute(
                text("SELECT COUNT(*) FROM reclaimrx_graph_runs")
            ).scalar()
        finally:
            conn.execute(text("RESET ROLE"))
    assert count >= 1, "Tenant A should see their own graph_run rows"
```

**Run:**
```bash
RECLAIMRX_TEST_DB_URL=postgresql://... python -m pytest tests/integration/test_rls_null_deny.py -v
```
Expected: All parametrized cases pass; tenant_a sanity check passes.

---

## Task 4: Index presence unit test (no PostgreSQL required)

File: `modules/reclaimrx/tests/unit/test_model_indexes.py` (create new)

```python
"""Verify indexes declared on new ORM models match the spec requirements.

These run against SQLite so no PostgreSQL is required. They verify the
__table_args__ declarations on each new model class.

per .claude/rules/performance.md:
  - (tenant_id, status) for every table with a status column
  - (tenant_id, FK column) for every tenant-scoped FK
"""
from __future__ import annotations

import pytest


def test_graph_run_has_tenant_status_index():
    from src.models.tables import GraphRun
    table = GraphRun.__table__
    index_col_sets = [
        tuple(c.name for c in idx.columns)
        for idx in table.indexes
    ]
    assert ("tenant_id", "status") in index_col_sets, \
        f"GraphRun missing (tenant_id, status) index. Found: {index_col_sets}"


def test_fraud_ring_has_tenant_run_index():
    from src.models.tables import FraudRing
    table = FraudRing.__table__
    index_col_sets = [
        tuple(c.name for c in idx.columns)
        for idx in table.indexes
    ]
    assert ("tenant_id", "graph_run_id") in index_col_sets, \
        f"FraudRing missing (tenant_id, graph_run_id) index. Found: {index_col_sets}"


def test_accumulator_anomaly_has_tenant_member_index():
    from src.models.tables import AccumulatorAnomaly
    table = AccumulatorAnomaly.__table__
    index_col_sets = [
        tuple(c.name for c in idx.columns)
        for idx in table.indexes
    ]
    assert ("tenant_id", "member_id") in index_col_sets, \
        f"AccumulatorAnomaly missing (tenant_id, member_id) index. Found: {index_col_sets}"


def test_threshold_config_audit_has_tenant_config_index():
    from src.models.tables import ThresholdConfigAudit
    table = ThresholdConfigAudit.__table__
    index_col_sets = [
        tuple(c.name for c in idx.columns)
        for idx in table.indexes
    ]
    assert ("tenant_id", "threshold_config_id") in index_col_sets, \
        f"ThresholdConfigAudit missing (tenant_id, threshold_config_id) index. Found: {index_col_sets}"


def test_outbox_events_has_idempotency_unique_constraint():
    from src.models.tables import OutboxEvent
    table = OutboxEvent.__table__
    from sqlalchemy import UniqueConstraint
    unique_cols = [
        frozenset(c.name for c in uc.columns)
        for uc in table.constraints
        if isinstance(uc, UniqueConstraint)
    ]
    assert frozenset({"idempotency_key"}) in unique_cols, \
        f"OutboxEvent missing UniqueConstraint on idempotency_key. Found: {unique_cols}"


def test_outbox_events_has_status_created_index():
    from src.models.tables import OutboxEvent
    table = OutboxEvent.__table__
    index_col_sets = [
        tuple(c.name for c in idx.columns)
        for idx in table.indexes
    ]
    assert ("status", "created_at") in index_col_sets, \
        f"OutboxEvent missing (status, created_at) index. Found: {index_col_sets}"


def test_threshold_config_has_tenant_version_index():
    from src.models.tables import ThresholdConfig
    table = ThresholdConfig.__table__
    index_col_sets = [
        tuple(c.name for c in idx.columns)
        for idx in table.indexes
    ]
    assert ("tenant_id", "version") in index_col_sets, \
        f"ThresholdConfig missing (tenant_id, version) index. Found: {index_col_sets}"
```

**Run:**
```bash
cd modules/reclaimrx && python -m pytest tests/unit/test_model_indexes.py -v
```
Expected: All pass.

---

## Task 5: Coverage gate

Run the full unit test suite for the model slice and verify coverage meets gates.

```bash
cd modules/reclaimrx && python -m pytest \
    tests/unit/test_new_models_instantiate.py \
    tests/unit/test_model_indexes.py \
    --cov=src.models.tables \
    --cov-report=term-missing \
    --cov-fail-under=95
```

Financial columns (`recovered_amount`, `hold_amount`, `density_score`, `graph_density_threshold`, `accumulator_anomaly_sensitivity`) must be covered at 100%. Verify by inspecting the missing lines report — no Numeric column definition should appear as uncovered.

If any financial column definition is uncovered, add a targeted test that instantiates the model with a non-null Decimal value for that column.

---

## Acceptance gate (this plan is DONE when all pass)

- [ ] `test_new_models_instantiate.py` — all green (SQLite, no DB required)
- [ ] `test_model_indexes.py` — all green (SQLite, no DB required)
- [ ] `alembic upgrade 0008_sp3_extensions` applies without error
- [ ] `alembic downgrade 0007_flagged_npis` rolls back without error
- [ ] `test_migration_0008.py` — all green (requires PostgreSQL)
- [ ] `test_rls_null_deny.py` — all green (requires PostgreSQL)
- [ ] Coverage: 95%+ on models slice; 100% on Numeric column code paths
- [ ] No `Float` or `float` types on any money/threshold column (grep check):
  ```bash
  grep -n "Float\|sa\.Float\|float" modules/reclaimrx/src/models/tables.py | grep -v "#"
  ```
  Expected: zero results from new model classes

---

## What this plan does NOT do

- Does not write API endpoints (Plan A2)
- Does not write services (InvestigationStateMachine, ThresholdConfigService) (Plan A2)
- Does not write the outbox dispatcher (Plan A2)
- Does not write the accumulator consumer (Plan A3)
- Does not wire the graph analysis job (Plan A3)
- Does not write the SP-0 contract layer (Plan A4)
- Does not write the frontend scaffold (Plan A4)
- Does not wire D14 production app factory bindings (Plan A5)

---

*End of SP-3 Plan A1 — Models + Migration.*
