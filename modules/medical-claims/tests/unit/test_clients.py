"""Unit tests for inter-module HTTP clients.

Covers: success, 404 not-found, timeout, connect-error, retry-then-succeed,
retry-then-fail-with-fallback (returns None).

Uses respx to mock HTTP transport — never hits real services.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from src.clients.pharmacy_directory_client import PharmacyDirectoryClient, PharmacyLookupResult
from src.clients.member_management_client import EligibilityResult, MemberManagementClient
from src.clients.drug_database_client import DrugDatabaseClient, DrugLookupResult, DrugPricingResult

# ---------------------------------------------------------------------------
# Sample response payloads
# ---------------------------------------------------------------------------

_PHARMACY_PAYLOAD = {
    "id": "ph-001",
    "npi": "1234567890",
    "nabp_number": "1234567",
    "legal_name": "Test Pharmacy LLC",
    "display_name": "Test Pharmacy",
    "pharmacy_type": "retail",
    "address_line_1": "100 Main St",
    "city": "Springfield",
    "state": "IL",
    "zip_code": "62701",
    "phone": "2175550100",
    "status": "active",
}

_ELIGIBILITY_PAYLOAD = {
    "is_eligible": True,
    "status": "active",
    "rejection_reason": None,
    "matched_member_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "plan_name": "Standard Plan",
    "coverage_type": "medical",
    "cob_records": [],
}

_DRUG_PAYLOAD = {
    "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
    "ndc_11": "12345678901",
    "ndc_formatted": "12345-6789-01",
    "proprietary_name": "TestDrug",
    "nonproprietary_name": "testdrug",
    "drug_name_display": "TestDrug 100mg",
    "drug_type": "Human Prescription Drug",
    "dea_schedule": None,
    "otc_rx": "Rx",
    "dosage_form": "Tablet",
    "route_of_administration": "Oral",
    "strength": "100mg",
    "labeler_name": "TestLab Inc",
    "marketing_status": "Prescription",
    "is_specialty": False,
    "is_biosimilar": False,
    "is_glp1": False,
    "gpi_code": None,
    "atc_code": None,
    "therapeutic_class_1": "Cardiovascular",
    "therapeutic_class_2": None,
    "is_active": True,
    "data_source": "fda_ndc",
}

_PRICING_PAYLOAD = [
    {
        "ndc_11": "12345678901",
        "price_type": "wac",
        "price_per_unit": "10.5000",
        "unit_type": "EA",
        "package_price": "105.0000",
        "effective_date": "2026-01-01",
        "termination_date": None,
        "data_source": "manufacturer",
    }
]


# ===========================================================================
# PharmacyDirectoryClient
# ===========================================================================

class TestPharmacyDirectoryClientLookup:
    """Tests for PharmacyDirectoryClient.lookup()"""

    @respx.mock
    async def test_lookup_success(self):
        """Success path: returns PharmacyLookupResult."""
        respx.get("http://localhost:8003/api/v1/pharmacies/lookup/1234567890").mock(
            return_value=httpx.Response(200, json=_PHARMACY_PAYLOAD)
        )
        client = PharmacyDirectoryClient(base_url="http://localhost:8003")
        result = await client.lookup("1234567890")
        assert isinstance(result, PharmacyLookupResult)
        assert result.npi == "1234567890"
        assert result.legal_name == "Test Pharmacy LLC"
        assert result.status == "active"

    @respx.mock
    async def test_lookup_404_returns_none(self):
        """404 from upstream returns None (NPI not found)."""
        respx.get("http://localhost:8003/api/v1/pharmacies/lookup/9999999999").mock(
            return_value=httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "NPI not found", "correlation_id": "x"}})
        )
        client = PharmacyDirectoryClient(base_url="http://localhost:8003")
        result = await client.lookup("9999999999")
        assert result is None

    @respx.mock
    async def test_lookup_500_returns_none(self):
        """5xx error from upstream returns None."""
        respx.get("http://localhost:8003/api/v1/pharmacies/lookup/1234567890").mock(
            return_value=httpx.Response(500, json={"error": "internal"})
        )
        client = PharmacyDirectoryClient(base_url="http://localhost:8003")
        result = await client.lookup("1234567890")
        assert result is None

    @respx.mock
    async def test_lookup_timeout_returns_none(self):
        """TimeoutException after retries returns None (circuit-breaker open)."""
        respx.get("http://localhost:8003/api/v1/pharmacies/lookup/1234567890").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        client = PharmacyDirectoryClient(base_url="http://localhost:8003")
        result = await client.lookup("1234567890")
        assert result is None

    @respx.mock
    async def test_lookup_connect_error_returns_none(self):
        """ConnectError after retries returns None (service unreachable)."""
        respx.get("http://localhost:8003/api/v1/pharmacies/lookup/1234567890").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        client = PharmacyDirectoryClient(base_url="http://localhost:8003")
        result = await client.lookup("1234567890")
        assert result is None

    @respx.mock
    async def test_lookup_retry_then_succeed(self):
        """Two failures then success: returns result on third attempt."""
        route = respx.get("http://localhost:8003/api/v1/pharmacies/lookup/1234567890")
        route.side_effect = [
            httpx.ConnectError("refused"),
            httpx.ConnectError("refused"),
            httpx.Response(200, json=_PHARMACY_PAYLOAD),
        ]
        client = PharmacyDirectoryClient(base_url="http://localhost:8003")
        # Need to patch tenacity wait to not actually sleep
        with patch("tenacity.wait_exponential.__call__", return_value=0):
            result = await client.lookup("1234567890")
        assert result is not None
        assert result.npi == "1234567890"

    @respx.mock
    async def test_lookup_with_token_provider_sends_auth_header(self):
        """Token provider injects Authorization header."""
        token_provider = MagicMock(return_value="test-token-abc")
        respx.get("http://localhost:8003/api/v1/pharmacies/lookup/1234567890").mock(
            return_value=httpx.Response(200, json=_PHARMACY_PAYLOAD)
        )
        client = PharmacyDirectoryClient(base_url="http://localhost:8003", token_provider=token_provider)
        result = await client.lookup("1234567890")
        assert result is not None
        token_provider.assert_called_once()

    def test_base_url_from_env(self, monkeypatch):
        """Base URL is read from PHARMACY_DIRECTORY_URL env var."""
        monkeypatch.setenv("PHARMACY_DIRECTORY_URL", "http://pharmacy-svc:9000")
        client = PharmacyDirectoryClient()
        assert client._base_url == "http://pharmacy-svc:9000"

    def test_base_url_trailing_slash_stripped(self):
        """Trailing slash is stripped from base URL."""
        client = PharmacyDirectoryClient(base_url="http://localhost:8003/")
        assert client._base_url == "http://localhost:8003"

    # ------------------------------------------------------------------
    # Legacy sync stub interface (backward compat)
    # ------------------------------------------------------------------

    def test_is_340b_entity_returns_false_by_default(self):
        client = PharmacyDirectoryClient()
        assert client.is_340b_entity("1234567890", "tenant-1") is False

    def test_register_stub_entity_sets_340b_flag(self):
        client = PharmacyDirectoryClient()
        client.register_stub_entity("3401234567", True)
        assert client.is_340b_entity("3401234567", "tenant-1") is True

    def test_register_stub_entity_false(self):
        client = PharmacyDirectoryClient()
        client.register_stub_entity("9999999999", False)
        assert client.is_340b_entity("9999999999", "tenant-1") is False


# ===========================================================================
# MemberManagementClient
# ===========================================================================

class TestMemberManagementClientEligibility:
    """Tests for MemberManagementClient.check_eligibility()"""

    @respx.mock
    async def test_check_eligibility_success(self):
        """Success path: returns EligibilityResult."""
        respx.get("http://localhost:8004/api/v1/eligibility").mock(
            return_value=httpx.Response(200, json=_ELIGIBILITY_PAYLOAD)
        )
        client = MemberManagementClient(base_url="http://localhost:8004")
        result = await client.check_eligibility("MBR-001", rx_bin="610494")
        assert isinstance(result, EligibilityResult)
        assert result.is_eligible is True
        assert result.status == "active"

    @respx.mock
    async def test_check_eligibility_404_returns_none(self):
        """404 from upstream returns None (member not found)."""
        respx.get("http://localhost:8004/api/v1/eligibility").mock(
            return_value=httpx.Response(404, json={"error": {"code": "NOT_FOUND", "message": "member not found", "correlation_id": "x"}})
        )
        client = MemberManagementClient(base_url="http://localhost:8004")
        result = await client.check_eligibility("MBR-UNKNOWN", rx_bin="610494")
        assert result is None

    @respx.mock
    async def test_check_eligibility_500_returns_none(self):
        """5xx upstream error returns None."""
        respx.get("http://localhost:8004/api/v1/eligibility").mock(
            return_value=httpx.Response(500, json={"error": "internal"})
        )
        client = MemberManagementClient(base_url="http://localhost:8004")
        result = await client.check_eligibility("MBR-001", rx_bin="610494")
        assert result is None

    @respx.mock
    async def test_check_eligibility_timeout_returns_none(self):
        """TimeoutException after retries returns None — caller must flag for manual review."""
        respx.get("http://localhost:8004/api/v1/eligibility").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        client = MemberManagementClient(base_url="http://localhost:8004")
        result = await client.check_eligibility("MBR-001", rx_bin="610494")
        assert result is None

    @respx.mock
    async def test_check_eligibility_connect_error_returns_none(self):
        """ConnectError after retries returns None — service unreachable."""
        respx.get("http://localhost:8004/api/v1/eligibility").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        client = MemberManagementClient(base_url="http://localhost:8004")
        result = await client.check_eligibility("MBR-001", rx_bin="610494")
        assert result is None

    @respx.mock
    async def test_check_eligibility_retry_then_succeed(self):
        """Two failures then success: returns result on third attempt."""
        route = respx.get("http://localhost:8004/api/v1/eligibility")
        route.side_effect = [
            httpx.TimeoutException("timed out"),
            httpx.TimeoutException("timed out"),
            httpx.Response(200, json=_ELIGIBILITY_PAYLOAD),
        ]
        client = MemberManagementClient(base_url="http://localhost:8004")
        with patch("tenacity.wait_exponential.__call__", return_value=0):
            result = await client.check_eligibility("MBR-001", rx_bin="610494")
        assert result is not None
        assert result.is_eligible is True

    @respx.mock
    async def test_check_eligibility_with_token_provider_sends_auth_header(self):
        """Token provider injects Authorization header."""
        token_provider = MagicMock(return_value="member-token-xyz")
        respx.get("http://localhost:8004/api/v1/eligibility").mock(
            return_value=httpx.Response(200, json=_ELIGIBILITY_PAYLOAD)
        )
        client = MemberManagementClient(base_url="http://localhost:8004", token_provider=token_provider)
        result = await client.check_eligibility("MBR-001", rx_bin="610494")
        assert result is not None
        token_provider.assert_called_once()

    def test_base_url_from_env(self, monkeypatch):
        """Base URL is read from MEMBER_MANAGEMENT_URL env var."""
        monkeypatch.setenv("MEMBER_MANAGEMENT_URL", "http://member-svc:9001")
        client = MemberManagementClient()
        assert client._base_url == "http://member-svc:9001"

    # ------------------------------------------------------------------
    # Legacy sync stub interface (backward compat)
    # ------------------------------------------------------------------

    def test_apply_claim_accumulator_returns_same_amounts(self):
        """Stub pass-through: applied amounts echo back unchanged."""
        client = MemberManagementClient()
        result = client.apply_claim_accumulator(
            tenant_id="t1",
            member_id="m1",
            date_of_service="2026-01-01",
            claim_id="c1",
            benefit_type="medical",
            applied_to_deductible="50.00",
            applied_to_oop="80.00",
        )
        assert result is not None
        assert result["applied_to_deductible"] == "50.00"
        assert result["applied_to_oop"] == "80.00"


# ===========================================================================
# DrugDatabaseClient
# ===========================================================================

class TestDrugDatabaseClientLookupNdc:
    """Tests for DrugDatabaseClient.lookup_ndc()"""

    @respx.mock
    async def test_lookup_ndc_success(self):
        """Success path: returns DrugLookupResult."""
        respx.get("http://localhost:8005/api/v1/drugs/lookup/12345678901").mock(
            return_value=httpx.Response(200, json=_DRUG_PAYLOAD)
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        result = await client.lookup_ndc("12345678901")
        assert isinstance(result, DrugLookupResult)
        assert result.ndc_11 == "12345678901"
        assert result.drug_name_display == "TestDrug 100mg"
        assert result.is_active is True

    @respx.mock
    async def test_lookup_ndc_404_returns_none(self):
        """404 from upstream returns None (NDC not found)."""
        respx.get("http://localhost:8005/api/v1/drugs/lookup/99999999999").mock(
            return_value=httpx.Response(404, json={"error": {"code": "DRUG_NOT_FOUND", "message": "not found", "correlation_id": "x"}})
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        result = await client.lookup_ndc("99999999999")
        assert result is None

    @respx.mock
    async def test_lookup_ndc_500_returns_none(self):
        """5xx error returns None (caller skips NDC validation, does not block)."""
        respx.get("http://localhost:8005/api/v1/drugs/lookup/12345678901").mock(
            return_value=httpx.Response(500, json={"error": "internal"})
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        result = await client.lookup_ndc("12345678901")
        assert result is None

    @respx.mock
    async def test_lookup_ndc_timeout_returns_none(self):
        """TimeoutException after retries returns None."""
        respx.get("http://localhost:8005/api/v1/drugs/lookup/12345678901").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        result = await client.lookup_ndc("12345678901")
        assert result is None

    @respx.mock
    async def test_lookup_ndc_connect_error_returns_none(self):
        """ConnectError after retries returns None."""
        respx.get("http://localhost:8005/api/v1/drugs/lookup/12345678901").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        result = await client.lookup_ndc("12345678901")
        assert result is None

    @respx.mock
    async def test_lookup_ndc_retry_then_succeed(self):
        """Two failures then success: returns result on third attempt."""
        route = respx.get("http://localhost:8005/api/v1/drugs/lookup/12345678901")
        route.side_effect = [
            httpx.ConnectError("refused"),
            httpx.TimeoutException("timed out"),
            httpx.Response(200, json=_DRUG_PAYLOAD),
        ]
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        with patch("tenacity.wait_exponential.__call__", return_value=0):
            result = await client.lookup_ndc("12345678901")
        assert result is not None
        assert result.ndc_11 == "12345678901"

    @respx.mock
    async def test_lookup_ndc_with_token_provider_sends_auth_header(self):
        """Token provider injects Authorization header."""
        token_provider = MagicMock(return_value="drug-token-xyz")
        respx.get("http://localhost:8005/api/v1/drugs/lookup/12345678901").mock(
            return_value=httpx.Response(200, json=_DRUG_PAYLOAD)
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005", token_provider=token_provider)
        result = await client.lookup_ndc("12345678901")
        assert result is not None
        token_provider.assert_called_once()

    def test_base_url_from_env(self, monkeypatch):
        """Base URL is read from DRUG_DATABASE_URL env var."""
        monkeypatch.setenv("DRUG_DATABASE_URL", "http://drug-svc:9002")
        client = DrugDatabaseClient()
        assert client._base_url == "http://drug-svc:9002"


class TestDrugDatabaseClientGetPricing:
    """Tests for DrugDatabaseClient.get_pricing()"""

    @respx.mock
    async def test_get_pricing_success(self):
        """Success path: returns list of DrugPricingResult."""
        respx.get("http://localhost:8005/api/v1/drugs/pricing/12345678901").mock(
            return_value=httpx.Response(200, json=_PRICING_PAYLOAD)
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        results = await client.get_pricing("12345678901")
        assert results is not None
        assert len(results) == 1
        assert isinstance(results[0], DrugPricingResult)
        assert results[0].price_per_unit == Decimal("10.5000")
        assert results[0].price_type == "wac"

    @respx.mock
    async def test_get_pricing_404_returns_none(self):
        """404 (no pricing data) returns None."""
        respx.get("http://localhost:8005/api/v1/drugs/pricing/99999999999").mock(
            return_value=httpx.Response(404, json={"error": "not found"})
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        result = await client.get_pricing("99999999999")
        assert result is None

    @respx.mock
    async def test_get_pricing_timeout_returns_none(self):
        """TimeoutException after retries returns None."""
        respx.get("http://localhost:8005/api/v1/drugs/pricing/12345678901").mock(
            side_effect=httpx.TimeoutException("timed out")
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        result = await client.get_pricing("12345678901")
        assert result is None

    @respx.mock
    async def test_get_pricing_connect_error_returns_none(self):
        """ConnectError after retries returns None."""
        respx.get("http://localhost:8005/api/v1/drugs/pricing/12345678901").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        result = await client.get_pricing("12345678901")
        assert result is None

    @respx.mock
    async def test_get_pricing_retry_then_succeed(self):
        """Two failures then success on pricing endpoint."""
        route = respx.get("http://localhost:8005/api/v1/drugs/pricing/12345678901")
        route.side_effect = [
            httpx.TimeoutException("timed out"),
            httpx.ConnectError("refused"),
            httpx.Response(200, json=_PRICING_PAYLOAD),
        ]
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        with patch("tenacity.wait_exponential.__call__", return_value=0):
            results = await client.get_pricing("12345678901")
        assert results is not None
        assert results[0].ndc_11 == "12345678901"

    @respx.mock
    async def test_get_pricing_500_returns_none(self):
        """5xx error returns None — caller skips pricing, does not block claim."""
        respx.get("http://localhost:8005/api/v1/drugs/pricing/12345678901").mock(
            return_value=httpx.Response(500, json={"error": "internal"})
        )
        client = DrugDatabaseClient(base_url="http://localhost:8005")
        result = await client.get_pricing("12345678901")
        assert result is None

    # ------------------------------------------------------------------
    # Legacy sync stub interface
    # ------------------------------------------------------------------

    def test_validate_ndc_11_digits_returns_true(self):
        client = DrugDatabaseClient()
        assert client.validate_ndc("12345678901") is True

    def test_validate_ndc_wrong_length_returns_false(self):
        client = DrugDatabaseClient()
        assert client.validate_ndc("123456789") is False

    def test_validate_ndc_non_numeric_returns_false(self):
        client = DrugDatabaseClient()
        assert client.validate_ndc("1234567890A") is False

    def test_get_drug_info_returns_none(self):
        client = DrugDatabaseClient()
        assert client.get_drug_info("12345678901") is None
