"""Plan hierarchy service — PRD §2-3.

Handles: org/group/plan/subgroup CRUD, inheritance resolver, cloning,
plan promotion/rollback, bulk import.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, UTC
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from shared.utils.money import money, TWO_PLACES
from src.models.tables import (
    Group,
    Organization,
    Plan,
    PricingModelConfig,
    ProgramType,
    SubGroup,
)


class HierarchyService:
    """Business logic for plan hierarchy management."""

    def __init__(self, db: Session, tenant_id: uuid.UUID) -> None:
        self._db = db
        self._tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Organizations
    # ------------------------------------------------------------------

    def create_organization(self, data: dict[str, Any]) -> Organization:
        org = Organization(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            name=data["name"],
            tin=data.get("tin"),
            contact_name=data.get("contact_name"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            effective_date=data["effective_date"],
            termination_date=data.get("termination_date"),
            status="active",
        )
        self._db.add(org)
        self._db.flush()
        return org

    def get_organization(self, org_id: uuid.UUID) -> Organization | None:
        return (
            self._db.query(Organization)
            .filter(
                Organization.id == org_id,
                Organization.tenant_id == self._tenant_id,
            )
            .first()
        )

    def list_organizations(self, status: str | None = None) -> list[Organization]:
        q = self._db.query(Organization).filter(
            Organization.tenant_id == self._tenant_id
        )
        if status:
            q = q.filter(Organization.status == status)
        return q.order_by(Organization.name).all()

    def update_organization(self, org_id: uuid.UUID, data: dict[str, Any]) -> Organization | None:
        org = self.get_organization(org_id)
        if org is None:
            return None
        for field, value in data.items():
            if value is not None and hasattr(org, field):
                setattr(org, field, value)
        self._db.flush()
        return org

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    def create_group(self, data: dict[str, Any]) -> Group:
        group = Group(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            organization_id=data["organization_id"],
            name=data["name"],
            group_id_external=data.get("group_id_external"),
            bin_number=data.get("bin_number"),
            pcn=data.get("pcn"),
            billing_entity_ref=data.get("billing_entity_ref"),
            effective_date=data["effective_date"],
            termination_date=data.get("termination_date"),
            status="active",
        )
        self._db.add(group)
        self._db.flush()
        return group

    def get_group(self, group_id: uuid.UUID) -> Group | None:
        return (
            self._db.query(Group)
            .filter(
                Group.id == group_id,
                Group.tenant_id == self._tenant_id,
            )
            .first()
        )

    def list_groups(
        self, organization_id: uuid.UUID | None = None, status: str | None = None
    ) -> list[Group]:
        q = self._db.query(Group).filter(Group.tenant_id == self._tenant_id)
        if organization_id:
            q = q.filter(Group.organization_id == organization_id)
        if status:
            q = q.filter(Group.status == status)
        return q.order_by(Group.name).all()

    def update_group(self, group_id: uuid.UUID, data: dict[str, Any]) -> Group | None:
        group = self.get_group(group_id)
        if group is None:
            return None
        for field, value in data.items():
            if value is not None and hasattr(group, field):
                setattr(group, field, value)
        self._db.flush()
        return group

    # ------------------------------------------------------------------
    # Plans
    # ------------------------------------------------------------------

    def create_plan(self, data: dict[str, Any]) -> Plan:
        plan = Plan(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            group_id=data["group_id"],
            name=data["name"],
            plan_code=data.get("plan_code"),
            program_type_id=data.get("program_type_id"),
            pricing_model_id=data.get("pricing_model_id"),
            formulary_id=data.get("formulary_id"),
            network_id=data.get("network_id"),
            effective_date=data["effective_date"],
            termination_date=data.get("termination_date"),
            status="draft",
            benefit_config=data.get("benefit_config"),
            glp1_config=data.get("glp1_config"),
            cash_pay_comparison_enabled=data.get("cash_pay_comparison_enabled", False),
            accumulator_config=data.get("accumulator_config"),
            deductible_individual=self._coerce_decimal(data.get("deductible_individual")),
            deductible_family=self._coerce_decimal(data.get("deductible_family")),
            oop_max_individual=self._coerce_decimal(data.get("oop_max_individual")),
            oop_max_family=self._coerce_decimal(data.get("oop_max_family")),
        )
        self._db.add(plan)
        self._db.flush()
        return plan

    def get_plan(self, plan_id: uuid.UUID) -> Plan | None:
        return (
            self._db.query(Plan)
            .filter(
                Plan.id == plan_id,
                Plan.tenant_id == self._tenant_id,
            )
            .first()
        )

    def list_plans(
        self,
        group_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> list[Plan]:
        q = self._db.query(Plan).filter(Plan.tenant_id == self._tenant_id)
        if group_id:
            q = q.filter(Plan.group_id == group_id)
        if status:
            q = q.filter(Plan.status == status)
        return q.order_by(Plan.name).all()

    def update_plan(self, plan_id: uuid.UUID, data: dict[str, Any]) -> Plan | None:
        plan = self.get_plan(plan_id)
        if plan is None:
            return None
        money_fields = {
            "deductible_individual", "deductible_family",
            "oop_max_individual", "oop_max_family",
        }
        for field, value in data.items():
            if field in money_fields:
                setattr(plan, field, self._coerce_decimal(value))
            elif value is not None and hasattr(plan, field):
                setattr(plan, field, value)
        self._db.flush()
        return plan

    def resolve_plan(self, plan_id: uuid.UUID) -> dict[str, Any]:
        """Resolve effective plan config with inheritance (PRD §2).

        Inheritance chain: Organization → Group → Plan → SubGroup.
        Each level overrides only explicitly set fields.
        """
        plan = self.get_plan(plan_id)
        if plan is None:
            return {}
        group = self.get_group(plan.group_id)
        org = self.get_organization(group.organization_id) if group else None

        # Build inheritance chain (most general → most specific)
        chain: list[dict[str, Any]] = []
        if org:
            chain.append({"level": "organization", "id": str(org.id), "name": org.name})
        if group:
            chain.append({"level": "group", "id": str(group.id), "name": group.name})
        chain.append({"level": "plan", "id": str(plan.id), "name": plan.name})

        # Merge configs — plan overrides group inherits, group overrides org
        resolved: dict[str, Any] = {}
        if org and org.metadata_:
            resolved.update(org.metadata_)
        if group and group.inherited_config:
            resolved.update(group.inherited_config)
        # Apply plan-specific fields
        plan_fields: dict[str, Any] = {
            "benefit_config": plan.benefit_config or {},
            "formulary_id": str(plan.formulary_id) if plan.formulary_id else None,
            "network_id": str(plan.network_id) if plan.network_id else None,
            "pricing_model_id": str(plan.pricing_model_id) if plan.pricing_model_id else None,
            "cash_pay_comparison_enabled": plan.cash_pay_comparison_enabled,
            "glp1_config": plan.glp1_config or {},
            "accumulator_config": plan.accumulator_config or {},
            "deductible_individual": str(plan.deductible_individual)
            if plan.deductible_individual
            else None,
            "deductible_family": str(plan.deductible_family) if plan.deductible_family else None,
            "oop_max_individual": str(plan.oop_max_individual)
            if plan.oop_max_individual
            else None,
            "oop_max_family": str(plan.oop_max_family) if plan.oop_max_family else None,
        }
        resolved.update(plan_fields)

        return {
            "plan_id": str(plan_id),
            "tenant_id": str(self._tenant_id),
            "resolved_at": datetime.now(UTC).isoformat(),
            "effective_config": resolved,
            "inheritance_chain": chain,
        }

    def clone_plan(
        self,
        source_plan_id: uuid.UUID,
        new_name: str,
        target_group_id: uuid.UUID | None = None,
        copy_formulary: bool = True,
        copy_network: bool = True,
    ) -> Plan:
        """Clone a plan with all settings (PRD §8)."""
        source = self.get_plan(source_plan_id)
        if source is None:
            raise ValueError(f"Plan {source_plan_id} not found")

        clone = Plan(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            group_id=target_group_id or source.group_id,
            name=new_name,
            plan_code=None,  # New plan gets no code initially
            program_type_id=source.program_type_id,
            pricing_model_id=source.pricing_model_id,
            formulary_id=source.formulary_id if copy_formulary else None,
            network_id=source.network_id if copy_network else None,
            effective_date=source.effective_date,
            termination_date=source.termination_date,
            status="draft",
            benefit_config=dict(source.benefit_config) if source.benefit_config else None,
            glp1_config=dict(source.glp1_config) if source.glp1_config else None,
            cash_pay_comparison_enabled=source.cash_pay_comparison_enabled,
            accumulator_config=dict(source.accumulator_config)
            if source.accumulator_config
            else None,
            deductible_individual=source.deductible_individual,
            deductible_family=source.deductible_family,
            oop_max_individual=source.oop_max_individual,
            oop_max_family=source.oop_max_family,
        )
        self._db.add(clone)
        self._db.flush()
        return clone

    def promote_plan(self, plan_id: uuid.UUID) -> Plan | None:
        """Promote plan from draft/sandbox to active (PRD §10)."""
        plan = self.get_plan(plan_id)
        if plan is None:
            return None
        if plan.status == "active":
            return plan
        plan.status = "active"
        plan.sandbox_version = (plan.sandbox_version or 1) + 1
        self._db.flush()
        return plan

    def rollback_plan(self, plan_id: uuid.UUID) -> Plan | None:
        """Rollback plan to draft status (PRD §10)."""
        plan = self.get_plan(plan_id)
        if plan is None:
            return None
        plan.status = "draft"
        self._db.flush()
        return plan

    def bulk_import_plans(self, csv_content: str) -> dict[str, Any]:
        """Bulk create/update plans from CSV (PRD §8).

        CSV columns: name, group_id_external, effective_date, termination_date,
        deductible_individual, oop_max_individual, status.
        Returns summary of created/updated/error counts.
        """
        reader = csv.DictReader(io.StringIO(csv_content))
        created = 0
        updated = 0
        errors: list[dict[str, Any]] = []

        for row_num, row in enumerate(reader, start=2):
            try:
                # Minimal required field validation
                if not row.get("name"):
                    errors.append({"row": row_num, "error": "Missing required field: name"})
                    continue
                if not row.get("group_id"):
                    errors.append({"row": row_num, "error": "Missing required field: group_id"})
                    continue

                group_id = uuid.UUID(row["group_id"])
                effective_date = date.fromisoformat(row["effective_date"])

                # Check existing by plan_code if provided
                existing = None
                if row.get("plan_code"):
                    existing = (
                        self._db.query(Plan)
                        .filter(
                            Plan.tenant_id == self._tenant_id,
                            Plan.plan_code == row["plan_code"],
                        )
                        .first()
                    )

                plan_data: dict[str, Any] = {
                    "group_id": group_id,
                    "name": row["name"],
                    "plan_code": row.get("plan_code"),
                    "effective_date": effective_date,
                    "termination_date": date.fromisoformat(row["termination_date"])
                    if row.get("termination_date")
                    else None,
                    "deductible_individual": row.get("deductible_individual") or None,
                    "oop_max_individual": row.get("oop_max_individual") or None,
                }
                if existing:
                    self.update_plan(existing.id, plan_data)
                    updated += 1
                else:
                    self.create_plan(plan_data)
                    created += 1
            except (ValueError, KeyError) as exc:
                errors.append({"row": row_num, "error": str(exc)})

        return {
            "total_rows": created + updated + len(errors),
            "created": created,
            "updated": updated,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # SubGroups
    # ------------------------------------------------------------------

    def create_subgroup(self, data: dict[str, Any]) -> SubGroup:
        sg = SubGroup(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            plan_id=data["plan_id"],
            name=data["name"],
            override_config=data.get("override_config"),
            effective_date=data["effective_date"],
            termination_date=data.get("termination_date"),
        )
        self._db.add(sg)
        self._db.flush()
        return sg

    def get_subgroup(self, sg_id: uuid.UUID) -> SubGroup | None:
        return (
            self._db.query(SubGroup)
            .filter(
                SubGroup.id == sg_id,
                SubGroup.tenant_id == self._tenant_id,
            )
            .first()
        )

    def list_subgroups(self, plan_id: uuid.UUID) -> list[SubGroup]:
        return (
            self._db.query(SubGroup)
            .filter(
                SubGroup.tenant_id == self._tenant_id,
                SubGroup.plan_id == plan_id,
            )
            .all()
        )

    def update_subgroup(self, sg_id: uuid.UUID, data: dict[str, Any]) -> SubGroup | None:
        sg = self.get_subgroup(sg_id)
        if sg is None:
            return None
        for field, value in data.items():
            if value is not None and hasattr(sg, field):
                setattr(sg, field, value)
        self._db.flush()
        return sg

    # ------------------------------------------------------------------
    # Program Types
    # ------------------------------------------------------------------

    def create_program_type(self, data: dict[str, Any]) -> ProgramType:
        pt = ProgramType(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            code=data["code"],
            name=data["name"],
            description=data.get("description"),
            default_rules=data.get("default_rules"),
        )
        self._db.add(pt)
        self._db.flush()
        return pt

    def list_program_types(self) -> list[ProgramType]:
        return (
            self._db.query(ProgramType)
            .filter(ProgramType.tenant_id == self._tenant_id, ProgramType.is_active.is_(True))
            .order_by(ProgramType.name)
            .all()
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
