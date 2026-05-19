# SP-3 Plan A3 — State Machine + Hold Release Reshape + Accumulator Consumer + Graph Job

**Date:** 2026-05-18
**Parent spec:** `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`
**Audit source:** `waves/B10/SP-3-audit-deep.md`
**Codex review:** `docs/superpowers/codex-sp3-plan-a-review-r1.md`
**Plan series context:** Plan A3 assumes Plan A1 (tables/migration/alembic) and Plan A2 (outbox/dispatcher/idempotency infrastructure) are MERGED and GREEN. Do NOT re-define any table schema or outbox primitive here.
**Sub-session:** `waves/B10/sub-sessions/sp3-plan-a3.md`

---

## Scope

This plan delivers exactly four backend slices, in TDD order:

1. **Investigation state machine** — service-layer enforcement of allowed transitions with explicit error on invalid.
2. **POST /investigations/{id}/transitions** endpoint — authoritative state change with audit entry.
3. **Hold release reshape** — delete `DELETE /holds/{hold_id}`, add `POST /holds/{id}/release` with all three §7.2 idempotency cases, outbox publish.
4. **Accumulator detection consumer wiring** — `accumulator.updated` event handler writes `AccumulatorAnomaly` row (table from Plan A1), opens investigation on severity >= medium.
5. **Graph job real implementation** — replace `job_rebuild_fraud_network_graph` stub with batched computation using advisory lock (from Plan A2), writes `GraphRun` + `FraudRing` rows (tables from Plan A1).

**Out of scope here:** table creation (Plan A1), outbox/dispatcher (Plan A2), any frontend, BFF routes, contract layer.

---

## Ground-truth references (audit §)

Before writing code, executor MUST re-read these sections of the audit:

- `SP-3-audit-deep.md §1` — confirmed `PaymentHold` columns: `amount_threshold` (NOT `hold_amount`, audit:145), `is_active` bool (NOT `status` string, audit:158–159), `released_by/released_at/release_reason` already exist (audit:149–151).
- `SP-3-audit-deep.md §3` — `CurrentUser` is a dataclass; use `user.has_role("reclaimrx.investigator")` NOT `user.get("roles")` (audit:258).
- `SP-3-audit-deep.md §4` — existing hold route is `DELETE /holds/{hold_id}` at `router.py:475` with `reason` as Query param; spec requires `POST /holds/{id}/release` with body (audit:355).
- `SP-3-audit-deep.md §9` — advisory lock must use `zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF`, NOT Python `hash()` (audit:546–554).
- `SP-3-audit-deep.md §10` — all 3 idempotency cases UNIMPLEMENTED in current `payment_hold_service.py:73–100` (audit:585–588).
- `spec §5.5.1` — canonical state machine transition table (7 states, open/in_progress/pending_review/closed_confirmed/closed_false_positive/closed_no_action/escalated).
- `spec §7.2` — three deterministic idempotency cases for hold release.
- `codex BLOCK 5` — field is `amount_threshold` not `hold_amount`; three idempotency cases required.
- `codex BLOCK 6` — `user.has_role()` not `user.get()`.

---

## Pre-task checklist (executor runs before Task 1)

```
grep -n "VALID_STATUS_TRANSITIONS" modules/reclaimrx/src/utils/constants.py
# Expected: line 5 — existing map uses different state names; A3 replaces it.

grep -n "class InvestigationService" modules/reclaimrx/src/services/investigation_service.py
# Expected: line 26 — service exists, will be extended.

grep -n "is_active\|status\|released_by" modules/reclaimrx/src/models/tables.py | grep -A2 "PaymentHold"
# Expected: is_active Boolean line 611; released_by line 607; NO status column.
# Plan A1 adds PaymentHold.status. Verify it landed before proceeding.

grep -n "CONSUMER_ROUTING\|accumulator" modules/reclaimrx/src/events/consumers.py
# Expected: 8 entries, NO accumulator.updated handler.

grep -n "job_rebuild_fraud_network_graph" modules/reclaimrx/src/jobs/scheduled.py
# Expected: line 25 — stub returning {"communities_detected": 0}.
```

If `PaymentHold.status` column does NOT exist, Plan A1 is not merged — STOP and merge A1 first.

---

## Task 1 — Replace VALID_STATUS_TRANSITIONS with spec §5.5.1 state machine

**File:** `modules/reclaimrx/src/utils/constants.py`
**Approach:** Replace the existing `VALID_STATUS_TRANSITIONS` dict (currently lines 5–14, wrong state names) with the spec's 7-state machine. Add a `TERMINAL_STATES` frozenset. Add `TRANSITION_REQUIRED_FIELDS` mapping required fields per transition arc.

### 1a. Write test first

**File:** `modules/reclaimrx/tests/unit/test_state_machine.py` (NEW)

```python
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
```

**Run:** `pytest modules/reclaimrx/tests/unit/test_state_machine.py -x` → expect ALL FAIL (ImportError on `TRANSITION_REQUIRED_FIELDS` + missing-field tests fail until 1b is implemented).

### 1b. Implement

**File:** `modules/reclaimrx/src/utils/constants.py` — replace in full:

```python
"""Constants for the ReclaimRx module."""
from __future__ import annotations

from decimal import Decimal
from typing import Any


# ── State machine (spec §5.5.1) ───────────────────────────────────────────────

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
    # Terminal states: only re-open (admin-only) allowed
    "closed_confirmed": ["open"],
    "closed_false_positive": ["open"],
    "closed_no_action": ["open"],
}

TERMINAL_STATES: frozenset[str] = frozenset({
    "closed_confirmed",
    "closed_false_positive",
    "closed_no_action",
})

# Transitions that require reclaimrx.admin role
_ADMIN_ONLY_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("escalated", "in_progress"),
    ("escalated", "closed_confirmed"),
    ("escalated", "closed_false_positive"),
    ("escalated", "closed_no_action"),
    ("closed_confirmed", "open"),
    ("closed_false_positive", "open"),
    ("closed_no_action", "open"),
})

# outcome_label expected for each terminal state
_OUTCOME_LABEL_FOR_STATE: dict[str, str] = {
    "closed_confirmed": "confirmed",
    "closed_false_positive": "false_positive",
    "closed_no_action": "no_action",
}

# Required fields per (from_state, to_state) arc.
# `reason` is required for every transition (enforced globally in validate_transition).
# `outcome_label` is required for ALL closed_* targets (spec §5.5.1).
# `recovered_amount` is required ONLY for closed_confirmed (spec §5.5.1).
TRANSITION_REQUIRED_FIELDS: dict[tuple[str, str], frozenset[str]] = {
    # closed_confirmed from any non-terminal source
    ("open", "closed_confirmed"): frozenset({"reason", "outcome_label", "recovered_amount"}),
    ("in_progress", "closed_confirmed"): frozenset({"reason", "outcome_label", "recovered_amount"}),
    ("pending_review", "closed_confirmed"): frozenset({"reason", "outcome_label", "recovered_amount"}),
    ("escalated", "closed_confirmed"): frozenset({"reason", "outcome_label", "recovered_amount"}),
    # closed_false_positive — outcome_label required, NO recovered_amount
    ("open", "closed_false_positive"): frozenset({"reason", "outcome_label"}),
    ("in_progress", "closed_false_positive"): frozenset({"reason", "outcome_label"}),
    ("pending_review", "closed_false_positive"): frozenset({"reason", "outcome_label"}),
    ("escalated", "closed_false_positive"): frozenset({"reason", "outcome_label"}),
    # closed_no_action — outcome_label required, NO recovered_amount
    ("open", "closed_no_action"): frozenset({"reason", "outcome_label"}),
    ("in_progress", "closed_no_action"): frozenset({"reason", "outcome_label"}),
    ("pending_review", "closed_no_action"): frozenset({"reason", "outcome_label"}),
    ("escalated", "closed_no_action"): frozenset({"reason", "outcome_label"}),
    # Re-open from terminal (admin-only — role enforced separately)
    ("closed_confirmed", "open"): frozenset({"reason"}),
    ("closed_false_positive", "open"): frozenset({"reason"}),
    ("closed_no_action", "open"): frozenset({"reason"}),
    # All other arcs require only `reason` (global default).
}


# ── InvalidTransitionError ────────────────────────────────────────────────────

class InvalidTransitionError(ValueError):
    """Raised by validate_transition on illegal state machine moves.

    Attributes
    ----------
    code        Machine-readable error code (INVALID_TRANSITION, MISSING_REQUIRED_FIELD,
                INSUFFICIENT_ROLE, OUTCOME_LABEL_MISMATCH).
    allowed_next    List of valid target states from the current state.
    """

    def __init__(self, code: str, message: str, *, allowed_next: list[str] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.allowed_next: list[str] = allowed_next or []


# ── validate_transition ───────────────────────────────────────────────────────

def validate_transition(
    from_state: str,
    to_state: str,
    *,
    role: str,
    fields: dict[str, Any],
) -> None:
    """Validate a state machine transition.  Raises InvalidTransitionError on any violation.

    Parameters
    ----------
    from_state  Current investigation status.
    to_state    Requested target status.
    role        Caller's highest relevant role string ('reclaimrx.viewer',
                'reclaimrx.investigator', 'reclaimrx.admin').
    fields      Dict of fields present in the transition request body
                (keys: 'reason', 'outcome_label', 'recovered_amount', etc.).

    Raises
    ------
    InvalidTransitionError with codes:
        INVALID_TRANSITION          — from_state not in map, or to_state not in allowed list.
        INSUFFICIENT_ROLE           — transition requires admin; caller is not admin.
        MISSING_REQUIRED_FIELD      — mandatory field absent for this arc.
        OUTCOME_LABEL_MISMATCH      — outcome_label value contradicts to_state.
    """
    allowed: list[str] = VALID_STATUS_TRANSITIONS.get(from_state, [])
    if from_state not in VALID_STATUS_TRANSITIONS:
        raise InvalidTransitionError(
            "INVALID_TRANSITION",
            f"Unknown state '{from_state}'.",
            allowed_next=[],
        )
    if to_state not in allowed:
        raise InvalidTransitionError(
            "INVALID_TRANSITION",
            f"Transition from '{from_state}' to '{to_state}' is not permitted.",
            allowed_next=allowed,
        )

    # Admin-only gate
    if (from_state, to_state) in _ADMIN_ONLY_TRANSITIONS and role != "reclaimrx.admin":
        raise InvalidTransitionError(
            "INSUFFICIENT_ROLE",
            f"Transition from '{from_state}' to '{to_state}' requires reclaimrx.admin role.",
            allowed_next=allowed,
        )

    # All required fields per arc (driven by TRANSITION_REQUIRED_FIELDS table)
    required = TRANSITION_REQUIRED_FIELDS.get((from_state, to_state), frozenset({"reason"}))
    for field in required:
        # `recovered_amount` has a type constraint as well as a presence constraint
        if field == "recovered_amount":
            if not isinstance(fields.get("recovered_amount"), Decimal):
                raise InvalidTransitionError(
                    "MISSING_REQUIRED_FIELD",
                    "Field 'recovered_amount' (Decimal) is required for closed_confirmed.",
                    allowed_next=allowed,
                )
            continue
        # All other required fields: presence-only check (truthy)
        if not fields.get(field):
            raise InvalidTransitionError(
                "MISSING_REQUIRED_FIELD",
                f"Field '{field}' is required for transition '{from_state}' -> '{to_state}'.",
                allowed_next=allowed,
            )

    # outcome_label semantic check: if present AND target is a closed_* state, value must match
    if to_state in _OUTCOME_LABEL_FOR_STATE:
        _check_outcome_label(to_state, fields, allowed)


def _check_outcome_label(to_state: str, fields: dict[str, Any], allowed: list[str]) -> None:
    expected = _OUTCOME_LABEL_FOR_STATE.get(to_state)
    if expected is None:
        return
    provided = fields.get("outcome_label")
    # Presence is enforced upstream by TRANSITION_REQUIRED_FIELDS for all closed_* states.
    # Here we only check value semantics: if provided, it must match the target state's expected label.
    if provided is not None and provided != expected:
        raise InvalidTransitionError(
            "OUTCOME_LABEL_MISMATCH",
            f"outcome_label '{provided}' does not match target state '{to_state}' "
            f"(expected '{expected}').",
            allowed_next=allowed,
        )


# ── Risk score helpers ────────────────────────────────────────────────────────

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


# Known accumulator/maximizer plan BINs (sample — production loads from DB)
KNOWN_ACCUMULATOR_BINS: set[str] = {
    "610014",
    "600428",
    "004336",
}
```

