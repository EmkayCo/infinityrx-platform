"""Unit tests for OFAC screening service — security path, 100% coverage."""
from __future__ import annotations


from src.services.ofac_screening import OfacScreeningService


class TestOfacScreeningService:
    def test_clear_entity_not_blocked(self):
        svc = OfacScreeningService()
        result = svc.screen("ENT-001", "Clean Pharmacy")
        assert result.is_blocked is False
        assert result.entity_id == "ENT-001"

    def test_blocked_entity_returns_blocked(self):
        svc = OfacScreeningService(blocked_entity_ids={"ENT-BAD"})
        result = svc.screen("ENT-BAD", "Bad Actor")
        assert result.is_blocked is True
        assert result.match_score == 100

    def test_batch_screen_all_clear(self):
        svc = OfacScreeningService()
        results = svc.screen_batch([("E1", "Pharm A"), ("E2", "Pharm B")])
        assert all(not r.is_blocked for r in results)

    def test_batch_screen_one_blocked(self):
        svc = OfacScreeningService(blocked_entity_ids={"E2"})
        results = svc.screen_batch([("E1", "Clear"), ("E2", "Blocked")])
        assert not results[0].is_blocked
        assert results[1].is_blocked

    def test_add_blocked(self):
        svc = OfacScreeningService()
        svc.add_blocked("NEW-BAD")
        result = svc.screen("NEW-BAD", "Bad")
        assert result.is_blocked is True

    def test_remove_blocked(self):
        svc = OfacScreeningService(blocked_entity_ids={"TO-REMOVE"})
        svc.remove_blocked("TO-REMOVE")
        result = svc.screen("TO-REMOVE", "Now Clear")
        assert result.is_blocked is False

    def test_empty_blocked_set_default(self):
        svc = OfacScreeningService()
        result = svc.screen("ANY", "Any Pharmacy")
        assert result.is_blocked is False

    def test_blocked_result_has_sdn_id(self):
        svc = OfacScreeningService(blocked_entity_ids={"X"})
        result = svc.screen("X", "X Org")
        assert result.sdn_id is not None
