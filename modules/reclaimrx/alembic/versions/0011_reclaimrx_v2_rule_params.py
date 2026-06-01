"""Data migration: update detection_rule_instance.parameters for recalibrated B rules.

Sets all §12 H2 required keys on existing instances. Idempotent (JSON merge via
Postgres || operator — merging the same keys twice is a no-op).

revision: 0011_reclaimrx_v2_rule_params
down_revision: 0010_reclaimrx_v2_ref_grants
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0011_reclaimrx_v2_rule_params"
down_revision = "0010_reclaimrx_v2_ref_grants"
branch_labels = None
depends_on = None

_PARAMS = {
    "MFR-003": {
        "cohort_key": ["pharmacy_npi", "ndc"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "zscore",
        "z_threshold": "3.0",
        "tie_handling": "midrank",
        "min_group_size": 30,
        "min_entity_count": 1,
        "dollar_floor": "50.00",
        "rule_fire_rate_cap": "0.005",
        "field": "contracted_rate_deviation_pct",
        "operator": "gt",
        "threshold": 0.15,
    },
    "MFR-004": {
        "cohort_key": ["ndc"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "zscore",
        "z_threshold": "3.0",
        "tie_handling": "midrank",
        "min_group_size": 5,
        "min_entity_count": 5,
        "dollar_floor": "100.00",
        "rule_fire_rate_cap": "0.005",
        "field": "volume_vs_avg_ratio",
        "operator": "gt",
        "threshold": 2.0,
    },
    "HP-005": {
        "cohort_key": ["ndc"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "zscore",
        "z_threshold": "3.0",
        "tie_handling": "midrank",
        "min_group_size": 20,
        "min_entity_count": 20,
        "dollar_floor": "0.00",
        "rule_fire_rate_cap": "0.005",
        "field": "prescriber_volume_std_devs",
        "operator": "gt",
        "threshold": 3.0,
    },
    "HP-008": {
        "cohort_key": ["run"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "percentile_cont",
        "percentile_threshold": "0.99",
        "tie_handling": "midrank",
        "min_group_size": 100,
        "min_entity_count": 1,
        "dollar_floor": "500.00",
        "rule_fire_rate_cap": "0.005",
        "field": "cost_percentile",
        "operator": "gte",
        "threshold": 0.99,
    },
    "ALL-006": {
        "cohort_key": ["pharmacy_npi"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "zscore",
        "z_threshold": "3.0",
        "tie_handling": "midrank",
        "min_group_size": 20,
        "min_entity_count": 1,
        "dollar_floor": "0.00",
        "rule_fire_rate_cap": "0.005",
        "field": "weekend_volume_vs_weekday_ratio",
        "operator": "gt",
        "threshold": 2.0,
    },
    "ALL-005": {
        "cohort_key": ["patient_unique_hash", "ndc"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 180,
        "current_window": None,
        "statistic": "threshold",
        "refill_pct_threshold": "0.50",
        "repeat_offender_min_count": 2,
        "tie_handling": "midrank",
        "min_group_size": 2,
        "min_entity_count": 1,
        "dollar_floor": "0.00",
        "rule_fire_rate_cap": "0.005",
        "field": "refill_pct",
        "operator": "lt",
        "threshold": 0.75,
    },
}


def upgrade() -> None:
    conn = op.get_bind()
    for code, params in _PARAMS.items():
        conn.execute(
            sa.text(
                "UPDATE reclaimrx.detection_rule_instances "
                "SET parameters = parameters || CAST(:p AS jsonb) "
                "WHERE rule_type_code = :code"
            ),
            {"code": code, "p": json.dumps(params)},
        )


def downgrade() -> None:
    # Parameter rollback is not practical; if needed, re-run upgrade with old param values
    pass

