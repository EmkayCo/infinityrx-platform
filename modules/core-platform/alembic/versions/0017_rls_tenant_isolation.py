"""RLS policies for core-platform tenant-scoped tables (Wave 20 B3).

Enables Row-Level Security on core's tenant-owned tables. Mix of all
three policy shapes — the first schema to exercise PLATFORM_GLOBAL and
CHILD together.

Classification
--------------
CANONICAL (6 tables, NOT NULL tenant_id):
  audit_log, event_dlq, files, notifications, sessions, users

PLATFORM_GLOBAL (2 tables, nullable tenant_id):
  jobs, roles — tenants see own rows + NULL rows; tenant writes require
  matching tenant_id.

CHILD via parent (3 tables, no own tenant_id, FK to core.users):
  user_roles, user_fido2_credentials, notification_preferences — the
  parent is CANONICAL so EXISTS subquery checks users.tenant_id = GUC.

OUT_OF_SCOPE (7 tables intentionally skipped):
  alembic_version, bank_holidays (global reference),
  permissions (global role def), role_permissions (role↔permission
  lookup), tenants (the registry itself), processed_events (shared
  event-dedup), job_runs (DEFERRED — parent core.jobs has nullable
  tenant_id; child-of-platform-global is a new policy shape not yet
  implemented in the applier; revisit design in a future wave).

Two hard-won rules from Wave 20 B2 are non-negotiable and encoded:
  1. FORCE ROW LEVEL SECURITY alongside ENABLE (tenant role is owner).
  2. NULLIF-wrapped current_setting to survive empty-string GUC.

Generated from ``scripts/apply_rls.py``. To regenerate:
    python scripts/apply_rls.py --schema core
and confirm emitted SQL matches this migration.

Revision ID: 0017_rls_tenant_isolation
Revises: 0016_drop_core_exclusion_tables
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0017_rls_tenant_isolation"
down_revision: Union[str, None] = "0016_drop_core_exclusion_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "core"
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"

_CANONICAL_TABLES: list[str] = [
    "audit_log",
    "event_dlq",
    "files",
    "notifications",
    "sessions",
    "users",
]

_PLATFORM_GLOBAL_TABLES: list[str] = ["jobs", "roles"]

# (child_table, parent_table, fk_column_on_child). Parent lives in the
# same schema (core.users).
_CHILD_TABLES: list[tuple[str, str, str]] = [
    ("notification_preferences", "users", "user_id"),
    ("user_fido2_credentials", "users", "user_id"),
    ("user_roles", "users", "user_id"),
]


def upgrade() -> None:
    # ── Canonical: 6 tables × 1 policy each ──
    for table in _CANONICAL_TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
              FOR ALL
              TO {_TENANT_ROLES}
              USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )

    # ── Platform-global: 2 tables × 4 policies each ──
    for table in _PLATFORM_GLOBAL_TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_or_global_read ON {_SCHEMA}.{table}
              FOR SELECT
              TO {_TENANT_ROLES}
              USING (tenant_id IS NULL
                     OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_write_insert ON {_SCHEMA}.{table}
              FOR INSERT
              TO {_TENANT_ROLES}
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_write_update ON {_SCHEMA}.{table}
              FOR UPDATE
              TO {_TENANT_ROLES}
              USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )
        op.execute(
            f"""
            CREATE POLICY tenant_write_delete ON {_SCHEMA}.{table}
              FOR DELETE
              TO {_TENANT_ROLES}
              USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )

    # ── Child via parent: 3 tables × 1 policy each ──
    for table, parent, fk in _CHILD_TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_via_parent ON {_SCHEMA}.{table}
              FOR ALL
              TO {_TENANT_ROLES}
              USING (EXISTS (
                SELECT 1 FROM {_SCHEMA}.{parent} c
                WHERE c.id = {_SCHEMA}.{table}.{fk}
                  AND c.tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
              ))
              WITH CHECK (EXISTS (
                SELECT 1 FROM {_SCHEMA}.{parent} c
                WHERE c.id = {_SCHEMA}.{table}.{fk}
                  AND c.tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
              ))
            """
        )


def downgrade() -> None:
    for table, _parent, _fk in reversed(_CHILD_TABLES):
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation_via_parent ON {_SCHEMA}.{table}"
        )
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY")

    for table in reversed(_PLATFORM_GLOBAL_TABLES):
        for policy in ("tenant_write_delete", "tenant_write_update",
                       "tenant_write_insert", "tenant_or_global_read"):
            op.execute(f"DROP POLICY IF EXISTS {policy} ON {_SCHEMA}.{table}")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY")

    for table in reversed(_CANONICAL_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.{table}")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY")