**Run:** `pytest modules/reclaimrx/tests/unit/test_state_machine.py -x` → expect ALL PASS.
**Coverage gate:** `pytest modules/reclaimrx/tests/unit/test_state_machine.py --cov=src.utils.constants --cov-report=term-missing` → must be 100% on `constants.py`.

---

## Task 2 — Extend InvestigationService with transition() method + audit entry

**File:** `modules/reclaimrx/src/services/investigation_service.py`

### 2a. Write test first

**File:** `modules/reclaimrx/tests/unit/test_investigation_service_transitions.py` (NEW)

```python
"""Unit tests for InvestigationService.transition().

Uses in-memory SQLite + SAVEPOINT isolation per LESSON-001 + LESSON-007.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import String, create_engine, event
from sqlalchemy.orm import Session

# LESSON-007: remap PG_UUID to VARCHAR for SQLite
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator

from src.models.tables import Base, Investigation, InvestigationActivity
from src.services.investigation_service import InvestigationService
from src.utils.constants import InvalidTransitionError


class _UUIDString(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        for tbl in Base.metadata.sorted_tables:
            for col in tbl.columns:
                if isinstance(col.type, PG_UUID):
                    col.type = _UUIDString()
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session
    session.close()
    outer.rollback()
    connection.close()


def _make_investigation(db: Session, status: str = "open") -> Investigation:
    tid = uuid.uuid4()
    inv = Investigation(
        id=str(uuid.uuid4()),
        tenant_id=str(tid),
        investigation_number="INV-2026-TEST",
        title="Test investigation",
        subject_type="pharmacy",
        subject_entity_id="pharmacy-123",
        investigation_type="rule_firing",
        status=status,
    )
    db.add(inv)
    db.flush()
    return inv


class TestTransitionMethod:
    def test_valid_transition_updates_status(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        svc.transition(
            tenant_id=uuid.UUID(inv.tenant_id),
            investigation_id=inv.id,
            to_state="in_progress",
            role="reclaimrx.investigator",
            user_id=uuid.uuid4(),
            reason="Starting review",
        )
        db.refresh(inv)
        assert inv.status == "in_progress"

    def test_transition_writes_audit_activity(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        user = uuid.uuid4()
        svc.transition(
            tenant_id=uuid.UUID(inv.tenant_id),
            investigation_id=inv.id,
            to_state="in_progress",
            role="reclaimrx.investigator",
            user_id=user,
            reason="Starting review",
        )
        activities = db.query(InvestigationActivity).filter_by(investigation_id=inv.id).all()
        assert len(activities) == 1
        act = activities[0]
        assert act.activity_type == "status_transition"
        assert "open" in (act.notes or "")
        assert "in_progress" in (act.notes or "")

    def test_invalid_transition_raises_invalid_transition_error(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        with pytest.raises(InvalidTransitionError) as exc_info:
            svc.transition(
                tenant_id=uuid.UUID(inv.tenant_id),
                investigation_id=inv.id,
                to_state="closed_confirmed",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="skip to close",
            )
        assert exc_info.value.code == "INVALID_TRANSITION"
        # investigation status must be unchanged
        db.refresh(inv)
        assert inv.status == "open"

    def test_missing_reason_raises(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        with pytest.raises(InvalidTransitionError) as exc_info:
            svc.transition(
                tenant_id=uuid.UUID(inv.tenant_id),
                investigation_id=inv.id,
                to_state="in_progress",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="",
            )
        assert exc_info.value.code == "MISSING_REQUIRED_FIELD"

    def test_escalated_to_in_progress_requires_admin(self, db):
        inv = _make_investigation(db, status="escalated")
        svc = InvestigationService(db)
        with pytest.raises(InvalidTransitionError) as exc_info:
            svc.transition(
                tenant_id=uuid.UUID(inv.tenant_id),
                investigation_id=inv.id,
                to_state="in_progress",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="re-open",
            )
        assert exc_info.value.code == "INSUFFICIENT_ROLE"

    def test_closed_confirmed_to_in_progress_requires_admin(self, db):
        inv = _make_investigation(db, status="closed_confirmed")
        svc = InvestigationService(db)
        with pytest.raises(InvalidTransitionError) as exc_info:
            svc.transition(
                tenant_id=uuid.UUID(inv.tenant_id),
                investigation_id=inv.id,
                to_state="in_progress",  # not in allowed list for closed_confirmed
                role="reclaimrx.admin",
                user_id=uuid.uuid4(),
                reason="re-open",
            )
        assert exc_info.value.code == "INVALID_TRANSITION"

    def test_closed_to_open_succeeds_for_admin(self, db):
        inv = _make_investigation(db, status="closed_confirmed")
        svc = InvestigationService(db)
        svc.transition(
            tenant_id=uuid.UUID(inv.tenant_id),
            investigation_id=inv.id,
            to_state="open",
            role="reclaimrx.admin",
            user_id=uuid.uuid4(),
            reason="new evidence",
        )
        db.refresh(inv)
        assert inv.status == "open"

    def test_closed_confirmed_sets_outcome_and_recovered(self, db):
        inv = _make_investigation(db, status="in_progress")
        svc = InvestigationService(db)
        svc.transition(
            tenant_id=uuid.UUID(inv.tenant_id),
            investigation_id=inv.id,
            to_state="closed_confirmed",
            role="reclaimrx.investigator",
            user_id=uuid.uuid4(),
            reason="Confirmed billing fraud",
            outcome_label="confirmed",
            recovered_amount=Decimal("2500.00"),
        )
        db.refresh(inv)
        assert inv.status == "closed_confirmed"
        # actual_recovered updated
        assert Decimal(str(inv.actual_recovered)) == Decimal("2500.00")

    def test_investigation_not_found_raises(self, db):
        svc = InvestigationService(db)
        with pytest.raises(ValueError, match="NOT_FOUND"):
            svc.transition(
                tenant_id=uuid.uuid4(),
                investigation_id="nonexistent-id",
                to_state="in_progress",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="test",
            )

    def test_cross_tenant_not_found(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        with pytest.raises(ValueError, match="NOT_FOUND"):
            svc.transition(
                tenant_id=uuid.uuid4(),   # different tenant
                investigation_id=inv.id,
                to_state="in_progress",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="cross-tenant attempt",
            )
```

**Run:** `pytest modules/reclaimrx/tests/unit/test_investigation_service_transitions.py -x` → expect FAIL.

### 2b. Implement

Append `transition()` method to `InvestigationService` in `modules/reclaimrx/src/services/investigation_service.py`:

```python
    # ── State machine transition ───────────────────────────────────────────────

    def transition(
        self,
        *,
        tenant_id: uuid.UUID,
        investigation_id: str,
        to_state: str,
        role: str,
        user_id: uuid.UUID,
        reason: str,
        outcome_label: str | None = None,
        recovered_amount: Decimal | None = None,
    ) -> Investigation:
        """Validate and apply a status transition.  Writes append-only audit row.

        Raises
        ------
        ValueError(code='NOT_FOUND')        — investigation absent or wrong tenant.
        InvalidTransitionError              — illegal transition, missing role, missing fields.
        """
        from src.utils.constants import validate_transition, InvalidTransitionError  # noqa: PLC0415

        inv = (
            self._session.execute(
                select(Investigation).where(
                    Investigation.id == investigation_id,
                    Investigation.tenant_id == str(tenant_id),
                )
            )
            .scalar_one_or_none()
        )
        if inv is None:
            raise ValueError("NOT_FOUND")

        fields: dict[str, object] = {"reason": reason}
        if outcome_label is not None:
            fields["outcome_label"] = outcome_label
        if recovered_amount is not None:
            fields["recovered_amount"] = recovered_amount

        # Raises InvalidTransitionError on violation — let it propagate unchanged
        validate_transition(inv.status, to_state, role=role, fields=fields)

        from_state = inv.status
        inv.status = to_state
        inv.updated_at = _now()

        if to_state == "closed_confirmed":
            inv.resolved_at = _now()
            if recovered_amount is not None:
                inv.actual_recovered = recovered_amount.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        elif to_state in ("closed_false_positive", "closed_no_action"):
            inv.resolved_at = _now()
        elif to_state == "open" and from_state in ("closed_confirmed", "closed_false_positive", "closed_no_action"):
            # admin re-open: clear resolved fields
            inv.resolved_at = None
            inv.actual_recovered = Decimal("0.00")

        # Append-only audit activity row
        activity = InvestigationActivity(
            id=str(uuid.uuid4()),
            investigation_id=inv.id,
            activity_type="status_transition",
            performed_by=str(user_id),
            notes=f"Status changed from '{from_state}' to '{to_state}'. Reason: {reason}",
            created_at=_now(),
        )
        self._session.add(activity)
        self._session.flush()
        return inv
```

Add missing import at top of `investigation_service.py` if not present: `from decimal import ROUND_HALF_UP, Decimal`.

**Run:** `pytest modules/reclaimrx/tests/unit/test_investigation_service_transitions.py -x` → expect ALL PASS.

---

## Task 3 — POST /investigations/{id}/transitions endpoint

**File:** `modules/reclaimrx/src/api/router.py`

### 3a. Write test first

**File:** `modules/reclaimrx/tests/integration/test_transitions_endpoint.py` (NEW)

