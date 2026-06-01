"""Drop stale eval-log anomaly_id <-> finding_raised CHECK constraint.

Phase-1c decoupled finding_raised eval-log rows from the bulk-inserted anomalies:
anomalies are written via execute_values (not session-tracked), so an eval-log row
written during the streaming pass cannot reference an anomaly id that does not exist
yet -- finding_raised rows therefore carry anomaly_id IS NULL by design. batch_engine
AND tests/detection/test_detection_passes.py both assert anomaly_id IS NULL for
finding_raised rows, but migration 0003's ck_reclaimrx_eval_log_anomaly_id_iff_finding
still required NOT NULL. Live Postgres ingest failed on a CheckViolation while SQLite
test fixtures (which strip CHECKs) passed. Drop the stale constraint.

revision: 0012_drop_evallog_anomaly_ck
down_revision: 0011_reclaimrx_v2_rule_params
"""
from alembic import op

revision = "0012_drop_evallog_anomaly_ck"
down_revision = "0011_reclaimrx_v2_rule_params"
branch_labels = None
depends_on = None

_SCHEMA = "reclaimrx"
_TABLE = "detection_rule_evaluation_log"
_CONSTRAINT = "ck_reclaimrx_eval_log_anomaly_id_iff_finding"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, _TABLE, schema=_SCHEMA, type_="check")


def downgrade() -> None:
    op.create_check_constraint(
        _CONSTRAINT,
        _TABLE,
        "(evaluation_result = 'finding_raised' AND anomaly_id IS NOT NULL) OR "
        "(evaluation_result <> 'finding_raised' AND anomaly_id IS NULL)",
        schema=_SCHEMA,
    )
