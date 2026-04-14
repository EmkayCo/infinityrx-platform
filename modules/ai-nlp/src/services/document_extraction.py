"""Document extraction service — Azure OpenAI-based structured data extraction.

Low-confidence fields (<0.85) flagged for human review, never auto-applied.
All costs tracked in Decimal via the shared OpenAI client.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.ai.openai_client import OpenAIClient, OpenAIRequest

logger = logging.getLogger("ai_nlp.document_extraction")

LOW_CONFIDENCE_THRESHOLD = 0.85


@dataclass
class ExtractionField:
    name: str
    value: str
    confidence: float

    @property
    def requires_review(self) -> bool:
        return self.confidence < LOW_CONFIDENCE_THRESHOLD


@dataclass
class DocumentExtractionResult:
    document_type: str
    fields: list[ExtractionField]
    overall_confidence: float
    requires_human_review: bool

    @property
    def low_confidence_fields(self) -> list[ExtractionField]:
        return [f for f in self.fields if f.requires_review]


class DocumentExtractionService:
    """Extract structured fields from documents using Azure OpenAI."""

    def __init__(self, db: AsyncSession, openai_client: OpenAIClient) -> None:
        self._db = db
        self._client = openai_client

    async def extract(
        self,
        tenant_id: UUID,
        service_request_id: UUID,
        document_type: str,
        extracted_text: str,
        fields_to_extract: list[str],
        phi_access_level: str = "redacted",
    ) -> DocumentExtractionResult:
        from pathlib import Path

        from jinja2 import Environment, FileSystemLoader

        prompts_dir = Path(__file__).parents[1] / "prompts"
        env = Environment(loader=FileSystemLoader(str(prompts_dir)), autoescape=False)
        tmpl = env.get_template("document_extraction.jinja")
        prompt = tmpl.render(
            document_type=document_type,
            extracted_text=extracted_text,
            fields_to_extract=fields_to_extract,
            phi_access_level=phi_access_level,
        )

        request = OpenAIRequest(
            tenant_id=str(tenant_id),
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4.1",
            temperature=Decimal("0"),
            phi_access_level=phi_access_level,
        )

        response = await self._client.complete(request)
        return self._parse_response(document_type, response.content)

    def _parse_response(self, document_type: str, content: str) -> DocumentExtractionResult:
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            logger.warning("document_extraction_malformed_json", extra={"svc_content_len": len(content)})
            return DocumentExtractionResult(
                document_type=document_type,
                fields=[],
                overall_confidence=0.0,
                requires_human_review=True,
            )

        fields = []
        for name, field_data in data.items():
            if isinstance(field_data, dict):
                value = str(field_data.get("value", ""))
                confidence = float(field_data.get("confidence", 0.0))
                fields.append(ExtractionField(name=name, value=value, confidence=confidence))

        if not fields:
            return DocumentExtractionResult(
                document_type=document_type,
                fields=[],
                overall_confidence=0.0,
                requires_human_review=True,
            )

        overall = sum(f.confidence for f in fields) / len(fields)
        requires_review = any(f.requires_review for f in fields)

        return DocumentExtractionResult(
            document_type=document_type,
            fields=fields,
            overall_confidence=overall,
            requires_human_review=requires_review,
        )
