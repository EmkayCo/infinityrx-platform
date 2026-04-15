"""HTTP client for Member Management module (eligibility check / accumulator integration).

Calls member-management service via HTTP. Never imports member-management code directly.
Uses httpx.AsyncClient with 5-second timeout and 3 retries with exponential backoff.

Circuit-breaker:
  - Service unreachable → return None; caller sets requires_manual_review=True
    with review_reason="member-management unreachable" on the claim record.
  - 404 → member not found; return None.
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8004"
_TIMEOUT = httpx.Timeout(5.0)
_MAX_RETRIES = 3
_WAIT_MIN = 0.5
_WAIT_MAX = 4.0


# ---------------------------------------------------------------------------
# Response schemas — typed wrappers for upstream API payloads
# ---------------------------------------------------------------------------

class EligibilityResult(BaseModel):
    """Typed result from GET /api/v1/eligibility."""
    is_eligible: bool
    status: str
    rejection_reason: str | None = None
    matched_member_id: str | None = None
    plan_name: str | None = None
    coverage_type: str | None = None
    cob_records: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class MemberManagementClient:
    """Async HTTP client for Member Management service.

    All network calls use httpx.AsyncClient with a 5-second timeout.
    Transient errors (timeout, connect error) are retried up to 3 times
    with exponential backoff.

    When the service is unreachable after all retries, check_eligibility()
    returns None. The caller MUST set requires_manual_review=True and
    review_reason="member-management unreachable" on the associated claim.

    The synchronous apply_claim_accumulator interface is kept for backward
    compat with AccumulatorService and its existing unit tests.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token_provider: Any = None,
    ) -> None:
        self._base_url = (base_url or os.environ.get("MEMBER_MANAGEMENT_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self._token_provider = token_provider

    def _auth_headers(self) -> dict[str, str]:
        if self._token_provider is None:
            return {}
        token = self._token_provider()
        return {"Authorization": f"Bearer {token}"}

    async def check_eligibility(
        self,
        member_id: str,
        *,
        rx_bin: str = "000000",
        date_of_service: date | None = None,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> EligibilityResult | None:
        """Check member eligibility.

        GET {MEMBER_MANAGEMENT_URL}/api/v1/eligibility?member_id={member_id}&rx_bin={rx_bin}&date_of_service={dos}

        Returns EligibilityResult on success, None if service is unreachable or member
        is not found (404). When None is returned, caller MUST flag claim for manual review.
        """
        dos = (date_of_service or date.today()).isoformat()
        url = f"{self._base_url}/api/v1/eligibility"
        params: dict[str, str] = {
            "member_id": member_id,
            "rx_bin": rx_bin,
            "date_of_service": dos,
        }
        if tenant_id:
            params["tenant_id"] = tenant_id
        extra = {
            "client_member_id": member_id,
            "client_url": url,
            "client_correlation_id": correlation_id or "",
            "client_tenant_id": tenant_id or "",
        }

        @retry(
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
            stop=stop_after_attempt(_MAX_RETRIES),
            wait=wait_exponential(multiplier=_WAIT_MIN, max=_WAIT_MAX),
            reraise=True,
        )
        async def _call() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as http:
                return await http.get(url, params=params, headers=self._auth_headers())

        try:
            response = await _call()
        except httpx.TimeoutException:
            logger.warning(
                "member-management eligibility timed out after retries — claim requires manual review",
                extra=extra,
            )
            return None
        except httpx.ConnectError:
            logger.warning(
                "member-management unreachable — connect error after retries — claim requires manual review",
                extra=extra,
            )
            return None

        if response.status_code == 404:
            logger.info("member-management member not found", extra=extra)
            return None

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "member-management returned unexpected status",
                extra={**extra, "client_status": exc.response.status_code},
            )
            return None

        return EligibilityResult.model_validate(response.json())

    # ------------------------------------------------------------------
    # Legacy synchronous stub interface
    # Kept for AccumulatorService and its unit tests.
    # ------------------------------------------------------------------

    def apply_claim_accumulator(
        self,
        tenant_id: str,
        member_id: str,
        date_of_service: str,
        claim_id: str,
        benefit_type: str,
        applied_to_deductible: str,
        applied_to_oop: str,
    ) -> dict[str, Any] | None:
        """Apply claim patient responsibility to member accumulators.

        Synchronous stub for AccumulatorService backward compat.
        Returns the input values unchanged (pass-through).
        In production, AccumulatorService should be updated to call an async
        POST endpoint on member-management; the stub interface is preserved
        so existing unit tests do not break.
        """
        return {
            "applied_to_deductible": applied_to_deductible,
            "applied_to_oop": applied_to_oop,
        }