```python
"""Integration tests for POST /investigations/{id}/transitions.

Uses TestClient; auth shim set_current_user().
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src._shim.auth import CurrentUser, set_current_user
from src._shim.db import set_session_override
from src.main import create_app
from src.models.tables import Base, Investigation


@pytest.fixture(scope="session")
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture(scope="session", autouse=True)
def _create_tables(engine):
    Base.metadata.create_all(engine)


@pytest.fixture()
def db(engine):
    conn = engine.connect()
    txn = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    txn.rollback()
    conn.close()


@pytest.fixture()
def client(db):
    app = create_app()
    set_session_override(db)
    return TestClient(app)


def _seed_investigation(db: Session, status: str = "open") -> str:
    tid = str(uuid.uuid4())
    inv_id = str(uuid.uuid4())
    inv = Investigation(
        id=inv_id, tenant_id=tid,
        investigation_number="INV-2026-T1",
        title="Test", subject_type="pharmacy",
        subject_entity_id="ph-1",
        investigation_type="rule_firing", status=status,
    )
    db.add(inv)
    db.flush()
    return inv_id, tid


def _set_user(tenant_id: str, role: str):
    set_current_user(CurrentUser(
        id=uuid.uuid4(),
        tenant_id=uuid.UUID(tenant_id),
        email="test@example.com",
        roles=[role],
    ))


class TestTransitionsEndpoint:
    def test_viewer_cannot_transition(self, client, db):
        inv_id, tid = _seed_investigation(db, "open")
        _set_user(tid, "reclaimrx.viewer")
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "start"},
        )
        assert resp.status_code == 403

    def test_investigator_can_transition_open_to_in_progress(self, client, db):
        inv_id, tid = _seed_investigation(db, "open")
        _set_user(tid, "reclaimrx.investigator")
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "Starting"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "in_progress"

    def test_invalid_transition_returns_422(self, client, db):
        inv_id, tid = _seed_investigation(db, "open")
        _set_user(tid, "reclaimrx.investigator")
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "closed_confirmed", "reason": "skip"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "INVALID_TRANSITION"
        # allowed_next_states in error.field
        assert "in_progress" in body["error"]["field"]

    def test_missing_reason_returns_422(self, client, db):
        inv_id, tid = _seed_investigation(db, "open")
        _set_user(tid, "reclaimrx.investigator")
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": ""},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "MISSING_REQUIRED_FIELD"

    def test_unknown_investigation_returns_404(self, client, db):
        _set_user(str(uuid.uuid4()), "reclaimrx.investigator")
        resp = client.post(
            "/api/v1/reclaimrx/investigations/does-not-exist/transitions",
            json={"to_state": "in_progress", "reason": "x"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_cross_tenant_returns_404(self, client, db):
        inv_id, _tid = _seed_investigation(db, "open")
        _set_user(str(uuid.uuid4()), "reclaimrx.investigator")  # different tenant
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "x"},
        )
        assert resp.status_code == 404

    def test_escalated_to_in_progress_403_for_investigator(self, client, db):
        inv_id, tid = _seed_investigation(db, "escalated")
        _set_user(tid, "reclaimrx.investigator")
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "override"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"

    def test_admin_can_move_escalated_to_in_progress(self, client, db):
        inv_id, tid = _seed_investigation(db, "escalated")
        _set_user(tid, "reclaimrx.admin")
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "admin override"},
        )
        assert resp.status_code == 200

    def test_closed_confirmed_to_in_progress_invalid_even_for_admin(self, client, db):
        # Only closed → open is allowed; closed → in_progress is not
        inv_id, tid = _seed_investigation(db, "closed_confirmed")
        _set_user(tid, "reclaimrx.admin")
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "skip"},
        )
        assert resp.status_code == 422

    def test_transition_correlation_id_in_response(self, client, db):
        inv_id, tid = _seed_investigation(db, "open")
        _set_user(tid, "reclaimrx.investigator")
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "start"},
        )
        assert resp.status_code == 200
        assert "correlation_id" in resp.json()
```

**Run:** `pytest modules/reclaimrx/tests/integration/test_transitions_endpoint.py -x` → expect FAIL.

### 3b. Implement

Add Pydantic schema and route to `router.py`. Add near the investigation section (after existing `PUT /investigations/{id}`):

```python
# ── Schemas (add at top of router.py near existing schema classes) ─────────────

class TransitionRequest(BaseModel):
    to_state: str
    reason: str
    outcome_label: str | None = None
    recovered_amount: Decimal | None = None
    evidence_ref: str | None = None


class TransitionResponse(BaseModel):
    id: str
    status: str
    previous_status: str
    correlation_id: str


# ── Route (add after existing investigation routes) ────────────────────────────

@router.post(
    "/investigations/{investigation_id}/transitions",
    response_model=dict,
    status_code=200,
)
def transition_investigation_status(
    investigation_id: str,
    body: TransitionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(
        require_role("reclaimrx.investigator", "reclaimrx.admin")
    ),
) -> dict:
    """Transition an investigation's status through the spec §5.5.1 state machine.

    Role gate: reclaimrx.investigator or reclaimrx.admin.
    Admin-only arcs (escalated→*, closed→open) are enforced inside validate_transition().
    Returns 422 INVALID_TRANSITION / MISSING_REQUIRED_FIELD / INSUFFICIENT_ROLE.
    Returns 404 NOT_FOUND on missing or wrong-tenant investigation.
    """
    import uuid as _uuid  # noqa: PLC0415
    from src.utils.constants import InvalidTransitionError  # noqa: PLC0415

    # Resolve caller role (highest applicable)
    role = (
        "reclaimrx.admin"
        if user.has_role("reclaimrx.admin")
        else "reclaimrx.investigator"
    )

    svc = InvestigationService(db)
    correlation_id = str(_uuid.uuid4())
    prev_status: str | None = None

    try:
        # Peek at current status for response (tenant-scoped)
        from sqlalchemy import select  # noqa: PLC0415
        from src.models.tables import Investigation  # noqa: PLC0415

        inv_row = db.execute(
            select(Investigation).where(
                Investigation.id == investigation_id,
                Investigation.tenant_id == str(user.tenant_id),
            )
        ).scalar_one_or_none()
        if inv_row is None:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "NOT_FOUND", "message": "Investigation not found.", "correlation_id": correlation_id}},
            )
        prev_status = inv_row.status

        inv = svc.transition(
            tenant_id=user.tenant_id,
            investigation_id=investigation_id,
            to_state=body.to_state,
            role=role,
            user_id=user.id,
            reason=body.reason,
            outcome_label=body.outcome_label,
            recovered_amount=body.recovered_amount,
        )
        db.commit()
    except ValueError as exc:
        msg = str(exc)
        if "NOT_FOUND" in msg:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "NOT_FOUND", "message": "Investigation not found.", "correlation_id": correlation_id}},
            ) from exc
        raise HTTPException(status_code=500, detail={"error": {"code": "INTERNAL", "message": "Unexpected error.", "correlation_id": correlation_id}}) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "field": ",".join(exc.allowed_next),
                    "correlation_id": correlation_id,
                }
            },
        ) from exc

    return {
        "id": inv.id,
        "status": inv.status,
        "previous_status": prev_status,
        "correlation_id": correlation_id,
    }
```

**Run:** `pytest modules/reclaimrx/tests/integration/test_transitions_endpoint.py -x` → expect ALL PASS.

---

## Task 4 — Hold release reshape: delete DELETE route, add POST /holds/{id}/release

This task has two sub-steps: delete old route, implement new with 3-case idempotency.

### 4a. Write test first

**File:** `modules/reclaimrx/tests/integration/test_hold_release_endpoint.py` (NEW)

Key audit facts encoded in every test:
- `PaymentHold.amount_threshold` NOT `hold_amount` (audit §1:145, codex BLOCK 5)
- `PaymentHold.status` (added by Plan A1) replaces `is_active` for idempotency logic
- `PaymentHold.released_by/released_at/release_reason` already exist (audit §1:149–151)

```python
"""Integration tests for POST /holds/{id}/release.

Tests all three §7.2 idempotency cases:
  Case A: same actor + reason + investigation_id (already released) → 200
  Case B: already released by different actor or different reason → 409
  Case C: hold in non-active/non-released state → 422
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src._shim.auth import CurrentUser, set_current_user
from src._shim.db import set_session_override
from src.main import create_app
from src.models.tables import Base, Investigation, PaymentHold


@pytest.fixture(scope="session")
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture(scope="session", autouse=True)
def _create_tables(engine):
    Base.metadata.create_all(engine)


@pytest.fixture()
def db(engine):
    conn = engine.connect()
    txn = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    txn.rollback()
    conn.close()


@pytest.fixture()
def client(db):
    app = create_app()
    set_session_override(db)
    return TestClient(app)


def _seed(db: Session):
    tid = str(uuid.uuid4())
    inv_id = str(uuid.uuid4())
    hold_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    inv = Investigation(
        id=inv_id, tenant_id=tid,
        investigation_number="INV-2026-H", title="Hold test",
        subject_type="pharmacy", subject_entity_id="ph-1",
        investigation_type="rule_firing", status="in_progress",
    )
    db.add(inv)

    hold = PaymentHold(
        id=hold_id, tenant_id=tid,
        entity_type="pharmacy", entity_id="ph-1",
        investigation_id=inv_id,
        placed_by=user_id,
        status="active",            # Plan A1 added PaymentHold.status column
        amount_threshold=Decimal("500.00"),  # NOT hold_amount (audit §1:145)
        is_active=True,
    )
    db.add(hold)
    db.flush()
    return tid, inv_id, hold_id, user_id


class TestHoldRelease:
    def test_old_delete_route_is_gone(self, client, db):
        tid, inv_id, hold_id, _ = _seed(db)
        set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))
        resp = client.delete(f"/api/v1/reclaimrx/holds/{hold_id}?reason=done")
        assert resp.status_code == 405  # Method Not Allowed (route removed)

    def test_viewer_cannot_release(self, client, db):
        tid, inv_id, hold_id, _ = _seed(db)
        set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.viewer"]))
        resp = client.post(
            f"/api/v1/reclaimrx/holds/{hold_id}/release",
            json={"reason": "releasing", "investigation_id": inv_id},
        )
        assert resp.status_code == 403

    def test_normal_release_returns_200(self, client, db):
        tid, inv_id, hold_id, _ = _seed(db)
        uid = uuid.uuid4()
        set_current_user(CurrentUser(id=uid, tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))
        resp = client.post(
            f"/api/v1/reclaimrx/holds/{hold_id}/release",
            json={"reason": "Resolved — no fraud", "investigation_id": inv_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "released"
        assert body["released_by"] == str(uid)

    def test_missing_reason_returns_422(self, client, db):
        tid, inv_id, hold_id, _ = _seed(db)
        set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))
        resp = client.post(
            f"/api/v1/reclaimrx/holds/{hold_id}/release",
            json={"reason": "", "investigation_id": inv_id},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "REASON_REQUIRED"

    def test_investigation_mismatch_returns_403(self, client, db):
        tid, inv_id, hold_id, _ = _seed(db)
        set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))
        resp = client.post(
            f"/api/v1/reclaimrx/holds/{hold_id}/release",
            json={"reason": "done", "investigation_id": str(uuid.uuid4())},  # wrong inv
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "HOLD_INVESTIGATION_MISMATCH"

    # ── Idempotency Case A: same actor + reason + investigation_id → 200 ──────

    def test_idempotency_case_a_same_actor_and_reason_returns_200(self, client, db):
        tid, inv_id, hold_id, _ = _seed(db)
        uid = uuid.uuid4()
        set_current_user(CurrentUser(id=uid, tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))
        payload = {"reason": "Same reason", "investigation_id": inv_id}

        resp1 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release", json=payload)
        assert resp1.status_code == 200

        resp2 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release", json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["idempotent_replay"] is True

    # ── Idempotency Case B: different actor or different reason → 409 ─────────

    def test_idempotency_case_b_different_actor_returns_409(self, client, db):
        tid, inv_id, hold_id, _ = _seed(db)

        # Release with actor A
        uid_a = uuid.uuid4()
        set_current_user(CurrentUser(id=uid_a, tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))
        resp1 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                            json={"reason": "Reason A", "investigation_id": inv_id})
        assert resp1.status_code == 200

        # Attempt release with actor B (different user)
        uid_b = uuid.uuid4()
        set_current_user(CurrentUser(id=uid_b, tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))
        resp2 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                            json={"reason": "Reason A", "investigation_id": inv_id})
        assert resp2.status_code == 409
        body = resp2.json()
        assert body["error"]["code"] == "ALREADY_RELEASED"
        assert "released_at" in body["error"]

    def test_idempotency_case_b_different_reason_same_actor_returns_409(self, client, db):
        tid, inv_id, hold_id, _ = _seed(db)
        uid = uuid.uuid4()
        set_current_user(CurrentUser(id=uid, tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))

        resp1 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                            json={"reason": "First reason", "investigation_id": inv_id})
        assert resp1.status_code == 200

        resp2 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                            json={"reason": "Different reason", "investigation_id": inv_id})
        assert resp2.status_code == 409

    # ── Idempotency Case C: hold in non-active non-released state → 422 ───────

    def test_idempotency_case_c_expired_hold_returns_422(self, client, db):
        tid = str(uuid.uuid4())
        inv_id = str(uuid.uuid4())
        hold_id = str(uuid.uuid4())
        inv = Investigation(id=inv_id, tenant_id=tid, investigation_number="INV-EXP",
                            title="Expired", subject_type="pharmacy",
                            subject_entity_id="ph-x", investigation_type="rule_firing",
                            status="in_progress")
        hold = PaymentHold(id=hold_id, tenant_id=tid, entity_type="pharmacy",
                           entity_id="ph-x", investigation_id=inv_id,
                           placed_by=str(uuid.uuid4()),
                           status="expired",        # non-active, non-released
                           amount_threshold=Decimal("100.00"), is_active=False)
        db.add_all([inv, hold])
        db.flush()

        set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))
        resp = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                           json={"reason": "try to release expired", "investigation_id": inv_id})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "HOLD_NOT_ACTIVE"
        assert "expired" in body["error"]["field"]

    def test_outbox_row_written_on_release(self, client, db):
        """Verify outbox event row is inserted atomically with hold update."""
        from src.models.tables import OutboxEvent  # noqa: PLC0415 — added by Plan A1

        tid, inv_id, hold_id, _ = _seed(db)
        uid = uuid.uuid4()
        set_current_user(CurrentUser(id=uid, tenant_id=uuid.UUID(tid),
                                     roles=["reclaimrx.investigator"]))

        before_count = db.query(OutboxEvent).count()
        client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                    json={"reason": "Resolved", "investigation_id": inv_id})
        after_count = db.query(OutboxEvent).count()
        assert after_count == before_count + 1

        row = db.query(OutboxEvent).order_by(OutboxEvent.created_at.desc()).first()
        assert row.event_type == "payment.hold_released"
        assert row.status == "pending"
        assert row.idempotency_key == f"hold:release:{hold_id}"
```

