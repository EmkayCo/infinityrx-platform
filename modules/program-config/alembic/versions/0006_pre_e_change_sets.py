"""program_config Wave 26 Phase C.7-PRE-E: parameter change sets.

Adds the scheduled-change-set grouping table on top of PRE-H's
``program_parameters`` table. A change set is an atomic bundle of
parameter scope rows that all become effective on the change set's
``effective_date``. Workflow:

1. ``create_change_set(program_id, effective_date, ...)`` — opens a
   draft bundle.
2. Multiple ``stage_parameter_change(change_set_id, scope, params,
   ...)`` calls insert draft rows under the bundle. Draft rows sit
   in ``program_parameters`` with ``change_set_id`` set; they do NOT
   appear to the resolver because their effective_date is in the
   future (resolver filters ``effective_date <= as_of``).
3. ``approve_change_set(change_set_id, approver_id)`` — marks the
   bundle approved. Still doesn't change resolver behavior.
4. ``apply_change_set(change_set_id)`` — atomically:
     - For each draft row's (tenant, program, scope) tuple,
       TERMINATE any currently-active row at that scope by setting
       ``termination_date = change_set.effective_date``. Postgres
       enforces ``termination_date > effective_date`` via check
       constraint, so this only fires on rows whose effective_date
       predates the change-set's effective_date (the expected case).
     - The new rows were already inserted by ``stage_parameter_change``
       with ``effective_date = change_set.effective_date``; no row
       mutation needed to "activate" them — the resolver naturally
       picks them up at ``as_of >= effective_date``.
     - Update the change set: ``status='applied'``,
       ``applied_at=now()``.

Point-in-time audit is served directly by PRE-H's
``resolve_program_parameters(as_of_date=...)`` — the union of active
rows at any date IS the effective config at that date, reproducible
from the current table state.

Revision ID: 0006_pre_e_change_sets
Revises: 0005_pre_h_parameters
Create Date: 2026-04-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_pre_e_change_sets"
down_revision: Union[str, None] = "0005_pre_h_parameters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "program_config"
import os
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_ROLES = f"ifx_dev_app, ifx_mock_app, {_APP_ROLE}"
_TENANT_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
)


def upgrade() -> None:
    op.create_table(
        "program_parameter_change_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'applied', 'cancelled')",
            name="ck_change_set_status",
        ),
        sa.CheckConstraint(
            "(status <> 'approved') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_change_set_approved_has_metadata",
        ),
        sa.CheckConstraint(
            "(status <> 'applied') OR applied_at IS NOT NULL",
            name="ck_change_set_applied_has_timestamp",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_program_parameter_change_sets_tenant_id",
        "program_parameter_change_sets", ["tenant_id"], schema=_SCHEMA,
    )
    op.create_index(
        "idx_change_sets_program_effective",
        "program_parameter_change_sets",
        ["tenant_id", "program_id", "effective_date"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_change_sets_program_status",
        "program_parameter_change_sets",
        ["tenant_id", "program_id", "status"],
        schema=_SCHEMA,
    )

    # Add change_set_id column on program_parameters with FK.
    op.add_column(
        "program_parameters",
        sa.Column("change_set_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=_SCHEMA,
    )
    op.create_foreign_key(
        "fk_program_parameters_change_set",
        "program_parameters", "program_parameter_change_sets",
        ["change_set_id"], ["id"],
        source_schema=_SCHEMA, referent_schema=_SCHEMA,
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_program_parameters_change_set",
        "program_parameters", ["change_set_id"], schema=_SCHEMA,
    )

    # Widen PRE-H's partial unique to include effective_date. The PRE-E
    # workflow stages a new row with termination_date=NULL at the same
    # scope as an existing active row (whose termination_date is also
    # NULL until apply runs); the original PRE-H unique blocked that.
    # Two rows at the same scope with different effective_dates are
    # legitimate staging state. A duplicate (scope, effective_date,
    # NULL termination) is still blocked, which is the constraint's
    # actual purpose — preventing accidentally-duplicated active
    # configuration.
    op.execute(f"DROP INDEX IF EXISTS {_SCHEMA}.uq_program_parameters_active_scope;")
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_program_parameters_active_scope_effective
          ON {_SCHEMA}.program_parameters
            (tenant_id, program_id,
             COALESCE(ndc, ''),
             COALESCE(network_tier, ''),
             COALESCE(occ_code, ''),
             effective_date)
          WHERE termination_date IS NULL;
        """
    )

    # Tenant-role privileges on the new change_sets table. Matches
    # PRE-H's grant pattern.
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE "
        f"ON {_SCHEMA}.program_parameter_change_sets TO {_ROLES};"
    )

    # RLS on the new table
    op.execute(f"ALTER TABLE {_SCHEMA}.program_parameter_change_sets ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {_SCHEMA}.program_parameter_change_sets FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.program_parameter_change_sets
          FOR ALL TO {_ROLES}
          USING ({_TENANT_PREDICATE})
          WITH CHECK ({_TENANT_PREDICATE});
        """
    )


def downgrade() -> None:
    # Restore PRE-H's narrower partial unique.
    op.execute(
        f"DROP INDEX IF EXISTS {_SCHEMA}.uq_program_parameters_active_scope_effective;"
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_program_parameters_active_scope
          ON {_SCHEMA}.program_parameters
            (tenant_id, program_id,
             COALESCE(ndc, ''),
             COALESCE(network_tier, ''),
             COALESCE(occ_code, ''))
          WHERE termination_date IS NULL;
        """
    )
    op.execute(
        f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.program_parameter_change_sets;"
    )
    op.drop_index(
        "idx_program_parameters_change_set",
        table_name="program_parameters", schema=_SCHEMA,
    )
    op.drop_constraint(
        "fk_program_parameters_change_set",
        "program_parameters", type_="foreignkey", schema=_SCHEMA,
    )
    op.drop_column("program_parameters", "change_set_id", schema=_SCHEMA)
    op.drop_index(
        "idx_change_sets_program_status",
        table_name="program_parameter_change_sets", schema=_SCHEMA,
    )
    op.drop_index(
        "idx_change_sets_program_effective",
        table_name="program_parameter_change_sets", schema=_SCHEMA,
    )
    op.drop_index(
        "ix_program_parameter_change_sets_tenant_id",
        table_name="program_parameter_change_sets", schema=_SCHEMA,
    )
    op.drop_table("program_parameter_change_sets", schema=_SCHEMA)
