"""Stub HTTP client for Drug Database module (NDC validation).

# TODO: replace stub implementation with real HTTP calls to drug-database service
# when Drug Database module is available.
"""
from __future__ import annotations

from typing import Any


class DrugDatabaseClient:
    """Stub client for Drug Database service.

    In production this makes HTTP calls to modules/drug-database/.
    Never imports drug-database code directly.
    """

    def __init__(self, base_url: str = "http://drug-database:8000") -> None:
        self._base_url = base_url

    def validate_ndc(self, ndc: str) -> bool:
        """Validate an NDC against the drug database.

        # TODO: implement real HTTP GET {base_url}/api/v1/drugs/{ndc}/validate
        """
        # Stub: accept any 11-digit NDC
        return len(ndc) == 11 and ndc.isdigit()

    def get_drug_info(self, ndc: str) -> dict[str, Any] | None:
        """Get drug information for an NDC.

        # TODO: implement real HTTP GET {base_url}/api/v1/drugs/{ndc}
        """
        return None
