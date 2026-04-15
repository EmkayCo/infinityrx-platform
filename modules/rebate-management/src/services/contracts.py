"""Rebate contract management service.

Lifecycle: draft → negotiated → executed → active → amended → terminated
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import (
    RebateContract,
    RebateContractNDC,
    RebateTier,
)

# Valid lifecycle transitions
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"negotiated", "terminated"},
    "negotiated": {"executed", "draft", "terminated"},
    "executed": {"active", "terminated"},
    "active": {"amended", "terminated"},
    "amended": {"active", "terminated"},
    "terminated": set(),
}


class ContractLifecycleError(ValueError):
    """Raised when an invalid lifecycle transition is attempted."""


class ContractService:
    """CRUD and lifecycle management for rebate contracts."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_contract(
        self,
        tenant_id: uuid.UUID,
        manufacturer_id: uuid.UUID,
        manufacturer_name: str,
        contract_number: str,
        contract_type: str,
        effective_date: Any,
        payment_frequency: str = "quarterly",
        termination_date: Any | None = None,
        minimum_volume_threshold: Decimal | None = None,
        bfsf_only: bool = False,
        notes: str | None = None,
    ) -> RebateContract:
        now = datetime.now(UTC)
        contract = RebateContract(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            manufacturer_id=manufacturer_id,
            manufacturer_name=manufacturer_name,
            contract_number=contract_number,
            contract_type=contract_type,
            status="draft",
            effective_date=effective_date,
            termination_date=termination_date,
            payment_frequency=payment_frequency,
            minimum_volume_threshold=minimum_volume_threshold,
            bfsf_only=bfsf_only,
            notes=notes,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._db.add(contract)
        self._db.flush()
        return contract

    def get_contract(
        self, tenant_id: uuid.UUID, contract_id: uuid.UUID
    ) -> RebateContract | None:
        return (
            self._db.query(RebateContract)
            .filter(
                RebateContract.tenant_id == tenant_id,
                RebateContract.id == contract_id,
            )
            .first()
        )

    def list_contracts(
        self, tenant_id: uuid.UUID, status: str | None = None
    ) -> list[RebateContract]:
        q = self._db.query(RebateContract).filter(
            RebateContract.tenant_id == tenant_id
        )
        if status:
            q = q.filter(RebateContract.status == status)
        return q.all()

    def transition_status(
        self,
        tenant_id: uuid.UUID,
        contract_id: uuid.UUID,
        new_status: str,
        approved_by: uuid.UUID | None = None,
    ) -> RebateContract:
        contract = self.get_contract(tenant_id, contract_id)
        if contract is None:
            raise ValueError(f"Contract {contract_id} not found")
        allowed = _VALID_TRANSITIONS.get(contract.status, set())
        if new_status not in allowed:
            raise ContractLifecycleError(
                f"Cannot transition contract from {contract.status!r} to {new_status!r}. "
                f"Allowed: {sorted(allowed)}"
            )
        now = datetime.now(UTC)
        contract.status = new_status
        contract.updated_at = now
        if new_status in ("executed", "active") and approved_by:
            contract.approved_by = approved_by
            contract.approved_at = now
        self._db.flush()
        return contract

    def amend_contract(
        self,
        tenant_id: uuid.UUID,
        contract_id: uuid.UUID,
        updates: dict[str, Any],
    ) -> RebateContract:
        """Create an amendment — increments version, transitions to amended."""
        contract = self.get_contract(tenant_id, contract_id)
        if contract is None:
            raise ValueError(f"Contract {contract_id} not found")
        if contract.status not in ("active",):
            raise ContractLifecycleError(
                f"Only active contracts can be amended; current status: {contract.status!r}"
            )
        now = datetime.now(UTC)
        for field, value in updates.items():
            if hasattr(contract, field) and field not in (
                "id",
                "tenant_id",
                "created_at",
                "version",
                "status",
            ):
                setattr(contract, field, value)
        contract.version += 1
        contract.status = "amended"
        contract.parent_contract_id = contract.parent_contract_id or contract_id
        contract.updated_at = now
        self._db.flush()
        return contract

    # --- NDC terms ---

    def add_ndc_term(
        self,
        tenant_id: uuid.UUID,
        contract_id: uuid.UUID,
        ndc11: str,
        rebate_type: str,
        effective_date: Any,
        rebate_percent: Decimal | None = None,
        rebate_per_unit: Decimal | None = None,
        drug_name: str | None = None,
        formulary_position: str | None = None,
        formulary_position_bonus_percent: Decimal | None = None,
        growth_bonus_percent: Decimal | None = None,
        termination_date: Any | None = None,
    ) -> RebateContractNDC:
        ndc_term = RebateContractNDC(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contract_id=contract_id,
            ndc11=ndc11,
            drug_name=drug_name,
            rebate_type=rebate_type,
            rebate_percent=rebate_percent,
            rebate_per_unit=rebate_per_unit,
            formulary_position=formulary_position,
            formulary_position_bonus_percent=formulary_position_bonus_percent,
            growth_bonus_percent=growth_bonus_percent,
            effective_date=effective_date,
            termination_date=termination_date,
            created_at=datetime.now(UTC),
        )
        self._db.add(ndc_term)
        self._db.flush()
        return ndc_term

    def add_tier(
        self,
        tenant_id: uuid.UUID,
        contract_id: uuid.UUID,
        tier_name: str,
        tier_type: str,
        threshold_value: Decimal,
        rebate_percent: Decimal,
    ) -> RebateTier:
        tier = RebateTier(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contract_id=contract_id,
            tier_name=tier_name,
            tier_type=tier_type,
            threshold_value=threshold_value,
            rebate_percent=rebate_percent,
            created_at=datetime.now(UTC),
        )
        self._db.add(tier)
        self._db.flush()
        return tier
