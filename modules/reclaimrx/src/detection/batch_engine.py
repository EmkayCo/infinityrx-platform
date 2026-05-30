"""Batch detection engine — applicability gate (Task 3.4).

gate_rules(db, run, available_columns) loads enabled DetectionRuleInstance rows
for run.tenant_id, joins to DetectionRuleType, and splits them into:

  - APPLICABLE: type.deferred_data_feed is False AND
    set(type.required_data_columns) <= available_columns.
  - NON-APPLICABLE: everything else (deferred feed, or missing required columns).

For each non-applicable instance, one run-wide DetectionRuleEvaluationLog row
is written with evaluation_result='skipped_inapplicable', source_table=NULL,
source_row_id=NULL, error_message=NULL (satisfying all four DB CHECKs from
migrations 0003 + 0005).

Disabled instances (enabled=False) are silently excluded — no skip row is
written for them because they are not part of the active rule set for this run.

CHECKs satisfied by skip rows:
  ck_reclaimrx_eval_log_result           — 'skipped_inapplicable' is in the enum
  ck_reclaimrx_eval_log_per_claim_columns— result='skipped_inapplicable' permits NULL source
  ck_reclaimrx_eval_log_error_iff_message— error_message=NULL and result!='error'
  ck_reclaimrx_eval_log_anomaly_id_iff_finding — anomaly_id=NULL and result!='finding_raised'
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.detection_run_models import (
    DetectionRuleEvaluationLog,
    DetectionRuleInstance,
    DetectionRuleType,
    DetectionRun,
)


def gate_rules(
    db: Session,
    run: DetectionRun,
    available_columns: set[str],
) -> list[DetectionRuleInstance]:
    """Return applicable instances; write run-wide skip rows for non-applicable ones.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.
    run:
        The DetectionRun whose tenant_id scopes the query.
    available_columns:
        Set of CSV column names present in this run's source file.

    Returns
    -------
    list[DetectionRuleInstance]
        The enabled instances whose rule type is not deferred AND whose
        required_data_columns are all present in available_columns.
    """
    # Load all enabled instances for this tenant, joined to their rule type.
    instances_with_types: list[tuple[DetectionRuleInstance, DetectionRuleType]] = (
        db.execute(
            select(DetectionRuleInstance, DetectionRuleType)
            .join(
                DetectionRuleType,
                DetectionRuleInstance.rule_type_code == DetectionRuleType.code,
            )
            .where(
                DetectionRuleInstance.tenant_id == run.tenant_id,
                DetectionRuleInstance.enabled.is_(True),
            )
        )
        .all()
    )

    applicable: list[DetectionRuleInstance] = []

    for instance, rule_type in instances_with_types:
        # An instance is applicable iff:
        #   1. Its type is not a deferred data feed, AND
        #   2. All required columns are present in available_columns.
        is_applicable = (
            not rule_type.deferred_data_feed
            and set(rule_type.required_data_columns) <= available_columns
        )

        if is_applicable:
            applicable.append(instance)
        else:
            # Write one run-wide skip row per non-applicable instance.
            # Satisfies all four DB CHECKs (see module docstring).
            skip_row = DetectionRuleEvaluationLog(
                tenant_id=run.tenant_id,
                rule_instance_id=instance.id,
                detection_run_id=run.id,
                source_table=None,       # NULL — permitted for skipped_inapplicable
                source_row_id=None,      # NULL — permitted for skipped_inapplicable
                evaluation_result="skipped_inapplicable",
                anomaly_id=None,         # NULL — only non-null for finding_raised
                error_message=None,      # NULL — only non-null for error result
                elapsed_ms=0,
            )
            db.add(skip_row)

    return applicable
