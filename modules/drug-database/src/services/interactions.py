"""Drug interaction checker — severity-ranked pairwise check.

Stateless pure functions — DB query is the caller's responsibility.
"""
from __future__ import annotations

from enum import IntEnum
from itertools import combinations
from typing import Any


class InteractionSeverity(IntEnum):
    MILD = 1
    MODERATE = 2
    SEVERE = 3
    CONTRAINDICATED = 4


class InteractionChecker:
    """Pairwise drug interaction checker."""

    @staticmethod
    def check_pairs(
        drug_identifiers: list[str],
        all_interactions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return interactions found among the given drug identifiers.

        Checks all pairs; results sorted by severity descending (contraindicated first).
        """
        if len(drug_identifiers) < 2:
            return []

        pairs = {
            frozenset(pair) for pair in combinations(drug_identifiers, 2)
        }

        found = [
            interaction
            for interaction in all_interactions
            if frozenset([
                interaction["drug_1_identifier"],
                interaction["drug_2_identifier"],
            ]) in pairs
        ]

        return InteractionChecker.sort_by_severity(found)

    @staticmethod
    def sort_by_severity(
        interactions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sort interactions by severity descending (contraindicated first)."""
        return sorted(
            interactions,
            key=lambda i: i["severity"],
            reverse=True,
        )
