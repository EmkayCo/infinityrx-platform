"""Baseline tables for prescriber_dir.

Creates the seven tables that 0001+ migrations and 0004 ALTER assume already
exist but no prior migration ever created. Each table maps 1:1 to a model in
``src/models/tables.py``.

Tables created (in dependency order):
  * prescriber_dir.prescribers                       (owned by Prescriber model)
  * prescriber_dir.taxonomy_codes                    (TaxonomyCode)
  * prescriber_dir.practice_affiliations             (PracticeAffiliation)
  * prescriber_dir.credential_alerts                 (CredentialAlert)
  * prescriber_dir.data_refresh_log                  (DataRefreshLog)
  * prescriber_dir.prescriber_pharmacy_relationships (PrescriberPharmacyRelationship)
  * prescriber_dir.state_prescribing_rules           (StatePrescribingRule)

Note: the prescribers table is created WITHOUT the four exclusion-tracking
columns (``is_excluded``, ``excluded_source``, ``exclusion_date``,
``exclusion_type``). Migration 0004 adds those on top via ALTER TABLE.

Revision ID: 0000_prescriber_baseline
Revises: None
Create Date: 2026-04-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0000_prescriber_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "prescriber_dir"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    # ── prescribers ───────────────────────────────────────────────────────
    op.create_table(
        "prescribers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("npi", sa.String(10), nullable=False),
        sa.Column("entity_type", sa.String(5), nullable=False, server_default="1"),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("middle_name", sa.String(100), nullable=True),
        sa.Column("prefix", sa.String(20), nullable=True),
        sa.Column("suffix", sa.String(20), nullable=True),
        sa.Column("credential", sa.String(100), nullable=True),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("organization_name", sa.String(500), nullable=True),
        sa.Column("organization_type", sa.String(100), nullable=True),
        sa.Column("authorized_official_name", sa.String(255), nullable=True),
        sa.Column("authorized_official_title", sa.String(100), nullable=True),
        sa.Column("primary_taxonomy_code", sa.String(20), nullable=True),
        sa.Column("primary_taxonomy_description", sa.String(255), nullable=True),
        sa.Column("primary_specialty", sa.String(255), nullable=True),
        sa.Column("taxonomy_codes", sa.JSON(), nullable=True),
        sa.Column("gender", sa.String(1), nullable=True),
        sa.Column("practice_address_line_1", sa.String(255), nullable=True),
        sa.Column("practice_address_line_2", sa.String(255), nullable=True),
        sa.Column("practice_city", sa.String(100), nullable=True),
        sa.Column("practice_state", sa.String(2), nullable=True),
        sa.Column("practice_zip", sa.String(10), nullable=True),
        sa.Column("practice_phone", sa.String(20), nullable=True),
        sa.Column("practice_fax", sa.String(20), nullable=True),
        sa.Column("practice_latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("practice_longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("mailing_address_line_1", sa.String(255), nullable=True),
        sa.Column("mailing_address_line_2", sa.String(255), nullable=True),
        sa.Column("mailing_city", sa.String(100), nullable=True),
        sa.Column("mailing_state", sa.String(2), nullable=True),
        sa.Column("mailing_zip", sa.String(10), nullable=True),
        sa.Column("additional_locations", sa.JSON(), nullable=True),
        sa.Column("dea_number", sa.String(9), nullable=True),
        sa.Column("dea_status", sa.String(50), nullable=True),
        sa.Column("dea_expiration_date", sa.Date(), nullable=True),
        sa.Column("dea_schedules", sa.JSON(), nullable=True),
        sa.Column("dea_state", sa.String(2), nullable=True),
        sa.Column("state_license_number", sa.String(50), nullable=True),
        sa.Column("state_license_state", sa.String(2), nullable=True),
        sa.Column("state_license_status", sa.String(50), nullable=True),
        sa.Column("state_license_expiry", sa.Date(), nullable=True),
        sa.Column("additional_state_licenses", sa.JSON(), nullable=True),
        sa.Column("pecos_enrolled", sa.Boolean(), nullable=True),
        sa.Column("medicare_participation", sa.Boolean(), nullable=True),
        sa.Column("medicare_opt_out", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("enumeration_date", sa.Date(), nullable=True),
        sa.Column("last_update_date", sa.Date(), nullable=True),
        sa.Column("deactivation_date", sa.Date(), nullable=True),
        sa.Column("deactivation_reason", sa.String(100), nullable=True),
        sa.Column("reactivation_date", sa.Date(), nullable=True),
        sa.Column("offers_telehealth", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("telehealth_states", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("nppes_last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dea_last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("license_last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manual_last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("npi", name="uq_prescriber_npi"),
        schema=_SCHEMA,
    )
    op.create_index("idx_prescriber_status", "prescribers", ["status"], schema=_SCHEMA)
    op.create_index("idx_prescriber_last_name_first", "prescribers", ["last_name", "first_name"], schema=_SCHEMA)
    op.create_index("idx_prescriber_dea", "prescribers", ["dea_number"], schema=_SCHEMA)
    op.create_index("idx_prescriber_taxonomy", "prescribers", ["primary_taxonomy_code"], schema=_SCHEMA)
    op.create_index("idx_prescriber_state", "prescribers", ["practice_state"], schema=_SCHEMA)
    op.create_index("idx_prescriber_specialty", "prescribers", ["primary_specialty"], schema=_SCHEMA)

    # ── taxonomy_codes ────────────────────────────────────────────────────
    op.create_table(
        "taxonomy_codes",
        sa.Column("code", sa.String(20), primary_key=True),
        sa.Column("classification", sa.String(255), nullable=False),
        sa.Column("specialization", sa.String(255), nullable=True),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("grouping", sa.String(255), nullable=True),
        sa.Column("simplified_specialty", sa.String(100), nullable=True),
        sa.Column("is_prescriber", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("is_pharmacy", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("is_hospital", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── practice_affiliations ─────────────────────────────────────────────
    op.create_table(
        "practice_affiliations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("prescriber_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("data_source", sa.String(50), nullable=False, server_default="nppes"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("idx_affil_prescriber", "practice_affiliations", ["prescriber_id"], schema=_SCHEMA)
    op.create_index("idx_affil_org", "practice_affiliations", ["organization_id"], schema=_SCHEMA)

    # ── credential_alerts ─────────────────────────────────────────────────
    op.create_table(
        "credential_alerts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("prescriber_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )
    op.create_index("idx_alert_prescriber", "credential_alerts", ["prescriber_id"], schema=_SCHEMA)
    op.create_index("idx_alert_type", "credential_alerts", ["alert_type"], schema=_SCHEMA)

    # ── data_refresh_log ──────────────────────────────────────────────────
    op.create_table(
        "data_refresh_log",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("data_source", sa.String(50), nullable=False),
        sa.Column("refresh_type", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_deactivated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=_SCHEMA,
    )

    # ── prescriber_pharmacy_relationships ─────────────────────────────────
    op.create_table(
        "prescriber_pharmacy_relationships",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("prescriber_npi", sa.String(10), nullable=False),
        sa.Column("pharmacy_npi", sa.String(10), nullable=False),
        sa.Column("period_month", sa.String(7), nullable=False),
        sa.Column("claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("prescriber_npi", "pharmacy_npi", "period_month", name="uq_ppr_npi_month"),
        schema=_SCHEMA,
    )
    op.create_index("idx_ppr_prescriber", "prescriber_pharmacy_relationships", ["prescriber_npi"], schema=_SCHEMA)
    op.create_index("idx_ppr_pharmacy", "prescriber_pharmacy_relationships", ["pharmacy_npi"], schema=_SCHEMA)

    # ── state_prescribing_rules ───────────────────────────────────────────
    op.create_table(
        "state_prescribing_rules",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("state_code", sa.String(2), nullable=False),
        sa.Column("provider_type", sa.String(20), nullable=False),
        sa.Column("can_prescribe_independently", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("requires_collaborative_agreement", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("controlled_substance_authority", sa.String(20), nullable=False, server_default="full"),
        sa.Column("schedule_restrictions", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("state_code", "provider_type", name="uq_state_provider_rule"),
        schema=_SCHEMA,
    )
    op.create_index("idx_state_rule_state", "state_prescribing_rules", ["state_code"], schema=_SCHEMA)


def downgrade() -> None:
    op.drop_index("idx_state_rule_state", table_name="state_prescribing_rules", schema=_SCHEMA)
    op.drop_table("state_prescribing_rules", schema=_SCHEMA)

    op.drop_index("idx_ppr_pharmacy", table_name="prescriber_pharmacy_relationships", schema=_SCHEMA)
    op.drop_index("idx_ppr_prescriber", table_name="prescriber_pharmacy_relationships", schema=_SCHEMA)
    op.drop_table("prescriber_pharmacy_relationships", schema=_SCHEMA)

    op.drop_table("data_refresh_log", schema=_SCHEMA)

    op.drop_index("idx_alert_type", table_name="credential_alerts", schema=_SCHEMA)
    op.drop_index("idx_alert_prescriber", table_name="credential_alerts", schema=_SCHEMA)
    op.drop_table("credential_alerts", schema=_SCHEMA)

    op.drop_index("idx_affil_org", table_name="practice_affiliations", schema=_SCHEMA)
    op.drop_index("idx_affil_prescriber", table_name="practice_affiliations", schema=_SCHEMA)
    op.drop_table("practice_affiliations", schema=_SCHEMA)

    op.drop_table("taxonomy_codes", schema=_SCHEMA)

    op.drop_index("idx_prescriber_specialty", table_name="prescribers", schema=_SCHEMA)
    op.drop_index("idx_prescriber_state", table_name="prescribers", schema=_SCHEMA)
    op.drop_index("idx_prescriber_taxonomy", table_name="prescribers", schema=_SCHEMA)
    op.drop_index("idx_prescriber_dea", table_name="prescribers", schema=_SCHEMA)
    op.drop_index("idx_prescriber_last_name_first", table_name="prescribers", schema=_SCHEMA)
    op.drop_index("idx_prescriber_status", table_name="prescribers", schema=_SCHEMA)
    op.drop_table("prescribers", schema=_SCHEMA)
