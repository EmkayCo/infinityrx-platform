"""RLS null-deny acceptance test.

Per spec D8: open a session WITHOUT setting app.current_tenant_id ->
query each new tenant-owned table -> assert zero rows AND no exception.

This validates the NULLIF(..., '') pattern: when GUC is unset (missing_ok=true
returns empty string), NULLIF converts it to NULL, and
tenant_id = NULL evaluates to false -> zero rows visible.

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
            f"(gen_random_uuid(), '{tid_a}', 'payment.hold_released', "
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
    RLS by default -- a passing assertion would prove nothing about real
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
        "or the role has BYPASSRLS -- both are production safety regressions."
    )


@pytest.mark.parametrize("table", ALL_NEW_TENANT_OWNED_TABLES)
def test_tenant_b_sees_zero_rows_under_app_role(seeded_engine, table):
    """R1 BLOCK 7 fix: a DIFFERENT tenant context AS the app role sees zero
    rows belonging to tenant A. Distinct from null-deny -- exercises the
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
