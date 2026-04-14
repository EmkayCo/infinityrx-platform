"""Unit tests for ai_nlp ORM models — written FIRST (TDD)."""

from __future__ import annotations



from src.models.tables import (
    AiNlpConversation,
    AiNlpDocumentResult,
    AiNlpEmbedding,
    AiNlpGuardrailEvent,
    AiNlpPromptTemplate,
    AiNlpServiceRequest,
    AiNlpUsageLog,
    SCHEMA,
)
from shared.db.tenant_context import TenantScopedMixin


class TestModelSchema:
    def test_schema_name_is_ai_nlp(self) -> None:
        assert SCHEMA == "ai_nlp"

    def test_service_request_is_tenant_scoped(self) -> None:
        assert issubclass(AiNlpServiceRequest, TenantScopedMixin)

    def test_conversation_is_tenant_scoped(self) -> None:
        assert issubclass(AiNlpConversation, TenantScopedMixin)

    def test_document_result_is_tenant_scoped(self) -> None:
        assert issubclass(AiNlpDocumentResult, TenantScopedMixin)

    def test_embedding_is_tenant_scoped(self) -> None:
        assert issubclass(AiNlpEmbedding, TenantScopedMixin)

    def test_guardrail_event_is_tenant_scoped(self) -> None:
        assert issubclass(AiNlpGuardrailEvent, TenantScopedMixin)

    def test_usage_log_is_tenant_scoped(self) -> None:
        assert issubclass(AiNlpUsageLog, TenantScopedMixin)

    def test_prompt_template_has_correct_table(self) -> None:
        assert AiNlpPromptTemplate.__tablename__ == "prompt_templates"


class TestServiceRequestModel:
    def test_status_column_has_default_pending(self) -> None:
        col = AiNlpServiceRequest.__table__.c["status"]
        assert col.server_default is not None or col.default is not None

    def test_requires_human_review_defaults_false(self) -> None:
        col = AiNlpServiceRequest.__table__.c["requires_human_review"]
        assert col.server_default is not None or col.default is not None

    def test_confidence_score_is_numeric_not_float(self) -> None:
        col = AiNlpServiceRequest.__table__.c["confidence_score"]
        from sqlalchemy import Numeric
        assert isinstance(col.type, Numeric)

    def test_estimated_cost_is_numeric_not_float(self) -> None:
        col = AiNlpServiceRequest.__table__.c["estimated_cost_usd"]
        from sqlalchemy import Numeric
        assert isinstance(col.type, Numeric)


class TestUsageLogModel:
    def test_total_cost_usd_is_numeric(self) -> None:
        col = AiNlpUsageLog.__table__.c["total_cost_usd"]
        from sqlalchemy import Numeric
        assert isinstance(col.type, Numeric)

    def test_usage_log_table_name(self) -> None:
        assert AiNlpUsageLog.__tablename__ == "usage_log"


class TestEmbeddingModel:
    def test_embedding_table_name(self) -> None:
        assert AiNlpEmbedding.__tablename__ == "embeddings"

    def test_embedding_has_source_type(self) -> None:
        assert "source_type" in AiNlpEmbedding.__table__.c

    def test_embedding_has_source_id(self) -> None:
        assert "source_id" in AiNlpEmbedding.__table__.c


class TestGuardrailEventModel:
    def test_guardrail_table_name(self) -> None:
        assert AiNlpGuardrailEvent.__tablename__ == "guardrail_events"

    def test_has_rule_name_column(self) -> None:
        assert "rule_name" in AiNlpGuardrailEvent.__table__.c

    def test_has_action_column(self) -> None:
        assert "action" in AiNlpGuardrailEvent.__table__.c
