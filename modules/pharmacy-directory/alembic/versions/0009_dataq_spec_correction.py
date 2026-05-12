"""DataQ schema correction to NCPDP v3.1 spec — Wave 30 Phase A M4.

Replaces Wave 29's reverse-engineered tables with spec-canonical
shapes per the NCPDP dataQ Implementation Guide v3.1 May 2023
Section 6. See docs/audit/wave-30-dataq-spec-vs-reversed.md for
the field-by-field diff.

Strategy: DROP + CREATE rather than ALTER COLUMN × dozens. The
DataQ data tables are full-replace monthly; re-ingest restores
content under correct shapes (Wave 30 M5 runs the re-ingest).

Preserved across the migration:
  - dataq_ingestion_runs (run history; unchanged)
  - exclusion-overlay columns on dataq_master (uei, cage_code,
    is_excluded, excluded_source, exclusion_date, exclusion_type)
    — these come from scripts/refresh_pharmacy_exclusions.py, not
    from DataQ. The spec's federal_tax_id_number column (15-char,
    cols 888-902 of mas.txt) replaces the Wave 28 9-char
    federal_tax_id overlay.

File→record-type corrections (5 of 13 files entirely re-shaped):

  mas_af.txt   alternate_firms       → relationship_demographic_info
  mas_rr.txt   remittance_routing    → provider_relationship_info
  mas_pc.txt   parent_corps          → payment_center_info (col rename)
  mas_pr.txt   primary_records       → parent_organization_info
  mas_rec.txt  remittance_entities   → remit_and_reconciliation_info
  mas_svc.txt  service_codes (packed)→ service_codes (25 cols)
  mas_fwa.txt  fwa_markers           → fwa_attestation (different fields)
  mas_md.txt   medicaid_ids          (renamed columns only)
  mas_tx.txt   taxonomy_codes        (added provider_type_code)
  mas_stl.txt  state_licenses        (col renames; added delete_date)
  mas_erx.txt  erx_capability        (renamed columns; widened service codes)
  mas_coo.txt  change_of_ownership   (col renames)

Revision ID: 0009_dataq_spec_correction
Revises: 0008_dataq_master_exclusion_cols
Create Date: 2026-04-24
"""

from __future__ import annotations

from typing import Sequence, Union

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_dataq_spec_correction"
down_revision: Union[str, None] = "0008_dataq_master_exclusion_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "pharmacy_dir"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_APP_ROLES = ("ifx_dev_app", "ifx_mock_app", _APP_ROLE)


def _grant_all(table: str) -> None:
    for role in _APP_ROLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE "
            f"ON {_SCHEMA}.{table} TO {role}"
        )


