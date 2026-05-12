"""B9.A C2 — Generated migration template for FDB tier batches.

Consumes a list of `TableSpec` instances + tier label and emits an
idempotent Alembic migration source as a string. Used by B9.B-G to
mass-produce the 6 SPEC-locked migrations:

    0009_fdb_tier_a              — 113 simple lookups (Tier A)
    0010_fdb_tier_b              — 66 NDC/GCN-keyed joins (Tier B)
    0011_fdb_tier_c_minus_rndc14 — 16 complex/large non-RNDC14 (Tier C)
    0012_fdb_rndc14              — RNDC14_NDC_MSTR standalone (68 cols)
    0013_fdb_pricing_big         — RNP2 + RPRDPP0 (Tier C, D2 perf gate)
    0014_fdb_mtl_schema          — 19 MTL schema-only (Tier D)

The generator is intentionally NOT invoked at migration time. It runs
ONCE per tier during B9.B-G execution; the operator reviews the
output, lands it as a real `.py` file in `alembic/versions/`, and
that file becomes the canonical migration. The generator is a
helper, not a runtime dependency.

ADVERSARIAL R1 A2 mitigation: every generated migration includes an
explicit `alembic upgrade + downgrade + upgrade` evidence-capture
docstring footer reminding the operator to dry-run on a disposable
DB before committing.

ADVERSARIAL R1 N4 mitigation: column types are derived from a known
coercer-to-SQL-type table. Unknown coercers raise loudly — they do
NOT silently fall through to a default type.

B7.3 lesson folded in: GRANT statements use the `IFX_APP_ROLE`
env-driven pattern with `ifx_dev_app` safe fallback, NOT a hardcoded
`ifx_prod_app` reference.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from drug_database.services.fdb_adapter import TableSpec, Tier


# ---------------------------------------------------------------------------
# Coercer → SQL column-type lookup
# ---------------------------------------------------------------------------
#
# Maps the Python coercer attached to a TableSpec column to a string
# representation of the SQLAlchemy column type. Unknown coercers
# raise ValueError — the operator must extend this table explicitly
# rather than fall through to a sloppy default.


def _sql_type_for_coercer(coercer: Callable[[str], Any]) -> str:
    """Return SQLAlchemy type literal for a TableSpec coercer.

    Raises ValueError if the coercer isn't recognized. Extend this
    function (not the call site) when adding new coercer kinds.
    """
    # Built-in types (functions are also types in Python)
    if coercer is int:
        return "sa.Integer()"
    if coercer is str:
        return "sa.Text()"
    if coercer is bool:
        return "sa.Boolean()"
    if coercer is float:  # explicitly reject — FDB has no float columns
        raise ValueError(
            "float coercer is forbidden in FDB tables (see "
            "financial-precision.md). Use Decimal."
        )
    if coercer is Decimal:
        return "sa.Numeric(16, 5)"  # FDB pricing precision; override per-table if different

    # Named functions — match by attribute name
    name = getattr(coercer, "__name__", "")
    if name == "_parse_fdb_date":
        return "sa.Date()"
    if name == "normalize_ndc":
        return "sa.String(11)"
    if name in {"_str11", "_str14"}:  # NDC string forms used in fdb_adapter helpers
        width = int(name[4:])
        return f"sa.String({width})"
    # B9.B GATE-CLOSE R1 MEDIUM 2 mitigation — per-precision Decimal coercers
    if name == "decimal_16_6":
        return "sa.Numeric(16, 6)"

    raise ValueError(
        f"Unknown coercer {coercer!r} (name={name!r}) — extend "
        "_sql_type_for_coercer() in gen_fdb_tier_migration.py before "
        "regenerating this tier's migration."
    )


# ---------------------------------------------------------------------------
# Migration source template
# ---------------------------------------------------------------------------


def _column_block(spec: TableSpec) -> str:
    """Generate the sa.Column(...) lines for one table."""
    lines: list[str] = []
    for col in spec.columns:
        coercer = spec.coercers[col]
        sql_type = _sql_type_for_coercer(coercer)
        nullable = col in spec.nullable
        nullable_kw = "True" if nullable else "False"
        lines.append(
            f'        sa.Column({col!r}, {sql_type}, nullable={nullable_kw}),'
        )
    return "\n".join(lines)


def _create_table_block(spec: TableSpec, schema: str) -> str:
    """Generate the op.create_table(...) call for one table.

    When `spec.natural_key` is non-empty, emits a PrimaryKeyConstraint
    over those columns so Postgres `ON CONFLICT (natural_key)` upserts
    have a unique surface to bind to.  Per codex B9.B GATE-CLOSE R1
    HIGH 2.
    """
    table_name = spec.table_name.lower()  # FDB names are upper; DB tables snake_case
    rcounts_key = spec.record_counts_key or spec.table_name
    pk_line = ""
    if spec.natural_key:
        pk_cols = ", ".join(repr(c) for c in spec.natural_key)
        pk_line = (
            f'\n        sa.PrimaryKeyConstraint({pk_cols}, '
            f'name="pk_{table_name}"),'
        )
    return f"""    # {spec.table_name} — tier={spec.tier.value} delta={spec.delta_semantics.value} record_counts_key={rcounts_key}
    op.create_table(
        "{table_name}",
{_column_block(spec)}{pk_line}
        schema={schema!r},
    )"""


def _grant_block(table_names: Sequence[str], schema: str) -> str:
    """Emit GRANT statements via env-driven role (B7.3 pattern)."""
    lines = ['    for _table in (']
    for tn in table_names:
        lines.append(f'        "{tn.lower()}",')
    lines.append("    ):")
    lines.append(
        f'        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE '
        f'ON {schema}.{{_table}} TO {{role}}" '
        f'for role in _APP_ROLES)'
    )
    return "\n".join(lines)


_MIGRATION_TEMPLATE = '''"""B9 {tier_label} batch — {n_tables} FDB tables ({tier_desc}).

