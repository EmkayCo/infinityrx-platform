"""Add NCPDP DataQ 13 tables.

Revision ID: 0001_ncpdp_tables
Revises:
Create Date: 2026-04-14

Creates the 13 NCPDP DataQ v3.1 reference tables in the pharmacy_dir schema.
All tables are global reference data (not tenant-scoped) per LESSON-011.

Downgrade drops all 13 tables.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_ncpdp_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "pharmacy_dir"


def upgrade() -> None:
    # Ensure schema exists (no-op if already there)
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # -----------------------------------------------------------------------
    # 1. ncpdp_pharmacies — master pharmacy record (mas.txt)
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
        # Identity
        sa.Column("legal_name", sa.String(60), nullable=True),
        sa.Column("dba_name", sa.String(60), nullable=True),
        sa.Column("store_number", sa.String(10), nullable=True),
        sa.Column("nabp_number", sa.String(10), nullable=True),
        sa.Column("pharmacy_type_code", sa.String(2), nullable=True),
        sa.Column("npi", sa.String(10), nullable=True),
        sa.Column("dea_number", sa.String(9), nullable=True),
        sa.Column("dea_expiration_date", sa.Date(), nullable=True),
        sa.Column("federal_tax_id", sa.String(9), nullable=True),
        # Physical address
        sa.Column("address_line_1", sa.String(60), nullable=True),
        sa.Column("address_line_2", sa.String(50), nullable=True),
        sa.Column("city", sa.String(30), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("zip5", sa.String(5), nullable=True),
        sa.Column("zip_plus4", sa.String(4), nullable=True),
        sa.Column("cross_street", sa.String(50), nullable=True),
        # Contact
        sa.Column("phone", sa.String(10), nullable=True),
        sa.Column("phone_extension", sa.String(5), nullable=True),
        sa.Column("fax", sa.String(10), nullable=True),
        sa.Column("email", sa.String(50), nullable=True),
        # Mailing address
        sa.Column("mailing_address_line_1", sa.String(60), nullable=True),
        sa.Column("mailing_address_line_2", sa.String(50), nullable=True),
        sa.Column("mailing_city", sa.String(30), nullable=True),
        sa.Column("mailing_state", sa.String(2), nullable=True),
        sa.Column("mailing_zip5", sa.String(5), nullable=True),
        sa.Column("mailing_zip_plus4", sa.String(4), nullable=True),
        # Authorized official
        sa.Column("auth_official_last_name", sa.String(20), nullable=True),
        sa.Column("auth_official_first_name", sa.String(20), nullable=True),
        sa.Column("auth_official_title", sa.String(30), nullable=True),
        sa.Column("auth_official_phone", sa.String(11), nullable=True),
        sa.Column("auth_official_email", sa.String(50), nullable=True),
        # Dates
        sa.Column("store_open_date", sa.Date(), nullable=True),
        sa.Column("store_close_date", sa.Date(), nullable=True),
        sa.Column("deactivation_date", sa.Date(), nullable=True),
        # Raw / unknown fields
        sa.Column("raw_field_127", sa.String(60), nullable=True),
        sa.Column("raw_field_483", sa.String(4), nullable=True),
        sa.Column("raw_field_489", sa.String(47), nullable=True),
        sa.Column("raw_field_834", sa.String(5), nullable=True),
        sa.Column("raw_field_839", sa.String(4), nullable=True),
        sa.Column("raw_field_843", sa.String(14), nullable=True),
        sa.Column("raw_field_876", sa.String(3), nullable=True),
        sa.Column("raw_field_896", sa.String(12), nullable=True),
        sa.Column("raw_field_908", sa.String(13), nullable=True),
        sa.Column("raw_field_929", sa.String(71), nullable=True),
        # Timestamps
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacies"),
        sa.UniqueConstraint("ncpdp_provider_id", name="uq_ncpdp_pharmacies_ncpdp_provider_id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_pharmacies_npi", "ncpdp_pharmacies", ["npi"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_pharmacies_state_city", "ncpdp_pharmacies", ["state", "city"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_pharmacies_zip5", "ncpdp_pharmacies", ["zip5"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_pharmacies_pharmacy_type", "ncpdp_pharmacies", ["pharmacy_type_code"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_pharmacies_last_updated", "ncpdp_pharmacies", ["last_updated_at"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 2. ncpdp_pharmacy_taxonomies (mas_tx.txt)
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_taxonomies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
        sa.Column("taxonomy_code", sa.String(10), nullable=True),
        sa.Column("primary_indicator", sa.String(1), nullable=True),
        sa.Column("raw_field_18", sa.String(1), nullable=True),
        sa.Column("deactivation_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_taxonomies"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_taxonomies_ncpdp_id", "ncpdp_pharmacy_taxonomies", ["ncpdp_provider_id"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_taxonomies_code", "ncpdp_pharmacy_taxonomies", ["taxonomy_code"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 3. ncpdp_pharmacy_state_licenses (mas_stl.txt)
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_state_licenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("license_number", sa.String(20), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("deactivation_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_state_licenses"),
        sa.UniqueConstraint("ncpdp_provider_id", "state", "license_number", name="uq_ncpdp_stl_ncpdp_state_lic"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_stl_ncpdp_id", "ncpdp_pharmacy_state_licenses", ["ncpdp_provider_id"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_stl_state", "ncpdp_pharmacy_state_licenses", ["state"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 4. ncpdp_pharmacy_services (mas_svc.txt)
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
        sa.Column("svc_retail", sa.Boolean(), nullable=True),
        sa.Column("svc_mail_order", sa.Boolean(), nullable=True),
        sa.Column("svc_specialty", sa.Boolean(), nullable=True),
        sa.Column("svc_long_term_care", sa.Boolean(), nullable=True),
        sa.Column("svc_home_infusion", sa.Boolean(), nullable=True),
        sa.Column("svc_compounding", sa.Boolean(), nullable=True),
        sa.Column("svc_clinic", sa.Boolean(), nullable=True),
        sa.Column("svc_nuclear", sa.Boolean(), nullable=True),
        sa.Column("svc_dme", sa.Boolean(), nullable=True),
        sa.Column("svc_home_health", sa.Boolean(), nullable=True),
        sa.Column("svc_hospice", sa.Boolean(), nullable=True),
        sa.Column("svc_hospital_outpatient", sa.Boolean(), nullable=True),
        sa.Column("svc_indian_health", sa.Boolean(), nullable=True),
        sa.Column("svc_correctional", sa.Boolean(), nullable=True),
        sa.Column("svc_military", sa.Boolean(), nullable=True),
        sa.Column("svc_340b", sa.Boolean(), nullable=True),
        sa.Column("svc_ambulatory_surgery", sa.Boolean(), nullable=True),
        sa.Column("svc_central_fill", sa.Boolean(), nullable=True),
        sa.Column("svc_dialysis", sa.Boolean(), nullable=True),
        sa.Column("svc_immunization", sa.Boolean(), nullable=True),
        sa.Column("svc_mtm", sa.Boolean(), nullable=True),
        sa.Column("svc_pharmacogenomics", sa.Boolean(), nullable=True),
        sa.Column("svc_specialty_infusion", sa.Boolean(), nullable=True),
        sa.Column("svc_other", sa.Boolean(), nullable=True),
        sa.Column("services_raw", sa.String(143), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_services"),
        sa.UniqueConstraint("ncpdp_provider_id", name="uq_ncpdp_pharmacy_services_ncpdp_provider_id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_svc_ncpdp_id", "ncpdp_pharmacy_services", ["ncpdp_provider_id"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_svc_retail", "ncpdp_pharmacy_services", ["svc_retail"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_svc_specialty", "ncpdp_pharmacy_services", ["svc_specialty"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_svc_mail_order", "ncpdp_pharmacy_services", ["svc_mail_order"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_svc_340b", "ncpdp_pharmacy_services", ["svc_340b"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 5. ncpdp_pharmacy_remittance (mas_rr.txt)
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_remittance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
        sa.Column("aba_routing_number", sa.String(9), nullable=True),
        sa.Column("bank_account_number", sa.String(8), nullable=True),
        sa.Column("electronic_payment_flag", sa.String(1), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("deactivation_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_remittance"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_rr_ncpdp_id", "ncpdp_pharmacy_remittance", ["ncpdp_provider_id"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 6. ncpdp_pharmacy_erx_capabilities (mas_erx.txt)
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_erx_capabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
        sa.Column("software_vendor_code", sa.String(2), nullable=True),
        sa.Column("erx_capable_flag", sa.String(1), nullable=True),
        sa.Column("transaction_types", sa.String(93), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("deactivation_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_erx_capabilities"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_erx_ncpdp_id", "ncpdp_pharmacy_erx_capabilities", ["ncpdp_provider_id"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_erx_capable", "ncpdp_pharmacy_erx_capabilities", ["erx_capable_flag"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 7. ncpdp_pharmacy_medicaid (mas_md.txt)
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_medicaid",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("medicaid_provider_id", sa.String(20), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("deactivation_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_medicaid"),
        sa.UniqueConstraint("ncpdp_provider_id", "state", name="uq_ncpdp_md_ncpdp_state"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_md_ncpdp_id", "ncpdp_pharmacy_medicaid", ["ncpdp_provider_id"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_md_state", "ncpdp_pharmacy_medicaid", ["state"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 8. ncpdp_pharmacy_fwa_actions (mas_fwa.txt)
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_fwa_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
        sa.Column("fwa_flag_1", sa.String(1), nullable=True),
        sa.Column("fwa_flag_2", sa.String(1), nullable=True),
        sa.Column("schema_version", sa.String(3), nullable=True),
        sa.Column("review_year", sa.Integer(), nullable=True),
        sa.Column("review_flag_1", sa.String(1), nullable=True),
        sa.Column("review_flag_2", sa.String(1), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("raw_remainder", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_fwa_actions"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_fwa_ncpdp_id", "ncpdp_pharmacy_fwa_actions", ["ncpdp_provider_id"], schema=_SCHEMA)
    op.create_index("ix_ncpdp_fwa_year", "ncpdp_pharmacy_fwa_actions", ["review_year"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 9. ncpdp_pharmacy_coordinates (mas_coo.txt)
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_coordinates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ncpdp_provider_id", sa.String(7), nullable=False),
        sa.Column("location_id", sa.String(7), nullable=True),
        sa.Column("geocode_start_date", sa.Date(), nullable=True),
        sa.Column("geocode_end_date", sa.Date(), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("geocode_match_type", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_coordinates"),
        sa.UniqueConstraint("ncpdp_provider_id", name="uq_ncpdp_pharmacy_coordinates_ncpdp_provider_id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_coo_ncpdp_id", "ncpdp_pharmacy_coordinates", ["ncpdp_provider_id"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 10. ncpdp_pharmacy_additional_info (mas_af.txt) — chain level
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_additional_info",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chain_entity_id", sa.String(5), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_additional_info"),
        sa.UniqueConstraint("chain_entity_id", name="uq_ncpdp_pharmacy_additional_info_chain_entity_id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_af_chain_id", "ncpdp_pharmacy_additional_info", ["chain_entity_id"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 11. ncpdp_pharmacy_patient_care (mas_pc.txt) — chain level
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_patient_care",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chain_entity_id", sa.String(6), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_patient_care"),
        sa.UniqueConstraint("chain_entity_id", name="uq_ncpdp_pharmacy_patient_care_chain_entity_id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_pc_chain_id", "ncpdp_pharmacy_patient_care", ["chain_entity_id"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 12. ncpdp_pharmacy_programs (mas_pr.txt) — chain level
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_programs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chain_entity_id", sa.String(6), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_programs"),
        sa.UniqueConstraint("chain_entity_id", name="uq_ncpdp_pharmacy_programs_chain_entity_id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_pr_chain_id", "ncpdp_pharmacy_programs", ["chain_entity_id"], schema=_SCHEMA)

    # -----------------------------------------------------------------------
    # 13. ncpdp_pharmacy_recertification (mas_rec.txt) — chain level
    # -----------------------------------------------------------------------
    op.create_table(
        "ncpdp_pharmacy_recertification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chain_entity_id", sa.String(6), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_ncpdp_pharmacy_recertification"),
        sa.UniqueConstraint("chain_entity_id", name="uq_ncpdp_pharmacy_recertification_chain_entity_id"),
        schema=_SCHEMA,
    )
    op.create_index("ix_ncpdp_rec_chain_id", "ncpdp_pharmacy_recertification", ["chain_entity_id"], schema=_SCHEMA)


def downgrade() -> None:
    for table_name in [
        "ncpdp_pharmacy_recertification",
        "ncpdp_pharmacy_programs",
        "ncpdp_pharmacy_patient_care",
        "ncpdp_pharmacy_additional_info",
        "ncpdp_pharmacy_coordinates",
        "ncpdp_pharmacy_fwa_actions",
        "ncpdp_pharmacy_medicaid",
        "ncpdp_pharmacy_erx_capabilities",
        "ncpdp_pharmacy_remittance",
        "ncpdp_pharmacy_services",
        "ncpdp_pharmacy_state_licenses",
        "ncpdp_pharmacy_taxonomies",
        "ncpdp_pharmacies",
    ]:
        op.drop_table(table_name, schema=_SCHEMA)
