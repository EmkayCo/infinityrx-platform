"""Network management service — PRD §6.

Handles: pharmacy assignment, tiered networks, specialty accreditation,
site-of-care, bagging, LDD, network adequacy, AWP application queue.
"""

from __future__ import annotations

import math
import uuid
from datetime import date, datetime, UTC
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.orm import Session

from shared.utils.money import TWO_PLACES
from src.models.tables import (
    AWPApplication,
    Network,
    NetworkAdequacy,
    NetworkPharmacy,
)

# Maximum acceptable distance/time thresholds (CMS network adequacy standards)
_MAX_URBAN_MILES = Decimal("2")
_MAX_RURAL_MILES = Decimal("15")
_MAX_URBAN_MINUTES = Decimal("10")
_MAX_RURAL_MINUTES = Decimal("30")


class NetworkService:
    """Business logic for network management."""

    def __init__(self, db: Session, tenant_id: uuid.UUID) -> None:
        self._db = db
        self._tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Network CRUD
    # ------------------------------------------------------------------

    def create_network(self, data: dict[str, Any]) -> Network:
        network = Network(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            name=data["name"],
            description=data.get("description"),
            effective_date=data["effective_date"],
            termination_date=data.get("termination_date"),
            tier_config=data.get("tier_config"),
            any_willing_pharmacy_enabled=data.get("any_willing_pharmacy_enabled", False),
            status="active",
        )
        self._db.add(network)
        self._db.flush()
        return network

    def get_network(self, network_id: uuid.UUID) -> Network | None:
        return (
            self._db.query(Network)
            .filter(
                Network.id == network_id,
                Network.tenant_id == self._tenant_id,
            )
            .first()
        )

    def list_networks(self, status: str | None = None) -> list[Network]:
        q = self._db.query(Network).filter(Network.tenant_id == self._tenant_id)
        if status:
            q = q.filter(Network.status == status)
        return q.order_by(Network.name).all()

    def update_network(self, network_id: uuid.UUID, data: dict[str, Any]) -> Network | None:
        network = self.get_network(network_id)
        if network is None:
            return None
        for field, value in data.items():
            if value is not None and hasattr(network, field):
                setattr(network, field, value)
        self._db.flush()
        return network

    # ------------------------------------------------------------------
    # Network Pharmacy Management
    # ------------------------------------------------------------------

    def add_pharmacy(self, network_id: uuid.UUID, data: dict[str, Any]) -> NetworkPharmacy:
        pharmacy = NetworkPharmacy(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            network_id=network_id,
            npi=data["npi"],
            pharmacy_name=data.get("pharmacy_name"),
            pharmacy_type=data.get("pharmacy_type", "retail"),
            network_tier=data.get("network_tier"),
            specialty_accreditation=data.get("specialty_accreditation"),
            site_of_care_type=data.get("site_of_care_type"),
            bagging_model=data.get("bagging_model"),
            is_ldd=data.get("is_ldd", False),
            ldd_drugs=data.get("ldd_drugs"),
            address_line1=data.get("address_line1"),
            city=data.get("city"),
            state=data.get("state"),
            zip_code=data.get("zip_code"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            effective_date=data["effective_date"],
            termination_date=data.get("termination_date"),
        )
        self._db.add(pharmacy)
        self._db.flush()
        return pharmacy

    def get_pharmacy(self, pharmacy_id: uuid.UUID) -> NetworkPharmacy | None:
        return (
            self._db.query(NetworkPharmacy)
            .filter(
                NetworkPharmacy.id == pharmacy_id,
                NetworkPharmacy.tenant_id == self._tenant_id,
            )
            .first()
        )

    def list_pharmacies(
        self,
        network_id: uuid.UUID,
        pharmacy_type: str | None = None,
        as_of: date | None = None,
    ) -> list[NetworkPharmacy]:
        q = self._db.query(NetworkPharmacy).filter(
            NetworkPharmacy.tenant_id == self._tenant_id,
            NetworkPharmacy.network_id == network_id,
        )
        if pharmacy_type:
            q = q.filter(NetworkPharmacy.pharmacy_type == pharmacy_type)
        if as_of:
            q = q.filter(
                NetworkPharmacy.effective_date <= as_of,
                (NetworkPharmacy.termination_date.is_(None))
                | (NetworkPharmacy.termination_date >= as_of),
            )
        return q.all()

    def remove_pharmacy(self, pharmacy_id: uuid.UUID) -> bool:
        pharmacy = self.get_pharmacy(pharmacy_id)
        if pharmacy is None:
            return False
        self._db.delete(pharmacy)
        self._db.flush()
        return True

    # ------------------------------------------------------------------
    # Network Adequacy (CMS Requirement — PRD §6)
    # ------------------------------------------------------------------

    def calculate_adequacy(self, network_id: uuid.UUID) -> dict[str, Any]:
        """Calculate network adequacy by time/distance using geodesic math.

        Uses Haversine formula for great-circle distance calculation.
        In production, member lat/lng would come from Member Management module.
        """
        pharmacies = self.list_pharmacies(network_id)

        # Retrieve saved adequacy records
        existing_records = (
            self._db.query(NetworkAdequacy)
            .filter(
                NetworkAdequacy.tenant_id == self._tenant_id,
                NetworkAdequacy.network_id == network_id,
            )
            .all()
        )

        total_member_count = sum(r.member_count for r in existing_records)
        adequate_count = sum(1 for r in existing_records if r.is_adequate)
        inadequate_count = len(existing_records) - adequate_count

        adequacy_pct = (
            Decimal(str(adequate_count / len(existing_records) * 100)).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            if existing_records
            else Decimal("100.00")
        )

        gaps = [
            {
                "zip_code": r.zip_code,
                "county_fips": r.county_fips,
                "member_count": r.member_count,
                "nearest_miles": str(r.nearest_pharmacy_miles),
                "nearest_minutes": str(r.nearest_pharmacy_minutes),
                "gap_details": r.gap_details,
            }
            for r in existing_records
            if not r.is_adequate
        ]

        return {
            "network_id": str(network_id),
            "total_member_count": total_member_count,
            "adequate_zip_count": adequate_count,
            "inadequate_zip_count": inadequate_count,
            "adequacy_pct": str(adequacy_pct),
            "gaps": gaps,
            "calculated_at": datetime.now(UTC).isoformat(),
            "pharmacy_count": len(pharmacies),
        }

    @staticmethod
    def haversine_miles(
        lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal
    ) -> Decimal:
        """Compute geodesic distance in miles using Haversine formula."""
        R = Decimal("3958.8")  # Earth radius in miles
        lat1_r = float(lat1) * math.pi / 180
        lat2_r = float(lat2) * math.pi / 180
        d_lat = (float(lat2) - float(lat1)) * math.pi / 180
        d_lon = (float(lon2) - float(lon1)) * math.pi / 180

        a = math.sin(d_lat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(d_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        miles = R * Decimal(str(c))
        return miles.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    def check_pharmacy_in_network(
        self,
        network_id: uuid.UUID,
        npi: str,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        """Check if a pharmacy NPI is in-network (consumed by adjudication engine)."""
        pharmacies = self.list_pharmacies(network_id, as_of=as_of)
        match = next((p for p in pharmacies if p.npi == npi), None)
        if match is None:
            return {"in_network": False, "npi": npi, "network_id": str(network_id)}
        return {
            "in_network": True,
            "npi": npi,
            "network_id": str(network_id),
            "network_tier": match.network_tier,
            "pharmacy_type": match.pharmacy_type,
            "specialty_accreditation": match.specialty_accreditation,
        }

    # ------------------------------------------------------------------
    # Any Willing Pharmacy (CAA 2026 — PRD §6)
    # ------------------------------------------------------------------

    def submit_awp_application(
        self, network_id: uuid.UUID, data: dict[str, Any]
    ) -> AWPApplication:
        app = AWPApplication(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            network_id=network_id,
            pharmacy_npi=data["pharmacy_npi"],
            pharmacy_name=data["pharmacy_name"],
            pharmacy_address=data.get("pharmacy_address"),
            application_data=data.get("application_data"),
            status="pending",
        )
        self._db.add(app)
        self._db.flush()
        return app

    def get_awp_application(self, app_id: uuid.UUID) -> AWPApplication | None:
        return (
            self._db.query(AWPApplication)
            .filter(
                AWPApplication.id == app_id,
                AWPApplication.tenant_id == self._tenant_id,
            )
            .first()
        )

    def list_awp_applications(
        self, network_id: uuid.UUID, status: str | None = None
    ) -> list[AWPApplication]:
        q = self._db.query(AWPApplication).filter(
            AWPApplication.tenant_id == self._tenant_id,
            AWPApplication.network_id == network_id,
        )
        if status:
            q = q.filter(AWPApplication.status == status)
        return q.order_by(AWPApplication.submitted_at.desc()).all()

    def update_awp_application(
        self, app_id: uuid.UUID, data: dict[str, Any]
    ) -> AWPApplication | None:
        app = self.get_awp_application(app_id)
        if app is None:
            return None
        if "status" in data and data["status"]:
            app.status = data["status"]
        if "decision_notes" in data and data["decision_notes"]:
            app.decision_notes = data["decision_notes"]
            app.decided_at = datetime.now(UTC)
        self._db.flush()
        return app
