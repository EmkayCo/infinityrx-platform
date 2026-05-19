"""Investigation service — business logic for the investigation workflow state machine."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import Investigation, InvestigationActivity, Recovery
from decimal import ROUND_HALF_UP

from src.utils.constants import VALID_STATUS_TRANSITIONS
from src.utils.money import money


def _now() -> datetime:
    return datetime.now(UTC)


def _generate_investigation_number() -> str:
    suffix = str(uuid.uuid4()).replace("-", "").upper()[:8]
    year = datetime.now(UTC).year
    return f"INV-{year}-{suffix}"


class InvestigationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Creation ──────────────────────────────────────────────────────────────

    def create_investigation(
        self,
        *,
        tenant_id: uuid.UUID,
        subject_type: str,
        subject_entity_id: str,
        subject_name: str | None,
        investigation_type: str,
        title: str,
        priority: str,
        user_id: uuid.UUID,
        client_id: uuid.UUID | None = None,
        program_id: uuid.UUID | None = None,
        date_range_start: object | None = None,
        date_range_end: object | None = None,
    ) -> Investigation:
        inv = Investigation(
            tenant_id=str(tenant_id),
            investigation_number=_generate_investigation_number(),
            title=title,
            subject_type=subject_type,
            subject_entity_id=subject_entity_id,
            subject_name=subject_name,
            investigation_type=investigation_type,
            priority=priority,
            status="open",
            client_id=str(client_id) if client_id else None,
            program_id=str(program_id) if program_id else None,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
        )
        self._session.add(inv)
        self._session.flush()

        self._add_activity(
            investigation_id=inv.id,
            tenant_id=tenant_id,
            activity_type="investigation_opened",
            description=f"Investigation {inv.investigation_number} opened.",
            performed_by=user_id,
        )
        return inv

    # ── Status Transitions ────────────────────────────────────────────────────

    def update_status(
        self,
        *,
        tenant_id: uuid.UUID,
        investigation_id: str,
        new_status: str,
        user_id: uuid.UUID,
        notes: str | None = None,
    ) -> Investigation:
        inv = self._get_or_raise(tenant_id, investigation_id)
        allowed = VALID_STATUS_TRANSITIONS.get(inv.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition from '{inv.status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )
        inv.status = new_status
        inv.updated_at = _now()
        if new_status in ("closed_confirmed", "closed_false_positive", "closed_no_action"):
            inv.resolved_at = _now()

        self._add_activity(
            investigation_id=inv.id,
            tenant_id=tenant_id,
            activity_type="status_changed",
            description=f"Status changed to '{new_status}'" + (f": {notes}" if notes else "."),
            performed_by=user_id,
        )
        return inv

    # ── Assignment ────────────────────────────────────────────────────────────

    def assign(
        self,
        *,
        tenant_id: uuid.UUID,
        investigation_id: str,
        assignee_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Investigation:
        inv = self._get_or_raise(tenant_id, investigation_id)
        inv.assigned_to = str(assignee_id)
        inv.assigned_at = _now()
        inv.updated_at = _now()
        self._add_activity(
            investigation_id=inv.id,
            tenant_id=tenant_id,
            activity_type="assigned",
            description=f"Investigation assigned to {assignee_id}.",
            performed_by=user_id,
        )
        return inv

    # ── Recovery Records ──────────────────────────────────────────────────────

    def create_recovery(
        self,
        *,
        tenant_id: uuid.UUID,
        investigation_id: str,
        recovery_method: str,
        amount: Decimal,
        confidence_tier: str,
        methodology_tag: str,
        user_id: uuid.UUID,
    ) -> Recovery:
        self._get_or_raise(tenant_id, investigation_id)
        safe_amount = money(amount)
        recovery = Recovery(
            investigation_id=investigation_id,
            tenant_id=str(tenant_id),
            recovery_method=recovery_method,
            amount=safe_amount,
            confidence_tier=confidence_tier,
            methodology_tag=methodology_tag,
            status="estimated",
        )
        self._session.add(recovery)
        self._session.flush()
        return recovery

    def update_recovery_status(
        self,
        *,
        tenant_id: uuid.UUID,
        recovery_id: str,
        new_status: str,
        user_id: uuid.UUID,
    ) -> Recovery:
        recovery = self._session.execute(
            select(Recovery).where(
                Recovery.id == recovery_id,
                Recovery.tenant_id == str(tenant_id),
            )
        ).scalar_one_or_none()
        if recovery is None:
            raise ValueError(f"Recovery {recovery_id} not found for tenant")
        recovery.status = new_status
        recovery.updated_at = _now()
        return recovery

    # ── Activities ────────────────────────────────────────────────────────────

    def add_activity(
        self,
        *,
        tenant_id: uuid.UUID,
        investigation_id: str,
        activity_type: str,
        description: str,
        user_id: uuid.UUID,
        file_id: str | None = None,
    ) -> InvestigationActivity:
        self._get_or_raise(tenant_id, investigation_id)
        return self._add_activity(
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            activity_type=activity_type,
            description=description,
            performed_by=user_id,
            file_id=file_id,
        )

    def get_timeline(
        self,
        *,
        tenant_id: uuid.UUID,
        investigation_id: str,
    ) -> list[InvestigationActivity]:
        self._get_or_raise(tenant_id, investigation_id)
        return list(
            self._session.execute(
                select(InvestigationActivity)
                .where(
                    InvestigationActivity.investigation_id == investigation_id,
                    InvestigationActivity.tenant_id == str(tenant_id),
                )
                .order_by(InvestigationActivity.created_at.asc())
            ).scalars()
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    def list_investigations(
        self,
        *,
        tenant_id: uuid.UUID,
        status: str | None = None,
        subject_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Investigation]:
        stmt = select(Investigation).where(Investigation.tenant_id == str(tenant_id))
        if status:
            stmt = stmt.where(Investigation.status == status)
        if subject_type:
            stmt = stmt.where(Investigation.subject_type == subject_type)
        stmt = stmt.order_by(Investigation.opened_at.desc()).limit(limit).offset(offset)
        return list(self._session.execute(stmt).scalars())

    def get(self, *, tenant_id: uuid.UUID, investigation_id: str) -> Investigation | None:
        return self._session.execute(
            select(Investigation).where(
                Investigation.id == investigation_id,
                Investigation.tenant_id == str(tenant_id),
            )
        ).scalar_one_or_none()

    def set_litigation_hold(
        self,
        *,
        tenant_id: uuid.UUID,
        investigation_id: str,
        placed_by: uuid.UUID,
    ) -> Investigation:
        inv = self._get_or_raise(tenant_id, investigation_id)
        inv.litigation_hold = True
        inv.litigation_hold_placed_by = str(placed_by)
        inv.litigation_hold_placed_at = _now()
        inv.updated_at = _now()
        self._add_activity(
            investigation_id=inv.id,
            tenant_id=tenant_id,
            activity_type="litigation_hold_placed",
            description="Litigation hold placed on investigation.",
            performed_by=placed_by,
        )
        return inv

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_or_raise(self, tenant_id: uuid.UUID, investigation_id: str) -> Investigation:
        inv = self._session.execute(
            select(Investigation).where(
                Investigation.id == investigation_id,
                Investigation.tenant_id == str(tenant_id),
            )
        ).scalar_one_or_none()
        if inv is None:
            raise ValueError(f"Investigation {investigation_id} not found for tenant {tenant_id}")
        return inv

    def _add_activity(
        self,
        *,
        investigation_id: str,
        tenant_id: uuid.UUID,
        activity_type: str,
        description: str,
        performed_by: uuid.UUID,
        file_id: str | None = None,
    ) -> InvestigationActivity:
        activity = InvestigationActivity(
            investigation_id=investigation_id,
            tenant_id=str(tenant_id),
            activity_type=activity_type,
            description=description,
            performed_by=str(performed_by),
            file_id=file_id,
        )
        self._session.add(activity)
        self._session.flush()
        return activity

    # ── State machine transition ──────────────────────────────────────────────

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
    ) -> "Investigation":
        """Validate and apply a status transition.  Writes append-only audit row.

        Raises
        ------
        ValueError(code='NOT_FOUND')        -- investigation absent or wrong tenant.
        InvalidTransitionError              -- illegal transition, missing role, missing fields.
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

        # Raises InvalidTransitionError on violation -- let it propagate unchanged
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
            tenant_id=str(tenant_id),
            activity_type="status_transition",
            description=f"Status changed from '{from_state}' to '{to_state}'. Reason: {reason}",
            performed_by=str(user_id),
        )
        self._session.add(activity)
        self._session.flush()
        return inv
