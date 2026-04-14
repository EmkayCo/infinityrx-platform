"""Guardrail service — input sanitization, output validation, topic enforcement.

Security boundary: 100% branch coverage required.
Every guardrail hit is logged to ai_nlp.guardrail_events.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import AiNlpGuardrailEvent


class GuardrailAction(StrEnum):
    PASS = "pass"
    BLOCK = "block"
    REPROMPT = "reprompt"
    ESCALATE = "escalate"
    CANNED_RESPONSE = "canned_response"


@dataclass
class GuardrailResult:
    triggered: bool
    rule_name: str = ""
    action: GuardrailAction = GuardrailAction.PASS
    matched_text: str = ""
    canned_response: str = ""


_PROMPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(previous|all|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all|previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"###\s*SYSTEM", re.IGNORECASE),
    re.compile(r"act\s+as\s+(an?\s+)?unrestricted", re.IGNORECASE),
    re.compile(r"you\s+(are|have|can)\s+now\s+(DAN|no restrictions)", re.IGNORECASE),
    re.compile(r"override\s+(your|all)\s+(instructions|restrictions)", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+\w+\s*(?:unrestricted|jailbroken|no\s+restrictions)", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)\s+(a|an)\s+\w+\s*(?:unrestricted|jailbroken)", re.IGNORECASE),
]

_SELF_REFERENCE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bI\s+am\s+a\s+(language\s+model|AI|LLM|chatbot)\b", re.IGNORECASE),
    re.compile(r"\bAs\s+an?\s+(AI|language\s+model|LLM)\b", re.IGNORECASE),
    re.compile(r"\bI('m|\s+am)\s+(an?\s+)?(AI|artificial\s+intelligence)\b", re.IGNORECASE),
]

_PROHIBITED_OUTPUT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\byou\s+are\s+required\s+to\b", re.IGNORECASE),
    re.compile(r"\byou\s+must\s+(pay|submit|provide)\b", re.IGNORECASE),
    re.compile(r"\byou\s+should\s+take\s+\w+\s+mg\b", re.IGNORECASE),
]

_PHI_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")
_PHI_DOB_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")

_IN_SCOPE_KEYWORDS = re.compile(
    r"\b(claim|copay|deductible|formulary|NDC|NPI|drug|pharmacy|benefit|"
    r"coverage|member|prescription|refill|prior\s+auth|PA\s+request|"
    r"payment|remittance|audit|appeal|plan|tier|network|DAW|"
    r"generic|brand|specialty|insulin|dosage|quantity|days.supply)\b",
    re.IGNORECASE,
)

_OUT_OF_SCOPE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(sports?|score|game|election|vote|weather|stock|crypto|bitcoin)\b", re.IGNORECASE),
]

_CANNED_OUT_OF_SCOPE = (
    "I can only help with pharmacy benefit and claims-related questions. "
    "Please contact customer support for other inquiries."
)


class InputGuardrail:
    """Check user input before sending to OpenAI."""

    def check(self, text: str) -> GuardrailResult:
        for pattern in _PROMPT_INJECTION_PATTERNS:
            m = pattern.search(text)
            if m:
                return GuardrailResult(
                    triggered=True,
                    rule_name="prompt_injection",
                    action=GuardrailAction.BLOCK,
                    matched_text=m.group(0),
                )
        return GuardrailResult(triggered=False)


class OutputGuardrail:
    """Check LLM output before returning to caller."""

    def check(self, text: str) -> GuardrailResult:
        for pattern in _SELF_REFERENCE_PATTERNS:
            m = pattern.search(text)
            if m:
                return GuardrailResult(
                    triggered=True,
                    rule_name="self_reference",
                    action=GuardrailAction.REPROMPT,
                    matched_text=m.group(0),
                )

        name_hit = _PHI_NAME_PATTERN.search(text)
        dob_hit = _PHI_DOB_PATTERN.search(text)
        if name_hit and dob_hit:
            return GuardrailResult(
                triggered=True,
                rule_name="phi_leakage",
                action=GuardrailAction.ESCALATE,
                matched_text=f"{name_hit.group(0)} + {dob_hit.group(0)}",
            )

        for pattern in _PROHIBITED_OUTPUT_PATTERNS:
            m = pattern.search(text)
            if m:
                return GuardrailResult(
                    triggered=True,
                    rule_name="prohibited_pattern",
                    action=GuardrailAction.REPROMPT,
                    matched_text=m.group(0),
                )

        return GuardrailResult(triggered=False)


class TopicGuardrail:
    """Reject queries outside pharmacy/benefits scope."""

    def check(self, text: str) -> GuardrailResult:
        if not text.strip():
            return GuardrailResult(triggered=False)

        for pattern in _OUT_OF_SCOPE_PATTERNS:
            m = pattern.search(text)
            if m and not _IN_SCOPE_KEYWORDS.search(text):
                return GuardrailResult(
                    triggered=True,
                    rule_name="out_of_scope",
                    action=GuardrailAction.CANNED_RESPONSE,
                    matched_text=m.group(0),
                    canned_response=_CANNED_OUT_OF_SCOPE,
                )

        return GuardrailResult(triggered=False)


class GuardrailService:
    """Composite guardrail service — logs every hit to the DB."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._input = InputGuardrail()
        self._output = OutputGuardrail()
        self._topic = TopicGuardrail()

    async def check_input(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
        text: str,
        service_request_id: UUID | None = None,
    ) -> GuardrailResult:
        result = self._input.check(text)
        if result.triggered:
            await self._log(tenant_id, user_id, service_request_id, result)
        return result

    async def check_output(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
        text: str,
        service_request_id: UUID | None = None,
    ) -> GuardrailResult:
        result = self._output.check(text)
        if result.triggered:
            await self._log(tenant_id, user_id, service_request_id, result)
        return result

    async def check_topic(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
        text: str,
        service_request_id: UUID | None = None,
    ) -> GuardrailResult:
        result = self._topic.check(text)
        if result.triggered:
            await self._log(tenant_id, user_id, service_request_id, result)
        return result

    async def _log(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
        service_request_id: UUID | None,
        result: GuardrailResult,
    ) -> None:
        event = AiNlpGuardrailEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            service_request_id=service_request_id,
            rule_name=result.rule_name,
            action=result.action.value,
            matched_text=result.matched_text[:500] if result.matched_text else None,
        )
        self._db.add(event)
        await self._db.commit()
