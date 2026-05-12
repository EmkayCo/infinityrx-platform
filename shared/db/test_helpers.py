"""Test helpers for RLS-aware test fixtures (Wave 20 B1).

``seed_as_admin()`` yields a psycopg2 connection using the
``ifx_<tier>_admin`` role. This role has BYPASSRLS, so test fixtures
can seed rows across tenants without being blocked by RLS policies.

Usage::

    with seed_as_admin() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO ai_nlp.service_requests (...) VALUES (...)")
        conn.commit()

The admin URL is derived from ``DATABASE_URL_SYNC`` by swapping the
role + password portions. For local dev, that resolves to
``ifx_dev_admin:dev_admin_password``; for mock ``ifx_mock_admin``;
for prod ``ifx_prod_admin`` (real password must be provided via env
override). If the URL's role isn't recognised, a RuntimeError is
raised — the helper fails loud rather than silently connecting as
a tenant role.

This module is test-support code, but lives under ``shared/db/`` (not
``shared/tests/``) because some integration tests in modules import
it across the module boundary and the test dir isn't on sys.path for
cross-module imports.
"""

from __future__ import annotations

import contextlib
import os
import re
import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg2.extensions


# ---------------------------------------------------------------------------
# Phase A test tenant (Wave 26 Phase A.2)
# ---------------------------------------------------------------------------
# Well-known UUID used by all Phase A integration tests against the
# persistent dev DB. Tenant row is seeded via ensure_phase_a_test_tenant().
# Cleanup via cleanup_phase_a_test_data() in teardown or manual
# scripts/cleanup_test_tenant.py.

PHASE_A_TEST_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PHASE_A_TEST_PROGRAM_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
PHASE_A_TEST_CLIENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
PHASE_A_TEST_CREATED_BY = uuid.UUID("00000000-0000-0000-0000-000000000004")
_PHASE_A_TENANT_SLUG = "phase-a-test-tenant"

# Well-known rule_type UUIDs for the 4 Phase A.2 codes. These are global
# catalog rows (rule_types has no tenant_id), so the same IDs persist
# across all test tenants. Regenerating these would force a coordinated
# update everywhere — prefer additive changes.
_PHASE_A_RULE_TYPE_IDS: dict[str, uuid.UUID] = {
    "missing_required_fields_rule": uuid.UUID("000000a2-0000-0000-0000-000000000001"),
    "days_supply_range_rule":       uuid.UUID("000000a2-0000-0000-0000-000000000002"),
    "quantity_range_rule":          uuid.UUID("000000a2-0000-0000-0000-000000000003"),
    "patient_age_range_rule":       uuid.UUID("000000a2-0000-0000-0000-000000000004"),
}

# Default parameters for the 4 Phase A.2 rule_instances — mirror the
# hard-coded Phase A.2 behavior (max_days_supply=100, max_quantity=10000,
# min_age=0, max_age=120; the missing_required rule needs no params).
_PHASE_A_RULE_DEFAULTS: tuple[tuple[str, int, dict], ...] = (
    ("missing_required_fields_rule", 1, {}),
    ("days_supply_range_rule",       2, {"max_days_supply": 100}),
    ("quantity_range_rule",          3, {"max_quantity": "10000"}),
    ("patient_age_range_rule",       4, {"min_age": 0, "max_age": 120}),
)


def phase_a_test_tenant_id() -> uuid.UUID:
    """Return the well-known Phase A integration test tenant UUID."""
    return PHASE_A_TEST_TENANT_ID


def phase_a_test_program_id() -> uuid.UUID:
    """Return the well-known Phase A integration test program UUID."""
    return PHASE_A_TEST_PROGRAM_ID


def ensure_phase_a_test_tenant() -> None:
    """Idempotently ensure the Phase A test tenant row exists in core.tenants.

    Uses the admin role (BYPASSRLS) so it works even if called before a
    tenant GUC is set. Safe to call from test setup or CLI scripts.
    """
    with seed_as_admin() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO core.tenants (id, name, slug, display_name, status) "
            "VALUES (%s, %s, %s, %s, 'active') "
            "ON CONFLICT (id) DO NOTHING",
            (
                str(PHASE_A_TEST_TENANT_ID),
                "Phase A Test Tenant",
                _PHASE_A_TENANT_SLUG,
                "Phase A Test Tenant",
            ),
        )
        conn.commit()