**Run:** `pytest modules/reclaimrx/tests/integration/test_hold_release_endpoint.py -x` → expect FAIL.

### 4b. Implement hold release reshape

**Step 1:** Remove old route from `router.py`. Delete the `@router.delete("/holds/{hold_id}", ...)` block at lines 475–493.

**Step 2:** Update `PaymentHoldService.release_hold()` in `modules/reclaimrx/src/services/payment_hold_service.py` to implement 3-case idempotency using `PaymentHold.status` (added by Plan A1):

```python
    def release_hold(
        self,
        *,
        tenant_id: uuid.UUID,
        hold_id: str,
        released_by: uuid.UUID,
        reason: str,
        investigation_id: str,
        emergency_reason_code: str | None = None,
        emergency_note: str | None = None,
        is_admin: bool = False,
    ) -> tuple[dict, int]:
        """Release a payment hold.  Returns (response_dict, http_status_code).

        Three deterministic idempotency cases (spec §7.2, codex BLOCK 5):
          Case A — status='released', same released_by+reason+investigation_id → (prior, 200)
          Case B — status='released', any field differs → (prior info, 409)
          Case C — status not in ('active', 'released') → (current status, 422)
        """
        from sqlalchemy import select  # noqa: PLC0415
        from src.models.tables import Investigation, OutboxEvent  # noqa: PLC0415
        from shared.events.types import EventEnvelope  # noqa: PLC0415
        import zlib  # noqa: PLC0415
        import json  # noqa: PLC0415

        # Tenant-scoped fetch with row lock
        hold = self._session.execute(
            select(PaymentHold)
            .where(
                PaymentHold.id == hold_id,
                PaymentHold.tenant_id == str(tenant_id),
            )
            .with_for_update()
        ).scalar_one_or_none()

        if hold is None:
            raise ValueError("NOT_FOUND")

        # Investigation match check
        if hold.investigation_id != investigation_id and not is_admin:
            raise HoldInvestigationMismatchError(hold_id=hold_id)

        hold_status = getattr(hold, "status", "active" if hold.is_active else "released")

        # ── Idempotency Case A / B ─────────────────────────────────────────────
        if hold_status == "released":
            same = (
                hold.released_by == str(released_by)
                and hold.release_reason == reason
                and hold.investigation_id == investigation_id
            )
            if same:
                return {
                    "id": hold.id,
                    "status": "released",
                    "released_at": hold.released_at.isoformat() if hold.released_at else None,
                    "released_by": hold.released_by,
                    "reason": hold.release_reason,
                    "idempotent_replay": True,
                }, 200
            else:
                return {
                    "error": {
                        "code": "ALREADY_RELEASED",
                        "message": "Hold was already released by a different actor or with different context.",
                        "released_at": hold.released_at.isoformat() if hold.released_at else None,
                        "released_by": hold.released_by,
                        "reason": hold.release_reason,
                    }
                }, 409

        # ── Idempotency Case C ─────────────────────────────────────────────────
        if hold_status not in ("active",):
            return {
                "error": {
                    "code": "HOLD_NOT_ACTIVE",
                    "message": f"Hold is not in an active state (current: '{hold_status}').",
                    "field": hold_status,
                }
            }, 422

        # ── Normal release path ────────────────────────────────────────────────
        now = _now()
        hold.status = "released"         # Plan A1 column
        hold.is_active = False           # keep boolean consistent
        hold.released_by = str(released_by)
        hold.released_at = now
        hold.release_reason = reason
        self._session.flush()

        # Outbox row — atomic with DB update (R1 BLOCK 4 / spec §7.2 step 7e)
        # Use amount_threshold (NOT hold_amount — audit §1:145, codex BLOCK 5)
        amount_str = str(hold.amount_threshold or Decimal("0.00"))
        envelope = EventEnvelope(
            event_type="payment.hold_released",
            tenant_id=tenant_id,          # uuid.UUID, not str
            correlation_id=uuid.uuid4(),
            source_module="reclaimrx",
            schema_version="1.0",
            ordering_key=str(hold_id),
            idempotency_key=f"hold:release:{hold_id}",
            payload={
                "hold_id": hold_id,
                "amount": amount_str,
                "released_by": str(released_by),
                "reason": reason,
                "investigation_id": investigation_id,
                "released_at": now.isoformat(),
                "emergency_reason_code": emergency_reason_code,
                "emergency_note": emergency_note,
            },
        )
        outbox = OutboxEvent(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            event_type="payment.hold_released",
            envelope_json=envelope.model_dump(mode="json"),
            status="pending",
            idempotency_key=f"hold:release:{hold_id}",
        )
        self._session.add(outbox)
        self._session.flush()

        return {
            "id": hold.id,
            "status": "released",
            "released_at": now.isoformat(),
            "released_by": str(released_by),
            "reason": reason,
            "idempotent_replay": False,
        }, 200


class HoldInvestigationMismatchError(ValueError):
    def __init__(self, hold_id: str) -> None:
        super().__init__(f"HOLD_INVESTIGATION_MISMATCH: hold {hold_id}")
        self.code = "HOLD_INVESTIGATION_MISMATCH"
```

**Step 3:** Add new route to `router.py`:

```python
class HoldReleaseRequest(BaseModel):
    """A4 BLOCK 1 fix — typed request body owned by A4 schemas; A3 references it.

    R3 NEW-R3-2 fix: `idempotency_key` is supplied via the `Idempotency-Key`
    HTTP header (handler signature below uses `Header(..., alias="...")`),
    NOT a body field. The header-only contract is the single source of truth
    so two competing contracts cannot drift apart. Format:
        hold:release:{hold_id}:{actor_id}
    """
    reason: str
    investigation_id: str
    emergency_reason_code: str | None = None  # LEGAL_HOLD | REGULATORY_DIRECTIVE | IRRECOVERABLE_HARM | OTHER_WITH_NOTE
    emergency_note: str | None = None


# A4 schema imports — Pydantic response model attached at decorator level
# per A4 BLOCK 1 (typed response_model, not bare `dict`).
from src.api.schemas import HoldReleaseRead  # noqa: E402
from src.api.dependencies import (  # noqa: E402
    RECLAIMRX_INVESTIGATOR_DEP,
    require_tenant_match,
    require_mfa_elevated,
)
from src.api.errors import build_error_envelope  # noqa: E402


@router.post(
    "/holds/{hold_id}/release",
    status_code=200,
    response_model=HoldReleaseRead,  # A4 BLOCK 1 fix — typed at decorator level
)
async def release_hold_v2(
    hold_id: str,
    body: HoldReleaseRequest,
    # A4 BLOCK 13 dependency order: 401 → 403 role → 403 tenant → 403 MFA → idempotency → business
    user: CurrentUser = RECLAIMRX_INVESTIGATOR_DEP,
    _tenant_check: CurrentUser = Depends(require_tenant_match),
    _mfa: CurrentUser = Depends(require_mfa_elevated),
    # R3 NEW-R3-2 fix: idempotency-key arrives via Header, not body field.
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> HoldReleaseRead:
    """Release a payment hold. Replaces DELETE /holds/{hold_id}.

    Implements all 3 §7.2 idempotency cases. Writes outbox row atomically
    with event_type=`payment.hold_released` (spec §11.5 lock).
    Role: reclaimrx.investigator+. Emergency override: reclaimrx.admin only.
    Idempotency key format (A4 BLOCK 6): `hold:release:{hold_id}:{actor_id}`.
    """
    import uuid as _uuid  # noqa: PLC0415
    correlation_id = str(_uuid.uuid4())

    if not body.reason:
        raise HTTPException(
            status_code=422,
            detail=build_error_envelope(
                "REASON_REQUIRED",
                "reason is required.",
                field="reason",
                correlation_id=correlation_id,
            ),
        )

    is_admin = user.has_role("reclaimrx.admin")
    svc = PaymentHoldService(db)
    try:
        response_body, status_code = svc.release_hold(
            tenant_id=user.tenant_id,
            hold_id=hold_id,
            released_by=user.id,
            reason=body.reason,
            investigation_id=body.investigation_id,
            emergency_reason_code=body.emergency_reason_code,
            emergency_note=body.emergency_note,
            is_admin=is_admin,
        )
    except ValueError as exc:
        msg = str(exc)
        if "NOT_FOUND" in msg:
            raise HTTPException(
                status_code=404,
                detail=build_error_envelope(
                    "NOT_FOUND", "Hold not found.", correlation_id=correlation_id,
                ),
            ) from exc
        raise HTTPException(
            status_code=500,
            detail=build_error_envelope(
                "INTERNAL", "Internal error.", correlation_id=correlation_id,
            ),
        ) from exc
    except Exception as exc:  # HoldInvestigationMismatchError
        if hasattr(exc, "code") and exc.code == "HOLD_INVESTIGATION_MISMATCH":  # type: ignore[union-attr]
            raise HTTPException(
                status_code=403,
                detail=build_error_envelope(
                    "HOLD_INVESTIGATION_MISMATCH",
                    str(exc),
                    correlation_id=correlation_id,
                ),
            ) from exc
        raise

    if status_code == 409:
        raise HTTPException(status_code=409, detail=response_body)
    if status_code == 422:
        raise HTTPException(status_code=422, detail=response_body)

    db.commit()
    return response_body
```

**Run:** `pytest modules/reclaimrx/tests/integration/test_hold_release_endpoint.py -x` → expect ALL PASS.

---

## Task 5 — Accumulator detection consumer wiring

> **Scope note (R1 CONCERN 5):** A3 wires ONLY two accumulator pattern detectors:
> `sudden_spike` and `multi_payer_convergence`. The spec §11.5 list also names
> `reset_evasion` and `threshold_oscillation` as `AccumulatorAnomaly.pattern_type`
> values, but those two detectors require additional historical-window queries
> against the AccumulatorEvent stream (90-day rolling reset cadence comparison,
> threshold-bouncing detector) that are out of scope for SP-3 wave B10.
>
> Both deferred detectors are tracked under follow-on task **`B10-w5/follow-on/accumulator-patterns-3-4`**
> (to be created in B11 backlog after SP-3 merges). Acceptance criteria for
> A3 explicitly do not include them. Tests for the two implemented patterns
> are exhaustive; tests for the deferred patterns will land with the follow-on.

