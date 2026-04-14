"""OFAC SDN screening service.

Screens pay-to entities against the SDN list before any payment submission.
In production: integrates with OFAC API or local SDN file refresh.
Dev/test: in-memory list with configurable matches.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("payment.ofac")


@dataclass
class OfacResult:
    entity_id: str
    is_blocked: bool
    match_name: str | None = None
    match_score: int | None = None
    sdn_id: str | None = None


class OfacScreeningService:
    """Screens entities against SDN list.

    Production: integrates with OFAC Data Services API.
    Dev/test: uses injected blocked-entity set.
    """

    def __init__(self, blocked_entity_ids: set[str] | None = None) -> None:
        self._blocked: set[str] = blocked_entity_ids or set()

    def screen(self, entity_id: str, entity_name: str = "") -> OfacResult:
        """Screen a single entity. Returns OfacResult with is_blocked flag."""
        if entity_id in self._blocked:
            logger.warning(
                "OFAC hit",
                extra={"entity_id": entity_id, "entity_name": entity_name},
            )
            return OfacResult(
                entity_id=entity_id,
                is_blocked=True,
                match_name=entity_name,
                match_score=100,
                sdn_id="SDN-TEST",
            )
        return OfacResult(entity_id=entity_id, is_blocked=False)

    def screen_batch(
        self, entities: list[tuple[str, str]]
    ) -> list[OfacResult]:
        """Screen multiple (entity_id, entity_name) pairs."""
        return [self.screen(eid, name) for eid, name in entities]

    def add_blocked(self, entity_id: str) -> None:
        self._blocked.add(entity_id)

    def remove_blocked(self, entity_id: str) -> None:
        self._blocked.discard(entity_id)
