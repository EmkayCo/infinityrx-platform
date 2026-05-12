"""RLS policies for ai_nlp tenant-scoped tables (Wave 20 B2).

Enables Row-Level Security on 8 ai-nlp tables and installs policies
following the three shapes defined in docs/architecture/rls-pattern.md:

* Canonical (6 tables: service_requests, document_results, conversations,
  embeddings, usage_log, guardrail_events) — NOT NULL tenant_id column,
  single policy `tenant_isolation` filters on
  ``tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid``.
* Platform-global (prompt_templates) — nullable tenant_id. Two policies:
  ``tenant_or_global_read`` (SELECT allows NULL rows + current tenant's),
  ``tenant_write`` (INSERT/UPDATE/DELETE require matching tenant).
  Platform-global writes (tenant_id=NULL) go through BYPASSRLS admin roles.
* Child via parent (conversation_messages) — no own tenant_id; scoped via
  EXISTS subquery against parent ``conversations.tenant_id``.

Policies apply only to ``ifx_dev_app`` / ``ifx_mock_app`` / ``ifx_prod_app``
(tenant roles). The ``infinityrx`` superuser and ``ifx_<tier>_admin`` roles
have BYPASSRLS so queries skip policy evaluation entirely.

Partitioned parents: ``service_requests`` and ``usage_log`` are partitioned.
PG propagates ENABLE ROW LEVEL SECURITY + policies from the partitioned
parent to all partitions automatically — no per-partition work needed.

Using ``current_setting('app.current_tenant_id', true)``: the ``true``
second argument is ``missing_ok`` — returns NULL if the setting isn't set
rather than raising. For tenant roles with unset context, NULL-to-UUID cast
yields NULL, comparison evaluates to UNKNOWN, zero rows match — fail-closed.
For BYPASSRLS roles, policies aren't evaluated.

Revision ID: 0004_rls_tenant_isolation
Revises: 0003_check_constraints
Create Date: 2026-04-20
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004_rls_tenant_isolation"
down_revision: Union[str, None] = "0003_check_constraints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "ai_nlp"

# Tenant roles the policies apply TO. Admin roles (BYPASSRLS) are
# intentionally omitted so they skip policy evaluation entirely.
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"

# Canonical tables: NOT NULL tenant_id, single FOR ALL policy.
_CANONICAL_TABLES: list[str] = [
    "service_requests",   # partitioned parent — policy propagates to partitions
    "document_results",
    "conversations",
    "embeddings",
    "usage_log",          # partitioned parent
    "guardrail_events",
]


def upgrade() -> None:
    # ── Canonical: 6 tables × 1 policy each ──
    for table in _CANONICAL_TABLES:
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"
        )
        # FORCE: required because the tenant role ifx_<tier>_app OWNS the
        # tables (init-multi-db.sql makes ifx_<tier>_app the DB owner, so
        # alembic-created tables inherit it as owner). PG bypasses RLS for
        # the table owner by default; FORCE removes that exception so
        # ifx_<tier>_app is subject to RLS. The rolbypassrls attribute
        # still wins — ifx_<tier>_admin and infinityrx skip RLS regardless.
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY"
        )
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
              FOR ALL
              TO {_TENANT_ROLES}
              USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )

    # ── Platform-global: prompt_templates (nullable tenant_id) ──
    op.execute(
        f"ALTER TABLE {_SCHEMA}.prompt_templates ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.prompt_templates FORCE ROW LEVEL SECURITY"
    )
    # Read: tenant sees their own rows + platform-global (NULL tenant_id) rows.
    op.execute(
        f"""
        CREATE POLICY tenant_or_global_read ON {_SCHEMA}.prompt_templates
          FOR SELECT
          TO {_TENANT_ROLES}
          USING (tenant_id IS NULL
                 OR tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )
    # Write: tenant may only INSERT/UPDATE/DELETE their own rows.
    # Platform-global writes (tenant_id=NULL) require a BYPASSRLS role.
    op.execute(
        f"""
        CREATE POLICY tenant_write_insert ON {_SCHEMA}.prompt_templates
          FOR INSERT
          TO {_TENANT_ROLES}
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_write_update ON {_SCHEMA}.prompt_templates
          FOR UPDATE
          TO {_TENANT_ROLES}
          USING      (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )
    op.execute(
        f"""
        CREATE POLICY tenant_write_delete ON {_SCHEMA}.prompt_templates
          FOR DELETE
          TO {_TENANT_ROLES}
          USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """
    )

    # ── Child via parent: conversation_messages ──
    op.execute(
        f"ALTER TABLE {_SCHEMA}.conversation_messages ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.conversation_messages FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_via_parent ON {_SCHEMA}.conversation_messages
          FOR ALL
          TO {_TENANT_ROLES}
          USING (EXISTS (
            SELECT 1 FROM {_SCHEMA}.conversations c
            WHERE c.id = {_SCHEMA}.conversation_messages.conversation_id
              AND c.tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
          ))
          WITH CHECK (EXISTS (
            SELECT 1 FROM {_SCHEMA}.conversations c
            WHERE c.id = {_SCHEMA}.conversation_messages.conversation_id
              AND c.tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
          ))
        """
    )


def downgrade() -> None:
    # Drop in reverse order for symmetry with upgrade().
    op.execute(
        f"DROP POLICY IF EXISTS tenant_isolation_via_parent "
        f"ON {_SCHEMA}.conversation_messages"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.conversation_messages DISABLE ROW LEVEL SECURITY"
    )

    for policy in ("tenant_write_delete", "tenant_write_update",
                   "tenant_write_insert", "tenant_or_global_read"):
        op.execute(
            f"DROP POLICY IF EXISTS {policy} ON {_SCHEMA}.prompt_templates"
        )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.prompt_templates DISABLE ROW LEVEL SECURITY"
    )

    for table in reversed(_CANONICAL_TABLES):
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.{table}"
        )
        op.execute(
            f"ALTER TABLE {_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY"
        )
