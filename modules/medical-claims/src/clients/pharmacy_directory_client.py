"""HTTP client for Pharmacy Directory module (NPI lookup / 340B entity check).

Calls pharmacy-directory service via HTTP. Never imports pharmacy-directory code directly.
Uses httpx.AsyncClient with 5-second timeout and 3 retries with exponential backoff.

Circuit-breaker: unreachable → return None, caller flags for manual review.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8003"
_TIMEOUT = httpx.Timeout(5.0)
_MAX_RETRIES = 3
_WAIT_MIN = 0.5
_WAIT_MAX = 4.0


# ---------------------------------------------------------------------------
# Response schemas — typed wrappers for upstream API payloads
# ---------------------------------------------------------------------------

class PharmacyLookupResult(BaseModel):
    """Typed result from GET /api/v1/pharmacies/lookup/{npi}."""
    id: str
    npi: str
    nabp_number: str | None = None
    legal_name: str
    display_name: str
    pharmacy_type: str
    address_line_1: str
    city: str
    state: str
    zip_code: str
    phone: str | None = None
    status: str


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

def _retrying_get(url: str, headers: dict[str, str]) -> Any:
    """Synchronous placeholder — unused; see _call() closures inside async methods."""
    raise NotImplementedError  # pragma: no cover


class PharmacyDirectoryClient:
    """Async HTTP client for Pharmacy Directory service.

    All network calls use httpx.AsyncClient with a 5-second timeout.
    Transient errors (timeout, connect error) are retried up to 3 times
    with exponential backoff. After retries are exhausted, returns None
    so callers can apply their own fallback policy.

    Never imports pharmacy-directory code directly — module boundary preserved.

    The synchronous is_340b_entity / register_stub_entity interface is kept
    for backward compat with Detection340bService and its existing unit tests.
    The primary async interface for new callers is lookup().
    """

    def __init__(
        self,
        base_url: str | None = None,
        token_provider: Any = None,
    ) -> None:
        self._base_url = (base_url or os.environ.get("PHARMACY_DIRECTORY_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self._token_provider = token_provider
        # In-memory stub for sync unit tests (Detection340bService)
        self._stub_entities: dict[str, bool] = {}

    def _auth_headers(self) -> dict[str, str]:
        if self._token_provider is None:
            return {}
        token = self._token_provider()
        return {"Authorization": f"Bearer {token}"}

    async def lookup(
        self,
        npi: str,
        *,
        correlation_id: str | None = None,
        tenant_id: str | None = None,
    ) -> PharmacyLookupResult | None:
        """Fetch pharmacy record by NPI.

        GET {PHARMACY_DIRECTORY_URL}/api/v1/pharmacies/lookup/{npi}

        Returns PharmacyLookupResult on success, None if service is unreachable
        or the NPI is not found (404).
        Caller should flag claim for manual review when None is returned.
        """
        url = f"{self._base_url}/api/v1/pharmacies/lookup/{npi}"
        extra = {
            "client_npi": npi,
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
                "pharmacy-directory lookup timed out after retries",
                extra=extra,
            )
            return None
        except httpx.ConnectError:
            logger.warning(
                "pharmacy-directory unreachable — connect error after retries",
                extra=extra,
            )
            return None

        if response.status_code == 404:
            logger.info("pharmacy-directory NPI not found", extra=extra)
            return None

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "pharmacy-directory returned unexpected status",
                extra={**extra, "client_status": exc.response.status_code},
            )
            return None

        return PharmacyLookupResult.model_validate(response.json())

    # ------------------------------------------------------------------
    # Legacy synchronous stub interface
    # Kept for Detection340bService and its unit tests.
    # ------------------------------------------------------------------

    def is_340b_entity(self, billing_provider_npi: str, tenant_id: Any) -> bool:
        """Synchronous stub: check if NPI is a registered 340B entity.

        In tests, populate via register_stub_entity().
        In production, callers should use lookup() (async) and interpret pharmacy_type.
        """
        return self._stub_entities.get(billing_provider_npi, False)

    def register_stub_entity(self, npi: str, is_340b: bool = True) -> None:
        """Test helper: register a stub 340B entity."""
        self._stub_entities[npi] = is_340b
