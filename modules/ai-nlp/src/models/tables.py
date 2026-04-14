"""SQLAlchemy ORM models for the ai_nlp schema.

All tenant-owned tables inherit TenantScopedMixin so the session-level
tenant isolation loader criteria apply automatically.

No Float anywhere — Numeric for all decimal columns per financial-precision rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.db.base import Base
from shared.db.tenant_context import TenantScopedMixin

SCHEMA = "ai_nlp"


def _uuid_pk() -> Mapped[UUID]:
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


def _ts_now() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Service requests — audit log for every AI call
# ---------------------------------------------------------------------------


class AiNlpServiceRequest(Base, TenantScopedMixin):
    __tablename__ = "service_requests"
    __table_args__ = (
        Index("ix_ai_service_requests_tenant_type", "tenant_id", "service_type"),
        Index("ix_ai_service_requests_module", "requesting_module"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    service_type: Mapped[str] = mapped_column(String(100), nullable=False)
    requesting_module: Mapped[str] = mapped_column(String(100), nullable=False)
    requesting_entity_type: Mapped[str | None] = mapped_column(String(100))
    requesting_entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    input_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_size_tokens: Mapped[int | None] = mapped_column(Integer)
    input_file_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    output_text: Mapped[str | None] = mapped_column(Text)
    output_structured: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence_score: Mapped[Any | None] = mapped_column(Numeric(5, 4))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[Any | None] = mapped_column(Numeric(10, 6))
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="pending"
    )
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    requires_human_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_outcome: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------


class AiNlpPromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(String(50), server_default="text")
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    temperature: Mapped[Any] = mapped_column(Numeric(3, 2), server_default="0.10")
    max_tokens: Mapped[int] = mapped_column(Integer, server_default="2000")
    required_confidence: Mapped[Any] = mapped_column(Numeric(5, 4), server_default="0.8000")
    prohibited_patterns: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    required_patterns: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Document extraction results
# ---------------------------------------------------------------------------


class AiNlpDocumentResult(Base, TenantScopedMixin):
    __tablename__ = "document_results"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[UUID] = _uuid_pk()
    service_request_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.service_requests.id"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    source_file_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(100))
    page_count: Mapped[int | None] = mapped_column(Integer)
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    primary_model_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    secondary_model_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    consensus_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    disagreement_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Conversations (chatbot)
# ---------------------------------------------------------------------------


class AiNlpConversation(Base, TenantScopedMixin):
    __tablename__ = "conversations"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    portal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = _ts_now()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message_count: Mapped[int] = mapped_column(Integer, server_default="0")
    escalated_to_human: Mapped[bool] = mapped_column(Boolean, server_default="false")
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    satisfaction_rating: Mapped[int | None] = mapped_column(Integer)

    messages: Mapped[list[AiNlpConversationMessage]] = relationship(
        "AiNlpConversationMessage", back_populates="conversation", lazy="select"
    )


class AiNlpConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[UUID] = _uuid_pk()
    conversation_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.conversations.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    service_request_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[datetime] = _ts_now()

    conversation: Mapped[AiNlpConversation] = relationship(
        "AiNlpConversation", back_populates="messages"
    )


# ---------------------------------------------------------------------------
# Embeddings table (pgvector RAG store)
# ---------------------------------------------------------------------------


class AiNlpEmbedding(Base, TenantScopedMixin):
    __tablename__ = "embeddings"
    __table_args__ = (
        Index("ix_ai_embeddings_tenant_source", "tenant_id", "source_type"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    section: Mapped[str | None] = mapped_column(String(255))
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any | None] = mapped_column(Vector(1536))
    chunk_index: Mapped[int] = mapped_column(Integer, server_default="0")
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Usage log (cost tracking — Decimal, never float)
# ---------------------------------------------------------------------------


class AiNlpUsageLog(Base, TenantScopedMixin):
    __tablename__ = "usage_log"
    __table_args__ = (
        Index("ix_ai_usage_log_tenant", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    service_request_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost_usd: Mapped[Any] = mapped_column(Numeric(10, 6), nullable=False)
    created_at: Mapped[datetime] = _ts_now()


# ---------------------------------------------------------------------------
# Guardrail events log
# ---------------------------------------------------------------------------


class AiNlpGuardrailEvent(Base, TenantScopedMixin):
    __tablename__ = "guardrail_events"
    __table_args__ = (
        Index("ix_ai_guardrail_events_tenant", "tenant_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[UUID] = _uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(  # type: ignore[assignment]
        PG_UUID(as_uuid=True), nullable=False, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    service_request_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts_now()
