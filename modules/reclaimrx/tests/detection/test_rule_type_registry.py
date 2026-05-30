"""TDD tests for the rule-type registry + 46-rule catalog + rule instance seeder.

Tests are written BEFORE the implementation (RED phase per TDD discipline).

Contract assertions:
- RULE_TYPE_CATALOG has >= 46 entries.
- register_rule_types(db) inserts exactly len(RULE_TYPE_CATALOG) rows on first call.
- Second call returns 0 (idempotent — DO NOTHING on conflict).
- Exactly 13 rules have deferred_data_feed=False (the "RUN" set).
  MFR-008 (Statement Credit Abuse) was reclassified to DEFERRED in the dry-run
  fix: it needs statement-only-pharmacy reference data not present in the CSV.
- Deferred rules have deferred_data_feed=True and a non-empty deferred_reason.
- MFR-001 is a RUN rule with required_data_columns containing 'extended_wac' and
  'ingredient_cost_paid', and family in {A1..A6}.
- ALL-002 is a DEFERRED rule with a truthy deferred_reason.
- MFR-008 is a DEFERRED rule with deferred_data_feed=True and a truthy deferred_reason.

register_rule_instances contract:
- Given full CSV column set: creates exactly 13 instances (the RUN rules).
- Deferred rules and rules with missing required columns get no instance.
- Second call returns 0 (idempotent).
- Restricted column set gates MFR-001 and MFR-003 (both require extended_wac).
- The 5 ML placeholder rows in ml_detector_registry are NOT touched by this function.

DB fixture pattern: SAVEPOINT-based isolation (LESSON-001).
UUID columns: _UUIDString TypeDecorator via module-level patch (LESSON-007).
ARRAY(String) is not natively supported by SQLite; the module-level patch swaps
it for a JSON column so required_data_columns round-trips correctly in SQLite.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Session
from sqlalchemy.types import String, TypeDecorator

# ---------------------------------------------------------------------------
# Module-level patch: SQLite compatibility for PG_UUID and ARRAY(String).
# Must happen BEFORE the engine fixture creates tables (LESSON-007).
# ---------------------------------------------------------------------------
from src._shim.db import Base
from src.models.detection_run_models import (  # noqa: F401 — registers tables
    DetectionRuleInstance,
    DetectionRuleType,
    MlDetectorRegistry,
)


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36) (LESSON-007)."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


# Patch ALL tables in Base.metadata for SQLite compatibility:
#   PG_UUID     -> _UUIDString (LESSON-007)
#   JSONB       -> JSON        (SQLite has no JSONB)
#   ARRAY(any)  -> JSON        (SQLite has no ARRAY, regardless of item type)
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
    register_rule_types() / register_rule_instances() receive an explicit
    db Session — they never call get_engine() internally.
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
# Imports under test (deliberately late so the patch applies first)
# ---------------------------------------------------------------------------
from src.detection.rule_type_registry import (  # noqa: E402
    RULE_TYPE_CATALOG,
    register_rule_instances,
    register_rule_types,
)

# ---------------------------------------------------------------------------
# Constants for the 13 RUN rules (deferred_data_feed=False)
# MFR-008 reclassified to DEFERRED (needs statement-only-pharmacy reference data).
# ---------------------------------------------------------------------------
_RUN_CODES = {
    "ALL-001", "MFR-001", "MFR-002", "ALL-005", "HP-010", "TH-005",
    "TH-002", "MFR-004", "MFR-003", "HP-005", "HP-008",
    "ALL-006", "MFR-009",
}
_VALID_FAMILIES = {"A1", "A2", "A3", "A4", "A5", "A6"}

# Full CSV column set — union of all required_data_columns across the 13 RUN rules.
# MFR-008 is now DEFERRED; statement_account is no longer needed to instantiate rules.
_FULL_CSV_COLUMNS: set[str] = {
    # ALL-001
    "patient_unique_hash", "ndc", "date_of_service", "auth_no_hash",
    "transaction_code", "transaction_status",
    # ALL-005
    "day_supply",
    # ALL-006 / MFR-004 / HP-005 / HP-010 / TH-005
    "pharmacy_npi", "prescriber_npi", "patient_state",
    # MFR-001 / MFR-003
    "extended_wac", "ingredient_cost_paid", "dispensing_fee_paid",
    "quantity_dispensed",
    # MFR-002
    "reversed_check", "date_added_timestamp",
    # MFR-009
    "u_c", "pos_adjustment",
    # HP-008
    "total_paid_amt",
}

# A system UUID used as created_by for instances in tests.
_SYSTEM_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCatalogCompleteness:
    def test_catalog_has_at_least_46_rules(self):
        assert len(RULE_TYPE_CATALOG) >= 46, (
            f"Expected >= 46 rules, got {len(RULE_TYPE_CATALOG)}"
        )

    def test_every_rule_has_required_keys(self):
        required = {
            "code", "name", "description", "family",
            "parameter_schema_version", "default_severity", "default_confidence",
            "requires_baseline", "requires_history",
            "deferred_data_feed", "deferred_reason",
            "required_data_columns", "default_parameters",
        }
        for rule in RULE_TYPE_CATALOG:
            missing = required - rule.keys()
            assert not missing, f"Rule {rule.get('code')} missing keys: {missing}"

    def test_all_families_are_valid(self):
        for rule in RULE_TYPE_CATALOG:
            assert rule["family"] in _VALID_FAMILIES, (
                f"Rule {rule['code']} has invalid family {rule['family']!r}"
            )

    def test_exactly_13_run_rules(self):
        run_rules = [r for r in RULE_TYPE_CATALOG if not r["deferred_data_feed"]]
        codes = {r["code"] for r in run_rules}
        assert len(run_rules) == 13, (
            f"Expected 13 RUN rules, got {len(run_rules)}: {codes}"
        )
        assert codes == _RUN_CODES, (
            f"RUN rule codes mismatch.\nExpected: {_RUN_CODES}\nGot: {codes}"
        )

    def test_deferred_rules_have_reason(self):
        for rule in RULE_TYPE_CATALOG:
            if rule["deferred_data_feed"]:
                assert rule["deferred_reason"], (
                    f"Rule {rule['code']} is deferred but has empty deferred_reason"
                )

    def test_run_rules_have_non_empty_required_data_columns(self):
        for rule in RULE_TYPE_CATALOG:
            if not rule["deferred_data_feed"]:
                assert rule["required_data_columns"], (
                    f"RUN rule {rule['code']} must have non-empty required_data_columns"
                )

    def test_default_confidence_is_float_in_0_1(self):
        for rule in RULE_TYPE_CATALOG:
            c = rule["default_confidence"]
            assert isinstance(c, float), (
                f"Rule {rule['code']} default_confidence must be float, got {type(c)}"
            )
            assert 0.0 < c <= 1.0, (
                f"Rule {rule['code']} default_confidence {c} out of (0, 1]"
            )

    def test_default_severity_values(self):
        valid_severities = {"low", "medium", "high", "critical"}
        for rule in RULE_TYPE_CATALOG:
            assert rule["default_severity"] in valid_severities, (
                f"Rule {rule['code']} has invalid severity {rule['default_severity']!r}"
            )


class TestMfr001RunRule:
    """Spot-check MFR-001 (NQ Inflation) — a canonical RUN rule."""

    def test_mfr001_not_deferred(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-001")
        assert rule["deferred_data_feed"] is False

    def test_mfr001_required_columns_contain_extended_wac(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-001")
        assert "extended_wac" in rule["required_data_columns"]

    def test_mfr001_required_columns_contain_ingredient_cost_paid(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-001")
        assert "ingredient_cost_paid" in rule["required_data_columns"]

    def test_mfr001_family_is_valid(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-001")
        assert rule["family"] in _VALID_FAMILIES

    def test_mfr001_family_is_a1(self):
        """pricing_integrity maps to A1."""
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-001")
        assert rule["family"] == "A1"

    def test_mfr001_default_parameters_preserve_thresholds(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-001")
        params = rule["default_parameters"]
        assert "threshold" in params
        assert params["threshold"] == 1.10


class TestAll002DeferredRule:
    """Spot-check ALL-002 (Phantom Pharmacy) — a canonical DEFERRED rule."""

    def test_all002_is_deferred(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "ALL-002")
        assert rule["deferred_data_feed"] is True

    def test_all002_deferred_reason_is_truthy(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "ALL-002")
        assert rule["deferred_reason"]


class TestMfr008DeferredRule:
    """MFR-008 (Statement Credit Abuse) reclassified to DEFERRED.

    The naive 'fires on any non-empty statement_account' logic was a false-positive
    flood: a populated statement_account is normal for statement-only pharmacies and
    not fraud without knowing which pharmacies are contractually statement-only.
    That reference data is not present in the CSV.
    """

    def test_mfr008_is_deferred(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-008")
        assert rule["deferred_data_feed"] is True, (
            "MFR-008 must be DEFERRED — requires statement-only-pharmacy reference data"
        )

    def test_mfr008_deferred_reason_is_truthy(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-008")
        assert rule["deferred_reason"], (
            "MFR-008 deferred_reason must explain why it needs reference data"
        )

    def test_mfr008_not_in_run_codes(self):
        assert "MFR-008" not in _RUN_CODES, (
            "MFR-008 must not appear in the RUN code set"
        )


class TestBaselineRequiredRules:
    """Rules flagged requires_baseline=True must be in the RUN set."""

    def test_baseline_rules_are_run_rules(self):
        for rule in RULE_TYPE_CATALOG:
            if rule["requires_baseline"]:
                assert not rule["deferred_data_feed"], (
                    f"Rule {rule['code']} requires_baseline=True but is deferred"
                )

    def test_mfr004_requires_baseline(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-004")
        assert rule["requires_baseline"] is True

    def test_mfr003_requires_baseline(self):
        rule = next(r for r in RULE_TYPE_CATALOG if r["code"] == "MFR-003")
        assert rule["requires_baseline"] is True


class TestRegisterRuleTypes:
    """Integration tests for the register_rule_types(db) upsert function."""

    def test_first_call_inserts_all_rules(self, db: Session):
        count = register_rule_types(db)
        assert count == len(RULE_TYPE_CATALOG)

    def test_second_call_returns_zero(self, db: Session):
        register_rule_types(db)
        count2 = register_rule_types(db)
        assert count2 == 0

    def test_rows_in_db_match_catalog_size(self, db: Session):
        from sqlalchemy import func, select

        register_rule_types(db)
        total = db.execute(
            select(func.count()).select_from(DetectionRuleType)
        ).scalar()
        assert total == len(RULE_TYPE_CATALOG)

    def test_mfr001_row_deferred_false(self, db: Session):
        from sqlalchemy import select

        register_rule_types(db)
        row = db.execute(
            select(DetectionRuleType).where(DetectionRuleType.code == "MFR-001")
        ).scalar_one()
        assert row.deferred_data_feed is False

    def test_mfr001_row_required_columns(self, db: Session):
        from sqlalchemy import select

        register_rule_types(db)
        row = db.execute(
            select(DetectionRuleType).where(DetectionRuleType.code == "MFR-001")
        ).scalar_one()
        cols = row.required_data_columns
        assert "extended_wac" in cols
        assert "ingredient_cost_paid" in cols

    def test_all002_row_is_deferred(self, db: Session):
        from sqlalchemy import select

        register_rule_types(db)
        row = db.execute(
            select(DetectionRuleType).where(DetectionRuleType.code == "ALL-002")
        ).scalar_one()
        assert row.deferred_data_feed is True
        assert row.deferred_reason

    def test_exactly_13_run_rows_in_db(self, db: Session):
        from sqlalchemy import select

        register_rule_types(db)
        rows = db.execute(
            select(DetectionRuleType).where(DetectionRuleType.deferred_data_feed.is_(False))
        ).scalars().all()
        assert len(rows) == 13

    def test_all_run_rows_have_required_data_columns(self, db: Session):
        from sqlalchemy import select

        register_rule_types(db)
        rows = db.execute(
            select(DetectionRuleType).where(DetectionRuleType.deferred_data_feed.is_(False))
        ).scalars().all()
        for row in rows:
            assert row.required_data_columns, (
                f"RUN rule {row.code} has empty required_data_columns in DB"
            )

    def test_mfr008_row_is_deferred_in_db(self, db: Session):
        from sqlalchemy import select

        register_rule_types(db)
        row = db.execute(
            select(DetectionRuleType).where(DetectionRuleType.code == "MFR-008")
        ).scalar_one()
        assert row.deferred_data_feed is True, (
            "MFR-008 must be stored as deferred in DB"
        )
        assert row.deferred_reason, (
            "MFR-008 deferred_reason must be non-empty in DB"
        )


class TestRegisterRuleInstances:
    """Integration tests for register_rule_instances(db, tenant_id, available_columns)."""

    def _seed_types(self, db: Session) -> None:
        """Seed rule types; required before instances (FK constraint)."""
        register_rule_types(db)

    def test_full_columns_creates_13_instances(self, db: Session):
        """Full CSV column set → exactly 13 instances (one per RUN rule).

        MFR-008 is now DEFERRED so it does not produce an instance even when
        statement_account is present in the column set.
        """
        from sqlalchemy import func, select

        self._seed_types(db)
        count = register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        assert count == 13
        total = db.execute(
            select(func.count()).select_from(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID
            )
        ).scalar()
        assert total == 13

    def test_idempotent_second_call_returns_zero(self, db: Session):
        """Second call with same tenant + columns → 0 inserts."""
        self._seed_types(db)
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        count2 = register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        assert count2 == 0

    def test_idempotent_row_count_unchanged(self, db: Session):
        """Total row count is still 13 after second call."""
        from sqlalchemy import func, select

        self._seed_types(db)
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        total = db.execute(
            select(func.count()).select_from(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID
            )
        ).scalar()
        assert total == 13

    def test_deferred_rules_get_no_instance(self, db: Session):
        """Deferred rules (deferred_data_feed=True) must not produce instances."""
        from sqlalchemy import select

        self._seed_types(db)
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        # ALL-002 is deferred; no instance should exist for it.
        rows = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID,
                DetectionRuleInstance.rule_type_code == "ALL-002",
            )
        ).scalars().all()
        assert rows == [], "ALL-002 is deferred and must not have an instance"

    def test_instance_codes_match_run_rule_set(self, db: Session):
        """The 14 instance rule_type_codes equal the expected RUN rule set."""
        from sqlalchemy import select

        self._seed_types(db)
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        rows = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID
            )
        ).scalars().all()
        codes = {r.rule_type_code for r in rows}
        assert codes == _RUN_CODES

    def test_instance_parameters_copied_from_type(self, db: Session):
        """Instance parameters equal the default_parameters from the rule type."""
        from sqlalchemy import select

        self._seed_types(db)
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        instance = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID,
                DetectionRuleInstance.rule_type_code == "MFR-001",
            )
        ).scalar_one()
        expected_params = next(
            r["default_parameters"] for r in RULE_TYPE_CATALOG if r["code"] == "MFR-001"
        )
        assert instance.parameters == expected_params

    def test_instance_enabled_true(self, db: Session):
        """All created instances default to enabled=True."""
        from sqlalchemy import select

        self._seed_types(db)
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        rows = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID
            )
        ).scalars().all()
        assert all(r.enabled for r in rows), "All instances must be enabled=True"

    def test_instance_effective_from_is_set(self, db: Session):
        """effective_from must be set (not None) since the column is NOT NULL."""
        from sqlalchemy import select

        self._seed_types(db)
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        rows = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID
            )
        ).scalars().all()
        assert all(r.effective_from is not None for r in rows), (
            "effective_from must be set on all instances"
        )

    def test_restricted_columns_excludes_mfr001(self, db: Session):
        """Drop extended_wac → MFR-001 (requires it) must NOT be instantiated."""
        from sqlalchemy import select

        self._seed_types(db)
        restricted = _FULL_CSV_COLUMNS - {"extended_wac"}
        register_rule_instances(db, _SYSTEM_UUID, restricted, _SYSTEM_UUID)
        rows = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID,
                DetectionRuleInstance.rule_type_code == "MFR-001",
            )
        ).scalars().all()
        assert rows == [], "MFR-001 needs extended_wac; must not be created without it"

    def test_restricted_columns_excludes_mfr003(self, db: Session):
        """Drop extended_wac → MFR-003 (requires it) must NOT be instantiated."""
        from sqlalchemy import select

        self._seed_types(db)
        restricted = _FULL_CSV_COLUMNS - {"extended_wac"}
        register_rule_instances(db, _SYSTEM_UUID, restricted, _SYSTEM_UUID)
        rows = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID,
                DetectionRuleInstance.rule_type_code == "MFR-003",
            )
        ).scalars().all()
        assert rows == [], "MFR-003 needs extended_wac; must not be created without it"

    def test_restricted_columns_still_creates_eligible_rules(self, db: Session):
        """Removing extended_wac still leaves 11 eligible RUN rules instantiated.

        MFR-008 is DEFERRED (count 13 → 13 base).
        Drop extended_wac → MFR-001 and MFR-003 also gated → 13 - 2 = 11.
        """
        from sqlalchemy import func, select

        self._seed_types(db)
        restricted = _FULL_CSV_COLUMNS - {"extended_wac"}
        count = register_rule_instances(db, _SYSTEM_UUID, restricted, _SYSTEM_UUID)
        # MFR-001 and MFR-003 are column-gated; remaining 11 should be created.
        assert count == 11
        total = db.execute(
            select(func.count()).select_from(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == _SYSTEM_UUID
            )
        ).scalar()
        assert total == 11

    def test_ml_detector_registry_not_written(self, db: Session):
        """register_rule_instances must never INSERT into ml_detector_registry."""
        from sqlalchemy import func, select

        self._seed_types(db)
        # Count before
        before = db.execute(
            select(func.count()).select_from(MlDetectorRegistry)
        ).scalar()
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        # Count after — must be identical
        after = db.execute(
            select(func.count()).select_from(MlDetectorRegistry)
        ).scalar()
        assert after == before, (
            "register_rule_instances must not insert into ml_detector_registry; "
            f"count changed from {before} to {after}"
        )

    def test_different_tenants_get_independent_instances(self, db: Session):
        """Two tenants can each have their own 13 instances independently."""
        from sqlalchemy import func, select

        tenant_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        self._seed_types(db)
        register_rule_instances(db, _SYSTEM_UUID, _FULL_CSV_COLUMNS, _SYSTEM_UUID)
        register_rule_instances(db, tenant_b, _FULL_CSV_COLUMNS, tenant_b)
        # Each tenant has 13 instances; total = 26.
        total = db.execute(
            select(func.count()).select_from(DetectionRuleInstance)
        ).scalar()
        assert total == 26
