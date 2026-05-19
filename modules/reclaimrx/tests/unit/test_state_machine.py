"""Unit tests for investigation state machine constants.

TDD: write, run (FAIL), then implement.
"""
import pytest
from src.utils.constants import (
    VALID_STATUS_TRANSITIONS,
    TERMINAL_STATES,
    TRANSITION_REQUIRED_FIELDS,
    validate_transition,
    InvalidTransitionError,
)


# ── Allowed transitions ────────────────────────────────────────────────────────

class TestAllowedTransitions:
    def test_open_to_in_progress(self):
        assert "in_progress" in VALID_STATUS_TRANSITIONS["open"]

    def test_open_to_pending_review(self):
        assert "pending_review" in VALID_STATUS_TRANSITIONS["open"]

    def test_open_to_escalated(self):
        assert "escalated" in VALID_STATUS_TRANSITIONS["open"]

    def test_in_progress_to_pending_review(self):
        assert "pending_review" in VALID_STATUS_TRANSITIONS["in_progress"]

    def test_in_progress_to_closed_confirmed(self):
        assert "closed_confirmed" in VALID_STATUS_TRANSITIONS["in_progress"]

    def test_in_progress_to_closed_false_positive(self):
        assert "closed_false_positive" in VALID_STATUS_TRANSITIONS["in_progress"]

    def test_in_progress_to_closed_no_action(self):
        assert "closed_no_action" in VALID_STATUS_TRANSITIONS["in_progress"]

    def test_in_progress_to_escalated(self):
        assert "escalated" in VALID_STATUS_TRANSITIONS["in_progress"]

    def test_pending_review_to_in_progress(self):
        assert "in_progress" in VALID_STATUS_TRANSITIONS["pending_review"]

    def test_pending_review_to_escalated(self):
        assert "escalated" in VALID_STATUS_TRANSITIONS["pending_review"]

    def test_pending_review_to_closed_confirmed(self):
        assert "closed_confirmed" in VALID_STATUS_TRANSITIONS["pending_review"]

    def test_pending_review_to_closed_false_positive(self):
        assert "closed_false_positive" in VALID_STATUS_TRANSITIONS["pending_review"]

    def test_pending_review_to_closed_no_action(self):
        assert "closed_no_action" in VALID_STATUS_TRANSITIONS["pending_review"]

    def test_escalated_to_in_progress_admin_only(self):
        # escalated allows in_progress — admin-only enforcement is at service layer
        assert "in_progress" in VALID_STATUS_TRANSITIONS["escalated"]

    def test_escalated_to_closed_variants(self):
        for closed in ("closed_confirmed", "closed_false_positive", "closed_no_action"):
            assert closed in VALID_STATUS_TRANSITIONS["escalated"], closed

    def test_closed_confirmed_to_open(self):
        assert "open" in VALID_STATUS_TRANSITIONS["closed_confirmed"]

    def test_closed_false_positive_to_open(self):
        assert "open" in VALID_STATUS_TRANSITIONS["closed_false_positive"]

    def test_closed_no_action_to_open(self):
        assert "open" in VALID_STATUS_TRANSITIONS["closed_no_action"]


# ── Invalid transitions ────────────────────────────────────────────────────────

class TestInvalidTransitions:
    def test_open_cannot_go_directly_to_closed_confirmed(self):
        assert "closed_confirmed" not in VALID_STATUS_TRANSITIONS["open"]

    def test_closed_confirmed_cannot_go_to_in_progress(self):
        # closed → open is the only re-entry path (admin override)
        assert "in_progress" not in VALID_STATUS_TRANSITIONS["closed_confirmed"]

    def test_unknown_from_state_raises(self):
        with pytest.raises(InvalidTransitionError, match="INVALID_TRANSITION"):
            validate_transition("nonexistent", "open", role="reclaimrx.investigator", fields={})


# ── Terminal states ────────────────────────────────────────────────────────────

class TestTerminalStates:
    def test_terminal_states_set(self):
        assert TERMINAL_STATES == frozenset({
            "closed_confirmed", "closed_false_positive", "closed_no_action"
        })


# ── validate_transition service function ──────────────────────────────────────

