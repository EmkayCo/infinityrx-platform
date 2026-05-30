"""TDD tests for gate_rules() in batch_engine — Task 3.4.

RED phase: tests are written before the implementation.

Contract:
- gate_rules(db, run, available_columns) loads all enabled DetectionRuleInstance
  rows for run.tenant_id, joined to their DetectionRuleType.
- Returns the APPLICABLE subset: type.deferred_data_feed is False AND
  set(type.required_data_columns) <= available_columns.
- For each NON-applicable instance: writes ONE DetectionRuleEvaluationLog row
  with evaluation_result='skipped_inapplicable', source_table=NULL,
  source_row_id=NULL, no error_message (CHECK: error_message NULL iff result!='error').
- All four DB CHECKs are satisfied by the skip rows (no IntegrityError).

Fixture pattern:
- Module-scope SQLite engine with SAVEPOINT-based session isolation (LESSON-001).
- PG_UUID -> _UUIDString, JSONB -> JSON, ARRAY -> JSON (LESSON-007).
- Instances are created under _FULL_CSV_COLUMNS (13 instances).
- gate_rules is called with RESTRICTED columns -> 2 are inapplicable (MFR-001,
  MFR-003 both require extended_wac) -> 2 skip rows written, 11 returned.
  MFR-008 is now DEFERRED so it is never instantiated and never counted here.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import JSON, event, func, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session
from sqlalchemy.types import String, TypeDecorator

from src._shim.db import Base
from src.models.detection_run_models import (  # noqa: F401 — registers tables
    DetectionRuleEvaluationLog,
    DetectionRuleInstance,
    DetectionRuleType,
    DetectionRun,
)


# ---------------------------------------------------------------------------
# SQLite compatibility patch (must run before engine fixture) — LESSON-007
# ---------------------------------------------------------------------------

class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36)."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


for _table in Base.metadata.tables.values():
    for _col in _table.columns:
        if "sqlite" in getattr(_col.type, "_variant_mapping", {}):
            continue
        if isinstance(_col.type, PG_UUID):
            _col.type = _col.type.with_variant(_UUIDString(), "sqlite")
        elif isinstance(_col.type, JSONB):
            _col.type = _col.type.with_variant(JSON(), "sqlite")
        elif isinstance(_col.type, ARRAY):
            _col.type = _col.type.with_variant(JSON(), "sqlite")


# ---------------------------------------------------------------------------
# Engine + SAVEPOINT session fixtures (LESSON-001)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine with all reclaimrx tables materialised.

    Schema handling: table.schema values are NOT stripped.  StaticPool
    ensures every engine.connect() reuses the same DBAPI connection, and a
    pool-level 'connect' event ATTACHes ':memory:' AS 'reclaimrx' so that
    schema-qualified DDL/DML resolves correctly on SQLite.  Base.metadata
    stays schema-qualified so Postgres-gated tests running in the same
    process always emit fully-qualified 'reclaimrx.<table>' queries.

    NOTE: configure_engine / get_engine are not called here because
    gate_rules() receives an explicit db Session — it never calls
    get_engine() internally.  Building the engine directly keeps the
    shim state unaffected by this module-scoped fixture.
    """
    from sqlalchemy import create_engine as _ce
    from sqlalchemy import event as _sa_event
    from sqlalchemy.pool import StaticPool as _StaticPool

    eng = _ce(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=_StaticPool,
    )

    @_sa_event.listens_for(eng, "connect")
    def _attach(dbapi_conn, _rec):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS reclaimrx")

    with eng.connect() as _setup_conn:
        Base.metadata.create_all(_setup_conn)
        _setup_conn.commit()
    return eng


