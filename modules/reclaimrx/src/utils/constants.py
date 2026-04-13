"""Constants for the ReclaimRx module."""
from __future__ import annotations

# Investigation status transitions (state machine)
VALID_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "open": ["in_progress", "closed_no_action"],
    "in_progress": ["pending_response", "escalated", "recovery_in_progress", "closed_no_action", "closed_referred"],
    "pending_response": ["in_progress", "escalated", "recovery_in_progress", "closed_no_action"],
    "escalated": ["in_progress", "recovery_in_progress", "closed_referred"],
    "recovery_in_progress": ["recovered", "closed_no_action", "closed_referred"],
    "recovered": ["closed_no_action"],
    "closed_no_action": [],
    "closed_referred": [],
}

# Risk score thresholds
RISK_LOW_MAX = 25
RISK_ELEVATED_MAX = 50
RISK_HIGH_MAX = 75

# Severity levels by risk score
def risk_score_to_severity(score: int) -> str:
    if score > RISK_HIGH_MAX:
        return "critical"
    if score > RISK_ELEVATED_MAX:
        return "high"
    if score > RISK_LOW_MAX:
        return "medium"
    return "low"

# Known accumulator/maximizer plan BINs (sample set — production loads from database)
KNOWN_ACCUMULATOR_BINS: set[str] = {
    "610014",  # Express Scripts accumulator
    "600428",  # CVS Caremark accumulator
    "004336",  # OptumRx accumulator
}
