"""members schema canonical identity layer — Wave 30 Phase B M1.

Introduces the platform-wide canonical member identity layer:

  members.member_master                — internally-assigned UUID,
                                          resolved on first-seen via
                                          (tenant_id, cardholder_id, dob)
  members.member_program_enrollments    — per-program enrollment with
                                          NCPDP group/person/relationship
  members.member_addresses              — effective-dated address +
                                          contact records, sourced
                                          from claim/admin/import

Why a new schema vs reusing member_mgmt:

  - ``member_mgmt`` (the existing member-management module schema)
    is for 834/CSV-driven eligibility import and full member
    lifecycle. It carries PHI columns (encrypted SSN/DOB/etc.) and
    is owned by the member-management module.
  - ``members`` (this schema) is a thin canonical-identity layer
    that runtime adjudication uses to deduplicate the same patient
    across pharmacy claims (and, in Phase 4, medical claims). It's
    the resolution target for ``ClaimContext.member_id`` and the
    foreign key target for accumulator/flag tables. Owned by
    adjudication-engine.

Both schemas can coexist: a future wave can have member-management
populate canonical UUIDs in ``members.member_master`` from 834 imports
to pre-resolve members before their first claim arrives. Today the
canonical layer is populated by ``shared.program_config_queries.
member_resolution.resolve_or_create_member`` on first-claim sighting.

Resolution key (per Wave 30 Q1 decision): composite unique on
``(tenant_id, cardholder_id, dob)``. Two pharmacies submitting
claims for the same patient on the same plan resolve to the same
canonical member_id.

RLS: every table has ``tenant_id`` and forces RLS via the standard
NULLIF wrapped predicate (Wave 20 B2 pattern).

Revision ID: 0008_members_canonical
Revises: 0007_bin_routing
Create Date: 2026-04-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_members_canonical"
down_revision: Union[str, None] = "0007_bin_routing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "members"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_APP_ROLES = ("ifx_dev_app", "ifx_mock_app", _APP_ROLE)
_RLS_PREDICATE = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), "
    "'')::uuid"
)


def _grant_all(table: str) -> None:
    for role in _APP_ROLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE "
            f"ON {_SCHEMA}.{table} TO {role}"
        )


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
          FOR ALL
          TO {', '.join(_APP_ROLES)}
          USING      ({_RLS_PREDICATE})
          WITH CHECK ({_RLS_PREDICATE})
        """
    )


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")
    # Schema USAGE for the three tier app roles. Without this,
    # SELECTs from the app role hit "permission denied for schema".
    for role in _APP_ROLES:
        op.execute(f"GRANT USAGE ON SCHEMA {_SCHEMA} TO {role}")

    # ── members.member_master ─────────────────────────────────────
    op.create_table(
        "member_master",
        sa.Column(
            "member_id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cardholder_id", sa.String(20), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("first_name", sa.String(35)),
        sa.Column("last_name", sa.String(35)),
        sa.Column("middle_initial", sa.String(1)),
        sa.Column("gender_code", sa.String(1)),
        sa.Column(
            "first_seen_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "cardholder_id", "date_of_birth",
            name="uq_member_master_resolution_key",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_member_master_tenant_card", "member_master",
        ["tenant_id", "cardholder_id"], schema=_SCHEMA,
    )
    _grant_all("member_master")
    _enable_rls("member_master")

    # ── members.member_program_enrollments ────────────────────────
    # Per-program enrollment carrying NCPDP D.0 group/person/
    # relationship codes. One member can have multiple enrollments
    # (different programs, time windows). FK to program_config.programs
    # is intentional cross-schema to keep the program ID space
    # unified.
    op.create_table(
        "member_program_enrollments",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "member_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column(
            "program_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column("group_id", sa.String(15)),
        sa.Column("person_code", sa.String(3)),
        sa.Column("patient_relationship_code", sa.String(1)),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("termination_date", sa.Date),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"], [f"{_SCHEMA}.member_master.member_id"],
            ondelete="CASCADE",
        ),
        # Cross-schema FK to program_config — enforced at the DB
        # level so enrollments can't dangle. CASCADE on delete so
        # program teardown (test or admin lifecycle) doesn't strand
        # enrollment rows. Production safety against accidental
        # program deletion is enforced at the application layer
        # (program archival workflow), not via FK NO ACTION.
        sa.ForeignKeyConstraint(
            ["program_id"], ["program_config.programs.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "member_id", "program_id", "effective_from",
            name="uq_member_enrollment_period",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_member_enrollment_program", "member_program_enrollments",
        ["program_id", "effective_from"], schema=_SCHEMA,
    )
    op.create_index(
        "idx_member_enrollment_member", "member_program_enrollments",
        ["member_id"], schema=_SCHEMA,
    )
    _grant_all("member_program_enrollments")
    _enable_rls("member_program_enrollments")

    # ── members.member_addresses ──────────────────────────────────
    # Effective-dated address + contact records. Source enum tracks
    # provenance: 'claim' (auto-captured from NCPDP claim), 'admin'
    # (operator UI), 'import' (834 / CSV).
    op.create_table(
        "member_addresses",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "member_id", postgresql.UUID(as_uuid=True), nullable=False,
        ),
        sa.Column("address_line_1", sa.String(60)),
        sa.Column("address_line_2", sa.String(60)),
        sa.Column("city", sa.String(50)),
        sa.Column("state", sa.String(2)),
        sa.Column("zip", sa.String(5)),
        sa.Column("zip_plus_4", sa.String(4)),
        sa.Column("phone", sa.String(10)),
        sa.Column("email", sa.String(254)),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("termination_date", sa.Date),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["member_id"], [f"{_SCHEMA}.member_master.member_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "source IN ('claim', 'admin', 'import')",
            name="ck_member_address_source",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_member_addresses_member", "member_addresses", ["member_id"],
        schema=_SCHEMA,
    )
    _grant_all("member_addresses")
    _enable_rls("member_addresses")


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.member_addresses CASCADE")
    op.execute(
        f"DROP TABLE IF EXISTS {_SCHEMA}.member_program_enrollments CASCADE"
    )
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.member_master CASCADE")
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
