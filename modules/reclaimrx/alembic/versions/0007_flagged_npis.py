"""reclaimrx NPI elevated-scrutiny flag table (Wave 44b M6).

Operator-managed list of NPIs that receive heightened detection sensitivity:
  - Lower score thresholds for ML rules
  - Mandatory cross-rule aggregation for any anomaly touching this NPI
  - Optional auto-create investigation trigger

Table: reclaimrx.flagged_npis
  - tenant-scoped, FORCE RLS
  - one active flag per (tenant, npi_type, npi_value)

Revision ID: 0007_flagged_npis
Revises: 0006_ml_detector_registry
Create Date: 2026-04-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_flagged_npis"
down_revision: Union[str, None] = "0006_ml_detector_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "reclaimrx"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")
_NPI_TYPES = "('pharmacy', 'prescriber')"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {_SCHEMA}")

    op.create_table(
        "flagged_npis",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("npi_type", sa.Text, nullable=False),
        sa.Column("npi_value", sa.Text, nullable=False),
        sa.Column("flag_reason", sa.Text, nullable=False),
        sa.Column("flagged_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("flagged_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score_threshold_override", sa.Numeric(5, 4), nullable=True),
        sa.Column("auto_create_investigation", sa.Boolean, nullable=False,
                  server_default="false"),
        sa.Column("metadata", postgresql.JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.CheckConstraint(
            f"npi_type IN {_NPI_TYPES}",
            name="ck_flagged_npis_npi_type",
        ),
        sa.CheckConstraint(
            "score_threshold_override IS NULL OR "
            "(score_threshold_override > 0 AND score_threshold_override <= 1)",
            name="ck_flagged_npis_score_threshold_valid",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object'",
            name="ck_flagged_npis_metadata_object",
        ),
        schema=_SCHEMA,
    )

    # One active flag per (tenant, npi_type, npi_value) — partial unique index
    op.execute(
        f"""
        CREATE UNIQUE INDEX uq_flagged_npis_active_per_npi
          ON {_SCHEMA}.flagged_npis (tenant_id, npi_type, npi_value)
          WHERE is_active = true
        """
    )

    # Fast lookup by tenant+npi_value
    op.create_index(
        "idx_flagged_npis_tenant_npi",
        "flagged_npis",
        ["tenant_id", "npi_value"],
        schema=_SCHEMA,
    )

    # Enable RLS
    op.execute(f"ALTER TABLE {_SCHEMA}.flagged_npis ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_SCHEMA}.flagged_npis FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY flagged_npis_tenant_isolation
          ON {_SCHEMA}.flagged_npis
          USING (
            tenant_id = NULLIF(
              current_setting('app.current_tenant_id', true), ''
            )::uuid
          )
        """
    )

    # Grants
    for role in ("ifx_dev_app", _APP_ROLE):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {_SCHEMA}.flagged_npis TO {role}")
    for role in ("ifx_dev_admin", "ifx_prod_admin"):
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {_SCHEMA}.flagged_npis TO {role}"
        )


def downgrade() -> None:
    op.execute(f"DROP TABLE IF EXISTS {_SCHEMA}.flagged_npis CASCADE")
