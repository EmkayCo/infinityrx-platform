"""Member merge workflow.

Moves all related records (coverage, accumulators, COB, ledger) from
duplicate to surviving member. Marks duplicate as 'merged' with pointer.
Cross-tenant isolation: both members must belong to the same tenant.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from src.models.tables import (
    Accumulator,
    AccumulatorLedger,
    CobRecord,
    CoveragePeriod,
    Member,
)


class MergeServiceError(ValueError):
    pass


class MergeConflictError(MergeServiceError):
    pass


class MergeService:
    """Stateless merge orchestrator."""

    def _load_member(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        label: str,
    ) -> Member:
        m = db.query(Member).filter_by(id=member_id, tenant_id=tenant_id).first()
        if m is None:
            raise MergeServiceError(f"{label} member not found: {member_id}")
        return m

    def merge(
        self,
        db: Session,
        tenant_id: uuid.UUID,
        surviving_id: uuid.UUID,
        duplicate_id: uuid.UUID,
        operator_id: uuid.UUID,
    ) -> None:
        if surviving_id == duplicate_id:
            raise MergeServiceError("surviving and duplicate are the same member")

        surviving = self._load_member(db, tenant_id, surviving_id, "surviving")
        duplicate = self._load_member(db, tenant_id, duplicate_id, "duplicate")

        if duplicate.status == "merged":
            raise MergeServiceError(
                f"duplicate member {duplicate_id} is already merged"
            )

        # Transfer coverage periods
        db.query(CoveragePeriod).filter_by(
            member_id=duplicate_id, tenant_id=tenant_id
        ).update({"member_id": surviving_id})

        # Transfer accumulators (and their ledger entries)
        acc_ids = [
            row.id
            for row in db.query(Accumulator.id).filter_by(
                member_id=duplicate_id, tenant_id=tenant_id
            ).all()
        ]
        if acc_ids:
            db.query(Accumulator).filter(
                Accumulator.id.in_(acc_ids)
            ).update({"member_id": surviving_id}, synchronize_session="fetch")

        # Transfer COB records
        db.query(CobRecord).filter_by(
            member_id=duplicate_id, tenant_id=tenant_id
        ).update({"member_id": surviving_id})

        # Mark duplicate as merged
        duplicate.status = "merged"
        duplicate.merged_into_id = surviving_id

        db.flush()
