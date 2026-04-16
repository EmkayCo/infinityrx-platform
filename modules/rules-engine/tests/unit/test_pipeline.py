"""Unit tests for pipeline execution engine.

Verifies:
- Multi-rule pipeline with all pass
- Pipeline stops on reject
- Pipeline modifies claim context pricing
- Pipeline flags add warnings
- Empty pipeline (zero rules)
- Branching on reject
- Conflict detection
"""

from __future__ import annotations

from decimal import Decimal

from src.services.pipeline import (
    PipelineResult,
    PipelineRule,
    execute_pipeline,
)
from src.services.rule_types import ClaimContext, RuleAction


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_ctx(**overrides) -> ClaimContext:
    defaults = {
        "claim_id": "CLM-001",
        "member_id": "MEM-001",
        "member_age": 45,
        "member_state": "TX",
        "ndc": "12345678901",
        "drug_name": "TestDrug",
        "drug_type": "generic",
        "quantity": Decimal("30"),
        "days_supply": 30,
        "pharmacy_npi": "1234567890",
        "pharmacy_type": "retail",
        "plan_id": "PLAN-001",
        "ingredient_cost": Decimal("100.00"),
    }
    defaults.update(overrides)
    return ClaimContext(**defaults)


# ---------------------------------------------------------------------------
# Pipeline with 3 rules, all pass
# ---------------------------------------------------------------------------


class TestPipelineAllPass:
    def test_three_rules_all_pass(self):
        ctx = _base_ctx(member_age=30)
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="age_rule",
                parameters={"min_age": 18, "max_age": 65},
                priority_order=1,
            ),
            PipelineRule(
                rule_instance_id="R2",
                rule_type_code="quantity_limit_rule",
                parameters={"max_quantity": "90"},
                priority_order=2,
            ),
            PipelineRule(
                rule_instance_id="R3",
                rule_type_code="age_rule",
                parameters={"min_age": 0, "max_age": 100},
                priority_order=3,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        assert result.final_action == RuleAction.PASS
        assert len(result.results) == 3
        for rec in result.results:
            assert rec.result.action == RuleAction.PASS
        assert result.reject_code == ""
        assert result.warnings == []

    def test_rules_sorted_by_priority(self):
        """Rules should execute in priority order regardless of list order."""
        ctx = _base_ctx(member_age=30)
        rules = [
            PipelineRule(
                rule_instance_id="R3",
                rule_type_code="age_rule",
                parameters={"min_age": 0, "max_age": 100},
                priority_order=3,
            ),
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="age_rule",
                parameters={"min_age": 18, "max_age": 65},
                priority_order=1,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        assert result.results[0].rule_instance_id == "R1"
        assert result.results[1].rule_instance_id == "R3"


# ---------------------------------------------------------------------------
# Pipeline with reject stops execution
# ---------------------------------------------------------------------------


class TestPipelineReject:
    def test_reject_stops_pipeline(self):
        ctx = _base_ctx(member_age=12)
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="age_rule",
                parameters={"min_age": 18},
                priority_order=1,
            ),
            PipelineRule(
                rule_instance_id="R2",
                rule_type_code="quantity_limit_rule",
                parameters={"max_quantity": "90"},
                priority_order=2,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        assert result.final_action == RuleAction.REJECT
        assert result.reject_code == "AGE_MIN"
        # Only 1 rule executed — pipeline stopped
        assert len(result.results) == 1
        assert result.results[0].rule_instance_id == "R1"

    def test_reject_code_and_message_propagated(self):
        ctx = _base_ctx(quantity=Decimal("200"))
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="quantity_limit_rule",
                parameters={"max_quantity": "90"},
                priority_order=1,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        assert result.final_action == RuleAction.REJECT
        assert result.reject_code == "QL_EXCEEDED"
        assert "200" in result.reject_message


# ---------------------------------------------------------------------------
# Pipeline with modify changes pricing
# ---------------------------------------------------------------------------


class TestPipelineModify:
    def test_modify_updates_claim_context(self):
        ctx = _base_ctx(quantity=Decimal("30"), ingredient_cost=Decimal("0.00"))
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="bill_cost_calculator",
                parameters={"pricing_source": "awp", "awp_unit_price": "5.00"},
                priority_order=1,
            ),
            PipelineRule(
                rule_instance_id="R2",
                rule_type_code="copay_rule",
                parameters={"copay_type": "percentage", "percentage": "20"},
                priority_order=2,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        assert result.final_action == RuleAction.PASS
        assert len(result.results) == 2

        # BillCostCalculator sets ingredient_cost = 30 * 5.00 = 150.00
        assert ctx.ingredient_cost == Decimal("150.00")
        # CopayRule uses updated ingredient_cost: 20% of 150 = 30.00
        assert ctx.copay == Decimal("30.00")

    def test_modify_result_contains_modified_values(self):
        ctx = _base_ctx(quantity=Decimal("10"))
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="bill_cost_calculator",
                parameters={"pricing_source": "awp", "awp_unit_price": "2.00"},
                priority_order=1,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        assert result.results[0].result.action == RuleAction.MODIFY
        assert result.results[0].result.modified_values["ingredient_cost"] == Decimal("20.00")


# ---------------------------------------------------------------------------
# Pipeline with flag adds warning
# ---------------------------------------------------------------------------


class TestPipelineFlag:
    def test_flag_adds_warning_and_continues(self):
        ctx = _base_ctx(
            member_state="CA",
            prescriber_daw="0",
        )
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="biosimilar_substitution_rule",
                parameters={
                    "alternative_ndc": "22222222222",
                    "interchangeable": True,
                    "state_law_overrides": {"CA": False},
                },
                priority_order=1,
            ),
            PipelineRule(
                rule_instance_id="R2",
                rule_type_code="age_rule",
                parameters={"min_age": 0, "max_age": 100},
                priority_order=2,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        # Pipeline continues past FLAG
        assert result.final_action == RuleAction.PASS
        assert len(result.results) == 2
        assert len(result.warnings) == 1
        assert "CA" in result.warnings[0]

    def test_multiple_flags_accumulate(self):
        ctx = _base_ctx(prescriber_daw="1")
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="biosimilar_substitution_rule",
                parameters={"alternative_ndc": "22222222222", "interchangeable": True},
                priority_order=1,
            ),
            PipelineRule(
                rule_instance_id="R2",
                rule_type_code="biosimilar_substitution_rule",
                parameters={"alternative_ndc": "33333333333", "interchangeable": True},
                priority_order=2,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        assert len(result.warnings) == 2


# ---------------------------------------------------------------------------
# Empty pipeline (zero rules)
# ---------------------------------------------------------------------------


class TestPipelineEmpty:
    def test_empty_pipeline_passes(self):
        ctx = _base_ctx()
        result = execute_pipeline(ctx, [])

        assert result.final_action == RuleAction.PASS
        assert result.results == []
        assert result.total_execution_time_ms == 0
        assert result.warnings == []
        assert result.conflicts == []


# ---------------------------------------------------------------------------
# Rule branching on reject
# ---------------------------------------------------------------------------


class TestPipelineBranching:
    def test_branch_on_reject_skips_to_target(self):
        ctx = _base_ctx(member_age=12)
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="age_rule",
                parameters={"min_age": 18},
                priority_order=1,
                on_reject_skip_to="R3",
            ),
            PipelineRule(
                rule_instance_id="R2",
                rule_type_code="quantity_limit_rule",
                parameters={"max_quantity": "90"},
                priority_order=2,
            ),
            PipelineRule(
                rule_instance_id="R3",
                rule_type_code="age_rule",
                parameters={"min_age": 0, "max_age": 100},
                priority_order=3,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        # R1 rejects but branches to R3
        # R2 is skipped
        # R3 passes (min_age=0, member_age=12)
        assert result.final_action == RuleAction.PASS
        assert len(result.results) == 3
        assert result.results[0].rule_instance_id == "R1"
        assert result.results[0].result.action == RuleAction.REJECT
        assert result.results[1].rule_instance_id == "R2"
        assert result.results[1].skipped is True
        assert result.results[2].rule_instance_id == "R3"
        assert result.results[2].result.action == RuleAction.PASS

    def test_branch_to_nonexistent_rule_still_rejects(self):
        ctx = _base_ctx(member_age=12)
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="age_rule",
                parameters={"min_age": 18},
                priority_order=1,
                on_reject_skip_to="NONEXISTENT",
            ),
        ]

        result = execute_pipeline(ctx, rules)

        assert result.final_action == RuleAction.REJECT
        assert result.reject_code == "AGE_MIN"


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


