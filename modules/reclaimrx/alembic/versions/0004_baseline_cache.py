"""reclaimrx baseline_cache — Wave 43 M2.

Backing store for ``BaselineProvider`` rolling-window aggregates:
mean / stddev / sample_count over a fixed window scoped to
(tenant_id, baseline_kind, scope_key, window_days). Computed on demand
the first time a rule asks; subsequent reads hit the cache until it
exceeds ``ttl_seconds``.

  - ``baseline_kind``  identifies the metric family (e.g.
                       ``pharmacy_ndc_dvnq_ratio``,
                       ``pharmacy_ndc_nq_distribution``,
                       ``pharmacy_volume``,
                       ``prescriber_volume``,
                       ``pharmacy_weekday_volume``).
  - ``scope_key``      stable canonical string identifying the scope
                       (e.g. ``npi=1234567890|ndc=12345678901``). The
                       provider builds these.
  - ``window_days``    rolling window size (typically 30 / 90 / 180).
  - ``data_source``    'live_db' | 'paysync_data' | 'csv_upload' — a
                       baseline computed against paysync history is
                       not interchangeable with one against
                       claim_transactions.

Stored values:

  - ``mean``           Decimal(20,8) for ratio/count baselines
  - ``stddev``         Decimal(20,8)
  - ``sample_count``   integer
  - ``extra``          JSONB for kind-specific summaries (e.g. the
                       weekday_volume distribution dict)
  - ``computed_at``    UTC timestamp the row was written
  - ``ttl_seconds``    operator-tunable per row (defaults 86400)

FORCE RLS — every cached aggregate is tenant-bound. Compose
(tenant_id, baseline_kind, scope_key, window_days, data_source) is
the natural key; partial UNIQUE keeps one active row per scope.

Revision ID: 0004_baseline_cache
Revises: 0003_detection_rule_framework
Create Date: 2026-04-27
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import os

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_baseline_cache"
down_revision: Union[str, None] = "0003_detection_rule_framework"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SCHEMA = "reclaimrx"
_APP_ROLE = os.environ.get("IFX_APP_ROLE", "ifx_dev_app")


def upgrade() -> None:
    op.create_table(
        "baseline_cache",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("baseline_kind", sa.String(64), nullable=False),
        sa.Column("scope_key", sa.String(255), nullable=False),
        sa.Column("window_days", sa.Integer, nullable=False),
        sa.Column("data_source", sa.String(32), nullable=False),
        sa.Column("mean", sa.Numeric(20, 8), nullable=True),
        sa.Column("stddev", sa.Numeric(20, 8), nullable=True),
        sa.Column("sample_count", sa.Integer, nullable=False),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "ttl_seconds",
            sa.Integer,
            nullable=False,
            server_default=sa.text("86400"),
        ),
        sa.CheckConstraint(
            "data_source IN ('live_db', 'paysync_data', 'csv_upload')",
            name="ck_baseline_cache_data_source",
        ),
        sa.CheckConstraint(
            "window_days > 0",
            name="ck_baseline_cache_window_positive",
        ),
        sa.CheckConstraint(
            "sample_count >= 0",
            name="ck_baseline_cache_sample_count_nonneg",
        ),
        sa.CheckConstraint(
            "ttl_seconds > 0",
            name="ck_baseline_cache_ttl_positive",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(extra) = 'object'",
            name="ck_baseline_cache_extra_is_object",
        ),
        schema=_SCHEMA,
    )

    op.create_index(
        "uq_baseline_cache_scope",
        "baseline_cache",
        ["tenant_id", "baseline_kind", "scope_key", "window_days", "data_source"],
        unique=True,
        schema=_SCHEMA,
    )
    op.create_index(
        "ix_baseline_cache_tenant_kind",
        "baseline_cache",
        ["tenant_id", "baseline_kind"],
        schema=_SCHEMA,
    )

    # Force RLS — even though ifx_dev_app/prod_app would bypass via
    # admin role, FORCE makes the tenant predicate authoritative
    # under the app role per the project pattern.
    op.execute(
        f"ALTER TABLE {_SCHEMA}.baseline_cache ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        f"ALTER TABLE {_SCHEMA}.baseline_cache FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {_SCHEMA}.baseline_cache
            USING (
                tenant_id = (
                    NULLIF(current_setting('app.current_tenant_id', true), '')
                )::uuid
            )
        """
    )

    # Tier app + admin grants follow the project pattern.
    for role in ("ifx_dev_app", _APP_ROLE, "ifx_dev_admin", "ifx_prod_admin"):
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
            f"{_SCHEMA}.baseline_cache TO {role}"
        )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {_SCHEMA}.baseline_cache")
    op.drop_index("ix_baseline_cache_tenant_kind", table_name="baseline_cache", schema=_SCHEMA)
    op.drop_index("uq_baseline_cache_scope", table_name="baseline_cache", schema=_SCHEMA)
    op.drop_table("baseline_cache", schema=_SCHEMA)