Generated by `modules/drug-database/scripts/gen_fdb_tier_migration.py`
on {gen_date}. SPEC: charter v3.1 §SPEC-locked migration granularity;
plan v3.1 §W1-W4 tier scope.

Operator: dry-run on a disposable DB before committing (ADVERSARIAL R1 A2):

    alembic upgrade head      # forward
    alembic downgrade -1      # reverse
    alembic upgrade head      # re-apply

All three steps must succeed cleanly. Capture evidence to
`waves/B9/{tier_label}_dryrun_evidence.md` before committing.

Revision ID: {revision_id}
Revises: {down_revision}
Create Date: {gen_date}
"""
from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "{revision_id}"
down_revision: Union[str, None] = "{down_revision}"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "{schema}"

# B7.3 env-driven role pattern — defaults to dev-safe role if env unset.
# Production sets IFX_APP_ROLE=ifx_prod_app explicitly.
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_APP_ROLES = ("ifx_dev_app", "ifx_mock_app", _APP_ROLE)


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {{_SCHEMA}}".format(_SCHEMA=_SCHEMA))

{create_tables_block}

{grant_block}


def downgrade() -> None:
{drop_tables_block}
'''


def generate_tier_migration(
    *,
    specs: Sequence[TableSpec],
    tier: Tier,
    revision_id: str,
    down_revision: str,
    schema: str = "drug_database",
    gen_date: str | None = None,
) -> str:
    """Generate alembic migration source for a B9 tier batch.

    Args:
        specs: TableSpec list for this tier; all must have spec.tier == tier.
        tier: the B9 effort tier (used in docstring + revision metadata).
        revision_id: alembic revision identifier (e.g., "0009_fdb_tier_a").
        down_revision: parent revision (e.g., "0008_fdb_pricing").
        schema: target Postgres schema (default "drug_database").
        gen_date: ISO date string for the docstring; None → today.

    Returns:
        A string containing the full migration .py source. Caller is
        responsible for writing it to `alembic/versions/<revision>.py`
        and reviewing before committing.

    Raises:
        ValueError: if any spec has a coercer not in _sql_type_for_coercer.
        ValueError: if specs contains a spec whose tier != tier.
    """
    if not specs:
        raise ValueError("generate_tier_migration: empty specs list")
    # Import here to avoid a circular: fdb_adapter imports nothing from
    # this module, but `generate_tier_migration` is itself invoked by
    # scripts that import fdb_adapter via the registry.
    from drug_database.services.fdb_adapter import DeltaSemantics  # noqa: E402

    _checkable = {
        DeltaSemantics.UPSERT_BY_NATURAL_KEY,
        DeltaSemantics.UPSERT_WITH_EFFECTIVE_DATE,
    }
    for spec in specs:
        if spec.tier is not tier:
            raise ValueError(
                f"Spec {spec.table_name!r} has tier {spec.tier.value} "
                f"but generator was invoked for tier {tier.value}."
            )
        # B9.B GATE-CLOSE R1 HIGH 2: every UPSERT spec MUST declare a
        # natural_key so the migration can emit a PRIMARY KEY for
        # Postgres ON CONFLICT to bind to. Without this the migration
        # creates columns but no uniqueness surface — upsert fails at
        # runtime with `there is no unique or exclusion constraint`.
        if spec.delta_semantics in _checkable and not spec.natural_key:
            raise ValueError(
                f"Spec {spec.table_name!r} has delta_semantics="
                f"{spec.delta_semantics.value} but natural_key is empty. "
                f"Set natural_key=(<key col(s)>,) on the TableSpec so the "
                f"generated migration emits a PRIMARY KEY for ON CONFLICT "
                f"to bind to (B9.B GATE-CLOSE R1 HIGH 2)."
            )

    if gen_date is None:
        gen_date = date.today().isoformat()

    table_names = [s.table_name for s in specs]
    create_blocks = "\n\n".join(_create_table_block(s, schema) for s in specs)

    # Grant block: one for-loop over (table, role) pairs
    grants: list[str] = ["    for _table in ("]
    for tn in table_names:
        grants.append(f'        "{tn.lower()}",')
    grants.append("    ):")
    grants.append("        for _role in _APP_ROLES:")
    grants.append(
        f'            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE '
        f'ON {{_SCHEMA}}.{{_table}} TO {{_role}}")'
    )
    grant_block = "\n".join(grants)

    # Downgrade: drop in reverse order
    drop_lines = [
        f'    op.drop_table("{s.table_name.lower()}", schema=_SCHEMA)'
        for s in reversed(specs)
    ]
    drop_tables_block = "\n".join(drop_lines)

    tier_desc = {
        Tier.A: "simple lookups, generic ingester",
        Tier.B: "NDC/GCN-keyed joins",
        Tier.C: "complex/large (>8 cols or >50 MB)",
        Tier.D: "MTL — schema-only, no data load",
        Tier.UNKNOWN: "uncategorized (should not be generated)",
    }[tier]

    tier_label = f"Tier {tier.value}"
    return _MIGRATION_TEMPLATE.format(
        tier_label=tier_label,
        tier_desc=tier_desc,
        n_tables=len(specs),
        gen_date=gen_date,
        revision_id=revision_id,
        down_revision=down_revision,
        schema=schema,
        create_tables_block=create_blocks,
        grant_block=grant_block,
        drop_tables_block=drop_tables_block,
    )


__all__ = ["generate_tier_migration", "_sql_type_for_coercer"]
