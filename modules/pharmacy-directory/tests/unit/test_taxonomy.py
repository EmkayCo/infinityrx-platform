"""RED tests: NPPES taxonomy code -> pharmacy_type auto-classification."""
from __future__ import annotations

import pytest

from src.utils.taxonomy import classify_pharmacy_type


class TestTaxonomyClassification:
    @pytest.mark.parametrize(
        "taxonomy,expected",
        [
            ("333600000X", "retail"),
            ("3336C0003X", "retail"),
            ("3336C0004X", "compounding"),
            ("3336H0001X", "home_infusion"),
            ("3336I0012X", "institutional"),
            ("3336L0003X", "ltc"),
            ("3336M0002X", "mail_order"),
            ("3336N0007X", "nuclear"),
            ("3336S0011X", "specialty"),
        ],
    )
    def test_known_taxonomy_codes_classified(self, taxonomy: str, expected: str) -> None:
        assert classify_pharmacy_type(taxonomy) == expected

    def test_unknown_taxonomy_returns_retail(self) -> None:
        assert classify_pharmacy_type("9999999999") == "retail"
