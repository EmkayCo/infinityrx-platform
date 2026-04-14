"""Extended taxonomy service tests — hospital detection, pharmacy list."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from src.services.taxonomy_service import TaxonomyService


class TestTaxonomyServiceExtended:
    @pytest.fixture
    def service(self):
        return TaxonomyService()

    def test_is_hospital_for_hospital_taxonomy(self, service):
        assert service.is_hospital("282N00000X") is True

    def test_is_not_hospital_for_physician(self, service):
        assert service.is_hospital("207Q00000X") is False

    def test_list_pharmacy_codes_not_empty(self, service):
        codes = service.list_pharmacy_taxonomy_codes()
        assert len(codes) >= 3

    def test_unknown_code_is_not_hospital(self, service):
        assert service.is_hospital("UNKNOWN00X") is False

    def test_all_entries_returns_entries(self, service):
        entries = service.all_entries()
        assert len(entries) > 50
