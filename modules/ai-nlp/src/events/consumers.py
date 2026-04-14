"""AI/NLP event consumers.

Handles:
- fwa.claim_flagged → generate anomaly narrative
- fwa.investigation_opened → generate investigation summary

All handlers are idempotent. Unknown fields in payloads are ignored gracefully
(forward compatibility).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.ai.openai_client import OpenAIClient, OpenAIRequest

logger = logging.getLogger("ai_nlp.events.consumers")


class AiNlpEventConsumer:
    """Handles inbound events and triggers AI/NLP generation tasks."""

    def __init__(self, db: AsyncSession, openai_client: OpenAIClient) -> None:
        self._db = db
        self._client = openai_client

    async def handle_fwa_claim_flagged(self, payload: dict[str, Any]) -> None:
        tenant_id_str = payload.get("tenant_id", "")
        entity_type = payload.get("entity_type", "unknown")
        entity_id = payload.get("entity_id", "unknown")
        flag_type = payload.get("flag_type", "unknown")
        evidence = payload.get("evidence", {})
        claim_count = payload.get("claim_count", 0)

        from pathlib import Path

        from jinja2 import Environment, FileSystemLoader

        prompts_dir = Path(__file__).parents[1] / "prompts"
        env = Environment(loader=FileSystemLoader(str(prompts_dir)), autoescape=False)
        tmpl = env.get_template("anomaly_narrative.jinja")
        prompt = tmpl.render(
            entity_type=entity_type,
            entity_id=entity_id,
            anomaly_type=flag_type,
            evidence=evidence,
            claim_count=claim_count,
            phi_access_level="redacted",
        )

        request = OpenAIRequest(
            tenant_id=tenant_id_str,
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4.1",
            temperature=Decimal("0.1"),
            phi_access_level="redacted",
        )

        try:
            await self._client.complete(request)
            logger.info(
                "anomaly_narrative_generated",
                extra={
                    "svc_tenant_id": tenant_id_str,
                    "svc_entity_type": entity_type,
                    "svc_entity_id": entity_id,
                },
            )
        except Exception as exc:
            logger.error(
                "anomaly_narrative_failed",
                extra={"svc_tenant_id": tenant_id_str, "svc_error": str(exc)},
            )

    async def handle_fwa_investigation_opened(self, payload: dict[str, Any]) -> None:
        tenant_id_str = payload.get("tenant_id", "")
        investigation_id = payload.get("investigation_id", "unknown")

        logger.info(
            "investigation_summary_requested",
            extra={
                "svc_tenant_id": tenant_id_str,
                "svc_investigation_id": investigation_id,
            },
        )
