"""Unit tests for claims routing engine — 100% branch coverage required."""

from __future__ import annotations

import uuid
from decimal import Decimal

from src.services.routing import (
    RoutingRuleData,
    classify_claim,
    matches_rule,
)
from src.utils.constants import (
    ROUTE_DIRECT_ACH,
    ROUTE_ECHO,
    ROUTE_EXCLUDED,
    ROUTE_STATEMENT,
)

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLIENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROGRAM = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
VENDOR = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _rule(
    payment_route: str = ROUTE_ECHO,
    priority: int = 100,
    match_nrid: str | None = None,
    match_program_id: uuid.UUID | None = None,
    match_pharmacy_npi: str | None = None,
    match_claim_type: str | None = None,
    match_client_id: uuid.UUID | None = None,
    payment_vendor_config_id: uuid.UUID | None = None,
    payment_schedule: str | None = None,
) -> RoutingRuleData:
    return RoutingRuleData(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        name="Test Rule",
        priority=priority,
        payment_route=payment_route,
        payment_vendor_config_id=payment_vendor_config_id,
        payment_schedule=payment_schedule,
        match_nrid=match_nrid,
        match_program_id=match_program_id,
        match_pharmacy_npi=match_pharmacy_npi,
        match_claim_type=match_claim_type,
        match_client_id=match_client_id,
    )


def _claim(
    nrid: str | None = "NRID001",
    program_id: uuid.UUID | None = None,
    pharmacy_npi: str = "1234567890",
    claim_type: str = "new",
    client_id: uuid.UUID | None = None,
) -> dict:
    return {
        "id": uuid.uuid4(),
        "tenant_id": TENANT,
        "auth_number": "AUTH001",
        "net_amount": Decimal("100.00"),
        "network_reimbursement_id": nrid,
        "program_id": program_id or PROGRAM,
        "pharmacy_npi": pharmacy_npi,
        "claim_type": claim_type,
        "client_id": client_id or CLIENT,
    }


class TestMatchesRule:
    def test_wildcard_rule_matches_any_claim(self) -> None:
        rule = _rule()
        claim = _claim()
        assert matches_rule(rule, claim) is True

    def test_nrid_match(self) -> None:
        rule = _rule(match_nrid="NRID001")
        claim = _claim(nrid="NRID001")
        assert matches_rule(rule, claim) is True

    def test_nrid_no_match(self) -> None:
        rule = _rule(match_nrid="NRID999")
        claim = _claim(nrid="NRID001")
        assert matches_rule(rule, claim) is False

    def test_program_match(self) -> None:
        rule = _rule(match_program_id=PROGRAM)
        claim = _claim(program_id=PROGRAM)
        assert matches_rule(rule, claim) is True

    def test_program_no_match(self) -> None:
        other_program = uuid.uuid4()
        rule = _rule(match_program_id=other_program)
        claim = _claim(program_id=PROGRAM)
        assert matches_rule(rule, claim) is False

    def test_pharmacy_npi_match(self) -> None:
        rule = _rule(match_pharmacy_npi="1234567890")
        claim = _claim(pharmacy_npi="1234567890")
        assert matches_rule(rule, claim) is True

    def test_pharmacy_npi_no_match(self) -> None:
        rule = _rule(match_pharmacy_npi="9999999999")
        claim = _claim(pharmacy_npi="1234567890")
        assert matches_rule(rule, claim) is False

    def test_claim_type_match(self) -> None:
        rule = _rule(match_claim_type="reversal")
        claim = _claim(claim_type="reversal")
        assert matches_rule(rule, claim) is True

    def test_claim_type_no_match(self) -> None:
        rule = _rule(match_claim_type="reversal")
        claim = _claim(claim_type="new")
        assert matches_rule(rule, claim) is False

    def test_client_match(self) -> None:
        rule = _rule(match_client_id=CLIENT)
        claim = _claim(client_id=CLIENT)
        assert matches_rule(rule, claim) is True

    def test_client_no_match(self) -> None:
        other_client = uuid.uuid4()
        rule = _rule(match_client_id=other_client)
        claim = _claim(client_id=CLIENT)
        assert matches_rule(rule, claim) is False

    def test_multi_criteria_all_match(self) -> None:
        rule = _rule(match_nrid="NRID001", match_claim_type="new", match_pharmacy_npi="1234567890")
        claim = _claim(nrid="NRID001", claim_type="new", pharmacy_npi="1234567890")
        assert matches_rule(rule, claim) is True

    def test_multi_criteria_partial_match_fails(self) -> None:
        rule = _rule(match_nrid="NRID001", match_claim_type="reversal")
        claim = _claim(nrid="NRID001", claim_type="new")
        assert matches_rule(rule, claim) is False

    def test_nrid_null_in_claim_no_match(self) -> None:
        rule = _rule(match_nrid="NRID001")
        claim = _claim(nrid=None)
        assert matches_rule(rule, claim) is False