def ensure_phase_a_rule_types() -> None:
    """Idempotently seed the 4 Phase A.2 rule_types rows in the global catalog.

    Inserts rows with well-known UUIDs so rule_instances can reference
    them deterministically. Safe to call multiple times; ON CONFLICT
    DO NOTHING.
    """
    catalog_rows = [
        (
            _PHASE_A_RULE_TYPE_IDS["missing_required_fields_rule"],
            "missing_required_fields_rule",
            "Missing Required NCPDP Fields",
            "validation",
        ),
        (
            _PHASE_A_RULE_TYPE_IDS["days_supply_range_rule"],
            "days_supply_range_rule",
            "Days Supply Range",
            "validation",
        ),
        (
            _PHASE_A_RULE_TYPE_IDS["quantity_range_rule"],
            "quantity_range_rule",
            "Quantity Range",
            "validation",
        ),
        (
            _PHASE_A_RULE_TYPE_IDS["patient_age_range_rule"],
            "patient_age_range_rule",
            "Patient Age Range",
            "validation",
        ),
    ]
    with seed_as_admin() as conn, conn.cursor() as cur:
        for rt_id, code, name, category in catalog_rows:
            cur.execute(
                "INSERT INTO rules_engine.rule_types "
                "(id, code, name, category, parameter_schema) "
                "VALUES (%s, %s, %s, %s, %s::json) "
                "ON CONFLICT (code) DO NOTHING",
                (str(rt_id), code, name, category, "{}"),
            )
        conn.commit()


def seed_phase_a_test_program() -> None:
    """Idempotently create the Phase A test program under the test tenant.

    Assumes the tenant already exists (call ensure_phase_a_test_tenant
    first). Uses admin role (BYPASSRLS).
    """
    with seed_as_admin() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO program_config.programs "
            "(id, tenant_id, name, program_type, client_id, status, "
            " wizard_step, wizard_data, post_launch_monitoring, created_by) "
            "VALUES (%s, %s, %s, %s, %s, 'active', 1, '{}'::jsonb, false, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (
                str(PHASE_A_TEST_PROGRAM_ID),
                str(PHASE_A_TEST_TENANT_ID),
                "Phase A Test Program",
                "copay_assistance",
                str(PHASE_A_TEST_CLIENT_ID),
                str(PHASE_A_TEST_CREATED_BY),
            ),
        )
        conn.commit()


def seed_phase_a_test_rule_instances() -> None:
    """Idempotently create 4 rule_instances mirroring Phase A.2 defaults.

    Each instance has a deterministic UUID derived from the program ID
    plus the rule type code so repeated calls are stable and cleanup is
    straightforward. Uses admin role (BYPASSRLS).

    The catalog (rule_types) must already have the 4 codes seeded —
    callers should invoke ensure_phase_a_rule_types() first.

    Uses ``shared.db.rule_instance_seeding.seed_rule_instance`` for the
    actual INSERT — the helper defaults effective_date to
    ``DATE '2020-01-01'`` so no wall-clock-drift risk.
    """
    from shared.db.rule_instance_seeding import seed_rule_instance  # noqa: PLC0415

    with seed_as_admin() as conn:
        for code, priority, params in _PHASE_A_RULE_DEFAULTS:
            seed_rule_instance(
                conn,
                tenant_id=PHASE_A_TEST_TENANT_ID,
                rule_type_id=_PHASE_A_RULE_TYPE_IDS[code],
                program_id=PHASE_A_TEST_PROGRAM_ID,
                # Preserve deterministic uuid5(program_id, code)
                # identity for cross-test compatibility; existing
                # test_phase_c2_rule_config expects this shape.
                rule_instance_id=uuid.uuid5(PHASE_A_TEST_PROGRAM_ID, code),
                priority_order=priority,
                parameters=params,
            )
        conn.commit()


def ensure_phase_a_test_fixtures() -> None:
    """Convenience: seed tenant + rule_types + program + rule_instances.

    Idempotent. Typical call order from test setup:
        ensure_phase_a_test_fixtures()
        cleanup_phase_a_test_data()   # wipe prior test rows (doesn't
                                       # touch rule_types/programs by default)
    """
    ensure_phase_a_test_tenant()
    ensure_phase_a_rule_types()
    seed_phase_a_test_program()
    seed_phase_a_test_rule_instances()


# Tables to wipe under the test tenant. Extend as Phase A.2+ adds
# new write targets. Order matters — rows with FK dependencies come
# first so children are deleted before parents (billing.ap_records
# FK references billing.claim_records via ON DELETE RESTRICT).
_PHASE_A_WIPE_TABLES: tuple[tuple[str, str], ...] = (
    # Phase A.2 adjudication_engine
    ("adjudication_engine", "claim_transactions"),
    ("adjudication_engine", "claim_overrides"),
    ("adjudication_engine", "override_approval_configs"),
    ("adjudication_engine", "dur_screening_logs"),
    ("adjudication_engine", "copay_fraud_flags"),
    ("adjudication_engine", "drug_waste_alerts"),
    # Phase B billing (child → parent order for the FK cascade)
    ("billing", "ap_records"),
    ("billing", "claim_records"),
)


