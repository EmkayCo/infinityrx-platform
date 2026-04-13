"""Routing engine: classifies claims to payment route via priority-ordered rules.

First matching rule wins. Rules are sorted by priority (lower number = higher priority).
Null criterion fields match everything.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from src.utils.constants import ROUTE_EXCLUDED, ROUTE_STATEMENT


@dataclass
class RoutingRuleData:
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    priority: int
    payment_route: str
    payment_vendor_config_id: uuid.UUID | None = None
    payment_schedule: str | None = None
    match_nrid: str | None = None
    match_program_id: uuid.UUID | None = None
    match_pharmacy_npi: str | None = None
    match_claim_type: str | None = None
    match_client_id: uuid.UUID | None = None


@dataclass
class ClassifiedClaim:
    claim_id: uuid.UUID
    classified: bool
    payment_route: str | None
    payment_vendor_config_id: uuid.UUID | None
    payment_schedule: str | None
    matched_rule_id: uuid.UUID | None
    is_excluded: bool = False
    is_statement: bool = False


def matches_rule(rule: RoutingRuleData, claim: dict[str, Any]) -> bool:
    """Return True if the claim satisfies all non-null criteria on the rule."""
    if rule.match_nrid is not None:
        if claim.get("network_reimbursement_id") != rule.match_nrid:
            return False
    if rule.match_program_id is not None:
        if claim.get("program_id") != rule.match_program_id:
            return False
    if rule.match_pharmacy_npi is not None:
        if claim.get("pharmacy_npi") != rule.match_pharmacy_npi:
            return False
    if rule.match_claim_type is not None:
        if claim.get("claim_type") != rule.match_claim_type:
            return False
    if rule.match_client_id is not None:
        if claim.get("client_id") != rule.match_client_id:
            return False
    return True


def classify_claim(
    claim: dict[str, Any],
    rules: list[RoutingRuleData],
) -> ClassifiedClaim:
    """Evaluate rules in priority order. First match sets the route.

    Returns an unclassified result if no rule matches.
    """
    sorted_rules = sorted(rules, key=lambda r: r.priority)
    claim_id: uuid.UUID = claim["id"]

    for rule in sorted_rules:
        if matches_rule(rule, claim):
            is_excluded = rule.payment_route == ROUTE_EXCLUDED
            is_statement = rule.payment_route == ROUTE_STATEMENT
            return ClassifiedClaim(
                claim_id=claim_id,
                classified=True,
                payment_route=rule.payment_route,
                payment_vendor_config_id=rule.payment_vendor_config_id,
                payment_schedule=rule.payment_schedule,
                matched_rule_id=rule.id,
                is_excluded=is_excluded,
                is_statement=is_statement,
            )

    return ClassifiedClaim(
        claim_id=claim_id,
        classified=False,
        payment_route=None,
        payment_vendor_config_id=None,
        payment_schedule=None,
        matched_rule_id=None,
    )