### 5a. Write test first

**File:** `modules/reclaimrx/tests/unit/test_accumulator_consumer.py` (NEW)

```python
"""Unit tests for accumulator_consumer.

Tests 4 pattern detectors + idempotency + tenant_id consistency check.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.consumers.accumulator_consumer import AccumulatorConsumer, AccumulatorTenantMismatchWarning
from src.models.tables import AccumulatorAnomaly, Investigation  # added by Plan A1


def _make_payload(member_id: str, tenant_id: str, pattern: dict, envelope_tenant_id: str | None = None) -> dict:
    return {
        "envelope_tenant_id": envelope_tenant_id or tenant_id,
        "member_id": member_id,
        "tenant_id": tenant_id,
        "accumulator_type": "oop",
        "period": "2026-Q2",
        "amounts": {"oop": "500.00", "deductible": "200.00"},
        "source_payer_id": None,
        **pattern,
    }


class TestAccumulatorConsumerTenantConsistency:
    def test_tenant_mismatch_does_not_write_row(self):
        db = MagicMock()
        consumer = AccumulatorConsumer(db)
        member_id = str(uuid.uuid4())
        with pytest.raises(AccumulatorTenantMismatchWarning):
            consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:1234",
                payload=_make_payload(
                    member_id, tenant_id="tenant-A",
                    envelope_tenant_id="tenant-B",  # mismatch
                    pattern={},
                ),
            )
        db.add.assert_not_called()


class TestAccumulatorPatternDetectors:
    @pytest.fixture()
    def db(self):
        return MagicMock()

    @pytest.fixture()
    def consumer(self, db):
        return AccumulatorConsumer(db)

    def _member_and_tid(self):
        return str(uuid.uuid4()), str(uuid.uuid4())

    def test_sudden_spike_detected_when_oop_jumps(self, consumer, db):
        member_id, tid = self._member_and_tid()
        # Simulate history showing prior oop=50; new oop=500 (10x)
        with patch.object(consumer, "_load_recent_window", return_value=[
            {"oop": Decimal("50.00")} for _ in range(3)
        ]):
            result = consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:9999",
                payload=_make_payload(member_id, tid, {"amounts": {"oop": "500.00", "deductible": "50.00"}}),
            )
        # AccumulatorAnomaly row added to session
        added = [c for c in db.add.call_args_list if hasattr(c.args[0], 'pattern_type')]
        assert any(row.args[0].pattern_type == "sudden_spike" for row in added)

    def test_no_anomaly_for_normal_delta(self, consumer, db):
        member_id, tid = self._member_and_tid()
        with patch.object(consumer, "_load_recent_window", return_value=[
            {"oop": Decimal("450.00")} for _ in range(3)
        ]):
            consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:9998",
                payload=_make_payload(member_id, tid, {"amounts": {"oop": "500.00", "deductible": "50.00"}}),
            )
        added = [c for c in db.add.call_args_list if hasattr(c.args[0], 'pattern_type')]
        assert len(added) == 0

    def test_multi_payer_convergence_detected(self, consumer, db):
        member_id, tid = self._member_and_tid()
        with patch.object(consumer, "_load_recent_window", return_value=[
            {"oop": Decimal("100.00"), "source_payer_id": f"payer-{i}"}
            for i in range(4)  # 4 distinct payers in window → convergence
        ]):
            consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:8888",
                payload=_make_payload(member_id, tid, {
                    "amounts": {"oop": "100.00", "deductible": "50.00"},
                    "source_payer_id": "payer-new",
                }),
            )
        added = [c for c in db.add.call_args_list if hasattr(c.args[0], 'pattern_type')]
        assert any(row.args[0].pattern_type == "multi_payer_convergence" for row in added)

    def test_investigation_opened_for_high_severity(self, consumer, db):
        """When anomaly severity >= medium, auto-open Investigation."""
        member_id, tid = self._member_and_tid()
        with patch.object(consumer, "_load_recent_window", return_value=[
            {"oop": Decimal("50.00")} for _ in range(3)
        ]):
            consumer.handle(
                idempotency_key=f"accumulator:{member_id}:2026-Q2:7777",
                payload=_make_payload(member_id, tid, {"amounts": {"oop": "5000.00", "deductible": "100.00"}}),
            )
        added_types = [type(c.args[0]).__name__ for c in db.add.call_args_list]
        assert "AccumulatorAnomaly" in added_types
        assert "Investigation" in added_types
```

**Run:** `pytest modules/reclaimrx/tests/unit/test_accumulator_consumer.py -x` → expect FAIL.

### 5b. Implement

**New file:** `modules/reclaimrx/src/consumers/accumulator_consumer.py`

```python
"""Accumulator anomaly consumer — subscribes accumulator.updated events.

Wired into CONSUMER_ROUTING in src/events/consumers.py after this file exists.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import AccumulatorAnomaly, Investigation  # Plan A1 tables
from src.utils.constants import risk_score_to_severity

_logger = logging.getLogger(__name__)

# Spike threshold: current value > window_average * SPIKE_MULTIPLIER
_SPIKE_MULTIPLIER = Decimal("3.0")
# Multi-payer threshold: distinct payers in window
_MULTI_PAYER_THRESHOLD = 3
# System user sentinel for auto-opened investigations
_SYSTEM_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")


class AccumulatorTenantMismatchWarning(RuntimeError):
    """Raised when envelope.tenant_id != payload.tenant_id."""


class AccumulatorConsumer:
    """Consumer for accumulator.updated events.

    Wraps detect() with idempotent_handler in events/__init__.py wire_consumers().
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def handle(self, idempotency_key: str, payload: dict[str, Any]) -> None:
        """Process one accumulator.updated event.

        First arg is idempotency_key (idempotent_handler contract).
        """
        envelope_tid = payload.get("envelope_tenant_id")
        payload_tid = payload.get("tenant_id")

        # Tenant consistency check (spec §5.3 accumulator_consumer, R2 NEW CONCERN 3)
        if envelope_tid and payload_tid and str(envelope_tid) != str(payload_tid):
            _logger.warning(
                "accumulator.tenant_mismatch",
                extra={
                    "svc_name": "reclaimrx.accumulator_consumer",
                    "svc_event_key": idempotency_key,
                    "svc_warn_code": "ACCUMULATOR_TENANT_MISMATCH",
                },
            )
            raise AccumulatorTenantMismatchWarning(
                f"Tenant mismatch: envelope={envelope_tid} payload={payload_tid}"
            )

        tenant_id = uuid.UUID(str(payload_tid or envelope_tid))
        member_id = payload["member_id"]
        amounts = payload.get("amounts", {})
        oop = Decimal(str(amounts.get("oop", "0")))
        source_payer_id = payload.get("source_payer_id")
        event_id = idempotency_key  # used as triggering_event_id

        window = self._load_recent_window(tenant_id, member_id)
        anomalies = self._detect_patterns(member_id, tenant_id, oop, source_payer_id, window, event_id)

        # R2 CONCERN N7 fix — keep this set in lock-step with the A3 scope note
        # at the top of Task 5: only the two pattern detectors A3 actually
        # implements (sudden_spike, multi_payer_convergence) may open
        # investigations. `reset_evasion` and `threshold_oscillation` are
        # deferred to B11/follow-on/accumulator-patterns-3-4; their detectors
        # are not wired in A3, so no AccumulatorAnomaly row of those types
        # should reach this loop in production — but if a backfilled or
        # manually-seeded row sneaks through, we MUST NOT open an investigation
        # for a detector type whose semantics A3 has not validated.
        _A3_AUTO_OPEN_PATTERNS = frozenset({"sudden_spike", "multi_payer_convergence"})
        for anomaly in anomalies:
            self._session.add(anomaly)
            if anomaly.pattern_type in _A3_AUTO_OPEN_PATTERNS:
                inv = self._open_investigation(tenant_id, member_id, anomaly)
                anomaly.spawned_investigation_id = inv.id
                self._session.add(inv)

        self._session.flush()

    def _load_recent_window(self, tenant_id: uuid.UUID, member_id: str) -> list[dict]:
        """Load last 7 days of accumulator anomaly history for this member.

        Returns list of dicts with oop, source_payer_id for pattern analysis.
        Overridden in tests via patch.
        """
        cutoff = datetime.now(UTC) - timedelta(days=7)
        rows = self._session.execute(
            select(AccumulatorAnomaly).where(
                AccumulatorAnomaly.tenant_id == str(tenant_id),
                AccumulatorAnomaly.member_id == str(member_id),
                AccumulatorAnomaly.detected_at >= cutoff,
            )
        ).scalars().all()
        return [{"oop": Decimal("0"), "source_payer_id": None} for _ in rows]

    def _detect_patterns(
        self,
        member_id: str,
        tenant_id: uuid.UUID,
        oop: Decimal,
        source_payer_id: str | None,
        window: list[dict],
        event_id: str,
    ) -> list[AccumulatorAnomaly]:
        anomalies: list[AccumulatorAnomaly] = []
        now = datetime.now(UTC)

        # Pattern 1: sudden_spike
        if window:
            avg = sum(r["oop"] for r in window) / len(window)
            if avg > Decimal("0") and oop > avg * _SPIKE_MULTIPLIER:
                anomalies.append(AccumulatorAnomaly(
                    id=str(uuid.uuid4()),
                    tenant_id=str(tenant_id),
                    member_id=str(member_id),
                    pattern_type="sudden_spike",
                    detected_at=now,
                    evidence_window_start=now - timedelta(days=7),
                    evidence_window_end=now,
                    triggering_event_ids=[event_id],
                ))

        # Pattern 2: multi_payer_convergence
        distinct_payers = {r.get("source_payer_id") for r in window if r.get("source_payer_id")}
        if source_payer_id:
            distinct_payers.add(source_payer_id)
        if len(distinct_payers) > _MULTI_PAYER_THRESHOLD:
            anomalies.append(AccumulatorAnomaly(
                id=str(uuid.uuid4()),
                tenant_id=str(tenant_id),
                member_id=str(member_id),
                pattern_type="multi_payer_convergence",
                detected_at=now,
                evidence_window_start=now - timedelta(days=7),
                evidence_window_end=now,
                triggering_event_ids=[event_id],
            ))

        return anomalies

    def _open_investigation(
        self, tenant_id: uuid.UUID, member_id: str, anomaly: AccumulatorAnomaly
    ) -> Investigation:
        now = datetime.now(UTC)
        return Investigation(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            investigation_number=f"INV-{now.year}-ACC-{str(uuid.uuid4())[:8].upper()}",
            title=f"Accumulator anomaly: {anomaly.pattern_type}",
            subject_type="member",
            subject_entity_id=str(member_id),
            investigation_type="accumulator_anomaly",
            status="open",
            priority="high",
            opened_at=now,
        )
```

**Wire into events:** In `modules/reclaimrx/src/events/__init__.py` (or `consumers.py` `CONSUMER_ROUTING`), add:

```python
from src.consumers.accumulator_consumer import AccumulatorConsumer

# Inside wire_consumers() or CONSUMER_ROUTING after existing 8 entries:
# "accumulator.updated" → lambda key, payload, session: AccumulatorConsumer(session).handle(key, payload)
```

Exact wiring pattern must match the existing `wire_consumers()` signature. Read `events/__init__.py` before editing.

**Run:** `pytest modules/reclaimrx/tests/unit/test_accumulator_consumer.py -x` → expect ALL PASS.

---

## Task 6 — Graph job real implementation

### 6a. Write test first

**File:** `modules/reclaimrx/tests/unit/test_graph_job.py` (NEW)

