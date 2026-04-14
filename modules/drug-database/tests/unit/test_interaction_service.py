"""RED tests for drug interaction checker service."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


from src.services.interactions import InteractionChecker, InteractionSeverity


class TestInteractionCheckerSorting:
    def test_contraindicated_sorted_first(self) -> None:
        interactions = [
            _make_interaction("drug_a", "drug_b", InteractionSeverity.MODERATE),
            _make_interaction("drug_a", "drug_c", InteractionSeverity.CONTRAINDICATED),
            _make_interaction("drug_b", "drug_c", InteractionSeverity.SEVERE),
        ]
        ranked = InteractionChecker.sort_by_severity(interactions)
        assert ranked[0]["severity"] == InteractionSeverity.CONTRAINDICATED
        assert ranked[1]["severity"] == InteractionSeverity.SEVERE
        assert ranked[2]["severity"] == InteractionSeverity.MODERATE

    def test_single_drug_returns_empty(self) -> None:
        result = InteractionChecker.check_pairs(
            drug_identifiers=["drug_a"],
            all_interactions=[],
        )
        assert result == []

    def test_empty_drug_list_returns_empty(self) -> None:
        result = InteractionChecker.check_pairs(
            drug_identifiers=[],
            all_interactions=[],
        )
        assert result == []

    def test_no_interaction_for_unknown_pair(self) -> None:
        result = InteractionChecker.check_pairs(
            drug_identifiers=["drug_x", "drug_y"],
            all_interactions=[_make_interaction("drug_a", "drug_b", InteractionSeverity.SEVERE)],
        )
        assert result == []


class TestInteractionCheckerPairMatching:
    def test_detects_known_interaction(self) -> None:
        interactions = [_make_interaction("drug_a", "drug_b", InteractionSeverity.SEVERE)]
        result = InteractionChecker.check_pairs(
            drug_identifiers=["drug_a", "drug_b"],
            all_interactions=interactions,
        )
        assert len(result) == 1
        assert result[0]["severity"] == InteractionSeverity.SEVERE

    def test_matches_regardless_of_order(self) -> None:
        """Interaction (a, b) should match query (b, a)."""
        interactions = [_make_interaction("drug_a", "drug_b", InteractionSeverity.MODERATE)]
        result = InteractionChecker.check_pairs(
            drug_identifiers=["drug_b", "drug_a"],
            all_interactions=interactions,
        )
        assert len(result) == 1

    def test_three_drugs_checks_all_pairs(self) -> None:
        """3 drugs = 3 pairs: (a,b), (a,c), (b,c)."""
        interactions = [
            _make_interaction("drug_a", "drug_b", InteractionSeverity.MILD),
            _make_interaction("drug_b", "drug_c", InteractionSeverity.MODERATE),
        ]
        result = InteractionChecker.check_pairs(
            drug_identifiers=["drug_a", "drug_b", "drug_c"],
            all_interactions=interactions,
        )
        assert len(result) == 2

    def test_result_sorted_contraindicated_first(self) -> None:
        interactions = [
            _make_interaction("drug_a", "drug_b", InteractionSeverity.MILD),
            _make_interaction("drug_a", "drug_c", InteractionSeverity.CONTRAINDICATED),
        ]
        result = InteractionChecker.check_pairs(
            drug_identifiers=["drug_a", "drug_b", "drug_c"],
            all_interactions=interactions,
        )
        assert result[0]["severity"] == InteractionSeverity.CONTRAINDICATED


class TestInteractionSeverityOrder:
    def test_severity_enum_order(self) -> None:
        assert InteractionSeverity.CONTRAINDICATED > InteractionSeverity.SEVERE
        assert InteractionSeverity.SEVERE > InteractionSeverity.MODERATE
        assert InteractionSeverity.MODERATE > InteractionSeverity.MILD


def _make_interaction(d1: str, d2: str, severity: InteractionSeverity) -> dict:
    return {
        "drug_1_identifier": d1,
        "drug_2_identifier": d2,
        "severity": severity,
        "interaction_description": f"Test interaction {d1}-{d2}",
        "management_recommendation": "Monitor",
    }
