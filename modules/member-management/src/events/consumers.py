"""Member module event consumers.

Consumes claim.adjudicated and claim.reversed from the adjudication module.
Each handler wrapped with idempotent_handler pattern (manual here since
we receive raw payload dicts, not EventEnvelope directly).

Unknown payload fields are ignored (forward compatibility with schema_version).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from shared.events.idempotency import InMemoryIdempotencyStore, idempotent_handler
from src.services.accumulator_db import AccumulatorDbService, AccumulatorNotFoundError

_acc_db_svc = AccumulatorDbService()


class ClaimAdjudicatedConsumer:
    """Consumes claim.adjudicated → applies patient_pay to accumulator."""

    def __init__(
        self,
        db: Session,
        idempotency_store: InMemoryIdempotencyStore,
    ) -> None:
        self._db = db
        self._store = idempotency_store

    async def handle(self, idempotency_key: str, payload: dict) -> None:
        if await self._store.seen(idempotency_key, consumer_name="claim.adjudicated"):
            return
        await self._process(payload)
        await self._store.mark(idempotency_key, consumer_name="claim.adjudicated")

    async def _process(self, payload: dict) -> None:
        tenant_id = uuid.UUID(payload["tenant_id"])
        accumulator_id = uuid.UUID(payload["accumulator_id"])
        claim_id = uuid.UUID(payload["claim_id"])
        patient_pay = Decimal(payload["patient_pay"])
        # Unknown fields silently ignored (forward compat)
        _acc_db_svc.apply_claim(
            db=self._db,
            tenant_id=tenant_id,
            accumulator_id=accumulator_id,
            amount=patient_pay,
            claim_id=claim_id,
        )


class ClaimReversedConsumer:
    """Consumes claim.reversed → reverses patient_pay from accumulator."""

    def __init__(
        self,
        db: Session,
        idempotency_store: InMemoryIdempotencyStore,
    ) -> None:
        self._db = db
        self._store = idempotency_store

    async def handle(self, idempotency_key: str, payload: dict) -> None:
        if await self._store.seen(idempotency_key, consumer_name="claim.reversed"):
            return
        await self._process(payload)
        await self._store.mark(idempotency_key, consumer_name="claim.reversed")

    async def _process(self, payload: dict) -> None:
        tenant_id = uuid.UUID(payload["tenant_id"]) if "tenant_id" in payload else None
        accumulator_id = uuid.UUID(payload["accumulator_id"])
        claim_id = uuid.UUID(payload["claim_id"])
        patient_pay = Decimal(payload["patient_pay"])

        if tenant_id is None:
            return

        _acc_db_svc.reverse_claim(
            db=self._db,
            tenant_id=tenant_id,
            accumulator_id=accumulator_id,
            amount=patient_pay,
            claim_id=claim_id,
        )