class TestPipelineConflictDetection:
    def test_detect_conflicting_modify_values(self):
        ctx = _base_ctx(quantity=Decimal("30"))
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="bill_cost_calculator",
                parameters={"pricing_source": "awp", "awp_unit_price": "5.00"},
                priority_order=1,
            ),
            PipelineRule(
                rule_instance_id="R2",
                rule_type_code="bill_cost_calculator",
                parameters={"pricing_source": "mac", "mac_unit_price": "3.00"},
                priority_order=2,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        # Both modify ingredient_cost to different values
        assert len(result.conflicts) == 1
        assert "ingredient_cost" in result.conflicts[0]

    def test_no_conflict_when_same_value(self):
        ctx = _base_ctx(quantity=Decimal("30"))
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="bill_cost_calculator",
                parameters={"pricing_source": "awp", "awp_unit_price": "5.00"},
                priority_order=1,
            ),
            PipelineRule(
                rule_instance_id="R2",
                rule_type_code="bill_cost_calculator",
                parameters={"pricing_source": "mac", "mac_unit_price": "5.00"},
                priority_order=2,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        # Both produce same ingredient_cost = 150.00
        assert result.conflicts == []


# ---------------------------------------------------------------------------
# Execution timing
# ---------------------------------------------------------------------------


class TestPipelineTiming:
    def test_execution_time_tracked(self):
        ctx = _base_ctx()
        rules = [
            PipelineRule(
                rule_instance_id="R1",
                rule_type_code="age_rule",
                parameters={"min_age": 0, "max_age": 100},
                priority_order=1,
            ),
        ]

        result = execute_pipeline(ctx, rules)

        assert result.total_execution_time_ms >= 0
        assert result.results[0].execution_time_ms >= 0

    def test_claim_and_plan_ids_in_result(self):
        ctx = _base_ctx(claim_id="CLM-999", plan_id="PLAN-999")
        result = execute_pipeline(ctx, [])

        assert result.claim_id == "CLM-999"
        assert result.plan_id == "PLAN-999"
