"""Stub HTTP client for Pharmacy Directory module (340B entity lookup).

# TODO: replace stub implementation with real HTTP calls to pharmacy-directory service
# when Pharmacy Directory module is available.
"""
from __future__ import annotations

import uuid


class PharmacyDirectoryClient:
    """Stub client for Pharmacy Directory service.

    In production this makes HTTP calls to modules/pharmacy-directory/.
    Never imports pharmacy-directory code directly.
    """

    def __init__(self, base_url: str = "http://pharmacy-directory:8000") -> None:
        self._base_url = base_url
        # In-memory stub for testing: NPI → is_340b_entity
        self._stub_entities: dict[str, bool] = {}

    def is_340b_entity(self, billing_provider_npi: str, tenant_id: uuid.UUID) -> bool:
        """Check if an NPI is a registered 340B entity.

        # TODO: implement real HTTP GET {base_url}/api/v1/entities/340b/{npi}
        """
        return self._stub_entities.get(billing_provider_npi, False)

    def register_stub_entity(self, npi: str, is_340b: bool = True) -> None:
        """Test helper: register a stub 340B entity."""
        self._stub_entities[npi] = is_340b
