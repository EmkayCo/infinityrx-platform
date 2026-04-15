"""Onboarding Workflow Service.

Manages the 12-step default onboarding workflow (configurable) for each program.
Tracks SLA clocks per step, identifies bottlenecks, and triggers post-launch
30-day elevated alerting.

Business rules:
  - Required steps cannot be skipped.
  - Steps must be completed in order unless out-of-order is explicitly allowed.
  - A program cannot be activated before its onboarding workflow is complete.
  - SLA clock starts when a step becomes active.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Default 12-step onboarding workflow per PRD §6
DEFAULT_ONBOARDING_STEPS: list[dict[str, Any]] = [
    {"step_number": 1, "name": "contract_signed", "required": True, "sla_hours": 0},
    {"step_number": 2, "name": "brd_sent", "required": True, "sla_hours": 24},
    {"step_number": 3, "name": "brd_returned_parsed", "required": True, "sla_hours": 72},
    {"step_number": 4, "name": "program_configured", "required": True, "sla_hours": 48},
    {"step_number": 5, "name": "test_claims_simulator", "required": True, "sla_hours": 24},
    {"step_number": 6, "name": "client_approves_test_results", "required": True, "sla_hours": 48},
    {"step_number": 7, "name": "bin_pcn_registered", "required": True, "sla_hours": 24},
    {"step_number": 8, "name": "pharmacy_network_notified", "required": True, "sla_hours": 24},
    {"step_number": 9, "name": "member_enrollment_received", "required": False, "sla_hours": 48},
    {"step_number": 10, "name": "go_live_confirmed", "required": True, "sla_hours": 0},
    {"step_number": 11, "name": "program_activated", "required": True, "sla_hours": 0},
    {"step_number": 12, "name": "post_launch_monitoring", "required": True, "sla_hours": 720},  # 30 days
]

# Post-launch elevated monitoring window (days)
POST_LAUNCH_MONITORING_DAYS = 30


class OnboardingError(Exception):
    """Raised when an onboarding business rule is violated."""


def build_default_steps() -> list[dict[str, Any]]:
    """Return a copy of the default 12-step onboarding plan."""
    import copy

    steps = copy.deepcopy(DEFAULT_ONBOARDING_STEPS)
    now = datetime.now(UTC)
    # Mark first step as active, compute initial SLA deadline
    for step in steps:
        step["status"] = "pending"
        step["started_at"] = None
        step["completed_at"] = None
        step["sla_deadline"] = None
    # Start step 1 immediately
    steps[0]["status"] = "active"
    steps[0]["started_at"] = now.isoformat()
    if steps[0]["sla_hours"] > 0:
        steps[0]["sla_deadline"] = (now + timedelta(hours=steps[0]["sla_hours"])).isoformat()
    return steps


def advance_step(
    steps: list[dict[str, Any]],
    step_number: int,
    action: str,
    notes: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Mark a step as completed/skipped and activate the next step.

    Returns (updated_steps, new_current_step).
    Raises OnboardingError if the step cannot be advanced.
    """
    import copy

    steps = copy.deepcopy(steps)
    # Find the target step
    target = next((s for s in steps if s["step_number"] == step_number), None)
    if target is None:
        raise OnboardingError(f"Step {step_number} not found in workflow")

    if target["status"] == "completed":
        raise OnboardingError(f"Step {step_number} is already completed")

    if action == "skip" and target.get("required", True):
        raise OnboardingError(
            f"Step {step_number} ({target['name']}) is required and cannot be skipped"
        )

    if target["status"] != "active":
        raise OnboardingError(
            f"Step {step_number} is not active (status={target['status']!r}). "
            "Cannot complete a non-active step."
        )

    now = datetime.now(UTC)
    target["status"] = "completed" if action != "skip" else "skipped"
    target["completed_at"] = now.isoformat()
    if notes:
        target["notes"] = notes

    # Activate the next pending step
    new_current = step_number
    for step in steps:
        if step["status"] == "pending":
            step["status"] = "active"
            step["started_at"] = now.isoformat()
            if step["sla_hours"] > 0:
                step["sla_deadline"] = (
                    now + timedelta(hours=step["sla_hours"])
                ).isoformat()
            new_current = step["step_number"]
            break

    return steps, new_current


def identify_bottlenecks(
    steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return steps that are past their SLA deadline and still active."""
    now = datetime.now(UTC)
    bottlenecks = []
    for step in steps:
        if step["status"] != "active":
            continue
        deadline_str = step.get("sla_deadline")
        if deadline_str is None:
            continue
        deadline = datetime.fromisoformat(deadline_str)
        if now > deadline:
            hours_overdue = (now - deadline).total_seconds() / 3600
            bottlenecks.append(
                {
                    "step_number": step["step_number"],
                    "step_name": step["name"],
                    "hours_overdue": round(hours_overdue, 1),
                    "sla_deadline": deadline_str,
                }
            )
    return bottlenecks


def is_onboarding_complete(steps: list[dict[str, Any]]) -> bool:
    """Return True if all required steps are completed."""
    for step in steps:
        if step.get("required", True) and step.get("status") not in ("completed",):
            return False
    return True
