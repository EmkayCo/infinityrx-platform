"""Member service — CRUD, search, PHI masking, enrollment processing.

PHI rules:
- Never log PHI fields. Use member_id UUID only.
- PHI access audit entry on every PHI read.
- Cache-Control: no-store on every response containing PHI.
"""
from __future__ import annotations

import logging
from typing import Any

from src.api.schemas.member import PhiAccessLevel

logger = logging.getLogger("member-management.member_service")

_PHI_FIELDS = frozenset({
    "first_name", "last_name", "middle_name", "date_of_birth",
    "ssn", "address_line_1", "address_line_2", "city", "state",
    "zip_code", "phone", "email",
})

_REDACTED = "**REDACTED**"


class MemberService:
    """Stateless helpers + async DB methods for member management."""

    def mask_phi(
        self,
        data: dict[str, Any],
        access_level: PhiAccessLevel,
    ) -> dict[str, Any]:
        """Return a copy of *data* with PHI masked per *access_level*."""
        result = dict(data)

        if access_level == PhiAccessLevel.FULL:
            return result

        if access_level == PhiAccessLevel.REDACTED:
            for key in _PHI_FIELDS:
                if key in result:
                    result[key] = _REDACTED
            return result

        # PARTIAL: mask SSN (last 4 visible), DOB (year/month hidden), rest visible
        if "ssn" in result and result["ssn"] and result["ssn"] != _REDACTED:
            ssn = str(result["ssn"])
            result["ssn"] = f"***-**-{ssn[-4:]}" if len(ssn) >= 4 else _REDACTED

        if "date_of_birth" in result and result["date_of_birth"] and result["date_of_birth"] != _REDACTED:
            dob = str(result["date_of_birth"])
            # Keep day only: ****-**-DD
            parts = dob.split("-")
            if len(parts) == 3:
                result["date_of_birth"] = f"****-**-{parts[2]}"
            else:
                result["date_of_birth"] = _REDACTED

        return result