def upgrade() -> None:
    # ── 1. Drop all DataQ data tables (preserve dataq_ingestion_runs).
    # Order: supplementals (FK→master) first, then master, then the
    # 5 to-be-renamed/reshaped tables.
    drop_tables = [
        # supplementals with FK to dataq_master
        "dataq_taxonomy_codes",
        "dataq_service_codes",
        "dataq_state_licenses",
        "dataq_remittance_routing",
        "dataq_medicaid_ids",
        "dataq_fwa_markers",
        "dataq_erx_capability",
        "dataq_change_of_ownership",
        # standalone shape mismatches
        "dataq_alternate_firms",
        "dataq_remittance_entities",
        "dataq_primary_records",
        "dataq_parent_corps",
        # master last
        "dataq_master",
    ]
    for t in drop_tables:
        op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{t} CASCADE")

    # ── 2. dataq_master (Provider Information per spec 6.1.2) ─────
    op.create_table(
        "dataq_master",
        sa.Column("ncpdp_provider_id", sa.String(7), primary_key=True),
        sa.Column("legal_business_name", sa.String(60)),
        sa.Column("name", sa.String(60)),
        sa.Column("doctors_name", sa.String(60)),
        sa.Column("store_number", sa.String(10)),
        sa.Column("physical_location_address_1", sa.String(55)),
        sa.Column("physical_location_address_2", sa.String(55)),
        sa.Column("physical_location_city", sa.String(30)),
        sa.Column("physical_location_state_code", sa.String(2)),
        sa.Column("physical_location_zip_code", sa.String(9)),
        sa.Column("physical_location_phone_number", sa.String(10)),
        sa.Column("physical_location_extension", sa.String(5)),
        sa.Column("physical_location_fax", sa.String(10)),
        sa.Column("physical_location_email_address", sa.String(50)),
        sa.Column("physical_location_cross_street", sa.String(50)),
        sa.Column("physical_location_county_parish", sa.String(5)),
        sa.Column("physical_location_msa", sa.String(4)),
        sa.Column("physical_location_pmsa", sa.String(4)),
        sa.Column("physical_location_24_hour_operation_flag", sa.Boolean),
        sa.Column("physical_location_provider_hours", sa.String(35)),
        sa.Column("physical_location_congressional_voting_district",
                  sa.String(4)),
        sa.Column("physical_location_language_code_1", sa.String(2)),
        sa.Column("physical_location_language_code_2", sa.String(2)),
        sa.Column("physical_location_language_code_3", sa.String(2)),
        sa.Column("physical_location_language_code_4", sa.String(2)),
        sa.Column("physical_location_language_code_5", sa.String(2)),
        sa.Column("physical_location_store_open_date", sa.Date),
        sa.Column("physical_location_store_closure_date", sa.Date),
        sa.Column("mailing_address_1", sa.String(55)),
        sa.Column("mailing_address_2", sa.String(55)),
        sa.Column("mailing_address_city", sa.String(30)),
        sa.Column("mailing_address_state_code", sa.String(2)),
        sa.Column("mailing_address_zip_code", sa.String(9)),
        sa.Column("contact_last_name", sa.String(20)),
        sa.Column("contact_first_name", sa.String(20)),
        sa.Column("contact_middle_initial", sa.String(1)),
        sa.Column("contact_title", sa.String(30)),
        sa.Column("contact_phone_number", sa.String(10)),
        sa.Column("contact_extension", sa.String(5)),
        sa.Column("contact_email_address", sa.String(50)),
        sa.Column("dispenser_class_code", sa.String(2)),
        sa.Column("primary_provider_type_code", sa.String(2)),
        sa.Column("secondary_provider_type_code", sa.String(2)),
        sa.Column("tertiary_provider_type_code", sa.String(2)),
        sa.Column("medicare_provider_supplier_id", sa.String(10)),
        sa.Column("npi", sa.String(10)),
        sa.Column("dea_registration_id", sa.String(12)),
        sa.Column("dea_expiration_date", sa.Date),
        sa.Column("federal_tax_id_number", sa.String(15)),
        sa.Column("state_income_tax_id_number", sa.String(15)),
        sa.Column("deactivation_code", sa.String(2)),
        sa.Column("reinstatement_code", sa.String(2)),
        sa.Column("reinstatement_date", sa.Date),
        sa.Column("transaction_code", sa.String(1)),
        sa.Column("transaction_date", sa.Date),
        sa.Column("raw_line", sa.String(1000)),
        # ── Exclusion-overlay columns (populated by refresh script,
        # not DataQ) ─────────────────────────────────────────────────
        sa.Column("uei", sa.String(12)),
        sa.Column("cage_code", sa.String(5)),
        sa.Column(
            "is_excluded", sa.Boolean, nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("excluded_source", sa.String(40)),
        sa.Column("exclusion_date", sa.Date),
        sa.Column("exclusion_type", sa.String(40)),
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
    # Indexes for exclusion lookups + common joins.
    op.create_index(
        "idx_dataq_master_npi", "dataq_master", ["npi"],
        schema=_SCHEMA, postgresql_where=sa.text("npi IS NOT NULL"),
    )
    op.create_index(
        "idx_dataq_master_state_zip", "dataq_master",
        ["physical_location_state_code", "physical_location_zip_code"],
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_dataq_master_excluded", "dataq_master", ["is_excluded"],
        schema=_SCHEMA,
        postgresql_where=sa.text("is_excluded = TRUE"),
    )
    op.create_index(
        "idx_dataq_master_tin", "dataq_master", ["federal_tax_id_number"],
        schema=_SCHEMA,
        postgresql_where=sa.text("federal_tax_id_number IS NOT NULL"),
    )
    op.create_index(
        "idx_dataq_master_uei", "dataq_master", ["uei"],
        schema=_SCHEMA, postgresql_where=sa.text("uei IS NOT NULL"),
    )
    op.create_index(
        "idx_dataq_master_cage", "dataq_master", ["cage_code"],
        schema=_SCHEMA,
        postgresql_where=sa.text("cage_code IS NOT NULL"),
    )
    _grant_all("dataq_master")

    # ── 3. Helper: pharmacy-keyed supplemental ────────────────────
    def _supplemental(name: str, extra_cols: list[sa.Column],
                      indexes: list[tuple[str, list[str]]] | None = None):
        cols = [
            sa.Column(
                "id", postgresql.UUID(as_uuid=True), primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
            *extra_cols,
            sa.Column("raw_line", sa.Text),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), nullable=False,
                server_default=sa.text("now()"),
            ),
        ]
        op.create_table(name, *cols, schema=_SCHEMA)
        op.create_foreign_key(
            f"fk_{name}_master", name, "dataq_master",
            ["ncpdp_provider_id"], ["ncpdp_provider_id"],
            source_schema=_SCHEMA, referent_schema=_SCHEMA,
            ondelete="CASCADE",
        )
        op.create_index(
            f"idx_{name}_provider", name, ["ncpdp_provider_id"],
            schema=_SCHEMA,
        )
        for idx_name, idx_cols in (indexes or []):
            op.create_index(idx_name, name, idx_cols, schema=_SCHEMA)
        _grant_all(name)

    # ── 4. dataq_provider_relationship (mas_rr.txt — spec 6.2.2) ──
    _supplemental(
        "dataq_provider_relationship",
        [
            sa.Column("relationship_id", sa.String(3)),
            sa.Column("payment_center_id", sa.String(6)),
            sa.Column("remit_and_reconciliation_id", sa.String(6)),
            sa.Column("provider_type", sa.String(2)),
            sa.Column("is_primary", sa.Boolean),
            sa.Column("effective_from_date", sa.Date),
            sa.Column("effective_through_date", sa.Date),
        ],
        indexes=[
            ("idx_provider_relationship_relationship",
             ["relationship_id"]),
            ("idx_provider_relationship_payment_center",
             ["payment_center_id"]),
        ],
    )

    # ── 5. dataq_medicaid_information (mas_md.txt — spec 6.3.2) ───
    _supplemental(
        "dataq_medicaid_information",
        [
            sa.Column("state_code", sa.String(2)),
            sa.Column("medicaid_id", sa.String(20)),
            sa.Column("delete_date", sa.Date),
        ],
        indexes=[("idx_medicaid_state", ["state_code"])],
    )

    # ── 6. dataq_taxonomy_information (mas_tx.txt — spec 6.4.2) ───
    _supplemental(
        "dataq_taxonomy_information",
        [
            sa.Column("taxonomy_code", sa.String(10)),
            sa.Column("provider_type_code", sa.String(2)),
            sa.Column("delete_date", sa.Date),
        ],
        indexes=[("idx_taxonomy_code", ["taxonomy_code"])],
    )

    # ── 7. dataq_eprescribing_information (mas_erx.txt — spec 6.8.2)
    _supplemental(
        "dataq_eprescribing_information",
        [
            sa.Column("eprescribing_network_identifier", sa.String(3)),
            sa.Column("eprescribing_service_level_codes", sa.String(100)),
            sa.Column("effective_from_date", sa.Date),
            sa.Column("effective_through_date", sa.Date),
        ],
    )

    # ── 8. dataq_state_license (mas_stl.txt — spec 6.10.2) ────────
    _supplemental(
        "dataq_state_license",
        [
            sa.Column("license_state_code", sa.String(2)),
            sa.Column("state_license_number", sa.String(20)),
            sa.Column("state_license_expiration_date", sa.Date),
            sa.Column("delete_date", sa.Date),
        ],
        indexes=[
            ("idx_state_license_state", ["license_state_code"]),
            ("idx_state_license_expiry",
             ["state_license_expiration_date"]),
        ],
    )

    # ── 9. dataq_services_offered (mas_svc.txt — spec 6.11.2) ─────
    # 13 (indicator, code) pairs.
    _supplemental(
        "dataq_services_offered",
        [
            sa.Column("accepts_eprescriptions_indicator", sa.Boolean),
            sa.Column("accepts_eprescriptions_code", sa.String(2)),
            sa.Column("delivery_service_indicator", sa.Boolean),
            sa.Column("delivery_service_code", sa.String(2)),
            sa.Column("compounding_service_indicator", sa.Boolean),
            sa.Column("compounding_service_code", sa.String(2)),
            sa.Column("drive_up_window_indicator", sa.Boolean),
            sa.Column("drive_up_window_code", sa.String(2)),
            sa.Column("durable_medical_equipment_indicator", sa.Boolean),
            sa.Column("durable_medical_equipment_code", sa.String(2)),
            sa.Column("walk_in_clinic_indicator", sa.Boolean),
            sa.Column("walk_in_clinic_code", sa.String(2)),
            sa.Column("emergency_24_hour_service_indicator", sa.Boolean),
            sa.Column("emergency_24_hour_service_code", sa.String(2)),
            sa.Column("multi_dose_compliance_packaging_indicator",
                      sa.Boolean),
            sa.Column("multi_dose_compliance_packaging_code", sa.String(2)),
            sa.Column("immunizations_provided_indicator", sa.Boolean),
            sa.Column("immunizations_provided_code", sa.String(2)),
            sa.Column("handicapped_accessible_indicator", sa.Boolean),
            sa.Column("handicapped_accessible_code", sa.String(2)),
            sa.Column("status_340b_indicator", sa.Boolean),
            sa.Column("status_340b_code", sa.String(2)),
            sa.Column("closed_door_facility_indicator", sa.Boolean),
            sa.Column("closed_door_facility_status_code", sa.String(2)),
        ],
    )

    # ── 10. dataq_change_of_ownership (mas_coo.txt — spec 6.12.2) ─
    _supplemental(
        "dataq_change_of_ownership",
        [
            sa.Column("old_ncpdp_provider_id", sa.String(7)),
            sa.Column("old_store_close_date", sa.Date),
            sa.Column("change_of_ownership_effective_date", sa.Date),
        ],
    )

    # ── 11. dataq_fwa_attestation (mas_fwa.txt — spec 6.13.2) ─────
    _supplemental(
        "dataq_fwa_attestation",
        [
            sa.Column("medicare_part_d", sa.Boolean),
            sa.Column("fwa_attestation", sa.Boolean),
            sa.Column("version_number", sa.String(5)),
            sa.Column("plan_year", sa.String(4)),
            sa.Column("q1", sa.Boolean),
            sa.Column("q2", sa.Boolean),
            sa.Column("accreditation_date", sa.Date),
            sa.Column("accreditation_organization", sa.String(60)),
            sa.Column("q3", sa.Boolean),
            sa.Column("q4", sa.Boolean),
            sa.Column("signature_of_responsible_party", sa.String(60)),
            sa.Column("signature_date", sa.Date),
            sa.Column("responsible_party", sa.String(60)),
            sa.Column("participating_pharmacy_or_psao_name", sa.String(60)),
            sa.Column("address_1", sa.String(55)),
            sa.Column("address_2", sa.String(55)),
            sa.Column("city", sa.String(30)),
            sa.Column("state_code", sa.String(2)),
            sa.Column("zip_code", sa.String(9)),
            sa.Column("npi", sa.String(10)),
            sa.Column("fax", sa.String(10)),
            sa.Column("email", sa.String(50)),
        ],
        indexes=[("idx_fwa_attestation_plan_year", ["plan_year"])],
    )

    # ── 12. dataq_relationship_demographic (mas_af.txt — spec 6.5.2)
    # Standalone: keyed on relationship_id (3-char), distinct ID
    # space from ncpdp_provider_id. No FK to dataq_master.
    op.create_table(
        "dataq_relationship_demographic",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("relationship_id", sa.String(3), nullable=False),
        sa.Column("relationship_type", sa.String(2)),
        sa.Column("name", sa.String(35)),
        sa.Column("address_1", sa.String(55)),
        sa.Column("address_2", sa.String(55)),
        sa.Column("city", sa.String(30)),
        sa.Column("state_code", sa.String(2)),
        sa.Column("zip_code", sa.String(9)),
        sa.Column("phone_number", sa.String(10)),
        sa.Column("extension", sa.String(5)),
        sa.Column("fax_number", sa.String(10)),
        sa.Column("relationship_npi", sa.String(10)),
        sa.Column("relationship_federal_tax_id", sa.String(15)),
        sa.Column("contact_name", sa.String(30)),
        sa.Column("contact_title", sa.String(30)),
        sa.Column("email_address", sa.String(50)),
        sa.Column("contractual_contact_name", sa.String(30)),
        sa.Column("contractual_contact_title", sa.String(30)),
        sa.Column("contractual_contact_email", sa.String(50)),
        sa.Column("operational_contact_name", sa.String(30)),
        sa.Column("operational_contact_title", sa.String(30)),
        sa.Column("operational_contact_email", sa.String(50)),
        sa.Column("technical_contact_name", sa.String(30)),
        sa.Column("technical_contact_title", sa.String(30)),
        sa.Column("technical_contact_email", sa.String(50)),
        sa.Column("audit_contact_name", sa.String(30)),
        sa.Column("audit_contact_title", sa.String(30)),
        sa.Column("audit_contact_email", sa.String(50)),
        sa.Column("parent_organization_id", sa.String(6)),
        sa.Column("effective_from_date", sa.Date),
        sa.Column("delete_date", sa.Date),
        sa.Column("raw_line", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_relationship_demographic_id", "dataq_relationship_demographic",
        ["relationship_id"], schema=_SCHEMA,
    )
    op.create_index(
        "idx_relationship_demographic_parent",
        "dataq_relationship_demographic", ["parent_organization_id"],
        schema=_SCHEMA,
    )
    _grant_all("dataq_relationship_demographic")

    # ── 13. Generic-entity tables (mas_pc/pr/rec) ─────────────────
    # Standalone — keyed on 6-digit entity ID, distinct from
    # ncpdp_provider_id. The three files share the same generic
    # entity shape but distinct field-name prefixes per spec.
    op.create_table(
        "dataq_payment_center",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("payment_center_id", sa.String(6), nullable=False),
        sa.Column("payment_center_name", sa.String(35)),
        sa.Column("payment_center_address_1", sa.String(55)),
        sa.Column("payment_center_address_2", sa.String(55)),
        sa.Column("payment_center_city", sa.String(30)),
        sa.Column("payment_center_state_code", sa.String(2)),
        sa.Column("payment_center_zip_code", sa.String(9)),
        sa.Column("payment_center_phone_number", sa.String(10)),
        sa.Column("payment_center_extension", sa.String(5)),
        sa.Column("payment_center_fax_number", sa.String(10)),
        sa.Column("payment_center_npi", sa.String(10)),
        sa.Column("payment_center_federal_tax_id", sa.String(15)),
        sa.Column("payment_center_contact_name", sa.String(30)),
        sa.Column("payment_center_contact_title", sa.String(30)),
        sa.Column("payment_center_email_address", sa.String(50)),
        sa.Column("delete_date", sa.Date),
        sa.Column("raw_line", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_payment_center_id", "dataq_payment_center",
        ["payment_center_id"], schema=_SCHEMA,
    )
    _grant_all("dataq_payment_center")

    op.create_table(
        "dataq_parent_organization",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("parent_organization_id", sa.String(6), nullable=False),
        sa.Column("parent_organization_name", sa.String(35)),
        sa.Column("address_1", sa.String(55)),
        sa.Column("address_2", sa.String(55)),
        sa.Column("city", sa.String(30)),
        sa.Column("state_code", sa.String(2)),
        sa.Column("zip_code", sa.String(9)),
        sa.Column("phone_number", sa.String(10)),
        sa.Column("extension", sa.String(5)),
        sa.Column("fax_number", sa.String(10)),
        sa.Column("parent_organization_npi", sa.String(10)),
        sa.Column("parent_organization_federal_tax_id", sa.String(15)),
        sa.Column("contact_name", sa.String(30)),
        sa.Column("contact_title", sa.String(30)),
        sa.Column("email_address", sa.String(50)),
        sa.Column("delete_date", sa.Date),
        sa.Column("raw_line", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_parent_organization_id", "dataq_parent_organization",
        ["parent_organization_id"], schema=_SCHEMA,
    )
    _grant_all("dataq_parent_organization")

    op.create_table(
        "dataq_remit_and_reconciliation",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("remit_and_reconciliation_id", sa.String(6),
                  nullable=False),
        sa.Column("remit_and_reconciliation_name", sa.String(35)),
        sa.Column("remit_and_reconciliation_address_1", sa.String(55)),
        sa.Column("remit_and_reconciliation_address_2", sa.String(55)),
        sa.Column("remit_and_reconciliation_city", sa.String(30)),
        sa.Column("remit_and_reconciliation_state_code", sa.String(2)),
        sa.Column("remit_and_reconciliation_zip_code", sa.String(9)),
        sa.Column("remit_and_reconciliation_phone_number", sa.String(10)),
        sa.Column("remit_and_reconciliation_extension", sa.String(5)),
        sa.Column("remit_and_reconciliation_fax_number", sa.String(10)),
        sa.Column("remit_and_reconciliation_npi", sa.String(10)),
        sa.Column("remit_and_reconciliation_federal_tax_id", sa.String(15)),
        sa.Column("remit_and_reconciliation_contact_name", sa.String(30)),
        sa.Column("remit_and_reconciliation_contact_title", sa.String(30)),
        sa.Column("remit_and_reconciliation_email_address", sa.String(50)),
        sa.Column("delete_date", sa.Date),
        sa.Column("raw_line", sa.Text),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "idx_remit_and_reconciliation_id", "dataq_remit_and_reconciliation",
        ["remit_and_reconciliation_id"], schema=_SCHEMA,
    )
    _grant_all("dataq_remit_and_reconciliation")


def downgrade() -> None:
    """Drop all spec-shaped tables. Does not restore Wave 29 stubs —
    that path is one-way."""
    for t in (
        "dataq_remit_and_reconciliation",
        "dataq_parent_organization",
        "dataq_payment_center",
        "dataq_relationship_demographic",
        "dataq_fwa_attestation",
        "dataq_change_of_ownership",
        "dataq_services_offered",
        "dataq_state_license",
        "dataq_eprescribing_information",
        "dataq_taxonomy_information",
        "dataq_medicaid_information",
        "dataq_provider_relationship",
        "dataq_master",
    ):
        op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.{t} CASCADE")
