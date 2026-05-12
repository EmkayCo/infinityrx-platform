"""DataQ NCPDP schema — Wave 29 M3.

Full replacement of the Wave 27 partial-stub ``ncpdp_pharmacies``
table with a DataQ-canonical structure. Ingested monthly from the
NCPDP DataQ v3.1 13-file extract by
:mod:`shared.data_ingestion.dataq_ncpdp`.

Created tables (all under ``pharmacy_dir`` schema, no RLS —
reference data):

  1. dataq_master                — 1 row per NCPDP provider ID
                                    (from mas.txt)
  2. dataq_alternate_firms       — from mas_af.txt
  3. dataq_parent_corps          — from mas_pc.txt
  4. dataq_primary_records       — from mas_pr.txt
  5. dataq_remittance_entities   — from mas_rec.txt (NOT layout
                                    definitions — the plan's original
                                    assumption about this file was
                                    incorrect; it's peer parent/
                                    remittance-entity data)
  6. dataq_change_of_ownership   — from mas_coo.txt
  7. dataq_erx_capability        — from mas_erx.txt
  8. dataq_fwa_markers           — from mas_fwa.txt (largest; 383K
                                    rows / monthly)
  9. dataq_medicaid_ids          — from mas_md.txt
 10. dataq_remittance_routing    — from mas_rr.txt
 11. dataq_state_licenses        — from mas_stl.txt
 12. dataq_service_codes         — from mas_svc.txt
 13. dataq_taxonomy_codes        — from mas_tx.txt
 14. dataq_ingestion_runs        — per-ingest metadata

Every supplemental table ON DELETE CASCADE via FK to dataq_master.
A full monthly re-ingest TRUNCATEs all 13 data tables and re-inserts
(see shared.data_ingestion.dataq_ncpdp.ingester).

Indexes on npi / federal_tax_id (where present) support exclusion-
rule joins to shared.sam_exclusions + shared.oig_leie.

DROP: ``pharmacy_dir.ncpdp_pharmacies`` is dropped entirely. The
Wave 27 schema carried partial stub data and is superseded. No
FK constraints point at the dropped table (verified via pg_constraint
query before authoring this migration).

Revision ID: 0007_dataq_replace
Revises: 0006_uei_cage_columns
Create Date: 2026-04-24
"""

from __future__ import annotations

from typing import Sequence, Union

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_dataq_replace"
down_revision: Union[str, None] = "0006_uei_cage_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "pharmacy_dir"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_APP_ROLES = ("ifx_dev_app", "ifx_mock_app", _APP_ROLE)


