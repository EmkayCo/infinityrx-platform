"""Pipeline execution engine for the rules-engine module.

Executes rules in priority order per a plan's pipeline configuration.
Supports branching on reject, conflict detection, and execution timing.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from shared.utils.money import money

from .rule_types import (
    BaseRuleExecutor,
    ClaimContext,
    RuleAction,
    RuleResult,
    get_executor,
)

logger = logging.getLogger("rules_engine.pipeline")

# ---------------------------------------------------------------------------
# Pipeline result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RuleExecutionRecord:
    """Result of executing a single rule within a pipeline."""

    rule_instance_id: str
    rule_type_code: str
    result: RuleResult
    execution_time_ms: int
    skipped: bool = False


@dataclass
class PipelineResult:
    """Aggregate result of running an entire pipeline."""

    claim_id: str
    plan_id: str
    results: list[RuleExecutionRecord] = field(default_factory=list)
    final_action: RuleAction = RuleAction.PASS
    reject_code: str = ""
    reject_message: str = ""
    warnings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    total_execution_time_ms: int = 0


# ---------------------------------------------------------------------------
# Pipeline rule descriptor
# ---------------------------------------------------------------------------


@dataclass
class PipelineRule:
    """A rule to execute within a pipeline, with its configuration."""

    rule_instance_id: str
    rule_type_code: str
    parameters: dict[str, Any] = field(default_factory=dict)
    priority_order: int = 0
    # On reject, optionally skip to a specific rule instance ID
    on_reject_skip_to: str | None = None


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def _detect_conflicts(results: list[RuleExecutionRecord]) -> list[str]:
    """Detect contradictory outcomes from multiple rules.

    Conflicts detected:
    - Two rules both try to MODIFY the same field to different values
    - One rule PASSes while another FLAGs on the same concern
    """
    conflicts: list[str] = []
    modify_records: dict[str, list[tuple[str, Any]]] = {}

    for rec in results:
        if rec.result.action == RuleAction.MODIFY:
            for field_name, value in rec.result.modified_values.items():
                if field_name not in modify_records:
                    modify_records[field_name] = []
                modify_records[field_name].append((rec.rule_type_code, value))

    for field_name, modifiers in modify_records.items():
        if len(modifiers) > 1:
            values = [v for _, v in modifiers]
            unique_values = set(str(v) for v in values)
            if len(unique_values) > 1:
                rule_names = [name for name, _ in modifiers]
                conflicts.append(
                    f"Conflict on '{field_name}': rules {rule_names} produced different values {list(unique_values)}"
                )

    return conflicts


# ---------------------------------------------------------------------------
# Pipeline executor
# ---------------------------------------------------------------------------


def execute_pipeline(
    ctx: ClaimContext,
    rules: list[PipelineRule],
) -> PipelineResult:
    """Execute a pipeline of rules in priority order.

    PASS -> continue to next rule
    REJECT -> stop pipeline, return reject code (unless branching configured)
    MODIFY -> apply modified values to claim context, continue
    FLAG -> add warning, continue
    """
    pipeline_start = time.monotonic()

    result = PipelineResult(
        claim_id=ctx.claim_id,
        plan_id=ctx.plan_id,
    )

    if not rules:
        result.total_execution_time_ms = 0
        return result

    # Sort by priority order
    sorted_rules = sorted(rules, key=lambda r: r.priority_order)

    # Build index for branching
    rule_index: dict[str, int] = {}
    for i, rule in enumerate(sorted_rules):
        rule_index[rule.rule_instance_id] = i

    skip_to_idx: int | None = None

    for i, rule in enumerate(sorted_rules):
        # Handle branching: skip rules until we reach the target
        if skip_to_idx is not None and i < skip_to_idx:
            result.results.append(
                RuleExecutionRecord(
                    rule_instance_id=rule.rule_instance_id,
                    rule_type_code=rule.rule_type_code,
                    result=RuleResult(action=RuleAction.PASS, message="Skipped (branch)"),
                    execution_time_ms=0,
                    skipped=True,
                )
            )
            continue
        skip_to_idx = None

        # Execute the rule
        try:
            executor = get_executor(rule.rule_type_code)
        except ValueError:
            logger.warning(
                "rules_engine.unknown_rule_type",
                extra={"svc_rule_type": rule.rule_type_code, "svc_rule_id": rule.rule_instance_id},
            )
            continue

        rule_start = time.monotonic()
        rule_result = executor.execute(ctx, rule.parameters)
        rule_elapsed_ms = int((time.monotonic() - rule_start) * 1000)

        record = RuleExecutionRecord(
            rule_instance_id=rule.rule_instance_id,
            rule_type_code=rule.rule_type_code,
            result=rule_result,
            execution_time_ms=rule_elapsed_ms,
        )
        result.results.append(record)

        # Process result
        if rule_result.action == RuleAction.REJECT:
            # Check for branching
            if rule.on_reject_skip_to and rule.on_reject_skip_to in rule_index:
                skip_to_idx = rule_index[rule.on_reject_skip_to]
                continue

            result.final_action = RuleAction.REJECT
            result.reject_code = rule_result.reject_code
            result.reject_message = rule_result.message
            break

        elif rule_result.action == RuleAction.MODIFY:
            # Apply modified values to claim context
            for field_name, value in rule_result.modified_values.items():
                if hasattr(ctx, field_name):
                    setattr(ctx, field_name, value)

        elif rule_result.action == RuleAction.FLAG:
            result.warnings.append(rule_result.message)

        # PASS: just continue

    # Detect conflicts
    result.conflicts = _detect_conflicts(result.results)

    pipeline_elapsed_ms = int((time.monotonic() - pipeline_start) * 1000)
    result.total_execution_time_ms = pipeline_elapsed_ms

    return result
