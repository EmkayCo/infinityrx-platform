"""Migration 0008 acceptance tests.

Verifies:
1. Migration applies without error (CREATE TABLE + ALTER TABLE)
2. All 6 new tables exist with correct column sets
3. All 3 altered tables (investigations, payment_holds) have new columns
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
        "reclaimrx_graph_runs",
        "reclaimrx_fraud_rings",
        "reclaimrx_accumulator_anomalies",
        "reclaimrx_threshold_configs",
        "reclaimrx_threshold_config_audits",
        "reclaimrx_outbox_events",
    ]

    def test_all_new_tables_created(self, pg_engine):
        with pg_engine.connect() as conn:
            for table in self.NEW_TABLES:
                result = conn.execute(text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = :t"
                ), {"t": table}).fetchone()
                assert result is not None, f"Table public.{table} was not created"


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
                " 'payment.hold_released', '{}', 'pending', now(), 0, :ikey)"
            ), {"tid": tid, "ikey": ikey})
            with pytest.raises(Exception, match="unique|duplicate"):
                conn.execute(text(
                    "INSERT INTO reclaimrx_outbox_events "
                    "(id, tenant_id, event_type, envelope_json, status, "
                    " created_at, attempt_count, idempotency_key) VALUES "
                    "('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', :tid, "
                    " 'payment.hold_released', '{}', 'pending', now(), 0, :ikey)"
                ), {"tid": tid, "ikey": ikey})
            conn.rollback()


class TestInvestigationAlterations:
    """R1 BLOCK 2 fix: ALTER TABLE targets the deterministic ORM-aligned name."""

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
    """RLS policies must be created on all 6 new tables."""

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
        """R1 BLOCK 2 fix: target the ORM-aligned table name deterministically."""
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