class TestClassifyClaim:
    def test_first_matching_rule_wins(self) -> None:
        rules = [
            _rule(payment_route=ROUTE_ECHO, priority=10),
            _rule(payment_route=ROUTE_DIRECT_ACH, priority=20),
        ]
        claim = _claim()
        result = classify_claim(claim, rules)
        assert result.payment_route == ROUTE_ECHO

    def test_lower_priority_number_is_higher_priority(self) -> None:
        # priority=10 (wildcard) sorts before priority=200 — first match wins
        rules = [
            _rule(payment_route=ROUTE_DIRECT_ACH, priority=200, match_nrid="NRID001"),
            _rule(payment_route=ROUTE_ECHO, priority=10),
        ]
        claim = _claim(nrid="NRID001")
        result = classify_claim(claim, rules)
        # ECHO wins because priority=10 evaluates first (lower = higher priority)
        assert result.payment_route == ROUTE_ECHO

    def test_higher_priority_specific_rule_wins_when_wildcard_doesnt_match(self) -> None:
        # If wildcard is priority 10 but restricted to a different NRID, specific rule wins
        rules = [
            _rule(payment_route=ROUTE_ECHO, priority=10, match_nrid="NRID_OTHER"),
            _rule(payment_route=ROUTE_DIRECT_ACH, priority=200),
        ]
        claim = _claim(nrid="NRID001")
        result = classify_claim(claim, rules)
        assert result.payment_route == ROUTE_DIRECT_ACH

    def test_no_matching_rule_returns_unclassified(self) -> None:
        rules = [_rule(match_nrid="NRID999")]
        claim = _claim(nrid="NRID001")
        result = classify_claim(claim, rules)
        assert result.payment_route is None
        assert result.classified is False

    def test_excluded_route_sets_is_excluded(self) -> None:
        rules = [_rule(payment_route=ROUTE_EXCLUDED)]
        claim = _claim()
        result = classify_claim(claim, rules)
        assert result.is_excluded is True
        assert result.classified is True

    def test_statement_route_sets_is_statement(self) -> None:
        rules = [_rule(payment_route=ROUTE_STATEMENT)]
        claim = _claim()
        result = classify_claim(claim, rules)
        assert result.is_statement is True
        assert result.classified is True

    def test_vendor_and_schedule_carried_forward(self) -> None:
        rules = [
            _rule(
                payment_route=ROUTE_ECHO,
                payment_vendor_config_id=VENDOR,
                payment_schedule="daily",
            )
        ]
        claim = _claim()
        result = classify_claim(claim, rules)
        assert result.payment_vendor_config_id == VENDOR
        assert result.payment_schedule == "daily"

    def test_empty_rules_returns_unclassified(self) -> None:
        result = classify_claim(_claim(), [])
        assert result.classified is False

    def test_classified_result_has_correct_status(self) -> None:
        rules = [_rule(payment_route=ROUTE_ECHO)]
        claim = _claim()
        result = classify_claim(claim, rules)
        assert result.classified is True
        assert result.payment_route == ROUTE_ECHO