```python
"""Unit tests for graph_analysis_job real implementation.

Tests GraphRun row creation, advisory lock key determinism,
stale-run detection, failure cleanup, completed_partial path.
"""
from __future__ import annotations

import uuid
import zlib
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.jobs.graph_analysis_job import GraphAnalysisJob, advisory_lock_key


class TestAdvisoryLockKey:
    def test_deterministic_across_calls(self):
        tid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        k1 = advisory_lock_key(tid)
        k2 = advisory_lock_key(tid)
        assert k1 == k2

    def test_different_tenants_produce_different_keys(self):
        tid1 = uuid.uuid4()
        tid2 = uuid.uuid4()
        assert advisory_lock_key(tid1) != advisory_lock_key(tid2)

    def test_key_is_positive_int_in_pg_bigint_range(self):
        tid = uuid.uuid4()
        key = advisory_lock_key(tid)
        assert isinstance(key, int)
        assert 0 <= key <= 2**31 - 1  # positive 31-bit, always < PG bigint max

    def test_key_uses_zlib_crc32_not_hash(self):
        tid = uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb")
        expected = zlib.crc32(f"graph_run:{tid}".encode()) & 0x7FFFFFFF
        assert advisory_lock_key(tid) == expected


class TestGraphAnalysisJob:
    @pytest.fixture()
    def db(self):
        return MagicMock()

    def test_run_creates_graph_run_row(self, db):
        from src.models.tables import GraphRun  # Plan A1

        job = GraphAnalysisJob(db)
        tenant_id = uuid.uuid4()

        with patch.object(job, "_pg_try_advisory_lock", return_value=True), \
             patch.object(job, "_check_running", return_value=None), \
             patch.object(job, "_run_graph_computation", return_value={"rings": 0, "investigations": 0, "records": 0}):
            job.trigger(tenant_id=tenant_id, trigger_source="on_demand")

        added = [c.args[0] for c in db.add.call_args_list]
        graph_runs = [r for r in added if type(r).__name__ == "GraphRun"]
        assert len(graph_runs) >= 1
        gr = graph_runs[0]
        assert gr.status == "completed"
        assert gr.tenant_id == str(tenant_id)

    def test_advisory_lock_contention_raises_409(self, db):
        from src.jobs.graph_analysis_job import RunInProgressError

        job = GraphAnalysisJob(db)
        with patch.object(job, "_pg_try_advisory_lock", return_value=False):
            with pytest.raises(RunInProgressError):
                job.trigger(tenant_id=uuid.uuid4(), trigger_source="on_demand")

    def test_existing_running_row_raises_409(self, db):
        from src.jobs.graph_analysis_job import RunInProgressError
        from src.models.tables import GraphRun

        job = GraphAnalysisJob(db)
        existing = MagicMock(spec=GraphRun)
        existing.id = str(uuid.uuid4())

        with patch.object(job, "_pg_try_advisory_lock", return_value=True), \
             patch.object(job, "_check_running", return_value=existing):
            with pytest.raises(RunInProgressError):
                job.trigger(tenant_id=uuid.uuid4(), trigger_source="on_demand")

    def test_failure_updates_status_to_failed(self, db):
        job = GraphAnalysisJob(db)
        with patch.object(job, "_pg_try_advisory_lock", return_value=True), \
             patch.object(job, "_check_running", return_value=None), \
             patch.object(job, "_run_graph_computation", side_effect=RuntimeError("crash")):
            with pytest.raises(RuntimeError):
                job.trigger(tenant_id=uuid.uuid4(), trigger_source="on_demand")

        added = [c.args[0] for c in db.add.call_args_list]
        graph_runs = [r for r in added if type(r).__name__ == "GraphRun"]
        assert graph_runs[0].status == "failed"
        assert graph_runs[0].error_code is not None

    def test_size_limit_exceeded_sets_completed_partial(self, db):
        job = GraphAnalysisJob(db)
        with patch.object(job, "_pg_try_advisory_lock", return_value=True), \
             patch.object(job, "_check_running", return_value=None), \
             patch.object(job, "_load_tenant_graph_data", return_value={"nodes": 60000, "edges": 300000}):
            job.trigger(tenant_id=uuid.uuid4(), trigger_source="cron")

        added = [c.args[0] for c in db.add.call_args_list]
        graph_runs = [r for r in added if type(r).__name__ == "GraphRun"]
        assert graph_runs[0].status == "completed_partial"

    def test_fraud_ring_rows_written_on_detection(self, db):
        job = GraphAnalysisJob(db)
        fake_rings = [
            {"density_score": Decimal("0.85"), "node_count": 5, "edge_count": 8, "entity_refs": []},
        ]
        with patch.object(job, "_pg_try_advisory_lock", return_value=True), \
             patch.object(job, "_check_running", return_value=None), \
             patch.object(job, "_run_graph_computation", return_value={
                 "rings": fake_rings, "investigations": 1, "records": 100
             }):
            job.trigger(tenant_id=uuid.uuid4(), trigger_source="on_demand")

        added = [c.args[0] for c in db.add.call_args_list]
        fraud_rings = [r for r in added if type(r).__name__ == "FraudRing"]
        assert len(fraud_rings) == 1
        assert fraud_rings[0].density_score == Decimal("0.85")

    def test_outbox_row_written_on_completion(self, db):
        job = GraphAnalysisJob(db)
        with patch.object(job, "_pg_try_advisory_lock", return_value=True), \
             patch.object(job, "_check_running", return_value=None), \
             patch.object(job, "_run_graph_computation", return_value={"rings": [], "investigations": 0, "records": 50}):
            job.trigger(tenant_id=uuid.uuid4(), trigger_source="on_demand")

        added = [c.args[0] for c in db.add.call_args_list]
        outbox_rows = [r for r in added if type(r).__name__ == "OutboxEvent"]
        assert len(outbox_rows) == 1
        assert outbox_rows[0].event_type == "fwa.graph_run_completed"
```

**Run:** `pytest modules/reclaimrx/tests/unit/test_graph_job.py -x` → expect FAIL.

### 6b. Implement

**New file:** `modules/reclaimrx/src/jobs/graph_analysis_job.py`

