"""Unit tests for PostGIS geo analytics service.

TDD: tests written before implementation.
Spatial calculations use Decimal for distances in miles.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from src.services.geo_analytics import (
    MemberLocation,
    NetworkAdequacyResult,
    PharmacyLocation,
    calculate_network_adequacy,
    is_drug_desert,
    miles_to_meters,
)


class TestMilesToMeters:
    def test_one_mile_is_1609_34_meters(self) -> None:
        result = miles_to_meters(Decimal("1"))
        assert result == Decimal("1609.34")

    def test_zero_miles_is_zero_meters(self) -> None:
        result = miles_to_meters(Decimal("0"))
        assert result == Decimal("0.00")

    def test_result_is_decimal(self) -> None:
        result = miles_to_meters(Decimal("5"))
        assert isinstance(result, Decimal)


class TestNetworkAdequacy:
    def test_all_members_within_radius_returns_100_pct(self) -> None:
        members = [
            MemberLocation(member_id="m1", lat=Decimal("40.7128"), lon=Decimal("-74.0060")),
            MemberLocation(member_id="m2", lat=Decimal("40.7129"), lon=Decimal("-74.0061")),
        ]
        pharmacies = [
            PharmacyLocation(
                pharmacy_id="p1",
                lat=Decimal("40.7128"),
                lon=Decimal("-74.0060"),
                is_in_network=True,
            ),
        ]
        result = calculate_network_adequacy(
            members=members,
            pharmacies=pharmacies,
            radius_miles=Decimal("5"),
        )
        assert result.pct_members_covered == Decimal("100.00")

    def test_no_members_returns_zero_pct(self) -> None:
        result = calculate_network_adequacy(
            members=[],
            pharmacies=[
                PharmacyLocation(
                    pharmacy_id="p1",
                    lat=Decimal("40.7128"),
                    lon=Decimal("-74.0060"),
                    is_in_network=True,
                )
            ],
            radius_miles=Decimal("5"),
        )
        assert result.pct_members_covered == Decimal("0.00")

    def test_no_pharmacies_returns_zero_pct(self) -> None:
        members = [
            MemberLocation(member_id="m1", lat=Decimal("40.7128"), lon=Decimal("-74.0060")),
        ]
        result = calculate_network_adequacy(
            members=members,
            pharmacies=[],
            radius_miles=Decimal("5"),
        )
        assert result.pct_members_covered == Decimal("0.00")

    def test_out_of_network_pharmacies_not_counted(self) -> None:
        members = [
            MemberLocation(member_id="m1", lat=Decimal("40.7128"), lon=Decimal("-74.0060")),
        ]
        pharmacies = [
            PharmacyLocation(
                pharmacy_id="p1",
                lat=Decimal("40.7128"),
                lon=Decimal("-74.0060"),
                is_in_network=False,  # out of network
            ),
        ]
        result = calculate_network_adequacy(
            members=members,
            pharmacies=pharmacies,
            radius_miles=Decimal("5"),
        )
        assert result.pct_members_covered == Decimal("0.00")

    def test_result_has_required_fields(self) -> None:
        result = calculate_network_adequacy(
            members=[],
            pharmacies=[],
            radius_miles=Decimal("5"),
        )
        assert isinstance(result, NetworkAdequacyResult)
        assert isinstance(result.pct_members_covered, Decimal)
        assert isinstance(result.total_members, int)
        assert isinstance(result.covered_members, int)

    def test_member_far_away_not_covered(self) -> None:
        members = [
            MemberLocation(member_id="m1", lat=Decimal("25.7617"), lon=Decimal("-80.1918")),  # Miami
        ]
        pharmacies = [
            PharmacyLocation(
                pharmacy_id="p1",
                lat=Decimal("40.7128"),
                lon=Decimal("-74.0060"),  # New York
                is_in_network=True,
            ),
        ]
        result = calculate_network_adequacy(
            members=members,
            pharmacies=pharmacies,
            radius_miles=Decimal("5"),
        )
        assert result.pct_members_covered == Decimal("0.00")
        assert result.covered_members == 0

    def test_result_pct_is_decimal(self) -> None:
        members = [
            MemberLocation(member_id="m1", lat=Decimal("40.7128"), lon=Decimal("-74.0060")),
        ]
        pharmacies = [
            PharmacyLocation(
                pharmacy_id="p1",
                lat=Decimal("40.7128"),
                lon=Decimal("-74.0060"),
                is_in_network=True,
            ),
        ]
        result = calculate_network_adequacy(
            members=members,
            pharmacies=pharmacies,
            radius_miles=Decimal("5"),
        )
        assert isinstance(result.pct_members_covered, Decimal)


class TestIsDrugDesert:
    def test_area_with_zero_pharmacies_per_10k_is_desert(self) -> None:
        assert is_drug_desert(pharmacies=0, population=10000) is True

    def test_area_below_1_per_10k_is_desert(self) -> None:
        # 5 pharmacies / 100000 population = 0.5 per 10k
        assert is_drug_desert(pharmacies=5, population=100000) is True

    def test_area_with_exactly_1_per_10k_is_not_desert(self) -> None:
        assert is_drug_desert(pharmacies=1, population=10000) is False

    def test_area_above_1_per_10k_is_not_desert(self) -> None:
        assert is_drug_desert(pharmacies=5, population=10000) is False

    def test_zero_population_raises(self) -> None:
        with pytest.raises(ValueError):
            is_drug_desert(pharmacies=0, population=0)
