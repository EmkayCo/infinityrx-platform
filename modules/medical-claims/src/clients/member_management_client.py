"""Stub HTTP client for Member Management module (accumulator integration).

# TODO: replace stub implementation with real HTTP calls to member-management service
# when Member Management module is available.
"""
from __future__ import annotations

from typing import Any


class MemberManagementClient:
    """Stub client for Member Management accumulator service.

    In production this makes HTTP calls to modules/member-management/.
    Never imports member-management code directly.
    """

    def __init__(self, base_url: str = "http://member-management:8000") -> None:
        self._base_url = base_url

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

        # TODO: implement real HTTP POST {base_url}/api/v1/accumulators/apply
        Returns updated accumulator values or None if service unavailable.
        """
        # Stub: return the input values unchanged
        return {
            "applied_to_deductible": applied_to_deductible,
            "applied_to_oop": applied_to_oop,
        }