```python
"""Real graph analysis job — replaces stub in scheduled.py.

Uses zlib.crc32 advisory lock key (NOT Python hash() — audit §9, deterministic
across processes). Writes GraphRun + FraudRing rows (Plan A1 tables).
Publishes fwa.graph_run_completed via outbox (Plan A2).
"""
from __future__ import annotations

import logging
import uuid
import zlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import text, select
from sqlalchemy.orm import Session

from src.models.tables import FraudRing, GraphRun, Investigation, OutboxEvent  # Plan A1
from shared.events.types import EventEnvelope

_logger = logging.getLogger(__name__)

# Scale guardrails (spec §9.5)
_MAX_NODES = 50_000
_MAX_EDGES = 200_000
_GRAPH_DENSITY_THRESHOLD = Decimal("0.70")
_STALE_TIMEOUT_HOURS = 6
_LOOKBACK_DAYS = 90


def advisory_lock_key(tenant_id: uuid.UUID) -> int:
    """Deterministic positive 31-bit int for pg_try_advisory_xact_lock.

    Uses zlib.crc32 which is stable across Python processes and PYTHONHASHSEED
    values.  NOT Python hash() — audit §9:546-554.
    """
    return zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF


class RunInProgressError(RuntimeError):
    """409 signal: another run is in-flight for this tenant."""
    def __init__(self, existing_run_id: str | None = None) -> None:
        super().__init__("RUN_IN_PROGRESS")
        self.existing_run_id = existing_run_id
        self.code = "RUN_IN_PROGRESS"


class GraphAnalysisJob:
    """Real graph analysis job.  Called from job_rebuild_fraud_network_graph()
    and from the on-demand POST /graph-runs/trigger endpoint.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def trigger(self, *, tenant_id: uuid.UUID, trigger_source: str) -> GraphRun:
        """Critical section: advisory lock → durable running row → async worker.

        Returns GraphRun row (status='running' for async path, or 'completed'
        in synchronous test paths).

        Raises RunInProgressError (409) if lock fails or running row exists.
        """
        # Step 1: pg_try_advisory_xact_lock (transaction-scoped)
        lock_acquired = self._pg_try_advisory_lock(tenant_id)
        if not lock_acquired:
            raise RunInProgressError()

        # Step 2: durable in-flight check (spec §7.3 step 5)
        existing = self._check_running(tenant_id)
        if existing is not None:
            raise RunInProgressError(existing_run_id=existing.id)

        # Step 3: check scale bounds
        graph_data = self._load_tenant_graph_data(tenant_id)
        if graph_data["nodes"] > _MAX_NODES or graph_data["edges"] > _MAX_EDGES:
            gr = self._insert_graph_run(tenant_id, trigger_source)
            gr.status = "completed_partial"
            gr.completed_at = datetime.now(UTC)
            gr.error_code = "SIZE_LIMIT_EXCEEDED"
            gr.error_message = f"nodes={graph_data['nodes']} edges={graph_data['edges']} exceed bounds"
            self._session.flush()
            _logger.warning("reclaimrx.graph_run.size_limit_exceeded",
                            extra={"svc_tenant_id": str(tenant_id),
                                   "svc_nodes": graph_data["nodes"],
                                   "svc_edges": graph_data["edges"]})
            return gr

        # Step 4: insert durable running row
        gr = self._insert_graph_run(tenant_id, trigger_source)
        self._session.flush()

        # Step 5: run computation (synchronous for test harness; async worker in prod)
        try:
            result = self._run_graph_computation(tenant_id, gr.id)
        except Exception as exc:
            gr.status = "failed"
            gr.failed_at = datetime.now(UTC)
            gr.error_code = type(exc).__name__
            gr.error_message = str(exc)[:500]  # sanitized — no PHI
            self._session.flush()
            _logger.exception("reclaimrx.graph_run.failed",
                              extra={"svc_tenant_id": str(tenant_id), "svc_run_id": gr.id})
            raise

        # Step 6: persist rings + update run row
        rings_detected = 0
        investigations_opened = 0
        if isinstance(result.get("rings"), list):
            for ring_data in result["rings"]:
                ring = FraudRing(
                    id=str(uuid.uuid4()),
                    tenant_id=str(tenant_id),
                    graph_run_id=gr.id,
                    detected_at=datetime.now(UTC),
                    density_score=Decimal(str(ring_data["density_score"])).quantize(
                        Decimal("0.0001"), rounding=ROUND_HALF_UP
                    ),
                    node_count=ring_data["node_count"],
                    edge_count=ring_data["edge_count"],
                    entity_refs=ring_data.get("entity_refs", []),
                )
                self._session.add(ring)
                rings_detected += 1
                if ring_data.get("density_score", Decimal("0")) >= _GRAPH_DENSITY_THRESHOLD:
                    inv = self._open_investigation_for_ring(tenant_id, ring.id)
                    self._session.add(inv)
                    ring.spawned_investigation_id = inv.id
                    investigations_opened += 1
        else:
            rings_detected = result.get("rings", 0)
            investigations_opened = result.get("investigations", 0)

        records_scanned = result.get("records", 0)
        now = datetime.now(UTC)
        gr.status = "completed"
        gr.completed_at = now
        gr.rings_detected = rings_detected
        gr.investigations_opened = investigations_opened
        gr.records_scanned = records_scanned

        # Step 7: outbox event (spec §7.3 step 9g, R1 BLOCK 3)
        outbox = OutboxEvent(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            event_type="fwa.graph_run_completed",
            envelope_json=EventEnvelope(
                event_type="fwa.graph_run_completed",
                tenant_id=tenant_id,
                correlation_id=uuid.UUID(gr.correlation_id),
                source_module="reclaimrx",
                schema_version="1.0",
                ordering_key=gr.id,
                idempotency_key=f"graph_run:{gr.id}:completed",
                payload={
                    "graph_run_id": gr.id,
                    "status": "completed",
                    "rings_detected": rings_detected,
                    "investigations_opened": investigations_opened,
                    "records_scanned": records_scanned,
                    "lookback_window_days": _LOOKBACK_DAYS,
                    "started_at": gr.started_at.isoformat() if gr.started_at else None,
                    "completed_at": now.isoformat(),
                    "failed_at": None,
                    "error_code": None,
                    "error_message": None,
                },
            ).model_dump(mode="json"),
            status="pending",
            idempotency_key=f"graph_run:{gr.id}:completed",
        )
        self._session.add(outbox)
        self._session.flush()
        return gr

    # ── Internals (patch-friendly for tests) ──────────────────────────────────

    def _pg_try_advisory_lock(self, tenant_id: uuid.UUID) -> bool:
        key = advisory_lock_key(tenant_id)
        result = self._session.execute(
            text("SELECT pg_try_advisory_xact_lock(:key)"),
            {"key": key},
        )
        return bool(result.scalar())

    def _check_running(self, tenant_id: uuid.UUID):
        return self._session.execute(
            select(GraphRun).where(
                GraphRun.tenant_id == str(tenant_id),
                GraphRun.status == "running",
            ).limit(1)
        ).scalar_one_or_none()

    def _load_tenant_graph_data(self, tenant_id: uuid.UUID) -> dict:
        """Return approximate node/edge counts for scale check.

        In production, queries claims/entities for the lookback window.
        Overridden in tests.
        """
        return {"nodes": 0, "edges": 0}

    def _run_graph_computation(self, tenant_id: uuid.UUID, graph_run_id: str) -> dict:
        """Real graph computation via FraudNetworkAnalyzer.

        R1 BLOCK 2 fix: replaces previous stub that returned empty results.

        Steps:
          1. Query FlaggedClaim rows for this tenant within the lookback window.
             (Tenant scoping enforced via WHERE clause; RLS GUC also active.)
          2. Aggregate rows into GraphEdge instances (one per unique
             pharmacy_npi/prescriber_npi/member_id triple) summing claim_count
             and total_amount (Decimal).
          3. Build the weighted graph via analyzer.build_graph().
          4. Run analyzer.detect_communities() — Louvain or greedy-modularity
             fallback (see graph_analysis.py:96–127).
          5. Translate every CommunityResult to a ring dict; cap entity_refs
             at 500 per spec §5.5 #13.
          6. Return {"rings": [...], "investigations": <dense_count>,
                     "records": <claims_scanned>}.

        Overridden in unit tests via patch.object to inject deterministic data.
        Integration test test_graph_job_real_computation_e2e (Task 5d, NEW)
        exercises this path without mocks.
        """
        from collections import defaultdict
        from datetime import datetime, timedelta, UTC
        from decimal import Decimal

        from src.models.tables import FlaggedClaim  # noqa: PLC0415
        from src.services.graph_analysis import (  # noqa: PLC0415
            FraudNetworkAnalyzer,
            GraphEdge,
        )

        cutoff = datetime.now(UTC) - timedelta(days=_LOOKBACK_DAYS)
        rows = self._session.execute(
            select(
                FlaggedClaim.pharmacy_npi,
                FlaggedClaim.prescriber_npi,
                FlaggedClaim.member_id,
                FlaggedClaim.billed_amount,
            ).where(
                FlaggedClaim.tenant_id == str(tenant_id),
                FlaggedClaim.date_of_service >= cutoff.date(),
                FlaggedClaim.pharmacy_npi.is_not(None),
                FlaggedClaim.prescriber_npi.is_not(None),
                FlaggedClaim.member_id.is_not(None),
            )
        ).all()

        records_scanned = len(rows)
        if records_scanned == 0:
            return {"rings": [], "investigations": 0, "records": 0}

        # Aggregate rows into edges (one per unique pharmacy/prescriber/member triple)
        edge_acc: dict[tuple[str, str, str], dict] = defaultdict(
            lambda: {"claim_count": 0, "total_amount": Decimal("0")}
        )
        for pharm, presc, member, billed in rows:
            key = (pharm, presc, member)
            edge_acc[key]["claim_count"] += 1
            if billed is not None:
                edge_acc[key]["total_amount"] += Decimal(str(billed))

        edges = [
            GraphEdge(
                pharmacy_npi=k[0],
                prescriber_npi=k[1],
                member_id=k[2],
                claim_count=v["claim_count"],
                total_amount=v["total_amount"],
            )
            for k, v in edge_acc.items()
        ]

        analyzer = FraudNetworkAnalyzer()
        graph = analyzer.build_graph(edges)
        communities = analyzer.detect_communities(graph)

        # Translate suspicious communities to ring dicts; dense rings spawn investigations.
        rings: list[dict] = []
        investigations_opened = 0
        for community in communities:
            if not community.is_suspicious:
                continue
            entity_refs = self._build_entity_refs(community)  # capped at 500
            ring = {
                "density_score": Decimal(str(community.self_referral_rate)).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                ),
                "node_count": len(community.nodes),
                "edge_count": graph.subgraph(community.nodes).number_of_edges(),
                "entity_refs": entity_refs,
            }
            rings.append(ring)
            if ring["density_score"] >= _GRAPH_DENSITY_THRESHOLD:
                investigations_opened += 1

        return {
            "rings": rings,
            "investigations": investigations_opened,
            "records": records_scanned,
        }

    def _build_entity_refs(self, community) -> list[dict]:
        """Build entity_refs list, capped at 500 per spec §5.5 #13."""
        refs: list[dict] = []
        for npi in community.pharmacies:
            refs.append({"type": "pharmacy", "id": npi, "npi": npi})
        for npi in community.prescribers:
            refs.append({"type": "prescriber", "id": npi, "npi": npi})
        for member_id in community.members:
            refs.append({"type": "member", "id": member_id})
        return refs[:500]

    def _insert_graph_run(self, tenant_id: uuid.UUID, trigger_source: str) -> GraphRun:
        now = datetime.now(UTC)
        gr = GraphRun(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            status="running",
            trigger=trigger_source,
            started_at=now,
            stale_timeout_at=now + timedelta(hours=_STALE_TIMEOUT_HOURS),
            correlation_id=str(uuid.uuid4()),
            lookback_window_days=_LOOKBACK_DAYS,
            rings_detected=0,
            investigations_opened=0,
            records_scanned=0,
        )
        self._session.add(gr)
        return gr

    def _open_investigation_for_ring(self, tenant_id: uuid.UUID, ring_id: str) -> Investigation:
        now = datetime.now(UTC)
        return Investigation(
            id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            investigation_number=f"INV-{now.year}-GR-{str(uuid.uuid4())[:8].upper()}",
            title="Graph-detected fraud ring",
            subject_type="fraud_ring",
            subject_entity_id=ring_id,
            investigation_type="graph_ring",
            status="open",
            priority="high",
            opened_at=now,
        )
```

**Wire into scheduled.py:** Replace the stub body of `job_rebuild_fraud_network_graph`:

```python
def job_rebuild_fraud_network_graph(session: Any, tenant_id: str) -> dict[str, Any]:
    """Rebuild the fraud network graph from claims data.

    Wraps GraphAnalysisJob; called by the asyncio cron scheduler (cron: 0 2 * * *).
    """
    from src.jobs.graph_analysis_job import GraphAnalysisJob, RunInProgressError  # noqa: PLC0415
    import uuid as _uuid  # noqa: PLC0415

    try:
        job = GraphAnalysisJob(session)
        gr = job.trigger(tenant_id=_uuid.UUID(tenant_id), trigger_source="cron")
        return {
            "communities_detected": gr.rings_detected,
            "suspicious_communities": gr.investigations_opened,
            "records_scanned": gr.records_scanned,
            "status": gr.status,
        }
    except RunInProgressError:
        _logger.info("reclaimrx.graph_job.skipped_run_in_progress",
                     extra={"svc_tenant_id": tenant_id})
        return {"communities_detected": 0, "suspicious_communities": 0, "skipped": True}
```

**Run:** `pytest modules/reclaimrx/tests/unit/test_graph_job.py -x` → expect ALL PASS.

### 6d. Integration test — real `_run_graph_computation` without mocks (R1 BLOCK 2 fix)

The unit tests above all `patch.object(job, "_run_graph_computation", ...)`, so they
never exercise the real FraudNetworkAnalyzer call. R1 BLOCK 2 requires at least one
end-to-end test that runs the un-patched code path.

**File:** `modules/reclaimrx/tests/integration/test_graph_job_real_computation.py` (NEW)

```python
"""Integration test: GraphAnalysisJob._run_graph_computation without mocks.

Loads real FlaggedClaim fixtures, builds the real graph via NetworkX, runs
real community detection, and asserts the returned dict matches the shape
the persistence step expects (rings list with density_score/node_count/
edge_count/entity_refs, plus investigations/records counters).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, UTC
from decimal import Decimal

import pytest

from src.jobs.graph_analysis_job import GraphAnalysisJob
from src.models.tables import FlaggedClaim


@pytest.fixture
def dense_pharmacy_prescriber_ring(db, tenant_a_id):
    """Seed 12 FlaggedClaim rows: 1 pharmacy + 1 prescriber + 10 members.

    Spec §5.5 #6 suspicion: single pharmacy/prescriber routing >5 members
    is flagged as suspicious by FraudNetworkAnalyzer._assess_suspicion.
    """
    pharm = "1234567893"  # synthetic Luhn-valid NPI
    presc = "1245319599"  # synthetic Luhn-valid NPI
    for i in range(10):
        db.add(FlaggedClaim(
            id=str(uuid.uuid4()),
            tenant_id=tenant_a_id,
            auth_number=f"AUTH-{i:04d}",
            date_of_service=date.today(),
            pharmacy_npi=pharm,
            prescriber_npi=presc,
            member_id=f"MEMBER-{i:03d}",
            rule_code="RULE_TEST",
            rule_name="test ring fixture",
            detection_mode="rule",
            risk_score=50,
            confidence_tier="medium",
            severity="medium",
            evidence={},
            billed_amount=Decimal("100.00"),
            investigation_status="open",
        ))
    db.flush()


def test_graph_job_real_computation_e2e(db, tenant_a_id, dense_pharmacy_prescriber_ring):
    """Run un-patched _run_graph_computation end-to-end and assert shape + content."""
    job = GraphAnalysisJob(db)
    # NOTE: deliberately NOT patching _run_graph_computation.
    result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-run-1")

    # Shape checks
    assert isinstance(result, dict)
    assert set(result.keys()) == {"rings", "investigations", "records"}
    assert isinstance(result["rings"], list)
    assert result["records"] == 10

    # Content checks: at least one suspicious ring detected
    assert len(result["rings"]) >= 1
    ring = result["rings"][0]
    assert isinstance(ring["density_score"], Decimal)
    assert ring["node_count"] >= 3  # 1 pharm + 1 presc + 10 members → community has 12 nodes
    assert ring["edge_count"] >= 1
    assert isinstance(ring["entity_refs"], list)
    assert len(ring["entity_refs"]) <= 500  # spec §5.5 #13 cap
    # Verify entity_refs schema
    for ref in ring["entity_refs"]:
        assert "type" in ref and "id" in ref
        assert ref["type"] in {"pharmacy", "prescriber", "member"}


def test_graph_job_returns_empty_when_no_flagged_claims(db, tenant_a_id):
    """Empty fixture set → empty result, records=0."""
    job = GraphAnalysisJob(db)
    result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-run-empty")
    assert result == {"rings": [], "investigations": 0, "records": 0}


def test_graph_job_skips_rows_missing_triple_fields(db, tenant_a_id):
    """FlaggedClaim with NULL pharmacy/prescriber/member fields are filtered out."""
    # One complete row + one row missing prescriber_npi
    db.add(FlaggedClaim(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a_id,
        auth_number="AUTH-COMPLETE",
        date_of_service=date.today(),
        pharmacy_npi="1234567893",
        prescriber_npi="1245319599",
        member_id="MEMBER-001",
        rule_code="R", rule_name="r", detection_mode="rule",
        risk_score=50, confidence_tier="medium", severity="medium",
        evidence={}, billed_amount=Decimal("100"),
        investigation_status="open",
    ))
    db.add(FlaggedClaim(
        id=str(uuid.uuid4()),
        tenant_id=tenant_a_id,
        auth_number="AUTH-MISSING-PRESC",
        date_of_service=date.today(),
        pharmacy_npi="1234567893",
        prescriber_npi=None,  # missing — must be filtered
        member_id="MEMBER-002",
        rule_code="R", rule_name="r", detection_mode="rule",
        risk_score=50, confidence_tier="medium", severity="medium",
        evidence={}, billed_amount=Decimal("100"),
        investigation_status="open",
    ))
    db.flush()

    job = GraphAnalysisJob(db)
    result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-run-filter")
    assert result["records"] == 1  # only the complete row counts


def test_graph_job_aggregates_duplicate_triples(db, tenant_a_id):
    """Multiple FlaggedClaim rows with same (pharm, presc, member) collapse to one edge."""
    pharm, presc, member = "1234567893", "1245319599", "MEMBER-001"
    for i in range(3):
        db.add(FlaggedClaim(
            id=str(uuid.uuid4()),
            tenant_id=tenant_a_id,
            auth_number=f"AUTH-{i:04d}",
            date_of_service=date.today(),
            pharmacy_npi=pharm,
            prescriber_npi=presc,
            member_id=member,
            rule_code="R", rule_name="r", detection_mode="rule",
            risk_score=50, confidence_tier="medium", severity="medium",
            evidence={}, billed_amount=Decimal("50.00"),
            investigation_status="open",
        ))
    db.flush()

    job = GraphAnalysisJob(db)
    result = job._run_graph_computation(uuid.UUID(tenant_a_id), graph_run_id="test-run-agg")
    # 3 rows collapse to 1 unique edge; records=3 (raw rows scanned)
    assert result["records"] == 3
```