def upgrade() -> None:
    # ── 1. drop the Wave 27 stub table ─────────────────────────────────
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.ncpdp_pharmacies CASCADE")

    # ── 2. dataq_master (from mas.txt) ────────────────────────────────
    op.create_table(
        "dataq_master",
        sa.Column(
            "ncpdp_provider_id", sa.String(7), primary_key=True,
        ),
        sa.Column("legal_business_name", sa.String(60)),
        sa.Column("dba_name", sa.String(60)),
        sa.Column("dba_name_alt", sa.String(60)),
        sa.Column("aux_187_10", sa.String(10)),
        sa.Column("address_line_1", sa.String(60)),
        sa.Column("address_line_2", sa.String(50)),
        sa.Column("city", sa.String(30)),
        sa.Column("state", sa.String(2)),
        sa.Column("zip5", sa.String(5)),
        sa.Column("zip_ext", sa.String(4)),
        sa.Column("phone", sa.String(10)),
        sa.Column("phone_ext", sa.String(5)),
        sa.Column("fax", sa.String(10)),
        sa.Column("email", sa.String(30)),
        sa.Column("location_description", sa.String(70)),
        sa.Column("aux_473_9d", sa.String(9)),
        sa.Column("status_flag", sa.String(2)),
        sa.Column("capability_codes", sa.String(34)),
        sa.Column("languages", sa.String(10)),
        sa.Column("store_open_date", sa.Date),
        sa.Column("termination_date", sa.Date),
        sa.Column("mailing_address_line_1", sa.String(60)),
        sa.Column("mailing_address_line_2", sa.String(50)),
        sa.Column("mailing_city", sa.String(30)),
        sa.Column("mailing_state", sa.String(2)),
        sa.Column("mailing_zip5", sa.String(5)),
        sa.Column("mailing_zip_ext", sa.String(4)),
        sa.Column("contact_last_name", sa.String(20)),
        sa.Column("contact_first_name", sa.String(21)),
        sa.Column("contact_title", sa.String(30)),
        sa.Column("contact_phone", sa.String(10)),
        sa.Column("aux_784_5", sa.String(5)),
        sa.Column("contact_email", sa.String(50)),
        sa.Column("aux_839_18", sa.String(18)),
        sa.Column("npi", sa.String(10)),
        sa.Column("aux_867_12", sa.String(12)),
        sa.Column("license_expiry_date", sa.Date),
        sa.Column("aux_887_15", sa.String(15)),
        sa.Column("aux_902_9", sa.String(9)),
        sa.Column("aux_911_10", sa.String(10)),
        sa.Column("end_date_or_reserved", sa.Date),
        sa.Column("raw_line", sa.String(1000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    # Exclusion-cross-ref indexes:
    op.create_index(
        "idx_dataq_master_npi", "dataq_master", ["npi"],
        schema=_SCHEMA, postgresql_where=sa.text("npi IS NOT NULL"),
    )
    op.create_index(
        "idx_dataq_master_state_zip5", "dataq_master",
        ["state", "zip5"], schema=_SCHEMA,
    )

    # ── Helper for supplementals that share the standard shape ────────
    def _supplemental(name: str, extra_cols: list[sa.Column],
                      indexes: list[tuple[str, list[str]]] | None = None):
        """Create a supplemental table with:
           id UUID PK (server-generated), ncpdp_provider_id FK→dataq_master
           ON DELETE CASCADE, + extra columns, + raw_line, + created_at.
        """
        cols = [
            sa.Column(
                "id", postgresql.UUID(as_uuid=True), primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "ncpdp_provider_id", sa.String(7), nullable=False,
            ),
            *extra_cols,
            sa.Column("raw_line", sa.Text),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False,
                server_default=sa.text("now()"),
            ),
        ]
        op.create_table(name, *cols, schema=_SCHEMA)
        # FK — added out-of-band because create_table with ForeignKey
        # needs target table already present.
        op.create_foreign_key(
            f"fk_{name}_master", name, "dataq_master",
            ["ncpdp_provider_id"], ["ncpdp_provider_id"],
            source_schema=_SCHEMA, referent_schema=_SCHEMA,
            ondelete="CASCADE",
        )
        # Scan-by-provider index for join performance
        op.create_index(
            f"idx_{name}_provider", name, ["ncpdp_provider_id"],
            schema=_SCHEMA,
        )
        for idx_name, idx_cols in (indexes or []):
            op.create_index(idx_name, name, idx_cols, schema=_SCHEMA)

    # ── Non-pharmacy parent/remittance tables (different ID space) ────
    # mas_pc / mas_pr / mas_rec share the same parent-entity shape.
    # No FK to dataq_master (different ID space — 6-digit parent IDs,
    # not 7-digit pharmacy IDs).
    for parent_table in (
        "dataq_parent_corps",        # mas_pc.txt
        "dataq_primary_records",      # mas_pr.txt
        "dataq_remittance_entities",  # mas_rec.txt
    ):
        op.create_table(
            parent_table,
            sa.Column(
                "id", postgresql.UUID(as_uuid=True), primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("parent_entity_id", sa.String(6), nullable=False),
            sa.Column("entity_name", sa.String(35)),
            sa.Column("secondary_name", sa.String(40)),
            sa.Column("address_block", sa.String(240)),
            sa.Column("contact_block", sa.String(31)),
            sa.Column("effective_date_or_aux", sa.Date),
            sa.Column("raw_line", sa.Text),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False,
                server_default=sa.text("now()"),
            ),
            schema=_SCHEMA,
        )
        op.create_index(
            f"idx_{parent_table}_entity", parent_table,
            ["parent_entity_id"], schema=_SCHEMA,
        )

    # ── dataq_alternate_firms (mas_af.txt; 5-digit firm_id, distinct
    #     ID space from pharmacy ncpdp_provider_id) ─────────────────────
    op.create_table(
        "dataq_alternate_firms",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("firm_id", sa.String(5), nullable=False),
        sa.Column("firm_name", sa.String(35)),
        sa.Column("address_block", sa.Text),
        sa.Column("contact_block", sa.Text),
        sa.Column("raw_line", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_dataq_alternate_firms_firm", "dataq_alternate_firms",
        ["firm_id"], schema=_SCHEMA,
    )

    # ── Pharmacy-keyed supplementals (FK to dataq_master) ─────────────
    _supplemental(
        "dataq_change_of_ownership",
        [
            sa.Column("prior_ncpdp_provider_id", sa.String(7)),
            sa.Column("change_effective_date", sa.Date),
            sa.Column("change_observed_date", sa.Date),
        ],
    )

    _supplemental(
        "dataq_erx_capability",
        [
            sa.Column("erx_message_types", sa.String(23)),
            sa.Column("aux_30_96", sa.String(96)),
            sa.Column("effective_date", sa.Date),
            sa.Column("termination_date", sa.Date),
        ],
    )

    _supplemental(
        "dataq_fwa_markers",
        [
            sa.Column("signatory_flag_1", sa.Boolean),
            sa.Column("signatory_flag_2", sa.Boolean),
            sa.Column("fwa_version", sa.String(4)),
            sa.Column("audit_year", sa.String(6)),
            sa.Column("active_flag", sa.Boolean),
            sa.Column("aux_20_8", sa.Date),
            sa.Column("signatory_name", sa.String(44)),
            sa.Column("aux_72_78", sa.String(78)),
            sa.Column("audit_date", sa.Date),
            sa.Column("audit_signatory_name", sa.String(60)),
            sa.Column("audit_pharmacy_name", sa.String(60)),
            sa.Column("audit_address_line_1", sa.String(60)),
            sa.Column("aux_338_80", sa.String(80)),
            sa.Column("audit_state", sa.String(2)),
            sa.Column("audit_zip", sa.String(9)),
            sa.Column("audit_npi", sa.String(10)),
            sa.Column("audit_phone", sa.String(10)),
            sa.Column("audit_email", sa.String(34)),
        ],
        indexes=[("idx_dataq_fwa_audit_date", ["audit_date"])],
    )

    _supplemental(
        "dataq_medicaid_ids",
        [
            sa.Column("state", sa.String(2)),
            sa.Column("state_medicaid_id", sa.String(20)),
            sa.Column("termination_date", sa.Date),
        ],
        indexes=[("idx_dataq_medicaid_state", ["state"])],
    )

    _supplemental(
        "dataq_remittance_routing",
        [
            sa.Column("remit_entity_id", sa.String(9)),
            sa.Column("aux_16_8", sa.String(8)),
            sa.Column("active_flag", sa.Boolean),
            sa.Column("effective_date", sa.Date),
            sa.Column("termination_date", sa.Date),
        ],
        indexes=[
            ("idx_dataq_rr_remit_entity", ["remit_entity_id"]),
        ],
    )

    _supplemental(
        "dataq_state_licenses",
        [
            sa.Column("state", sa.String(2)),
            sa.Column("license_number", sa.String(20)),
            sa.Column("license_expiry_date", sa.Date),
            sa.Column("license_second_date", sa.Date),
        ],
        indexes=[
            ("idx_dataq_stl_state", ["state"]),
            ("idx_dataq_stl_expiry", ["license_expiry_date"]),
        ],
    )

    _supplemental(
        "dataq_service_codes",
        [sa.Column("service_codes_packed", sa.String(36))],
    )

    _supplemental(
        "dataq_taxonomy_codes",
        [
            sa.Column("taxonomy_code", sa.String(10)),
            sa.Column("aux_17_2", sa.String(2)),
            sa.Column("termination_date", sa.Date),
        ],
        indexes=[("idx_dataq_tx_code", ["taxonomy_code"])],
    )

    # ── dataq_ingestion_runs — metadata ────────────────────────────────
    op.create_table(
        "dataq_ingestion_runs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_archive_filename", sa.String(255), nullable=False,
        ),
        sa.Column("source_extract_date", sa.Date),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "rows_by_file", postgresql.JSONB,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed', 'failed')",
            name="ck_ingestion_status",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_ingestion_runs_ingested_at", "dataq_ingestion_runs",
        ["ingested_at"], schema=_SCHEMA,
    )

    # ── Grants: app roles read + write (admin roles already bypass via
    #     BYPASSRLS but owner privileges differ; mirror the Wave 28 SW3
    #     bin_routing grant pattern) ───────────────────────────────────
    tables_to_grant = [
        "dataq_master",
        "dataq_parent_corps", "dataq_primary_records",
        "dataq_remittance_entities", "dataq_alternate_firms",
        "dataq_change_of_ownership", "dataq_erx_capability",
        "dataq_fwa_markers", "dataq_medicaid_ids",
        "dataq_remittance_routing", "dataq_state_licenses",
        "dataq_service_codes", "dataq_taxonomy_codes",
        "dataq_ingestion_runs",
    ]
    for role in _APP_ROLES:
        for t in tables_to_grant:
            op.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE "
                f"ON {_SCHEMA}.{t} TO {role}"
            )


def downgrade() -> None:
    """Drop all DataQ tables. Does NOT restore the Wave 27 stub."""
    for t in (
        "dataq_ingestion_runs",
        "dataq_taxonomy_codes", "dataq_service_codes",
        "dataq_state_licenses", "dataq_remittance_routing",
        "dataq_medicaid_ids", "dataq_fwa_markers",
        "dataq_erx_capability", "dataq_change_of_ownership",
        "dataq_alternate_firms",
        "dataq_remittance_entities", "dataq_primary_records",
        "dataq_parent_corps",
        "dataq_master",
    ):
        op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{t} CASCADE")
