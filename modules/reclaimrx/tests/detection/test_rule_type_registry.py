"""TDD tests for the rule-type registry + 46-rule catalog.

Tests are written BEFORE the implementation (RED phase per TDD discipline).

Contract assertions:
- RULE_TYPE_CATALOG has >= 46 entries.
- register_rule_types(db) inserts exactly len(RULE_TYPE_CATALOG) rows on first call.
- Second call returns 0 (idempotent — DO NOTHING on conflict).
- Exactly 14 rules have deferred_data_feed=False (the "RUN" set).
- Deferred rules have deferred_data_feed=True and a non-empty deferred_reason.
- MFR-001 is a RUN rule with required_data_columns containing 'extended_wac' and
  'ingredient_cost_paid', and family in {A1..A6}.
- ALL-002 is a DEFERRED rule with a truthy deferred_reason.

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
from src._shim.db import Base, configure_engine, get_engine
from src.models.detection_run_models import DetectionRuleType  # noqa: F401 — registers table


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
        if isinstance(_col.type, PG_UUID):
            _col.type = _UUIDString()
        elif isinstance(_col.type, JSONB):
            _col.type = JSON()
        elif isinstance(_col.type, ARRAY):
            _col.type = JSON()


# ---------------------------------------------------------------------------
# Engine + SAVEPOINT session fixtures (LESSON-001)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    """In-memory SQLite engine with all reclaimrx tables materialised.

    SQLite does not support schema-qualified tables ('reclaimrx.*').
    We null out the schema on every table in Base.metadata before create_all
    so DDL renders as plain unqualified table names.
    """
    # Strip schema qualifiers so SQLite create_all works.
    for _t in Base.metadata.tables.values():
        _t.schema = None

    configure_engine("sqlite:///:memory:")
    eng = get_engine()
    Base.metadata.create_all(eng)
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
from src.detection.rule_type_registry import RULE_TYPE_CATALOG, register_rule_types  # noqa: E402

# ---------------------------------------------------------------------------
# Constants for the 14 RUN rules (deferred_data_feed=False)
# ---------------------------------------------------------------------------
_RUN_CODES = {
    "ALL-001", "MFR-001", "MFR-002", "ALL-005", "HP-010", "TH-005",
    "TH-002", "MFR-008", "MFR-004", "MFR-003", "HP-005", "HP-008",
    "ALL-006", "MFR-009",
}
_VALID_FAMILIES = {"A1", "A2", "A3", "A4", "A5", "A6"}


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

    def test_exactly_14_run_rules(self):
        run_rules = [r for r in RULE_TYPE_CATALOG if not r["deferred_data_feed"]]
        codes = {r["code"] for r in run_rules}
        assert len(run_rules) == 14, (
            f"Expected 14 RUN rules, got {len(run_rules)}: {codes}"
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

    def test_exactly_14_run_rows_in_db(self, db: Session):
        from sqlalchemy import select

        register_rule_types(db)
        rows = db.execute(
            select(DetectionRuleType).where(DetectionRuleType.deferred_data_feed.is_(False))
        ).scalars().all()
        assert len(rows) == 14

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
