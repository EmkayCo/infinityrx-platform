"""program_config Wave 26 Phase C.7-PRE-H: program_parameters table.

Hierarchical parameter resolution surface. Single table with optional
scope columns (ndc, network_tier, occ_code). A resolver in
``shared.program_config_queries.parameters`` walks from least-specific
(all nulls) to most-specific (all set) and deep-merges the JSONB
``parameters`` dicts, so more-specific rows override less-specific
keys at the dict-leaf level.

Per Section 6 Decision 2 of the BRD rule catalog synthesis:
  - Program-level coverage (which OCCs program pays for) gates rule
    processing.
  - Parameters hierarchical: program default → per-OCC → per-tier →
    per-(tier+OCC) [+ per-NDC orthogonal at each level].
  - Rules ask the resolution layer for values; rule code doesn't know
    about OCC variation.

Effective dating columns ship in this migration even though the
scheduled-change-set workflow is PRE-E: the resolver uses
``effective_date <= as_of`` + ``termination_date > as_of`` filters
from day one, so PRE-E adds only the change-set grouping table and
a helper for atomic-apply semantics, not a schema migration.

Revision ID: 0005_pre_h_parameters
Revises: 0004_pre_b_pre_c_tables
Create Date: 2026-04-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_pre_h_parameters"
down_revision: Union[str, None] = "0004_pre_b_pre_c_tables"
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
        "program_parameters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Scope columns. NULL = "applies to all values of this dimension."
        # An all-nulls row is the program default. All three set is the
        # most-specific override.
        sa.Column("ndc", sa.String(11), nullable=True),
        sa.Column("network_tier", sa.String(100), nullable=True),
        sa.Column("occ_code", sa.String(2), nullable=True),
        # The parameter payload. JSONB so the resolver can deep-merge
        # without schema-per-rule coupling. Rules read specific keys.
        sa.Column(
            "parameters", postgresql.JSONB(), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Effective dating: inclusive on effective_date, exclusive on
        # termination_date (so a row that terminates on 2026-06-01
        # applies through EOD 2026-05-31). Matches rule_instances
        # convention.
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date > effective_date",
            name="ck_program_parameters_dates_lifecycle",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(parameters) = 'object'",
            name="ck_program_parameters_is_object",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_program_parameters_tenant_id",
        "program_parameters", ["tenant_id"], schema=_SCHEMA,
    )
    # Primary resolver lookup: tenant + program + effective window. The
    # three scope columns are selective enough that a single composite
    # doesn't buy much over this; the resolver's WHERE clause filters
    # scope columns with OR branches that Postgres handles as index
    # scans on (tenant_id, program_id) followed by filter.
    op.create_index(
        "idx_program_parameters_lookup",
        "program_parameters",
        ["tenant_id", "program_id", "effective_date"],
        schema=_SCHEMA,
    )
    # Partial unique: at most one active row per (tenant, program,
    # scope_ndc, scope_tier, scope_occ) WHERE termination_date IS NULL.
    # COALESCE so NULL scope values participate in uniqueness
    # (two "program default" rows without COALESCE would both have
    # NULL in all three scope columns and the standard unique would
    # treat them as distinct).
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

    # Tenant-role privileges. The schema's default-privileges grant
    # doesn't automatically pick up new tables created in later
    # migrations; grant explicitly so ifx_*_app can SELECT/INSERT/
    # UPDATE/DELETE under RLS.
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE "
        f"ON {_SCHEMA}.program_parameters TO {_ROLES};"
    )

    # RLS
    op.execute(f"ALTER TABLE {_SCHEMA}.program_parameters ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {_SCHEMA}.program_parameters FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.program_parameters
          FOR ALL TO {_ROLES}
          USING ({_TENANT_PREDICATE})
          WITH CHECK ({_TENANT_PREDICATE});
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.program_parameters;")
    op.execute(f"DROP INDEX IF EXISTS {_SCHEMA}.uq_program_parameters_active_scope;")
    op.drop_index("idx_program_parameters_lookup", table_name="program_parameters", schema=_SCHEMA)
    op.drop_index("ix_program_parameters_tenant_id", table_name="program_parameters", schema=_SCHEMA)
    op.drop_table("program_parameters", schema=_SCHEMA)
