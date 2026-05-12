"""maxacc_registry baseline — Wave 44a M1.

Reference-data schema for the maximizer / accumulator program registry.
Five baseline tables:

  1. source_lists                  catalog of vendor/source feeds
  2. ndc_list_entries              NDCs appearing on a maximizer / accumulator
                                   target list
  3. bin_pcn_group_vendor_map      BIN/PCN/Group combos linked to a vendor
                                   program
  4. vendor_pbm_relationships      vendor → PBM / specialty pharmacy
                                   exclusivity
  5. import_runs                   provenance per ingest run

This module is **global reference data** — same architectural pattern
as DataQ NCPDP, prescriber NPPES, OIG/SAM exclusions:

  * NO ``tenant_id`` column on any table
  * NO Row-Level Security policies
  * Tables are owned by the platform; only ``platform_admin`` can mutate

CHECK constraints enforce value sets for source_type, scrape_strategy,
scrape_cadence, confidence, status enums. Composite uniques where
documented; partial uniques on (active=true) where one-active-row
semantics apply.

NDC normalization: stored as 11-digit string with NO hyphens (matches
existing drug_db convention). Hyphenated input is normalized at the
ingest layer; this schema stores the canonical form.

Revision ID: 0001_maxacc_registry_baseline
Revises:
Create Date: 2026-04-27
"""

from __future__ import annotations

from typing import Sequence, Union

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_maxacc_registry_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "maxacc_registry"

