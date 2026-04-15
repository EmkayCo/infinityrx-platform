"""Tests for state prescribing authority rules service."""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest

from src.services.state_prescribing_rules import StatePrescribingRuleService


class TestStatePrescribingRuleService:
    @pytest.fixture
    def service(self):
        return StatePrescribingRuleService()

    def test_md_can_prescribe_schedule_2_in_illinois(self, service):
        assert service.can_prescribe_controlled("IL", "MD", "2") is True

    def test_np_full_authority_can_prescribe_schedule_2_in_illinois(self, service):
        assert service.can_prescribe_controlled("IL", "NP", "2") is True

    def test_np_limited_authority_cannot_prescribe_schedule_2_in_texas(self, service):
        assert service.can_prescribe_controlled("TX", "NP", "2") is False

    def test_np_limited_can_prescribe_schedule_4_in_texas(self, service):
        assert service.can_prescribe_controlled("TX", "NP", "4") is True

    def test_md_does_not_require_supervision(self, service):
        assert service.requires_supervision("IL", "MD") is False

    def test_pa_requires_supervision_in_illinois(self, service):
        assert service.requires_supervision("IL", "PA") is True

    def test_np_requires_supervision_in_georgia(self, service):
        assert service.requires_supervision("GA", "NP") is True

    def test_np_no_supervision_in_washington(self, service):
        assert service.requires_supervision("WA", "NP") is False

    def test_get_rule_returns_safe_default_for_unknown_state(self, service):
        # Wave 3C: unmodeled (state, provider) pairs MUST default to the
        # restricted/manual-review rule per DEA compliance — never grant
        # silent full authority.
        rule = service.get_rule("ZZ", "MD")
        assert rule.state_code == "DEFAULT"
        assert rule.can_prescribe_independently is False
        assert rule.requires_manual_review is True
        assert rule.controlled_substance_authority == "none"

    def test_list_rules_for_state(self, service):
        rules = service.list_rules_for_state("IL")
        assert len(rules) >= 3  # MD, NP, PA, DDS, OD, DPM...

    def test_all_rules_returns_entries(self, service):
        rules = service.all_rules()
        assert len(rules) > 20

    def test_lowercase_state_code_normalized(self, service):
        rule = service.get_rule("il", "MD")
        assert rule.state_code == "IL"

    def test_lowercase_provider_type_normalized(self, service):
        rule = service.get_rule("IL", "md")
        assert rule.provider_type == "MD"

    def test_can_prescribe_controlled_none_authority(self, service):
        from src.services.state_prescribing_rules import StateRule, _RULE_MAP
        # Insert a temporary rule with "none" authority to test that branch
        key = ("XX", "TEST")
        rule = StateRule(
            state_code="XX", provider_type="TEST",
            can_prescribe_independently=False,
            requires_collaborative_agreement=False,
            controlled_substance_authority="none",
            schedule_restrictions=None,
            notes=None,
        )
        _RULE_MAP[key] = rule
        try:
            assert service.can_prescribe_controlled("XX", "TEST", "2") is False
        finally:
            del _RULE_MAP[key]

    def test_default_unmodeled_state_denies_controlled_substance(self, service):
        # Wave 3C: unknown state/provider must NOT silently authorize CS
        # prescribing — adjudication must escalate via requires_manual_review.
        assert service.can_prescribe_controlled("ZZ", "UNKNOWN", "2") is False
        assert service.requires_manual_review("ZZ", "UNKNOWN") is True

    def test_modeled_states_do_not_require_manual_review(self, service):
        # Sanity: properly-modeled rules should NOT trigger manual review.
        assert service.requires_manual_review("CA", "MD") is False
        assert service.requires_manual_review("TX", "PA") is False
        assert service.requires_manual_review("PA", "NP") is False
