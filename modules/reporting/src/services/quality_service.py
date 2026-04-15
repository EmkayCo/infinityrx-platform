"""Quality / Star Ratings service: D-Star measure tracking and projections."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.constants import DSTAR_MEASURES, PDC_ADHERENCE_THRESHOLD


class QualityService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_star_ratings_dashboard(self, tenant_id: str) -> dict[str, Any]:
        """Return current D-Star measure performance dashboard data.

        PDC measures (D01–D03) require adjudication-engine claims with fill dates,
        days supply, and NDC-to-drug-class mapping.
        MTM completion (D04) requires mtm-clinical module data.
        Medication safety measures (D05–D08) require drug-database interaction data.
        All measures depend on member-management for enrollment denominators.

        # TODO: depends on adjudication-engine — wire after adjudication-engine is built.
        # TODO: depends on member-management — wire after member-management consent/COBRA CR-XX is fixed.
        # TODO: depends on mtm-clinical — wire after mtm-clinical is built.
        # TODO: depends on drug-database — wire after drug-database compound ingredients are complete.
        """
        measures = []
        for measure_id, measure_name in DSTAR_MEASURES.items():
            measures.append(
                {
                    "measure_id": measure_id,
                    "measure_name": measure_name,
                    "current_rate": None,
                    "target": str(PDC_ADHERENCE_THRESHOLD),
                    "status": "pending_data",
                    "adherent_members": 0,
                    "total_members": 0,
                }
            )

        return {
            "tenant_id": tenant_id,
            "measurement_period": "2026",
            "measures": measures,
            "overall_status": "tracking",
            "data_as_of": datetime.now(UTC).isoformat(),
        }

    async def get_adherence_detail(self, tenant_id: str, measure: str) -> dict[str, Any]:
        """Return member-level adherence detail for a specific measure.

        # TODO: depends on adjudication-engine — PDC calculation requires fill history
        # per member per drug class. Wire after adjudication-engine is built.
        # TODO: depends on member-management — member roster for denominators.
        """
        if measure not in DSTAR_MEASURES:
            raise ValueError(f"Invalid measure: {measure!r}")

        return {
            "measure_id": measure,
            "measure_name": DSTAR_MEASURES[measure],
            "tenant_id": tenant_id,
            "members": [],
            "summary": {
                "adherent": 0,
                "at_risk": 0,
                "non_adherent": 0,
                "total": 0,
                "rate": "0.00",
            },
            "data_as_of": datetime.now(UTC).isoformat(),
        }

    async def get_gap_members(self, tenant_id: str) -> dict[str, Any]:
        """Return members below adherence threshold who need outreach.

        # TODO: depends on adjudication-engine — PDC per member required to identify gaps.
        # TODO: depends on member-management — contact info for outreach targeting.
        """
        return {
            "tenant_id": tenant_id,
            "members_below_threshold": [],
            "members_at_risk": [],
            "total_gap_members": 0,
            "data_as_of": datetime.now(UTC).isoformat(),
        }

    async def get_year_end_projections(self, tenant_id: str) -> dict[str, Any]:
        """Project year-end Star Ratings based on current trajectory.

        # TODO: depends on adjudication-engine — current PDC trajectory per measure required.
        # TODO: depends on member-management — eligible member count for denominator projection.
        """
        projections = {}
        for measure_id, measure_name in DSTAR_MEASURES.items():
            projections[measure_id] = {
                "measure_name": measure_name,
                "projected_rate": None,
                "projected_status": "insufficient_data",
            }

        return {
            "tenant_id": tenant_id,
            "projections": projections,
            "data_as_of": datetime.now(UTC).isoformat(),
        }
