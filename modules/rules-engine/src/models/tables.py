"""SQLAlchemy models for the rules-engine module.

All money columns are NUMERIC — never Float.
Every tenant-owned table inherits TenantScopedMixin.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "rules_engine"


class RulesBase(DeclarativeBase):
    """Declarative base for rules-engine module."""


# ---------------------------------------------------------------------------
# RULE TYPE DEFINITIONS
# ---------------------------------------------------------------------------


class RuleType(RulesBase):
    """Defines a type of rule (e.g. copay, quantity limit, step therapy).

    Each rule type has a unique code, a category, and a JSONB schema
    describing the parameters it accepts.
    """

    __tablename__ = "rule_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_rule_type_code"),
        Index("idx_rule_type_category", "category"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # pricing/coverage/authorization/specialty
    parameter_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    instances: Mapped[list[RuleInstance]] = relationship(back_populates="rule_type", lazy="selectin")


# ---------------------------------------------------------------------------
# RULE INSTANCES
# ---------------------------------------------------------------------------


class RuleInstance(RulesBase, TenantScopedMixin):
    """A configured instance of a rule type, bound to a plan or program."""

    __tablename__ = "rule_instances"
    __table_args__ = (
        Index("idx_rule_inst_tenant_plan", "tenant_id", "plan_id"),
        Index("idx_rule_inst_tenant_program", "tenant_id", "program_id"),
        Index("idx_rule_inst_tenant_status", "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.rule_types.id"), nullable=False
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    program_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # active/inactive/draft

    rule_type: Mapped[RuleType] = relationship(back_populates="instances", lazy="selectin")
    versions: Mapped[list[RuleVersion]] = relationship(back_populates="rule_instance", lazy="selectin")


# ---------------------------------------------------------------------------
# RULE VERSIONS (audit trail of parameter changes)
# ---------------------------------------------------------------------------


class RuleVersion(RulesBase, TenantScopedMixin):
    """Immutable snapshot of a rule instance's parameters at a point in time."""

    __tablename__ = "rule_versions"
    __table_args__ = (
        UniqueConstraint("rule_instance_id", "version", name="uq_rule_version"),
        Index("idx_rule_ver_tenant_inst", "tenant_id", "rule_instance_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_instance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.rule_instances.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    rule_instance: Mapped[RuleInstance] = relationship(back_populates="versions", lazy="selectin")


# ---------------------------------------------------------------------------
# RULE PIPELINES
# ---------------------------------------------------------------------------


class RulePipeline(RulesBase, TenantScopedMixin):
    """Ordered sequence of rule instances to execute for a plan."""

    __tablename__ = "rule_pipelines"
    __table_args__ = (
        Index("idx_pipeline_tenant_plan", "tenant_id", "plan_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    ordered_rule_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


# ---------------------------------------------------------------------------
# RULE EXECUTION LOG
# ---------------------------------------------------------------------------


class RuleExecutionLog(RulesBase, TenantScopedMixin):
    """Audit record of a single rule execution against a claim."""

    __tablename__ = "rule_execution_logs"
    __table_args__ = (
        Index("idx_exec_log_tenant_claim", "tenant_id", "claim_id"),
        Index("idx_exec_log_tenant_rule", "tenant_id", "rule_instance_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    rule_instance_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)  # pass/reject/modify/flag
    input_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# MAC PRICING
# ---------------------------------------------------------------------------


class MACPrice(RulesBase, TenantScopedMixin):
    """Maximum Allowable Cost price for a given NDC."""

    __tablename__ = "mac_prices"
    __table_args__ = (
        Index("idx_mac_tenant_ndc", "tenant_id", "ndc11"),
        Index("idx_mac_tenant_eff", "tenant_id", "effective_date"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ndc11: Mapped[str] = mapped_column(String(11), nullable=False)
    mac_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)


# ---------------------------------------------------------------------------
# STATE REGULATORY RULES
# ---------------------------------------------------------------------------


class StateRegulatoryRule(RulesBase, TenantScopedMixin):
    """State-specific regulatory constraints (e.g. biosimilar substitution laws)."""

    __tablename__ = "state_regulatory_rules"
    __table_args__ = (
        Index("idx_state_reg_tenant_state", "tenant_id", "state_code"),
        Index("idx_state_reg_tenant_cat", "tenant_id", "rule_category"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    rule_category: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)


# ---------------------------------------------------------------------------
# THERAPEUTIC ALTERNATIVES
# ---------------------------------------------------------------------------


class TherapeuticAlternative(RulesBase, TenantScopedMixin):
    """Maps a source NDC to a clinically equivalent alternative with savings estimate."""

    __tablename__ = "therapeutic_alternatives"
    __table_args__ = (
        Index("idx_ther_alt_tenant_src", "tenant_id", "source_ndc"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    alternative_ndc: Mapped[str] = mapped_column(String(11), nullable=False)
    savings_estimate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    clinical_equivalence: Mapped[str | None] = mapped_column(String(50), nullable=True)