@pytest.fixture()
def db(engine) -> Session:
    """Function-scoped SAVEPOINT session; rolled back on teardown (LESSON-001)."""
    connection = engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")  # type: ignore[call-arg]

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
# Import under test (deliberately late so the patch applies first)
# ---------------------------------------------------------------------------
from src.detection.batch_engine import gate_rules  # noqa: E402
from src.detection.rule_type_registry import (  # noqa: E402
    RULE_TYPE_CATALOG,
    register_rule_instances,
    register_rule_types,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_SYSTEM_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Full CSV column set — union of all required_data_columns across the 13 RUN rules.
# MFR-008 is DEFERRED; statement_account not needed to instantiate rules.
_FULL_CSV_COLUMNS: set[str] = {
    "patient_unique_hash", "ndc", "date_of_service", "auth_no_hash",
    "transaction_code", "transaction_status",
    "day_supply",
    "pharmacy_npi", "prescriber_npi", "patient_state",
    "extended_wac", "ingredient_cost_paid", "dispensing_fee_paid",
    "quantity_dispensed",
    "reversed_check", "date_added_timestamp",
    "u_c", "pos_adjustment",
    "total_paid_amt",
}

# Restricted set: drop extended_wac -> MFR-001 and MFR-003 become inapplicable.
_RESTRICTED_COLUMNS: set[str] = _FULL_CSV_COLUMNS - {"extended_wac"}

# Rules that require extended_wac (become inapplicable under restricted set).
_INAPPLICABLE_CODES: set[str] = {"MFR-001", "MFR-003"}
_EXPECTED_APPLICABLE_COUNT = 11  # 13 - 2


# ---------------------------------------------------------------------------
# Helper: build a minimal DetectionRun stub for test purposes.
# ---------------------------------------------------------------------------

def _make_run(db: Session, tenant_id: uuid.UUID) -> DetectionRun:
    """Insert and return a DetectionRun row for tenant_id."""
    run = DetectionRun(
        tenant_id=tenant_id,
        data_source="csv_upload",
        run_label="test-run",
        created_by=_SYSTEM_UUID,
    )
    db.add(run)
    db.flush()
    return run


def _seed(db: Session, tenant_id: uuid.UUID) -> DetectionRun:
    """Seed rule types + instances under full columns; return run."""
    register_rule_types(db)
    register_rule_instances(db, tenant_id, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
    return _make_run(db, tenant_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGateRulesReturnValue:
    """gate_rules returns exactly the applicable instances."""

    def test_full_columns_returns_all_13(self, db: Session):
        """Full column set -> all 13 instances are applicable (MFR-008 DEFERRED)."""
        run = _seed(db, _TENANT_ID)
        applicable = gate_rules(db, run, _FULL_CSV_COLUMNS)
        assert len(applicable) == 13

    def test_restricted_columns_returns_11(self, db: Session):
        """Restricted set (no extended_wac) -> 11 applicable; 2 skip rows written."""
        run = _seed(db, _TENANT_ID)
        applicable = gate_rules(db, run, _RESTRICTED_COLUMNS)
        assert len(applicable) == _EXPECTED_APPLICABLE_COUNT

    def test_applicable_instances_are_detectionruleinstance_objects(self, db: Session):
        """Return list elements are DetectionRuleInstance ORM objects."""
        run = _seed(db, _TENANT_ID)
        applicable = gate_rules(db, run, _RESTRICTED_COLUMNS)
        for inst in applicable:
            assert isinstance(inst, DetectionRuleInstance)

    def test_inapplicable_codes_not_in_applicable_set(self, db: Session):
        """MFR-001 and MFR-003 must NOT appear in the returned applicable list."""
        run = _seed(db, _TENANT_ID)
        applicable = gate_rules(db, run, _RESTRICTED_COLUMNS)
        codes = {inst.rule_type_code for inst in applicable}
        for code in _INAPPLICABLE_CODES:
            assert code not in codes, (
                f"{code} requires extended_wac and must not be in applicable set"
            )

    def test_applicable_codes_correct(self, db: Session):
        """The 11 returned codes match the 13-RUN-set minus the two inapplicable ones."""
        run = _seed(db, _TENANT_ID)
        applicable = gate_rules(db, run, _RESTRICTED_COLUMNS)
        all_run_codes = {
            entry["code"]
            for entry in RULE_TYPE_CATALOG
            if not entry["deferred_data_feed"]
        }
        expected_codes = all_run_codes - _INAPPLICABLE_CODES
        returned_codes = {inst.rule_type_code for inst in applicable}
        assert returned_codes == expected_codes

    def test_empty_available_columns_returns_no_instances(self, db: Session):
        """When no columns are available, every instance is inapplicable."""
        run = _seed(db, _TENANT_ID)
        applicable = gate_rules(db, run, set())
        assert applicable == []


class TestSkipRowsWritten:
    """gate_rules writes one skipped_inapplicable row per non-applicable instance."""

    def test_two_skip_rows_written_for_restricted_columns(self, db: Session):
        """Exactly 2 skip rows (MFR-001 + MFR-003) for the restricted column set."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()
        skip_count = db.execute(
            select(func.count()).select_from(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalar()
        assert skip_count == 2

    def test_skip_rows_have_null_source_table(self, db: Session):
        """Run-wide skips must have source_table=NULL (no per-claim context)."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()
        rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalars().all()
        for row in rows:
            assert row.source_table is None, (
                f"source_table must be NULL for run-wide skip; got {row.source_table!r}"
            )

    def test_skip_rows_have_null_source_row_id(self, db: Session):
        """Run-wide skips must have source_row_id=NULL."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()
        rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalars().all()
        for row in rows:
            assert row.source_row_id is None, (
                f"source_row_id must be NULL for run-wide skip; got {row.source_row_id!r}"
            )

    def test_skip_rows_have_null_error_message(self, db: Session):
        """error_message must be NULL (CHECK: error_message non-null IFF result='error')."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()
        rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalars().all()
        for row in rows:
            assert row.error_message is None, (
                f"error_message must be NULL for skipped_inapplicable; got {row.error_message!r}"
            )

    def test_skip_rows_have_null_anomaly_id(self, db: Session):
        """anomaly_id must be NULL (CHECK: anomaly_id non-null IFF result='finding_raised')."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()
        rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalars().all()
        for row in rows:
            assert row.anomaly_id is None

    def test_skip_rows_reference_correct_run(self, db: Session):
        """All skip rows reference the detection_run_id of the run passed to gate_rules."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()
        rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
            )
        ).scalars().all()
        for row in rows:
            assert row.detection_run_id == run.id

    def test_skip_rows_tenant_id_matches_run(self, db: Session):
        """Skip rows carry the correct tenant_id."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()
        rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalars().all()
        for row in rows:
            assert row.tenant_id == _TENANT_ID

    def test_skip_rows_reference_inapplicable_instance_ids(self, db: Session):
        """The rule_instance_ids in skip rows are exactly MFR-001 and MFR-003 instances."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()

        # Find the instance IDs for MFR-001 and MFR-003.
        inapplicable_instances = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _TENANT_ID,
                DetectionRuleInstance.rule_type_code.in_(list(_INAPPLICABLE_CODES)),
            )
        ).scalars().all()
        inapplicable_ids = {inst.id for inst in inapplicable_instances}

        skip_rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalars().all()
        skip_instance_ids = {row.rule_instance_id for row in skip_rows}
        assert skip_instance_ids == inapplicable_ids

    def test_no_skip_rows_written_when_all_applicable(self, db: Session):
        """Full columns -> 0 skip rows written."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _FULL_CSV_COLUMNS)
        db.flush()
        skip_count = db.execute(
            select(func.count()).select_from(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalar()
        assert skip_count == 0

    def test_empty_columns_writes_13_skip_rows(self, db: Session):
        """Empty column set -> all 13 instances inapplicable -> 13 skip rows."""
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, set())
        db.flush()
        skip_count = db.execute(
            select(func.count()).select_from(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalar()
        assert skip_count == 13


class TestCheckConstraintSatisfied:
    """Verify that skip row inserts do NOT cause IntegrityError from any DB CHECK."""

    def test_commit_does_not_raise_integrity_error(self, db: Session):
        """INSERT of skip rows must not violate any CHECK constraint.

        Under SQLite the CHECKs are not enforced by default (SQLite ignores
        them unless PRAGMA enforce_foreign_keys / PRAGMA check_constraints is set).
        The test exercises the ORM insert path with the correct field values;
        the absence of IntegrityError + the field-value assertions in sibling
        tests together prove constraint satisfaction.
        """
        run = _seed(db, _TENANT_ID)
        # Should not raise.
        applicable = gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()
        # If we reach here, no IntegrityError was raised.
        assert len(applicable) == _EXPECTED_APPLICABLE_COUNT

    def test_evaluation_result_is_valid_enum_value(self, db: Session):
        """'skipped_inapplicable' is in the CHECK-allowed set."""
        allowed = {"no_finding", "finding_raised", "error", "skipped_inapplicable"}
        run = _seed(db, _TENANT_ID)
        gate_rules(db, run, _RESTRICTED_COLUMNS)
        db.flush()
        rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalars().all()
        for row in rows:
            assert row.evaluation_result in allowed, (
                f"evaluation_result {row.evaluation_result!r} not in allowed set"
            )


class TestOnlyEnabledInstancesConsidered:
    """gate_rules must filter on enabled=True; disabled instances are not evaluated."""

    def test_disabled_instance_not_returned_as_applicable(self, db: Session):
        """Disabling an instance means it is not returned even if its columns match."""
        run = _seed(db, _TENANT_ID)

        # Disable MFR-002 instance.
        mfr002_inst = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _TENANT_ID,
                DetectionRuleInstance.rule_type_code == "MFR-002",
            )
        ).scalar_one()
        mfr002_inst.enabled = False
        db.flush()

        applicable = gate_rules(db, run, _FULL_CSV_COLUMNS)
        codes = {inst.rule_type_code for inst in applicable}
        assert "MFR-002" not in codes

    def test_disabled_instance_not_written_to_skip_log(self, db: Session):
        """Disabled instances are silently excluded — no skip row written for them."""
        run = _seed(db, _TENANT_ID)

        mfr002_inst = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _TENANT_ID,
                DetectionRuleInstance.rule_type_code == "MFR-002",
            )
        ).scalar_one()
        mfr002_inst.enabled = False
        db.flush()

        gate_rules(db, run, _FULL_CSV_COLUMNS)
        db.flush()

        skip_count = db.execute(
            select(func.count()).select_from(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.detection_run_id == run.id,
            )
        ).scalar()
        # With full columns and only MFR-002 disabled, no instances are inapplicable
        # (MFR-002 is disabled, not inapplicable due to columns), so 0 skip rows.
        assert skip_count == 0
