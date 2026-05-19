"""Constants for the ReclaimRx module."""
from __future__ import annotations

from decimal import Decimal
from typing import Any


# ── State machine (spec §5.5.1) ────────────────────────────────────────────

VALID_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "open": ["in_progress", "pending_review", "escalated"],
    "in_progress": [
        "pending_review",
        "closed_confirmed",
        "closed_false_positive",
        "closed_no_action",
        "escalated",
    ],
    "pending_review": [
        "in_progress",
        "closed_confirmed",
        "closed_false_positive",
        "closed_no_action",
        "escalated",
    ],
    "escalated": [
        "in_progress",
        "closed_confirmed",
        "closed_false_positive",
        "closed_no_action",
    ],
    "closed_confirmed": ["open"],
    "closed_false_positive": ["open"],
    "closed_no_action": ["open"],
}

TERMINAL_STATES: frozenset[str] = frozenset({
    "closed_confirmed",
    "closed_false_positive",
    "closed_no_action",
})

_ADMIN_ONLY_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("escalated", "in_progress"),
    ("escalated", "closed_confirmed"),
    ("escalated", "closed_false_positive"),
    ("escalated", "closed_no_action"),
    ("closed_confirmed", "open"),
    ("closed_false_positive", "open"),
    ("closed_no_action", "open"),
})

_OUTCOME_LABEL_FOR_STATE: dict[str, str] = {
    "closed_confirmed": "confirmed",
    "closed_false_positive": "false_positive",
    "closed_no_action": "no_action",
}

TRANSITION_REQUIRED_FIELDS: dict[tuple[str, str], frozenset[str]] = {
    ("open", "closed_confirmed"): frozenset({"reason", "outcome_label", "recovered_amount"}),
    ("in_progress", "closed_confirmed"): frozenset({"reason", "outcome_label", "recovered_amount"}),
    ("pending_review", "closed_confirmed"): frozenset({"reason", "outcome_label", "recovered_amount"}),
    ("escalated", "closed_confirmed"): frozenset({"reason", "outcome_label", "recovered_amount"}),
    ("open", "closed_false_positive"): frozenset({"reason", "outcome_label"}),
    ("in_progress", "closed_false_positive"): frozenset({"reason", "outcome_label"}),
    ("pending_review", "closed_false_positive"): frozenset({"reason", "outcome_label"}),
    ("escalated", "closed_false_positive"): frozenset({"reason", "outcome_label"}),
    ("open", "closed_no_action"): frozenset({"reason", "outcome_label"}),
    ("in_progress", "closed_no_action"): frozenset({"reason", "outcome_label"}),
    ("pending_review", "closed_no_action"): frozenset({"reason", "outcome_label"}),
    ("escalated", "closed_no_action"): frozenset({"reason", "outcome_label"}),
    ("closed_confirmed", "open"): frozenset({"reason"}),
    ("closed_false_positive", "open"): frozenset({"reason"}),
    ("closed_no_action", "open"): frozenset({"reason"}),
}


class InvalidTransitionError(ValueError):
    def __init__(self, code: str, message: str, *, allowed_next: list[str] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.allowed_next: list[str] = allowed_next or []


def validate_transition(
    from_state: str,
    to_state: str,
    *,
    role: str,
    fields: dict[str, Any],
) -> None:
    allowed: list[str] = VALID_STATUS_TRANSITIONS.get(from_state, [])
    if from_state not in VALID_STATUS_TRANSITIONS:
        raise InvalidTransitionError(
            "INVALID_TRANSITION",
            f"Unknown state {repr(from_state)}.",
            allowed_next=[],
        )
    if to_state not in allowed:
        raise InvalidTransitionError(
            "INVALID_TRANSITION",
            f"Transition from {repr(from_state)} to {repr(to_state)} is not permitted.",
            allowed_next=allowed,
        )
    if (from_state, to_state) in _ADMIN_ONLY_TRANSITIONS and role != "reclaimrx.admin":
        raise InvalidTransitionError(
            "INSUFFICIENT_ROLE",
            f"Transition from {repr(from_state)} to {repr(to_state)} requires reclaimrx.admin role.",
            allowed_next=allowed,
        )
    required = TRANSITION_REQUIRED_FIELDS.get((from_state, to_state), frozenset({"reason"}))
    for field in required:
        if field == "recovered_amount":
            if not isinstance(fields.get("recovered_amount"), Decimal):
                raise InvalidTransitionError(
                    "MISSING_REQUIRED_FIELD",
                    "Field recovered_amount (Decimal) is required for closed_confirmed.",
                    allowed_next=allowed,
                )
            continue
        if not fields.get(field):
            raise InvalidTransitionError(
                "MISSING_REQUIRED_FIELD",
                f"Field {repr(field)} is required for transition {repr(from_state)} -> {repr(to_state)}.",
                allowed_next=allowed,
            )
    if to_state in _OUTCOME_LABEL_FOR_STATE:
        _check_outcome_label(to_state, fields, allowed)


def _check_outcome_label(to_state: str, fields: dict[str, Any], allowed: list[str]) -> None:
    expected = _OUTCOME_LABEL_FOR_STATE.get(to_state)
    if expected is None:
        return
    provided = fields.get("outcome_label")
    if provided is not None and provided != expected:
        raise InvalidTransitionError(
            "OUTCOME_LABEL_MISMATCH",
            f"outcome_label {repr(provided)} does not match target state {repr(to_state)} (expected {repr(expected)}).",
            allowed_next=allowed,
        )


RISK_LOW_MAX = 25
RISK_ELEVATED_MAX = 50
RISK_HIGH_MAX = 75


def risk_score_to_severity(score: int) -> str:
    if score > RISK_HIGH_MAX:
        return "critical"
    if score > RISK_ELEVATED_MAX:
        return "high"
    if score > RISK_LOW_MAX:
        return "medium"
    return "low"


KNOWN_ACCUMULATOR_BINS: set[str] = {
    "610014",
    "600428",
    "004336",
}