_SOURCE_TYPES = "('ndc_list', 'employer_list', 'bin_pcn_list', 'curated')"
_SCRAPE_STRATEGIES = "('manual_upload', 'scheduled_scrape', 'api')"
_SCRAPE_CADENCES = "('never', 'daily', 'weekly', 'monthly', 'quarterly')"
_CONFIDENCE_LEVELS = "('high', 'medium', 'low', 'inferred')"
_IMPORT_STATUSES = "('in_progress', 'completed', 'failed', 'rolled_back')"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ── 1. source_lists ──
    op.create_table(
        "source_lists",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_name", sa.String(120), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("vendor_name", sa.String(120), nullable=True),
        sa.Column("scrape_strategy", sa.String(32), nullable=False),
        sa.Column("scrape_cadence", sa.String(32), nullable=False),
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_imported_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"source_type IN {_SOURCE_TYPES}",
            name="ck_source_lists_source_type",
        ),
        sa.CheckConstraint(
            f"scrape_strategy IN {_SCRAPE_STRATEGIES}",
            name="ck_source_lists_scrape_strategy",
        ),
        sa.CheckConstraint(
            f"scrape_cadence IN {_SCRAPE_CADENCES}",
            name="ck_source_lists_scrape_cadence",
        ),
        # Composite unique — vendor_name nullable, so use coalesce-style
        # via a partial unique to make NULLs collide as one bucket.
        # Postgres treats NULL distinct in a regular unique; we want
        # ('Foo', NULL) to clash with another ('Foo', NULL) so use
        # coalesce in a unique INDEX.
        schema=_SCHEMA,
    )
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_source_lists_name_vendor
            ON {_SCHEMA}.source_lists
            (source_name, COALESCE(vendor_name, ''))
        """
    )
    op.create_index(
        "ix_source_lists_vendor",
        "source_lists",
        ["vendor_name"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_source_lists_active_type",
        "source_lists",
        ["active", "source_type"],
        schema=_SCHEMA,
    )

    # ── 2. import_runs ──
    op.create_table(
        "import_runs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_list_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.source_lists.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("imported_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "import_started_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column("import_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("import_file_path", sa.Text(), nullable=True),
        sa.Column("import_file_sha256", sa.String(64), nullable=True),
        sa.Column("records_imported", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_unchanged", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_added", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "records_marked_dropped", sa.Integer(),
            nullable=False, server_default=sa.text("0"),
        ),
        sa.Column(
            "status", sa.String(32),
            nullable=False, server_default=sa.text("'in_progress'"),
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            f"status IN {_IMPORT_STATUSES}",
            name="ck_import_runs_status",
        ),
        sa.CheckConstraint(
            "records_imported >= 0 "
            "AND records_unchanged >= 0 "
            "AND records_added >= 0 "
            "AND records_marked_dropped >= 0",
            name="ck_import_runs_counts_nonneg",
        ),
        sa.CheckConstraint(
            "(status = 'in_progress' AND import_completed_at IS NULL) OR "
            "(status <> 'in_progress' AND import_completed_at IS NOT NULL)",
            name="ck_import_runs_completed_iff_terminal",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_import_runs_source",
        "import_runs",
        ["source_list_id", "import_started_at"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_import_runs_status",
        "import_runs",
        ["status"],
        schema=_SCHEMA,
    )

    # ── 3. ndc_list_entries ──
    op.create_table(
        "ndc_list_entries",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_list_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.source_lists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ndc", sa.String(20), nullable=False),
        sa.Column("drug_name_as_listed", sa.String(255), nullable=True),
        sa.Column("normalized_drug_name", sa.String(255), nullable=True),
        sa.Column("first_observed_at", sa.Date(), nullable=False),
        sa.Column("last_observed_at", sa.Date(), nullable=False),
        sa.Column("no_longer_listed_at", sa.Date(), nullable=True),
        sa.Column(
            "import_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.import_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "ndc ~ '^[0-9]{11}$'",
            name="ck_ndc_list_entries_ndc_format",
        ),
        sa.CheckConstraint(
            "last_observed_at >= first_observed_at",
            name="ck_ndc_list_entries_last_ge_first",
        ),
        sa.CheckConstraint(
            "no_longer_listed_at IS NULL OR no_longer_listed_at >= first_observed_at",
            name="ck_ndc_list_entries_drop_after_first",
        ),
        sa.UniqueConstraint(
            "source_list_id", "ndc", "first_observed_at",
            name="uq_ndc_list_entries_source_ndc_first_seen",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_ndc_list_entries_ndc",
        "ndc_list_entries",
        ["ndc"],
        schema=_SCHEMA,
    )
    # Partial — covers the hot lookup path "any current listing for this NDC"
    op.execute(
        f"""
        CREATE INDEX ix_ndc_list_entries_ndc_active
            ON {_SCHEMA}.ndc_list_entries (ndc)
         WHERE no_longer_listed_at IS NULL
        """
    )

    # ── 4. bin_pcn_group_vendor_map ──
    op.create_table(
        "bin_pcn_group_vendor_map",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("bin", sa.String(6), nullable=False),
        sa.Column("pcn", sa.String(20), nullable=True),
        sa.Column("group_id", sa.String(50), nullable=True),
        sa.Column("vendor_name", sa.String(120), nullable=False),
        sa.Column("employer_or_plan_label", sa.String(255), nullable=True),
        sa.Column(
            "confidence", sa.String(16),
            nullable=False, server_default=sa.text("'high'"),
        ),
        sa.Column(
            "source_list_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.source_lists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("first_observed_at", sa.Date(), nullable=False),
        sa.Column("last_observed_at", sa.Date(), nullable=False),
        sa.Column("no_longer_observed_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "import_run_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.import_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "bin ~ '^[0-9]{6}$'",
            name="ck_bin_pcn_vendor_bin_format",
        ),
        sa.CheckConstraint(
            f"confidence IN {_CONFIDENCE_LEVELS}",
            name="ck_bin_pcn_vendor_confidence",
        ),
        sa.CheckConstraint(
            "last_observed_at >= first_observed_at",
            name="ck_bin_pcn_vendor_last_ge_first",
        ),
        sa.CheckConstraint(
            "no_longer_observed_at IS NULL OR no_longer_observed_at >= first_observed_at",
            name="ck_bin_pcn_vendor_drop_after_first",
        ),
        schema=_SCHEMA,
    )
    # Composite unique with NULLs treated as distinct buckets via COALESCE.
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_bin_pcn_vendor_combo
            ON {_SCHEMA}.bin_pcn_group_vendor_map
            (bin,
             COALESCE(pcn, ''),
             COALESCE(group_id, ''),
             vendor_name)
        """
    )
    op.create_index(
        "ix_bin_pcn_vendor_bin",
        "bin_pcn_group_vendor_map",
        ["bin"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_bin_pcn_vendor_bin_pcn",
        "bin_pcn_group_vendor_map",
        ["bin", "pcn"],
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_bin_pcn_vendor_vendor",
        "bin_pcn_group_vendor_map",
        ["vendor_name"],
        schema=_SCHEMA,
    )
    # Partial — covers the hot lookup path "currently observed".
    op.execute(
        f"""
        CREATE INDEX ix_bin_pcn_vendor_active
            ON {_SCHEMA}.bin_pcn_group_vendor_map (bin)
         WHERE no_longer_observed_at IS NULL
        """
    )

    # ── 5. vendor_pbm_relationships ──
    op.create_table(
        "vendor_pbm_relationships",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            primary_key=True, server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("vendor_name", sa.String(120), nullable=False),
        sa.Column("pbm_carrier", sa.String(120), nullable=False),
        sa.Column("exclusive_specialty_pharmacy", sa.String(120), nullable=True),
        sa.Column(
            "is_exclusive_relationship", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "vendor_name", name="uq_vendor_pbm_vendor_name",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_vendor_pbm_termination_after_effective",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_vendor_pbm_pbm",
        "vendor_pbm_relationships",
        ["pbm_carrier"],
        schema=_SCHEMA,
    )

    # Reference data is platform-owned. App roles need SELECT for the
    # Wave 44b consumer path; admin roles write via M3/M4 ingest +
    # M6 admin API.
    _APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
    for role in ("ifx_dev_app", _APP_ROLE):
        op.execute(f"GRANT USAGE ON SCHEMA {_SCHEMA} TO {role}")
        op.execute(
            f"GRANT SELECT ON ALL TABLES IN SCHEMA {_SCHEMA} TO {role}"
        )
    for role in ("ifx_dev_admin", "ifx_prod_admin"):
        op.execute(f"GRANT USAGE ON SCHEMA {_SCHEMA} TO {role}")
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
            f"IN SCHEMA {_SCHEMA} TO {role}"
        )


def downgrade() -> None:
    op.drop_table("vendor_pbm_relationships", schema=_SCHEMA)
    op.drop_table("bin_pcn_group_vendor_map", schema=_SCHEMA)
    op.drop_table("ndc_list_entries", schema=_SCHEMA)
    op.drop_table("import_runs", schema=_SCHEMA)
    op.drop_table("source_lists", schema=_SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
