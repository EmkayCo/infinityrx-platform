"""HTTP client for Drug Database module (NDC validation and pricing lookup).

Calls drug-database service via HTTP. Never imports drug-database code directly.
Uses httpx.AsyncClient with 5-second timeout and 3 retries with exponential backoff.

Circuit-breaker:
  - Service unreachable → log warning, return None.
  - Caller skips NDC validation but does NOT block claim processing.
"""
from __future__ import annotations

import logging
import os
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8005"
_TIMEOUT = httpx.Timeout(5.0)
_MAX_RETRIES = 3
_WAIT_MIN = 0.5
_WAIT_MAX = 4.0


# ---------------------------------------------------------------------------
# Response schemas — typed wrappers for upstream API payloads
# ---------------------------------------------------------------------------

class DrugLookupResult(BaseModel):
    """Typed result from GET /api/v1/drugs/lookup/{ndc}."""
    id: str
    ndc_11: str
    ndc_formatted: str | None = None
    proprietary_name: str | None = None
    nonproprietary_name: str | None = None
    drug_name_display: str
    drug_type: str | None = None
    dea_schedule: str | None = None
    otc_rx: str | None = None
    dosage_form: str | None = None
    route_of_administration: str | None = None
    strength: str | None = None
    labeler_name: str | None = None
    marketing_status: str | None = None
    is_specialty: bool = False
    is_biosimilar: bool = False
    is_glp1: bool = False
    gpi_code: str | None = None
    atc_code: str | None = None
    therapeutic_class_1: str | None = None
    therapeutic_class_2: str | None = None
    is_active: bool = True
    data_source: str = ""


class DrugPricingResult(BaseModel):
    """Typed result from GET /api/v1/drugs/pricing/{ndc}."""
    ndc_11: str
    price_type: str
    price_per_unit: Decimal
    unit_type: str | None = None
    package_price: Decimal | None = None
    effective_date: date
    termination_date: date | None = None
    data_source: str


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class DrugDatabaseClient:
    """Async HTTP client for Drug Database service.

    All network calls use httpx.AsyncClient with a 5-second timeout.
    Transient errors (timeout, connect error) are retried up to 3 times
    with exponential backoff.

    When the service is unreachable after all retries, lookup_ndc() and
    get_pricing() return None. The caller SHOULD skip NDC validation but
    MUST NOT block claim processing.

    The synchronous validate_ndc / get_drug_info interface is kept for
    backward compat with existing unit tests.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token_provider: Any = None,
    ) -> None:
        self._base_url = (base_url or os.environ.get("DRUG_DATABASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self._token_provider = token_provider

    def _auth_headers(self) -> dict[str, str]:
        if self._token_provider is None:
            return {}
        token = self._token_provider()
        return {"Authorization": f"Bearer {token}"}

    async def lookup_ndc(
        self,
        ndc: str,
        *,
        correlation_id: str | None = None,
        tenant_id: str | None = None,
    ) -> DrugLookupResult | None:
        """Fetch drug record by NDC.

        GET {DRUG_DATABASE_URL}/api/v1/drugs/lookup/{ndc}

        Returns DrugLookupResult on success, None if service is unreachable
        or the NDC is not found (404).
        Caller skips NDC validation but does NOT block claim processing.
        """
        url = f"{self._base_url}/api/v1/drugs/lookup/{ndc}"
        extra = {
            "client_ndc": ndc,
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
                return await http.get(url, headers=self._auth_headers())

        try:
            response = await _call()
        except httpx.TimeoutException:
            logger.warning(
                "drug-database NDC lookup timed out after retries — skipping NDC validation",
                extra=extra,
            )
            return None
        except httpx.ConnectError:
            logger.warning(
                "drug-database unreachable — connect error after retries — skipping NDC validation",
                extra=extra,
            )
            return None

        if response.status_code == 404:
            logger.info("drug-database NDC not found", extra=extra)
            return None

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "drug-database returned unexpected status",
                extra={**extra, "client_status": exc.response.status_code},
            )
            return None

        return DrugLookupResult.model_validate(response.json())

    async def get_pricing(
        self,
        ndc: str,
        *,
        correlation_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[DrugPricingResult] | None:
        """Fetch pricing records for an NDC.

        GET {DRUG_DATABASE_URL}/api/v1/drugs/pricing/{ndc}

        Returns list of DrugPricingResult on success, None if service is
        unreachable or the NDC has no pricing data (404).
        Caller skips pricing enrichment but does NOT block claim processing.
        """
        url = f"{self._base_url}/api/v1/drugs/pricing/{ndc}"
        extra = {
            "client_ndc": ndc,
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
                return await http.get(url, headers=self._auth_headers())

        try:
            response = await _call()
        except httpx.TimeoutException:
            logger.warning(
                "drug-database pricing timed out after retries — skipping pricing enrichment",
                extra=extra,
            )
            return None
        except httpx.ConnectError:
            logger.warning(
                "drug-database unreachable — connect error after retries — skipping pricing enrichment",
                extra=extra,
            )
            return None

        if response.status_code == 404:
            logger.info("drug-database no pricing found for NDC", extra=extra)
            return None

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "drug-database pricing returned unexpected status",
                extra={**extra, "client_status": exc.response.status_code},
            )
            return None

        data = response.json()
        return [DrugPricingResult.model_validate(item) for item in data]

    # ------------------------------------------------------------------
    # Legacy synchronous stub interface
    # Kept for existing unit tests that use the old sync API.
    # ------------------------------------------------------------------

    def validate_ndc(self, ndc: str) -> bool:
        """Synchronous stub: validate an NDC by length/digit check.

        Real validation should use lookup_ndc() (async). This stub is kept
        for backward compat with tests that do not use the async interface.
        """
        return len(ndc) == 11 and ndc.isdigit()

    def get_drug_info(self, ndc: str) -> dict[str, Any] | None:
        """Synchronous stub: get drug info for an NDC.

        Real lookup should use lookup_ndc() (async). Returns None stub.
        """
        return None
