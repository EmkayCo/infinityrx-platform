"""Unit tests for validators module — 100% coverage required (security path)."""
from __future__ import annotations

import pytest

from src.utils.validators import (
    is_valid_npi,
    is_valid_ndc,
    is_drug_hcpcs,
    is_valid_quarter,
    classify_site_of_care,
    has_jw_modifier,
    has_340b_modifier,
)


class TestNpiValidation:
    def test_valid_npi_10_digits(self):
        assert is_valid_npi("1234567890") is True

    def test_invalid_npi_too_short(self):
        assert is_valid_npi("123456789") is False

    def test_invalid_npi_too_long(self):
        assert is_valid_npi("12345678901") is False

    def test_invalid_npi_letters(self):
        assert is_valid_npi("123456789X") is False

    def test_invalid_npi_trailing_newline(self):
        # LESSON-004: must reject trailing newline — would pass ^...$
        assert is_valid_npi("1234567890\n") is False

    def test_invalid_npi_empty(self):
        assert is_valid_npi("") is False


class TestNdcValidation:
    def test_valid_ndc_11_digits(self):
        assert is_valid_ndc("12345678901") is True

    def test_invalid_ndc_too_short(self):
        assert is_valid_ndc("1234567890") is False

    def test_invalid_ndc_with_dashes(self):
        assert is_valid_ndc("1234-5678-901") is False

    def test_invalid_ndc_trailing_newline(self):
        # LESSON-004: must reject trailing newline
        assert is_valid_ndc("12345678901\n") is False


class TestDrugHcpcs:
    def test_j_code_is_drug(self):
        assert is_drug_hcpcs("J0135") is True

    def test_q_code_is_drug(self):
        assert is_drug_hcpcs("Q0169") is True

    def test_c_code_is_drug(self):
        assert is_drug_hcpcs("C9399") is True

    def test_e_code_not_drug(self):
        assert is_drug_hcpcs("E0100") is False

    def test_cpt_not_drug(self):
        assert is_drug_hcpcs("99213") is False

    def test_empty_not_drug(self):
        assert is_drug_hcpcs("") is False

    def test_lowercase_j_code(self):
        # Codes should be uppercase; lowercase should fail
        assert is_drug_hcpcs("j0135") is False


class TestQuarterValidation:
    def test_valid_quarters(self):
        for q in ["2026-Q1", "2026-Q2", "2026-Q3", "2026-Q4"]:
            assert is_valid_quarter(q) is True

    def test_invalid_q5(self):
        assert is_valid_quarter("2026-Q5") is False

    def test_invalid_format(self):
        assert is_valid_quarter("2026Q1") is False
        assert is_valid_quarter("Q1-2026") is False

    def test_trailing_newline(self):
        # LESSON-004
        assert is_valid_quarter("2026-Q1\n") is False


class TestSiteOfCare:
    def test_office_pos_11(self):
        assert classify_site_of_care("11") == "office_infusion"

    def test_hospital_outpatient_pos_22(self):
        assert classify_site_of_care("22") == "hospital_outpatient"

    def test_asc_pos_24(self):
        assert classify_site_of_care("24") == "asc"

    def test_home_pos_12(self):
        assert classify_site_of_care("12") == "home_infusion"

    def test_specialty_pharmacy_pos_01(self):
        assert classify_site_of_care("01") == "specialty_pharmacy"

    def test_unknown_pos_returns_none(self):
        assert classify_site_of_care("99") is None

    def test_none_returns_none(self):
        assert classify_site_of_care(None) is None


class TestModifiers:
    def test_jw_modifier_present(self):
        assert has_jw_modifier("JW", None, None, None) is True
        assert has_jw_modifier(None, "JW", None, None) is True
        assert has_jw_modifier(None, None, "JW", None) is True
        assert has_jw_modifier(None, None, None, "JW") is True

    def test_jw_modifier_absent(self):
        assert has_jw_modifier("59", None, None, None) is False
        assert has_jw_modifier(None, None, None, None) is False

    def test_340b_modifier_jg(self):
        assert has_340b_modifier("JG", None, None, None) is True

    def test_340b_modifier_tb(self):
        assert has_340b_modifier(None, "TB", None, None) is True

    def test_340b_modifier_absent(self):
        assert has_340b_modifier("JW", None, None, None) is False
        assert has_340b_modifier(None, None, None, None) is False
