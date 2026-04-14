"""Tests for taxonomy code reference service."""

from __future__ import annotations

import pytest

from src.services.taxonomy_service import TaxonomyService


class TestTaxonomyService:
    @pytest.fixture
    def service(self):
        return TaxonomyService()

    def test_is_prescriber_for_physician_taxonomy(self, service):
        # 207Q00000X = Family Medicine — should be a prescriber
        assert service.is_prescriber("207Q00000X") is True

    def test_is_not_prescriber_for_pharmacy_taxonomy(self, service):
        # 3336C0003X = Community/Retail Pharmacy — not an individual prescriber
        assert service.is_prescriber("3336C0003X") is False

    def test_is_pharmacy_for_pharmacy_taxonomy(self, service):
        assert service.is_pharmacy("3336C0003X") is True

    def test_is_not_pharmacy_for_physician(self, service):
        assert service.is_pharmacy("207Q00000X") is False

    def test_get_simplified_specialty_for_family_medicine(self, service):
        result = service.get_simplified_specialty("207Q00000X")
        assert result is not None
        assert "family" in result.lower() or "medicine" in result.lower() or "primary" in result.lower()

    def test_unknown_taxonomy_code_returns_none(self, service):
        assert service.get_simplified_specialty("UNKNOWN00X") is None
        assert service.is_prescriber("UNKNOWN00X") is False
        assert service.is_pharmacy("UNKNOWN00X") is False

    def test_get_display_name_for_known_code(self, service):
        name = service.get_display_name("207Q00000X")
        assert name is not None
        assert len(name) > 0

    def test_list_prescriber_taxonomies_returns_non_empty(self, service):
        prescribers = service.list_prescriber_taxonomy_codes()
        assert len(prescribers) > 10

    def test_np_taxonomy_is_prescriber(self, service):
        # 363L00000X = Nurse Practitioner
        assert service.is_prescriber("363L00000X") is True

    def test_pa_taxonomy_is_prescriber(self, service):
        # 363A00000X = Physician Assistant
        assert service.is_prescriber("363A00000X") is True
