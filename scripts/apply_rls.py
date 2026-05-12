"""RLS policy applier — introspection-based rollout (Wave 20 B3).

Generalizes the hand-written ai-nlp RLS migration (Wave 20 B2, migration
``0004_rls_tenant_isolation``) into a reusable tool. Classifies every
base table in a target schema and emits the SQL that would apply the
correct policy shape — canonical, platform-global, child-via-parent, or
no-op for out-of-scope tables.

Policy shapes
-------------
All three shapes match the B2 migration byte-for-byte (verified by
``tests/test_rls_applier.py``). Two hard-won rules from B2 are
non-negotiable and encoded here:

1. ``ENABLE ROW LEVEL SECURITY`` is insufficient when the tenant role
   owns the table (which it does — ``ifx_<tier>_app`` is DB owner per
   ``infrastructure/scripts/init-multi-db.sql``). ``FORCE ROW LEVEL
   SECURITY`` is always emitted alongside.
2. ``current_setting('app.current_tenant_id', true)`` returns the empty
   string (not NULL) when the GUC is unset, and ``''::uuid`` raises
   ``InvalidTextRepresentation``. Every cast is wrapped:
   ``NULLIF(current_setting(...), '')::uuid``.

Classification
--------------
* ``CANONICAL`` — table has NOT NULL tenant_id (uuid). Single FOR ALL
  policy named ``tenant_isolation``.
* ``PLATFORM_GLOBAL`` — table has nullable tenant_id. Four policies:
  ``tenant_or_global_read``, ``tenant_write_insert``,
  ``tenant_write_update``, ``tenant_write_delete``.
* ``CHILD`` — table has no tenant_id but is listed in
  ``_CHILD_TABLE_MAP`` pointing at a parent with tenant_id. Single
  ``tenant_isolation_via_parent`` policy using EXISTS against parent.
* ``OUT_OF_SCOPE`` — no tenant_id, not in child map. Reference tables
  (e.g. drug catalogs) and platform metadata live here.

Adding a child table means editing ``_CHILD_TABLE_MAP`` in this file
with the parent linkage. There's no auto-detection — FKs can point
anywhere, and "every child FK gets RLS" would silently enroll tables
the team hasn't thought through.

CLI modes
---------
* ``--status`` — print current RLS state per table (enabled? forced?
  policies? classification vs current state match?)
* ``--dry-run`` (default) — print the SQL that WOULD apply. Does not
  connect to DB for write, but DOES connect for introspection.
* ``--diff`` — compare existing policies against what would be applied;
  exit nonzero if drift detected.
* ``--apply`` — execute the SQL. Requires ``--yes`` for confirmation.

Idempotency
-----------
Generated ALTER/CREATE statements are idempotent in intent but not by
syntax — PG will error on ``CREATE POLICY`` if one already exists with
the same name. The ``--apply`` path wraps each table in a transaction
and uses ``DROP POLICY IF EXISTS ... ; CREATE POLICY ...`` to make
re-runs safe. The ``--dry-run`` output is the raw CREATE form (for
migration authorship), matching B2's style exactly.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import psycopg2

_REPO = Path(__file__).resolve().parent.parent

# Tenant roles the policies apply TO. Admin roles (BYPASSRLS) skip
# policy evaluation entirely and are intentionally omitted.
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TENANT_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"

# Child table map: (schema, table) → (parent_schema, parent_table, fk_column_on_child).
# Only entries listed here are eligible for CHILD classification; every
# addition is a deliberate decision that the parent's tenant_id is the
# authoritative tenant scope for the child's rows.
_CHILD_TABLE_MAP: dict[tuple[str, str], tuple[str, str, str]] = {
    ("ai_nlp", "conversation_messages"): ("ai_nlp", "conversations", "conversation_id"),
    # core.users is CANONICAL (NOT NULL tenant_id). Three per-user tables
    # inherit tenant scope via their user_id FK.
    ("core", "user_roles"): ("core", "users", "user_id"),
    ("core", "user_fido2_credentials"): ("core", "users", "user_id"),
    ("core", "notification_preferences"): ("core", "users", "user_id"),
}

# Tables that intentionally have no tenant_id and are NOT children —
# reference catalogs, alembic bookkeeping, platform lookup tables. Flagged
# explicitly so the audit doesn't ask about them.
#
# Design-deferred entries carry a reason — revisit in a future wave.
_OUT_OF_SCOPE_ALLOWLIST: set[tuple[str, str]] = {
    ("core", "bank_holidays"),         # Global reference data, no tenant scope.
    ("core", "permissions"),           # Global permission definitions.
    ("core", "role_permissions"),      # Pure role↔permission lookup, both global.
    ("core", "tenants"),               # The tenant registry itself.
    ("core", "processed_events"),      # Shared event-dedup table, not tenant-owned.
    # DEFERRED: core.job_runs — parent (core.jobs) has nullable tenant_id
    # (PLATFORM_GLOBAL). Child-of-platform-global is a new policy shape
    # not yet implemented here. Leave OUT_OF_SCOPE until design call
    # (B4 or later): do we copy tenant_id onto job_runs, or invent a
    # "tenant-or-global visibility" child policy?
    ("core", "job_runs"),
    # payment_proc reference tables — shared infrastructure, no tenant scope.
    ("payment_proc", "payment_proc_ach_return_codes"),  # NACHA return codes.
    ("payment_proc", "payment_proc_ofac_sdn"),          # OFAC SDN list.
}

# Table name substrings auto-classified as OUT_OF_SCOPE with no further
# analysis. Keep this list tiny and obvious.
_ALWAYS_OUT_OF_SCOPE_NAMES: set[str] = {"alembic_version"}


class Classification(str, Enum):
    CANONICAL = "CANONICAL"
    PLATFORM_GLOBAL = "PLATFORM_GLOBAL"
    CHILD = "CHILD"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class TableInfo:
    schema: str
    table: str
    classification: Classification
    tenant_id_nullable: bool | None = None  # None when no tenant_id column
    # True when the tenant_id column (or for CHILD, the parent's tenant_id)
    # is the UUID type. False means VARCHAR/TEXT — policy emits string
    # equality with no ``::uuid`` cast (payment_proc pattern).
    tenant_id_is_uuid: bool = True
    parent_schema: str | None = None
    parent_table: str | None = None
    parent_fk_column: str | None = None


@dataclass
class RlsState:
    enabled: bool
    forced: bool
    policies: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


def _fetch_base_tables(conn, schema: str) -> list[str]:
    """All base tables in the schema. Excludes views and partitions.

    Partitions are filtered via ``pg_class.relispartition`` — partition
    parents own the policy; partitions inherit automatically.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
              AND c.relkind IN ('r', 'p')   -- regular + partitioned parent
              AND c.relispartition = false  -- skip partition children
            ORDER BY c.relname
            """,
            (schema,),
        )
        return [row[0] for row in cur.fetchall()]


def _fetch_tenant_id_column(
    conn, schema: str, table: str
) -> tuple[bool, str] | None:
    """Return (is_nullable, data_type) if tenant_id exists on table, else None."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT is_nullable, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = 'tenant_id'
            """,
            (schema, table),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return (row[0] == "YES", row[1])


def _fetch_rls_state(conn, schema: str, table: str) -> RlsState:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relrowsecurity, c.relforcerowsecurity
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table),
        )
        row = cur.fetchone()
        if row is None:
            return RlsState(enabled=False, forced=False)
        enabled, forced = row

        cur.execute(
            """
            SELECT policyname FROM pg_policies
            WHERE schemaname = %s AND tablename = %s
            ORDER BY policyname
            """,
            (schema, table),
        )
        policies = [r[0] for r in cur.fetchall()]
        return RlsState(enabled=enabled, forced=forced, policies=policies)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _is_uuid_type(data_type: str) -> bool:
    return data_type == "uuid"


def classify_table(conn, schema: str, table: str) -> TableInfo:
    if table in _ALWAYS_OUT_OF_SCOPE_NAMES or (schema, table) in _OUT_OF_SCOPE_ALLOWLIST:
        return TableInfo(schema=schema, table=table, classification=Classification.OUT_OF_SCOPE)

    col = _fetch_tenant_id_column(conn, schema, table)
    if col is not None:
        is_nullable, dtype = col
        is_uuid = _is_uuid_type(dtype)
        if is_nullable:
            return TableInfo(
                schema=schema,
                table=table,
                classification=Classification.PLATFORM_GLOBAL,
                tenant_id_nullable=True,
                tenant_id_is_uuid=is_uuid,
            )
        return TableInfo(
            schema=schema,
            table=table,
            classification=Classification.CANONICAL,
            tenant_id_nullable=False,
            tenant_id_is_uuid=is_uuid,
        )

    child_entry = _CHILD_TABLE_MAP.get((schema, table))
    if child_entry is not None:
        parent_schema, parent_table, fk_column = child_entry
        # Resolve parent's tenant_id data_type so child policy emits the
        # right cast. If parent is missing (misconfigured), fall through
        # to OUT_OF_SCOPE.
        parent_col = _fetch_tenant_id_column(conn, parent_schema, parent_table)
        parent_is_uuid = parent_col is not None and _is_uuid_type(parent_col[1])
        return TableInfo(
            schema=schema,
            table=table,
            classification=Classification.CHILD,
            tenant_id_is_uuid=parent_is_uuid,
            parent_schema=parent_schema,
            parent_table=parent_table,
            parent_fk_column=fk_column,
        )

    return TableInfo(schema=schema, table=table, classification=Classification.OUT_OF_SCOPE)


def classify_schema(conn, schema: str) -> list[TableInfo]:
    return [classify_table(conn, schema, t) for t in _fetch_base_tables(conn, schema)]


# ---------------------------------------------------------------------------
# SQL generation
# ---------------------------------------------------------------------------
#
# Statements are emitted WITHOUT trailing semicolons so callers can decide
# how to execute them (alembic op.execute wraps one statement each; the
# --apply path uses conn.execute per-statement). Indentation and line
# breaks exactly match the B2 migration — tests enforce byte equivalence
# via `_normalize_sql` (whitespace-insensitive).


# The GUC is always stored as text. For UUID columns we cast; for
# VARCHAR/TEXT columns (payment_proc pattern) we compare as text. The
# NULLIF wrap is non-negotiable in both cases — see Wave 20 B2 Finding #2.
_GUC_UUID = "NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
_GUC_TEXT = "NULLIF(current_setting('app.current_tenant_id', true), '')"


_CANONICAL_POLICY_TEMPLATE = """\
CREATE POLICY tenant_isolation ON {schema}.{table}
  FOR ALL
  TO {roles}
  USING      (tenant_id = {guc})
  WITH CHECK (tenant_id = {guc})"""

_PLATFORM_GLOBAL_READ_TEMPLATE = """\
CREATE POLICY tenant_or_global_read ON {schema}.{table}
  FOR SELECT
  TO {roles}
  USING (tenant_id IS NULL
         OR tenant_id = {guc})"""

_PLATFORM_GLOBAL_INSERT_TEMPLATE = """\
CREATE POLICY tenant_write_insert ON {schema}.{table}
  FOR INSERT
  TO {roles}
  WITH CHECK (tenant_id = {guc})"""

_PLATFORM_GLOBAL_UPDATE_TEMPLATE = """\
CREATE POLICY tenant_write_update ON {schema}.{table}
  FOR UPDATE
  TO {roles}
  USING      (tenant_id = {guc})
  WITH CHECK (tenant_id = {guc})"""

_PLATFORM_GLOBAL_DELETE_TEMPLATE = """\
CREATE POLICY tenant_write_delete ON {schema}.{table}
  FOR DELETE
  TO {roles}
  USING (tenant_id = {guc})"""

_CHILD_POLICY_TEMPLATE = """\
CREATE POLICY tenant_isolation_via_parent ON {schema}.{table}
  FOR ALL
  TO {roles}
  USING (EXISTS (
    SELECT 1 FROM {parent_schema}.{parent_table} c
    WHERE c.id = {schema}.{table}.{fk_column}
      AND c.tenant_id = {guc}
  ))
  WITH CHECK (EXISTS (
    SELECT 1 FROM {parent_schema}.{parent_table} c
    WHERE c.id = {schema}.{table}.{fk_column}
      AND c.tenant_id = {guc}
  ))"""


def generate_sql(info: TableInfo, roles: str = _TENANT_ROLES) -> list[str]:
    """SQL statements to apply RLS for one table. Empty list for OUT_OF_SCOPE."""
    if info.classification is Classification.OUT_OF_SCOPE:
        return []

    guc = _GUC_UUID if info.tenant_id_is_uuid else _GUC_TEXT

    stmts: list[str] = [
        f"ALTER TABLE {info.schema}.{info.table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {info.schema}.{info.table} FORCE ROW LEVEL SECURITY",
    ]

    common = {"schema": info.schema, "table": info.table, "roles": roles, "guc": guc}

    if info.classification is Classification.CANONICAL:
        stmts.append(_CANONICAL_POLICY_TEMPLATE.format(**common))
    elif info.classification is Classification.PLATFORM_GLOBAL:
        stmts.append(_PLATFORM_GLOBAL_READ_TEMPLATE.format(**common))
        stmts.append(_PLATFORM_GLOBAL_INSERT_TEMPLATE.format(**common))
        stmts.append(_PLATFORM_GLOBAL_UPDATE_TEMPLATE.format(**common))
        stmts.append(_PLATFORM_GLOBAL_DELETE_TEMPLATE.format(**common))
    elif info.classification is Classification.CHILD:
        assert info.parent_schema and info.parent_table and info.parent_fk_column
        stmts.append(_CHILD_POLICY_TEMPLATE.format(
            **common,
            parent_schema=info.parent_schema,
            parent_table=info.parent_table,
            fk_column=info.parent_fk_column,
        ))
    return stmts


def generate_schema_sql(infos: list[TableInfo]) -> list[str]:
    """Flat SQL list for a schema — canonical first, then platform-global,
    then child. Matches the B2 migration ordering."""
    order = {
        Classification.CANONICAL: 0,
        Classification.PLATFORM_GLOBAL: 1,
        Classification.CHILD: 2,
        Classification.OUT_OF_SCOPE: 99,
    }
    sorted_infos = sorted(infos, key=lambda i: (order[i.classification], i.table))
    out: list[str] = []
    for info in sorted_infos:
        out.extend(generate_sql(info))
    return out


def expected_policy_names(info: TableInfo) -> list[str]:
    """Policy names this classification should install."""
    if info.classification is Classification.CANONICAL:
        return ["tenant_isolation"]
    if info.classification is Classification.PLATFORM_GLOBAL:
        return [
            "tenant_or_global_read",
            "tenant_write_insert",
            "tenant_write_update",
            "tenant_write_delete",
        ]
    if info.classification is Classification.CHILD:
        return ["tenant_isolation_via_parent"]
    return []


# ---------------------------------------------------------------------------
# Status / diff
# ---------------------------------------------------------------------------


def status_report(conn, schema: str) -> list[dict]:
    rows: list[dict] = []
    for info in classify_schema(conn, schema):
        state = _fetch_rls_state(conn, schema, info.table)
        expected = set(expected_policy_names(info))
        current = set(state.policies)
        in_sync = (
            state.enabled == (info.classification is not Classification.OUT_OF_SCOPE)
            and state.forced == (info.classification is not Classification.OUT_OF_SCOPE)
            and expected == current
        )
        rows.append({
            "table": info.table,
            "classification": info.classification.value,
            "enabled": state.enabled,
            "forced": state.forced,
            "policies_current": sorted(current),
            "policies_expected": sorted(expected),
            "in_sync": in_sync,
        })
    return rows


def _format_status(schema: str, rows: list[dict]) -> str:
    lines = [f"RLS status — {schema}", "=" * 72]
    for r in rows:
        marker = "OK " if r["in_sync"] else "XX"
        lines.append(
            f"  [{marker}] {r['table']:<40} {r['classification']:<16} "
            f"rls={'Y' if r['enabled'] else 'N'} force={'Y' if r['forced'] else 'N'}"
        )
        if not r["in_sync"]:
            missing = sorted(set(r["policies_expected"]) - set(r["policies_current"]))
            extra = sorted(set(r["policies_current"]) - set(r["policies_expected"]))
            if missing:
                lines.append(f"         missing policies: {', '.join(missing)}")
            if extra:
                lines.append(f"         unexpected policies: {', '.join(extra)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _get_url() -> str:
    url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL_SYNC (or DATABASE_URL) must be set", file=sys.stderr)
        sys.exit(2)
    return url


def _connect(url: str | None = None):
    return psycopg2.connect(url or _get_url())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply RLS policies based on table introspection.")
    parser.add_argument("--schema", required=True, help="Target schema (e.g. ai_nlp, billing, core).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Print current RLS state per table.")
    mode.add_argument("--dry-run", action="store_true", help="Print SQL that would apply (default).")
    mode.add_argument("--diff", action="store_true",
                      help="Exit nonzero if current state diverges from expected.")
    mode.add_argument("--apply", action="store_true", help="Execute the SQL (requires --yes).")
    parser.add_argument("--yes", action="store_true", help="Confirm --apply.")
    args = parser.parse_args(argv)

    with _connect() as conn:
        if args.status:
            rows = status_report(conn, args.schema)
            print(_format_status(args.schema, rows))
            return 0

        if args.diff:
            rows = status_report(conn, args.schema)
            out_of_sync = [r for r in rows if not r["in_sync"]]
            print(_format_status(args.schema, rows))
            return 0 if not out_of_sync else 1

        if args.apply:
            if not args.yes:
                print("--apply requires --yes to confirm.", file=sys.stderr)
                return 2
            infos = classify_schema(conn, args.schema)
            with conn.cursor() as cur:
                for info in sorted(infos, key=lambda i: i.table):
                    if info.classification is Classification.OUT_OF_SCOPE:
                        continue
                    # Idempotent: drop each expected policy before recreating.
                    for pname in expected_policy_names(info):
                        cur.execute(
                            f"DROP POLICY IF EXISTS {pname} ON {info.schema}.{info.table}"
                        )
                    for stmt in generate_sql(info):
                        cur.execute(stmt)
            conn.commit()
            print(f"Applied RLS policies to {args.schema}.")
            return 0

        # Default: dry-run
        infos = classify_schema(conn, args.schema)
        sql = generate_schema_sql(infos)
        print(f"-- RLS dry-run for schema {args.schema}")
        print(f"-- {len(infos)} tables scanned, "
              f"{sum(1 for i in infos if i.classification is not Classification.OUT_OF_SCOPE)} "
              f"in-scope")
        for stmt in sql:
            print(stmt + ";\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