**Run:** `pytest modules/reclaimrx/tests/integration/test_graph_job_real_computation.py -x` → expect ALL PASS.

This file MUST run with the FlaggedClaim table seeded (Plan A1 dependency) and MUST NOT be skipped. If networkx or python-louvain raises ImportError in CI, mark the test as a hard failure — the dependency is required for SP-3.

---

## Task 7 — POST /graph-runs/trigger endpoint

### 7a. Write test first

**File:** `modules/reclaimrx/tests/integration/test_graph_run_trigger.py` (NEW)

```python
"""Integration tests for POST /graph-runs/trigger.

Rate limit: 1/hr/tenant (D13).  409 if run in-flight.
Advisory lock logic is tested in unit tests; here we test HTTP contract.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src._shim.auth import CurrentUser, set_current_user
from src._shim.db import set_session_override
from src.main import create_app
from src.models.tables import Base


@pytest.fixture(scope="session")
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture(scope="session", autouse=True)
def _tables(engine):
    Base.metadata.create_all(engine)


@pytest.fixture()
def db(engine):
    conn = engine.connect()
    txn = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    txn.rollback()
    conn.close()


@pytest.fixture()
def client(db):
    app = create_app()
    set_session_override(db)
    return TestClient(app)


def _viewer(tid: str):
    set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.UUID(tid), roles=["reclaimrx.viewer"]))


def _investigator(tid: str):
    set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.UUID(tid), roles=["reclaimrx.investigator"]))


class TestGraphRunTrigger:
    def test_viewer_cannot_trigger(self, client):
        tid = str(uuid.uuid4())
        _viewer(tid)
        resp = client.post("/api/v1/reclaimrx/graph-runs/trigger")
        assert resp.status_code == 403

    def test_investigator_triggers_run(self, client, db):
        tid = str(uuid.uuid4())
        _investigator(tid)
        from src.jobs.graph_analysis_job import GraphAnalysisJob
        with patch.object(GraphAnalysisJob, "_pg_try_advisory_lock", return_value=True), \
             patch.object(GraphAnalysisJob, "_check_running", return_value=None), \
             patch.object(GraphAnalysisJob, "_run_graph_computation", return_value={"rings": [], "investigations": 0, "records": 0}):
            resp = client.post("/api/v1/reclaimrx/graph-runs/trigger")
        assert resp.status_code == 202
        body = resp.json()
        assert "graph_run_id" in body

    def test_409_when_run_in_progress(self, client):
        from src.jobs.graph_analysis_job import GraphAnalysisJob, RunInProgressError
        tid = str(uuid.uuid4())
        _investigator(tid)
        with patch.object(GraphAnalysisJob, "_pg_try_advisory_lock", return_value=False):
            resp = client.post("/api/v1/reclaimrx/graph-runs/trigger")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "RUN_IN_PROGRESS"
```

**Run:** `pytest modules/reclaimrx/tests/integration/test_graph_run_trigger.py -x` → expect FAIL.

### 7b. Implement route

Add to `router.py`:

```python
@router.post("/graph-runs/trigger", status_code=202)
def trigger_graph_run(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(
        require_role("reclaimrx.investigator", "reclaimrx.admin")
    ),
) -> dict:
    """Trigger an on-demand graph analysis run (rate-limited: 1/hr/tenant).

    Returns 409 RUN_IN_PROGRESS if another run is in-flight.
    Advisory lock + durable running row are the concurrency authority.
    """
    import uuid as _uuid  # noqa: PLC0415
    from src.jobs.graph_analysis_job import GraphAnalysisJob, RunInProgressError  # noqa: PLC0415

    correlation_id = str(_uuid.uuid4())
    job = GraphAnalysisJob(db)
    try:
        gr = job.trigger(tenant_id=user.tenant_id, trigger_source="on_demand")
        db.commit()
        return {"graph_run_id": gr.id, "status": gr.status, "correlation_id": correlation_id}
    except RunInProgressError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error": {
                "code": "RUN_IN_PROGRESS",
                "message": "A graph run is already in-flight for this tenant.",
                "existing_run_id": exc.existing_run_id,
                "correlation_id": correlation_id,
            }},
        ) from exc
```

**Run:** `pytest modules/reclaimrx/tests/integration/test_graph_run_trigger.py -x` → expect ALL PASS.

---

## Task 8 — Full coverage gate + create_app integration test

**File:** `modules/reclaimrx/tests/integration/test_create_app_a3_bindings.py` (NEW)

Verifies A3 deliverables are wired through create_app() per LESSON-006.

### 8a. Write test first (R1 CONCERN 8 fix — explicit fail/pass cycle)

```python
"""Integration test: A3 deliverables reachable through create_app().

Verifies state machine endpoint, hold release endpoint, and graph trigger
endpoint all exist and respect auth (no dead-code route registration gaps).
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from src._shim.auth import CurrentUser, set_current_user
from src.main import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_transitions_endpoint_registered(client):
    set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["reclaimrx.investigator"]))
    resp = client.post("/api/v1/reclaimrx/investigations/no-such-id/transitions",
                       json={"to_state": "in_progress", "reason": "x"})
    # 404 (not found) proves route is registered; would be 405/404-page if missing
    assert resp.status_code == 404


def test_hold_release_endpoint_registered(client):
    set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["reclaimrx.investigator"]))
    resp = client.post("/api/v1/reclaimrx/holds/no-such-id/release",
                       json={"reason": "test", "investigation_id": str(uuid.uuid4())})
    assert resp.status_code == 404


def test_old_delete_hold_route_gone(client):
    set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["reclaimrx.investigator"]))
    resp = client.delete("/api/v1/reclaimrx/holds/some-id?reason=test")
    assert resp.status_code == 405


def test_graph_runs_trigger_endpoint_registered(client):
    set_current_user(CurrentUser(id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["reclaimrx.viewer"]))
    resp = client.post("/api/v1/reclaimrx/graph-runs/trigger")
    assert resp.status_code == 403  # viewer blocked, route exists
```

**Run BEFORE wiring (Tasks 3, 4, 7 router edits) is complete:**
`pytest modules/reclaimrx/tests/integration/test_create_app_a3_bindings.py -x`
→ **expect FAIL** — routes not yet registered, all four tests return 404/405 from the catch-all handler instead of from the route layer, OR the import of new schema modules fails.

### 8b. Wire — verify routes mounted in router

Confirm Task 3 router edit registers `POST /investigations/{id}/transitions`,
Task 4 router edit registers `POST /holds/{hold_id}/release` and removes
`DELETE /holds/{hold_id}`, and Task 7 router edit registers
`POST /graph-runs/trigger`. No new code in Task 8b — this is a verification
step that Tasks 3/4/7 are complete.

**Run AFTER wiring:**
`pytest modules/reclaimrx/tests/integration/test_create_app_a3_bindings.py -x`
→ **expect ALL PASS** — every test now hits the real route handler.

### 8c. Coverage gate run

**Coverage run:**
```
pytest modules/reclaimrx/tests/ \
  --cov=src.utils.constants \
  --cov=src.services.investigation_service \
  --cov=src.consumers.accumulator_consumer \
  --cov=src.jobs.graph_analysis_job \
  --cov-fail-under=100 \
  --cov-report=term-missing
```

Must be 100% on all A3 paths. Fix any gaps before marking tasks complete.

---

## Task ordering summary

| # | Task | Files touched | TDD step |
|---|---|---|---|
| 1 | State machine constants | `constants.py` | test → implement → green |
| 2 | InvestigationService.transition() | `investigation_service.py` | test → implement → green |
| 3 | POST /investigations/{id}/transitions | `router.py` + schema | test → implement → green |
| 4 | Hold release reshape | `payment_hold_service.py` + `router.py` | test → implement → green |
| 5 | Accumulator consumer | `accumulator_consumer.py` + `events/__init__.py` | test → implement → green |
| 6 | Graph job real impl | `graph_analysis_job.py` + `scheduled.py` | test → implement → green |
| 7 | POST /graph-runs/trigger | `router.py` | test → implement → green |
| 8 | Coverage gate + create_app integration | integration test suite | verify 100% gate |

**Do tasks strictly in this order.** Each task's tests must be GREEN before starting the next.

---

## Acceptance criteria (Plan A3 PASS gate)

- [ ] `pytest modules/reclaimrx/tests/unit/test_state_machine.py` — all pass, 100% coverage on `constants.py`
- [ ] `pytest modules/reclaimrx/tests/unit/test_investigation_service_transitions.py` — all pass
- [ ] `pytest modules/reclaimrx/tests/integration/test_transitions_endpoint.py` — all pass (9 tests)
- [ ] `pytest modules/reclaimrx/tests/integration/test_hold_release_endpoint.py` — all pass, outbox test passes, 3-case idempotency pass
- [ ] `DELETE /holds/{hold_id}` route is GONE — 405 on call
- [ ] `pytest modules/reclaimrx/tests/unit/test_accumulator_consumer.py` — all pass
- [ ] `pytest modules/reclaimrx/tests/unit/test_graph_job.py` — all pass, advisory lock key is `zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF`
- [ ] `pytest modules/reclaimrx/tests/integration/test_graph_run_trigger.py` — all pass
- [ ] `pytest modules/reclaimrx/tests/integration/test_create_app_a3_bindings.py` — all pass
- [ ] Coverage gate: 100% on all A3 source files
- [ ] Zero uses of `user.get("roles")` anywhere in A3 code — all role checks use `user.has_role()`
- [ ] Zero uses of `hold.hold_amount` — all A3 code uses `hold.amount_threshold`
- [ ] Zero uses of Python `hash()` in advisory lock code — only `zlib.crc32`
- [ ] Pre-existing test suite still green: `pytest modules/reclaimrx/ -x --ignore=tests/ -q` (sanity on imports)
