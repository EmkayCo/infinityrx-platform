"""paysync Wave 38 M4: export_templates + email_recipients + email_templates + email_deliveries.

Customizable per-tenant export templates with column definitions
(JSONB), filter expressions, sort orders, summary tab definitions,
and optional PHI tokenization via per-template HMAC seed.

Revision ID: 0007_export_templates
Revises: 0006_invoices
Create Date: 2026-04-25
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_export_templates"
down_revision: Union[str, None] = "0006_invoices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "paysync"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_TABLES = (
    "export_templates",
    "email_templates",
    "email_recipients",
    "email_deliveries",
)


def upgrade() -> None:
    # ── export_templates ──────────────────────────────────────────
    op.create_table(
        "export_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_name", sa.String(100), nullable=False),
        sa.Column("template_type", sa.String(40), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column(
            "column_definitions", postgresql.JSONB(),
            nullable=False, server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "filter_definitions", postgresql.JSONB(),
            nullable=False, server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "sort_definitions", postgresql.JSONB(),
            nullable=False, server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "include_summary_tab", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column(
            "summary_definitions", postgresql.JSONB(),
            nullable=False, server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "serialize_phi", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column("serialization_seed", sa.String(64), nullable=True),
        sa.Column(
            "applies_to_clients",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column(
            "is_default_for_type", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "template_name",
            name="uq_paysync_export_template_name",
        ),
        sa.CheckConstraint(
            "template_type IN ('invoice_backup_excel', "
            "'invoice_serialized_report', 'transaction_extract', "
            "'pharmacy_statement', 'cycle_summary', 'custom')",
            name="ck_paysync_export_template_type",
        ),
        sa.CheckConstraint(
            "format IN ('xlsx', 'csv', 'pipe_delimited')",
            name="ck_paysync_export_template_format",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(column_definitions) = 'array'",
            name="ck_paysync_export_columns_is_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(filter_definitions) = 'array'",
            name="ck_paysync_export_filters_is_array",
        ),
        sa.CheckConstraint(
            "NOT serialize_phi OR serialization_seed IS NOT NULL",
            name="ck_paysync_export_seed_required_when_phi",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_export_template_type", "export_templates",
        ["tenant_id", "template_type"], schema=_SCHEMA,
    )
    op.execute(
        f"CREATE UNIQUE INDEX uq_paysync_export_default_for_type "
        f"ON {_SCHEMA}.export_templates (tenant_id, template_type) "
        f"WHERE is_default_for_type = TRUE"
    )

    # ── email_templates ───────────────────────────────────────────
    op.create_table(
        "email_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_name", sa.String(100), nullable=False),
        sa.Column("applies_to_event", sa.String(64), nullable=False),
        sa.Column("subject_template", sa.Text(), nullable=False),
        sa.Column("body_text_template", sa.Text(), nullable=False),
        sa.Column("body_html_template", sa.Text(), nullable=True),
        sa.Column(
            "is_default_for_event", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "template_name",
            name="uq_paysync_email_template_name",
        ),
        sa.CheckConstraint(
            "applies_to_event IN ('invoice_finalized', 'invoice_sent', "
            "'invoice_reminder', 'payment_received', 'custom')",
            name="ck_paysync_email_template_event",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_email_template_event", "email_templates",
        ["tenant_id", "applies_to_event"], schema=_SCHEMA,
    )
    op.execute(
        f"CREATE UNIQUE INDEX uq_paysync_email_default_for_event "
        f"ON {_SCHEMA}.email_templates (tenant_id, applies_to_event) "
        f"WHERE is_default_for_event = TRUE"
    )

    # ── email_recipients ──────────────────────────────────────────
    op.create_table(
        "email_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bill_to_scope_type", sa.String(16), nullable=False),
        sa.Column("bill_to_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_address", sa.String(254), nullable=False),
        sa.Column("recipient_name", sa.String(120), nullable=True),
        sa.Column("recipient_role", sa.String(50), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column(
            "is_cc", sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "bill_to_scope_type IN ('client', 'program')",
            name="ck_paysync_email_rcpt_scope",
        ),
        sa.CheckConstraint(
            "email_address ~ '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'",
            name="ck_paysync_email_rcpt_format",
        ),
        sa.CheckConstraint(
            "termination_date IS NULL OR termination_date >= effective_from",
            name="ck_paysync_email_rcpt_period",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_email_rcpt_billto", "email_recipients",
        ["tenant_id", "bill_to_scope_type", "bill_to_id"], schema=_SCHEMA,
    )

    # ── email_deliveries (append-only) ───────────────────────────
    op.create_table(
        "email_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_SCHEMA}.invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column(
            "recipients_to", postgresql.ARRAY(sa.Text()),
            nullable=False, server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "recipients_cc", postgresql.ARRAY(sa.Text()),
            nullable=False, server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "attachment_paths", postgresql.ARRAY(sa.Text()),
            nullable=False, server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "attachment_sha256s", postgresql.ARRAY(sa.Text()),
            nullable=False, server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "delivery_status", sa.String(32),
            nullable=False, server_default=sa.text("'queued'"),
        ),
        sa.Column("delivery_provider_message_id", sa.String(255), nullable=True),
        sa.Column("delivery_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "delivery_status IN ('queued', 'sent', 'bounced', 'failed')",
            name="ck_paysync_email_delivery_status",
        ),
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_email_delivery_invoice", "email_deliveries",
        ["invoice_id"], schema=_SCHEMA,
    )
    op.create_index(
        "ix_paysync_email_delivery_tenant", "email_deliveries",
        ["tenant_id", "sent_at"], schema=_SCHEMA,
    )

    # RLS for all 4
    for table in _TABLES:
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {_SCHEMA}.{table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {_SCHEMA}.{table}
              FOR ALL
              TO ifx_dev_app, {_APP_ROLE}
              USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
              WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
            """
        )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
        + ", ".join(f"{_SCHEMA}.{t}" for t in _TABLES)
        + f" TO ifx_dev_app, {_APP_ROLE}, ifx_dev_admin, ifx_prod_admin"
    )


def downgrade() -> None:
    for t in reversed(_TABLES):
        op.drop_table(t, schema=_SCHEMA)