class TestValidateTransition:
    def test_valid_transition_returns_none(self):
        # No exception means success
        validate_transition(
            "open", "in_progress",
            role="reclaimrx.investigator",
            fields={"reason": "Starting review"},
        )

    def test_invalid_transition_raises_with_allowed_list(self):
        exc = pytest.raises(
            InvalidTransitionError,
            validate_transition,
            "open", "closed_confirmed",
            role="reclaimrx.investigator",
            fields={"reason": "Skip"},
        )
        assert "INVALID_TRANSITION" in str(exc.value)
        # error carries allowed next states
        assert "in_progress" in exc.value.allowed_next

    def test_missing_reason_raises(self):
        with pytest.raises(InvalidTransitionError, match="MISSING_REQUIRED_FIELD"):
            validate_transition(
                "open", "in_progress",
                role="reclaimrx.investigator",
                fields={},  # reason missing
            )

    def test_in_progress_to_closed_confirmed_requires_outcome_and_amount(self):
        with pytest.raises(InvalidTransitionError, match="MISSING_REQUIRED_FIELD"):
            validate_transition(
                "in_progress", "closed_confirmed",
                role="reclaimrx.investigator",
                fields={"reason": "done"},  # missing outcome_label + recovered_amount
            )

    def test_in_progress_to_closed_confirmed_succeeds_with_all_fields(self):
        from decimal import Decimal
        validate_transition(
            "in_progress", "closed_confirmed",
            role="reclaimrx.investigator",
            fields={
                "reason": "Confirmed fraud",
                "outcome_label": "confirmed",
                "recovered_amount": Decimal("1500.00"),
            },
        )

    def test_escalated_to_in_progress_requires_admin(self):
        with pytest.raises(InvalidTransitionError, match="INSUFFICIENT_ROLE"):
            validate_transition(
                "escalated", "in_progress",
                role="reclaimrx.investigator",
                fields={"reason": "re-open"},
            )

    def test_escalated_to_in_progress_succeeds_for_admin(self):
        validate_transition(
            "escalated", "in_progress",
            role="reclaimrx.admin",
            fields={"reason": "admin override"},
        )

    def test_closed_to_open_requires_admin(self):
        with pytest.raises(InvalidTransitionError, match="INSUFFICIENT_ROLE"):
            validate_transition(
                "closed_confirmed", "open",
                role="reclaimrx.investigator",
                fields={"reason": "re-open"},
            )

    def test_closed_to_open_succeeds_for_admin(self):
        validate_transition(
            "closed_confirmed", "open",
            role="reclaimrx.admin",
            fields={"reason": "re-open for new evidence"},
        )

    def test_outcome_label_must_match_closed_state(self):
        # closed_false_positive cannot have outcome_label='confirmed'
        with pytest.raises(InvalidTransitionError, match="OUTCOME_LABEL_MISMATCH"):
            validate_transition(
                "in_progress", "closed_false_positive",
                role="reclaimrx.investigator",
                fields={"reason": "done", "outcome_label": "confirmed"},
            )

    def test_closed_false_positive_requires_outcome_label(self):
        # Spec §5.5.1: outcome_label required for ALL closed_* states.
        with pytest.raises(InvalidTransitionError, match="MISSING_REQUIRED_FIELD"):
            validate_transition(
                "in_progress", "closed_false_positive",
                role="reclaimrx.investigator",
                fields={"reason": "not fraud"},  # missing outcome_label
            )

    def test_closed_no_action_requires_outcome_label(self):
        # Spec §5.5.1: outcome_label required for ALL closed_* states.
        with pytest.raises(InvalidTransitionError, match="MISSING_REQUIRED_FIELD"):
            validate_transition(
                "pending_review", "closed_no_action",
                role="reclaimrx.investigator",
                fields={"reason": "low priority"},  # missing outcome_label
            )

    def test_closed_false_positive_succeeds_with_outcome_label(self):
        # Positive test: providing the matching outcome_label allows the transition.
        validate_transition(
            "in_progress", "closed_false_positive",
            role="reclaimrx.investigator",
            fields={"reason": "verified not fraud", "outcome_label": "false_positive"},
        )

    def test_closed_no_action_succeeds_with_outcome_label(self):
        validate_transition(
            "pending_review", "closed_no_action",
            role="reclaimrx.investigator",
            fields={"reason": "below threshold", "outcome_label": "no_action"},
        )


# ── TRANSITION_REQUIRED_FIELDS table coverage ─────────────────────────────────

class TestTransitionRequiredFieldsTable:
    def test_required_fields_constant_is_importable(self):
        # Codex R1 BLOCK 1: constant must exist and be importable.
        assert isinstance(TRANSITION_REQUIRED_FIELDS, dict)
        assert len(TRANSITION_REQUIRED_FIELDS) >= 15  # 12 closed_* arcs + 3 reopen arcs

    def test_closed_confirmed_arcs_require_recovered_amount(self):
        for src in ("open", "in_progress", "pending_review", "escalated"):
            required = TRANSITION_REQUIRED_FIELDS[(src, "closed_confirmed")]
            assert "recovered_amount" in required
            assert "outcome_label" in required
            assert "reason" in required

    def test_closed_false_positive_arcs_require_outcome_label_not_amount(self):
        for src in ("open", "in_progress", "pending_review", "escalated"):
            required = TRANSITION_REQUIRED_FIELDS[(src, "closed_false_positive")]
            assert "outcome_label" in required
            assert "recovered_amount" not in required

    def test_closed_no_action_arcs_require_outcome_label_not_amount(self):
        for src in ("open", "in_progress", "pending_review", "escalated"):
            required = TRANSITION_REQUIRED_FIELDS[(src, "closed_no_action")]
            assert "outcome_label" in required
            assert "recovered_amount" not in required

    def test_reopen_arcs_require_only_reason(self):
        for src in ("closed_confirmed", "closed_false_positive", "closed_no_action"):
            required = TRANSITION_REQUIRED_FIELDS[(src, "open")]
            assert required == frozenset({"reason"})
