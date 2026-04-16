"""Program management service — CRUD + state machine transitions.

Handles all business logic for programs including:
  - State machine enforcement (draft → pending_review → approved → onboarding → active → suspended → terminated)
  - BIN/PCN conflict detection
  - Activation guard (cannot activate before onboarding is complete)
  - Wizard save/resume state management
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog
from sqlalchemy.orm import Session

from src.models.tables import (
    Contract,
    ManufacturerProgramConfig,
    OnboardingStepLog,
    OnboardingWorkflow,
    Program,
    ProgramActivityLog,
    ProgramDrug,
)
from src.services.onboarding import (
    POST_LAUNCH_MONITORING_DAYS,
    build_default_steps,
    is_onboarding_complete,
)

logger = structlog.get_logger(__name__)

# Valid state machine transitions
_VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["pending_review"],
    "pending_review": ["approved", "draft"],
    "approved": ["onboarding", "draft"],
    "onboarding": ["active", "draft"],
    "active": ["suspended", "terminated"],
    "suspended": ["active", "terminated"],
    "terminated": [],
}

# Wizard steps 1-8
WIZARD_STEP_COUNT = 8


class ProgramStateError(Exception):
    """Raised when an invalid state transition is attempted."""


class BinPcnConflictError(Exception):
    """Raised when a BIN/PCN pair is already in use by another active program."""


class OnboardingIncompleteError(Exception):
    """Raised when attempting to activate a program before onboarding is complete."""


def transition_program_status(
    program: Program,
    new_status: str,
    actor_id: uuid.UUID,
    db: Session,
    correlation_id: uuid.UUID | None = None,
) -> Program:
    """Transition a program to a new status, enforcing state machine rules.

    Logs the transition to ProgramActivityLog.
    Raises ProgramStateError for invalid transitions.
    Raises OnboardingIncompleteError when activating without complete onboarding.
    """
    if new_status not in _VALID_TRANSITIONS.get(program.status, []):
        raise ProgramStateError(
            f"Cannot transition program from {program.status!r} to {new_status!r}. "
            f"Valid transitions: {_VALID_TRANSITIONS.get(program.status, [])}"
        )

    # Guard: cannot activate before onboarding is complete
    if new_status == "active":
        workflow = (
            db.query(OnboardingWorkflow)
            .filter_by(program_id=program.id, tenant_id=program.tenant_id)
            .first()
        )
        if workflow is not None and not is_onboarding_complete(workflow.steps):
            raise OnboardingIncompleteError(
                f"Program {program.id} cannot be activated — onboarding workflow is not complete. "
                "Complete all required onboarding steps first."
            )

    before_state = {"status": program.status}
    program.status = new_status

    # Set post-launch monitoring flag on activation
    if new_status == "active":
        program.post_launch_monitoring = True
        program.post_launch_until = datetime.now(UTC) + timedelta(days=POST_LAUNCH_MONITORING_DAYS)
    elif new_status == "terminated":
        program.post_launch_monitoring = False

    after_state = {"status": new_status}

    log_entry = ProgramActivityLog(
        tenant_id=program.tenant_id,
        program_id=program.id,
        entity_type="program",
        entity_id=program.id,
        action=f"status_transition:{program.status}",
        performed_by=actor_id,
        before_state=before_state,
        after_state=after_state,
        correlation_id=correlation_id or uuid.uuid4(),
    )
    db.add(log_entry)

    logger.info(
        "program_status_transition",
        extra={
            "svc_program_id": str(program.id),
            "svc_tenant_id": str(program.tenant_id),
            "svc_from_status": before_state["status"],
            "svc_to_status": new_status,
            "svc_actor_id": str(actor_id),
        },
    )

    return program


def check_bin_pcn_conflict(
    tenant_id: uuid.UUID,
    bin_number: str | None,
    pcn: str | None,
    exclude_program_id: uuid.UUID | None,
    db: Session,
) -> str | None:
    """Check whether a BIN/PCN pair is already used by an active program.

    Returns the conflicting program's ID as a string if conflict exists, else None.
    """
    if bin_number is None:
        return None

    query = db.query(Program).filter(
        Program.tenant_id == tenant_id,
        Program.bin_number == bin_number,
        Program.pcn == pcn,
        Program.status.in_(["active", "onboarding", "approved"]),
    )
    if exclude_program_id is not None:
        query = query.filter(Program.id != exclude_program_id)

    conflict = query.first()
    return str(conflict.id) if conflict else None


def apply_brd_to_program(
    program: Program,
    config: dict[str, Any],
    actor_id: uuid.UUID,
    db: Session,
    correlation_id: uuid.UUID | None = None,
) -> None:
    """Atomically apply parsed BRD configuration to a program.

    Creates/updates ProgramDrug rows and updates BIN/PCN on the program.
    All changes are in one transaction — caller commits.

    Raises BinPcnConflictError if BIN/PCN already in use.
    """
    corr = correlation_id or uuid.uuid4()

    # --- BIN/PCN conflict check ---
    bin_pcn = config.get("bin_pcn", {})
    new_bin = bin_pcn.get("bin_number")
    new_pcn = bin_pcn.get("pcn")
    conflict_id = check_bin_pcn_conflict(
        program.tenant_id, new_bin, new_pcn, program.id, db
    )
    if conflict_id:
        raise BinPcnConflictError(
            f"BIN/PCN {new_bin}/{new_pcn} is already assigned to program {conflict_id}"
        )

    before_state = {
        "bin_number": program.bin_number,
        "pcn": program.pcn,
    }

    # Apply BIN/PCN
    program.bin_number = new_bin
    program.pcn = new_pcn

    # --- Drug entries: dedup by NDC ---
    drug_entries = config.get("drug_entries", [])
    # Fetch existing program drugs
    existing_drugs = (
        db.query(ProgramDrug)
        .filter_by(program_id=program.id, tenant_id=program.tenant_id)
        .all()
    )
    existing_by_ndc = {d.ndc: d for d in existing_drugs}

    for entry in drug_entries:
        ndc = entry["ndc"]

        def _dec_or_none(val: str | None) -> Decimal | None:
            if val is None:
                return None
            return Decimal(val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        copay = _dec_or_none(entry.get("copay_amount"))
        cap = _dec_or_none(entry.get("per_fill_cap"))
        annual = _dec_or_none(entry.get("annual_max"))

        if ndc in existing_by_ndc:
            drug = existing_by_ndc[ndc]
            drug.copay_amount = copay
            drug.per_fill_cap = cap
            drug.annual_max = annual
            drug.is_active = True
        else:
            drug = ProgramDrug(
                tenant_id=program.tenant_id,
                program_id=program.id,
                ndc=ndc,
                copay_amount=copay,
                per_fill_cap=cap,
                annual_max=annual,
            )
            db.add(drug)

    after_state = {
        "bin_number": new_bin,
        "pcn": new_pcn,
        "drug_count": len(drug_entries),
    }

    log_entry = ProgramActivityLog(
        tenant_id=program.tenant_id,
        program_id=program.id,
        entity_type="program",
        entity_id=program.id,
        action="brd_applied",
        performed_by=actor_id,
        before_state=before_state,
        after_state=after_state,
        correlation_id=corr,
    )
    db.add(log_entry)


def rollback_brd_apply(
    program: Program,
    snapshot: dict[str, Any],
    actor_id: uuid.UUID,
    db: Session,
) -> None:
    """Roll back a previously applied BRD to the snapshot state.

    snapshot shape: {"bin_number": ..., "pcn": ..., "ndcs_to_remove": [...]}
    """
    before_state = {"bin_number": program.bin_number, "pcn": program.pcn}

    program.bin_number = snapshot.get("bin_number")
    program.pcn = snapshot.get("pcn")

    # Remove drugs that were added by the apply
    for ndc in snapshot.get("ndcs_to_remove", []):
        drug = (
            db.query(ProgramDrug)
            .filter_by(program_id=program.id, tenant_id=program.tenant_id, ndc=ndc)
            .first()
        )
        if drug:
            db.delete(drug)

    log_entry = ProgramActivityLog(
        tenant_id=program.tenant_id,
        program_id=program.id,
        entity_type="program",
        entity_id=program.id,
        action="brd_rollback",
        performed_by=actor_id,
        before_state=before_state,
        after_state={"bin_number": program.bin_number, "pcn": program.pcn},
        correlation_id=uuid.uuid4(),
    )
    db.add(log_entry)
