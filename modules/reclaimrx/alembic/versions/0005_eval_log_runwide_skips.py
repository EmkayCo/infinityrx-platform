"""reclaimrx eval log: allow run-wide rows for skipped_inapplicable.

Wave 43 ships skipped_inapplicable as a once-per-run log signal (not per
claim). Relax source_table/source_row_id to NULL and add a CHECK so per-claim
results still fail loudly without those.

Revision ID: 0005_eval_log_runwide_skips
Revises: 0004_baseline_cache
Create Date: 2026-04-27
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0005_eval_log_runwide_skips"
down_revision = "0004_baseline_cache"
branch_labels = None
depends_on = None

_TBL = "detection_rule_evaluation_log"
_CK = "ck_reclaimrx_eval_log_per_claim_columns"


def upgrade() -> None:
    op.alter_column(_TBL, "source_table", existing_type=sa.String(64),
                    nullable=True, schema="reclaimrx")
    op.alter_column(_TBL, "source_row_id", existing_type=postgresql.UUID(as_uuid=True),
                    nullable=True, schema="reclaimrx")
    op.execute(f"ALTER TABLE reclaimrx.{_TBL} DROP CONSTRAINT IF EXISTS {_CK}")
    op.create_check_constraint(
        _CK, _TBL,
        "(evaluation_result = 'skipped_inapplicable') OR "
        "(source_table IS NOT NULL AND source_row_id IS NOT NULL)",
        schema="reclaimrx",
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE reclaimrx.{_TBL} DROP CONSTRAINT IF EXISTS {_CK}")
    op.alter_column(_TBL, "source_row_id", existing_type=postgresql.UUID(as_uuid=True),
                    nullable=False, schema="reclaimrx")
    op.alter_column(_TBL, "source_table", existing_type=sa.String(64),
                    nullable=False, schema="reclaimrx")
