"""Atomic control number generation for ISA/GS/ST sequences.

Concurrency safety: uses SELECT … FOR UPDATE on the
edi.control_number_sequences row so two concurrent callers never receive
the same number.  All increments are committed in the caller's transaction.
"""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SequenceType(str, Enum):
    ISA = "isa"
    GS = "gs"
    ST = "st"


async def next_control_number(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    trading_partner_id: uuid.UUID,
    seq_type: SequenceType,
) -> int:
    """Return the next available control number, atomically.

    Uses SELECT … FOR UPDATE to prevent duplicate numbers under concurrent
    load (PRD §9 — 50 concurrent 835 generations must produce distinct ISA
    control numbers).
    """
    row = await db.execute(
        text(
            """
            SELECT id, current_value, max_value
            FROM edi.control_number_sequences
            WHERE tenant_id = :tenant_id
              AND trading_partner_id = :partner_id
              AND sequence_type = :seq_type
            FOR UPDATE
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "partner_id": str(trading_partner_id),
            "seq_type": seq_type.value,
        },
    )
    record = row.fetchone()
    if record is None:
        await db.execute(
            text(
                """
                INSERT INTO edi.control_number_sequences
                    (id, tenant_id, trading_partner_id, sequence_type, current_value, max_value)
                VALUES
                    (:id, :tenant_id, :partner_id, :seq_type, 1, 999999999)
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": str(tenant_id),
                "partner_id": str(trading_partner_id),
                "seq_type": seq_type.value,
            },
        )
        return 1

    seq_id, current, max_val = record
    if current >= max_val:
        next_val = 1
    else:
        next_val = current + 1

    await db.execute(
        text(
            "UPDATE edi.control_number_sequences SET current_value = :val WHERE id = :id"
        ),
        {"val": next_val, "id": str(seq_id)},
    )
    return next_val