def cleanup_phase_a_test_data(*, dry_run: bool = False) -> dict[str, int]:
    """Delete all rows under PHASE_A_TEST_TENANT_ID across known test-
    touching tables. Uses admin role (BYPASSRLS). Idempotent.

    Returns a dict of table -> rows-deleted (or rows-that-would-be-
    deleted when ``dry_run=True``).
    """
    results: dict[str, int] = {}
    with seed_as_admin() as conn, conn.cursor() as cur:
        for schema, table in _PHASE_A_WIPE_TABLES:
            qualified = f"{schema}.{table}"
            if dry_run:
                cur.execute(
                    f"SELECT COUNT(*) FROM {qualified} WHERE tenant_id = %s",
                    (str(PHASE_A_TEST_TENANT_ID),),
                )
                row = cur.fetchone()
                results[qualified] = int(row[0]) if row else 0
            else:
                cur.execute(
                    f"DELETE FROM {qualified} WHERE tenant_id = %s",
                    (str(PHASE_A_TEST_TENANT_ID),),
                )
                results[qualified] = cur.rowcount
        if not dry_run:
            conn.commit()
        else:
            conn.rollback()
    return results


# Map tenant-role name -> (admin-role name, admin password).
# Matches the roles created in infrastructure/scripts/init-multi-db.sql.
# Passwords here match the init-script defaults for dev and mock; prod
# expects the real admin password to arrive via env override (see
# _resolve_admin_url).
_ROLE_PAIRS: dict[str, tuple[str, str]] = {
    "ifx_dev_app":  ("ifx_dev_admin",  "dev_admin_password"),
    "ifx_mock_app": ("ifx_mock_admin", "mock_admin_password"),
}


def _resolve_admin_url() -> str:
    """Derive the admin-role connection URL from DATABASE_URL_SYNC.

    Strips SQLAlchemy driver prefixes, locates the role:password
    segment, and swaps to the matching admin role. Overrides:
      - ADMIN_DATABASE_URL: full URL, used directly if set
      - IFX_<TIER>_ADMIN_PASSWORD: per-tier password override
    """
    override = os.environ.get("ADMIN_DATABASE_URL")
    if override:
        return override

    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "seed_as_admin needs DATABASE_URL_SYNC (or ADMIN_DATABASE_URL) "
            "to derive the admin connection URL."
        )

    # Strip any SQLAlchemy driver prefix for raw psycopg2.
    for prefix in ("postgresql+psycopg2://", "postgresql+asyncpg://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
            break

    # Extract "role:password" between scheme and @host.
    m = re.match(r"^(postgresql://)([^:]+):([^@]+)@(.+)$", url)
    if m is None:
        raise RuntimeError(
            f"seed_as_admin could not parse DATABASE_URL_SYNC as "
            f"postgresql://role:password@host/db: {url[:40]}..."
        )
    scheme, role, _password, rest = m.group(1), m.group(2), m.group(3), m.group(4)

    if role not in _ROLE_PAIRS:
        raise RuntimeError(
            f"seed_as_admin does not know an admin counterpart for role "
            f"{role!r}. Known tenant roles: {sorted(_ROLE_PAIRS)}. "
            f"Set ADMIN_DATABASE_URL to override."
        )
    admin_role, admin_password = _ROLE_PAIRS[role]

    # Per-tier password override (IFX_DEV_ADMIN_PASSWORD etc.)
    env_var = f"{admin_role.upper()}_PASSWORD"
    admin_password = os.environ.get(env_var, admin_password)

    return f"{scheme}{admin_role}:{admin_password}@{rest}"


@contextlib.contextmanager
def seed_as_admin() -> Iterator["psycopg2.extensions.connection"]:
    """Yield a psycopg2 connection authenticated as the BYPASSRLS admin role.

    Caller is responsible for calling ``.commit()`` on their writes —
    the helper does not auto-commit. The connection is closed on exit,
    including on exception.
    """
    import psycopg2  # noqa: PLC0415  — deferred so SQLite-only CI can import the helper module

    conn = psycopg2.connect(_resolve_admin_url())
    try:
        yield conn
    finally:
        conn.close()


__all__ = [
    "seed_as_admin",
    "PHASE_A_TEST_TENANT_ID",
    "phase_a_test_tenant_id",
    "ensure_phase_a_test_tenant",
    "cleanup_phase_a_test_data",
]
