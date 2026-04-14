"""Member event publishers.

All events use EventEnvelope with:
- ordering_key = str(member_id)
- idempotency_key = business-level deterministic key
- schema_version = "1.0"
- Decimal amounts serialized as str()
- No PHI in payloads
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope


class MemberEventPublisher:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def member_enrolled(
        self,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        await self._bus.publish(EventEnvelope(
            event_type="member.enrolled",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="member-management",
            schema_version="1.0",
            ordering_key=str(member_id),
            idempotency_key=f"member.enrolled:{member_id}",
            payload={"member_id": str(member_id)},
        ))

    async def member_updated(
        self,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        changed_fields: list[str],
        correlation_id: uuid.UUID,
    ) -> None:
        await self._bus.publish(EventEnvelope(
            event_type="member.updated",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="member-management",
            schema_version="1.0",
            ordering_key=str(member_id),
            idempotency_key=f"member.updated:{member_id}:{correlation_id}",
            payload={
                "member_id": str(member_id),
                "changed_fields": changed_fields,
            },
        ))

    async def member_terminated(
        self,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        termination_reason: str,
        termination_date: date,
        correlation_id: uuid.UUID,
    ) -> None:
        await self._bus.publish(EventEnvelope(
            event_type="member.terminated",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="member-management",
            schema_version="1.0",
            ordering_key=str(member_id),
            idempotency_key=f"member.terminated:{member_id}:{termination_date.isoformat()}",
            payload={
                "member_id": str(member_id),
                "termination_reason": termination_reason,
                "termination_date": termination_date.isoformat(),
            },
        ))

    async def member_plan_changed(
        self,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        old_plan_id: uuid.UUID | None,
        new_plan_id: uuid.UUID | None,
        correlation_id: uuid.UUID,
    ) -> None:
        await self._bus.publish(EventEnvelope(
            event_type="member.plan_changed",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="member-management",
            schema_version="1.0",
            ordering_key=str(member_id),
            idempotency_key=f"member.plan_changed:{member_id}:{correlation_id}",
            payload={
                "member_id": str(member_id),
                "old_plan_id": str(old_plan_id) if old_plan_id else None,
                "new_plan_id": str(new_plan_id) if new_plan_id else None,
            },
        ))

    async def accumulator_updated(
        self,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        accumulator_id: uuid.UUID,
        accumulator_type: str,
        accumulated_amount: Decimal,
        limit_amount: Decimal,
        applied: Decimal,
        claim_id: uuid.UUID | None,
        correlation_id: uuid.UUID,
    ) -> None:
        await self._bus.publish(EventEnvelope(
            event_type="member.accumulator_updated",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="member-management",
            schema_version="1.0",
            ordering_key=str(member_id),
            idempotency_key=f"member.accumulator_updated:{accumulator_id}:{claim_id}",
            payload={
                "member_id": str(member_id),
                "accumulator_id": str(accumulator_id),
                "accumulator_type": accumulator_type,
                "accumulated_amount": str(accumulated_amount),
                "limit_amount": str(limit_amount),
                "applied": str(applied),
                "claim_id": str(claim_id) if claim_id else None,
            },
        ))

    async def benefit_phase_changed(
        self,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        accumulator_id: uuid.UUID,
        old_phase: str,
        new_phase: str,
        troop: Decimal,
        correlation_id: uuid.UUID,
    ) -> None:
        await self._bus.publish(EventEnvelope(
            event_type="member.benefit_phase_changed",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="member-management",
            schema_version="1.0",
            ordering_key=str(member_id),
            idempotency_key=f"member.benefit_phase_changed:{accumulator_id}:{new_phase}",
            payload={
                "member_id": str(member_id),
                "accumulator_id": str(accumulator_id),
                "old_phase": old_phase,
                "new_phase": new_phase,
                "troop": str(troop),
            },
        ))

    async def cob_changed(
        self,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        action: str,
        payer_sequence: str,
        correlation_id: uuid.UUID,
    ) -> None:
        await self._bus.publish(EventEnvelope(
            event_type="member.cob_changed",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="member-management",
            schema_version="1.0",
            ordering_key=str(member_id),
            idempotency_key=f"member.cob_changed:{member_id}:{payer_sequence}:{correlation_id}",
            payload={
                "member_id": str(member_id),
                "action": action,
                "payer_sequence": payer_sequence,
            },
        ))

    async def member_merged(
        self,
        tenant_id: uuid.UUID,
        surviving_member_id: uuid.UUID,
        merged_member_id: uuid.UUID,
        correlation_id: uuid.UUID,
    ) -> None:
        await self._bus.publish(EventEnvelope(
            event_type="member.merged",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="member-management",
            schema_version="1.0",
            ordering_key=str(surviving_member_id),
            idempotency_key=f"member.merged:{surviving_member_id}:{merged_member_id}",
            payload={
                "surviving_member_id": str(surviving_member_id),
                "merged_member_id": str(merged_member_id),
            },
        ))

    async def retroactive_enrollment(
        self,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        effective_date: date,
        retroactive_days: int,
        correlation_id: uuid.UUID,
    ) -> None:
        await self._bus.publish(EventEnvelope(
            event_type="member.retroactive_enrollment",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="member-management",
            schema_version="1.0",
            ordering_key=str(member_id),
            idempotency_key=f"member.retroactive_enrollment:{member_id}:{effective_date.isoformat()}",
            payload={
                "member_id": str(member_id),
                "effective_date": effective_date.isoformat(),
                "retroactive_days": retroactive_days,
            },
        ))
