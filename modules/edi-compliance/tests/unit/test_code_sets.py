"""Tests for code set validation (code_sets.py)."""

from __future__ import annotations


from src.services.code_sets import (
    CodeSetType,
    validate_claim_frequency,
    validate_cpt,
    validate_hcpcs,
    validate_icd10cm,
    validate_icd10pcs,
    validate_ndc,
    validate_place_of_service,
    validate_procedure_code,
    validate_revenue_code,
)


class TestValidatePlaceOfService:
    def test_valid_pos_11(self):
        r = validate_place_of_service("11")
        assert r.valid is True
        assert r.code_set == CodeSetType.PLACE_OF_SERVICE
        assert r.error == ""

    def test_valid_pos_21(self):
        assert validate_place_of_service("21").valid is True

    def test_valid_pos_99(self):
        assert validate_place_of_service("99").valid is True

    def test_invalid_pos_unknown(self):
        r = validate_place_of_service("00")
        assert r.valid is False
        assert "00" in r.error

    def test_strips_whitespace(self):
        assert validate_place_of_service("  11  ").valid is True

    def test_invalid_pos_alpha(self):
        assert validate_place_of_service("AB").valid is False


class TestValidateClaimFrequency:
    def test_valid_freq_1(self):
        r = validate_claim_frequency("1")
        assert r.valid is True
        assert r.code_set == CodeSetType.CLAIM_FREQUENCY

    def test_valid_freq_7(self):
        assert validate_claim_frequency("7").valid is True

    def test_valid_freq_A(self):
        assert validate_claim_frequency("A").valid is True

    def test_valid_freq_H(self):
        assert validate_claim_frequency("H").valid is True

    def test_invalid_freq(self):
        r = validate_claim_frequency("Z")
        assert r.valid is False
        assert "Z" in r.error

    def test_strips_whitespace(self):
        assert validate_claim_frequency(" 1 ").valid is True


class TestValidateNdc:
    def test_valid_11_digit_ndc(self):
        r = validate_ndc("12345678901")
        assert r.valid is True
        assert r.code_set == CodeSetType.NDC

    def test_valid_with_hyphens_stripped(self):
        r = validate_ndc("1234-5678-901")
        assert r.valid is True

    def test_valid_with_spaces_stripped(self):
        r = validate_ndc("12345 67890 1")
        assert r.valid is True

    def test_invalid_too_short(self):
        r = validate_ndc("1234567890")
        assert r.valid is False
        assert "NDC" in r.error

    def test_invalid_too_long(self):
        r = validate_ndc("123456789012")
        assert r.valid is False

    def test_invalid_has_letters(self):
        r = validate_ndc("1234567890A")
        assert r.valid is False


class TestValidateCpt:
    def test_valid_5_digit_cpt(self):
        r = validate_cpt("99213")
        assert r.valid is True
        assert r.code_set == CodeSetType.CPT

    def test_valid_category_ii(self):
        r = validate_cpt("0002F")
        assert r.valid is True

    def test_valid_category_iii(self):
        r = validate_cpt("0001T")
        assert r.valid is True

    def test_invalid_format(self):
        r = validate_cpt("9921")
        assert r.valid is False
        assert "CPT" in r.error

    def test_strips_whitespace(self):
        assert validate_cpt(" 99213 ").valid is True


class TestValidateHcpcs:
    def test_valid_hcpcs_level2(self):
        r = validate_hcpcs("A9999")
        assert r.valid is True
        assert r.code_set == CodeSetType.HCPCS

    def test_valid_5_digit_numeric(self):
        r = validate_hcpcs("99213")
        assert r.valid is True

    def test_invalid_format(self):
        r = validate_hcpcs("AB123")
        assert r.valid is False
        assert "HCPCS" in r.error

    def test_strips_whitespace(self):
        assert validate_hcpcs(" A9999 ").valid is True


class TestValidateIcd10cm:
    def test_valid_without_dot(self):
        r = validate_icd10cm("A09")
        assert r.valid is True
        assert r.code_set == CodeSetType.ICD10CM

    def test_valid_with_dot(self):
        r = validate_icd10cm("A09.9")
        assert r.valid is True

    def test_valid_complex_code(self):
        r = validate_icd10cm("M54.5")
        assert r.valid is True

    def test_invalid_format(self):
        r = validate_icd10cm("123")
        assert r.valid is False
        assert "ICD-10-CM" in r.error

    def test_invalid_lowercase(self):
        r = validate_icd10cm("a09")
        assert r.valid is False

    def test_strips_whitespace(self):
        assert validate_icd10cm(" A09 ").valid is True


class TestValidateIcd10pcs:
    def test_valid_7_char(self):
        r = validate_icd10pcs("0BT20ZZ")
        assert r.valid is True
        assert r.code_set == CodeSetType.ICD10PCS

    def test_valid_digits_only(self):
        r = validate_icd10pcs("0000000")
        assert r.valid is True

    def test_invalid_too_short(self):
        r = validate_icd10pcs("0BT20Z")
        assert r.valid is False
        assert "7 alphanumeric" in r.error

    def test_invalid_too_long(self):
        r = validate_icd10pcs("0BT20ZZZ")
        assert r.valid is False

    def test_invalid_lowercase(self):
        r = validate_icd10pcs("0bt20zz")
        assert r.valid is False

    def test_strips_whitespace(self):
        assert validate_icd10pcs(" 0BT20ZZ ").valid is True


class TestValidateRevenueCode:
    def test_valid_4_digit(self):
        r = validate_revenue_code("0100")
        assert r.valid is True
        assert r.code_set == CodeSetType.REVENUE_CODE

    def test_valid_0001(self):
        assert validate_revenue_code("0001").valid is True

    def test_invalid_3_digits(self):
        r = validate_revenue_code("100")
        assert r.valid is False
        assert "4 digits" in r.error

    def test_invalid_5_digits(self):
        r = validate_revenue_code("01000")
        assert r.valid is False

    def test_invalid_letters(self):
        r = validate_revenue_code("01AB")
        assert r.valid is False

    def test_strips_whitespace(self):
        assert validate_revenue_code(" 0100 ").valid is True


class TestValidateProcedureCode:
    def test_hc_qualifier_valid_cpt(self):
        r = validate_procedure_code("99213", "HC")
        assert r.valid is True
        assert r.code_set == CodeSetType.CPT

    def test_hc_qualifier_valid_hcpcs_fallback(self):
        r = validate_procedure_code("A9999", "HC")
        assert r.valid is True

    def test_hc_qualifier_invalid_both(self):
        r = validate_procedure_code("XXXXX", "HC")
        assert r.valid is False

    def test_ad_qualifier_valid_ada(self):
        r = validate_procedure_code("D0120", "AD")
        assert r.valid is True

    def test_ad_qualifier_invalid_ada(self):
        r = validate_procedure_code("99213", "AD")
        assert r.valid is False
        assert "ADA" in r.error

    def test_n4_qualifier_routes_to_ndc(self):
        r = validate_procedure_code("12345678901", "N4")
        assert r.valid is True
        assert r.code_set == CodeSetType.NDC

    def test_er_qualifier_routes_to_revenue(self):
        r = validate_procedure_code("0100", "ER")
        assert r.valid is True
        assert r.code_set == CodeSetType.REVENUE_CODE

    def test_unknown_qualifier_passes(self):
        r = validate_procedure_code("XYZ", "XX")
        assert r.valid is True
        assert r.code_set == CodeSetType.CPT

    def test_default_qualifier_is_hc(self):
        r = validate_procedure_code("99213")
        assert r.valid is True
