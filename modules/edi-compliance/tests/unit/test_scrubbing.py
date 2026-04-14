"""Tests for pre-adjudication claim scrubbing engine."""

from __future__ import annotations

import pytest

from src.services.scrubbing import (
    ScrubEdit,
    ScrubResult,
    ScrubSeverity,
    scrub_claim,
)


def _minimal_valid_claim():
    return {
        "member_id": "MBR001",
        "date_of_service": "20260101",
        "billing_npi": "1234567893",  # Luhn-valid NPI
        "place_of_service": "11",
        "principal_diagnosis": "A09",
        "service_lines": [
            {
                "procedure_code": "99213",
                "qualifier": "HC",
                "charge_amount": "100.00",
                "units": "1",
            }
        ],
        "charge_amount": "100.00",
    }


class TestScrubResultProperties:
    def test_passed_when_no_errors(self):
        result = scrub_claim(_minimal_valid_claim())
        assert result.passed is True
        assert result.errors == []

    def test_errors_property_filters_warnings(self):
        edits = [
            ScrubEdit(ScrubSeverity.ERROR, "E001", "error"),
            ScrubEdit(ScrubSeverity.WARNING, "W001", "warning"),
        ]
        result = ScrubResult(passed=False, edits=edits)
        assert len(result.errors) == 1
        assert result.errors[0].code == "E001"

    def test_warnings_property_filters_errors(self):
        edits = [
            ScrubEdit(ScrubSeverity.ERROR, "E001", "error"),
            ScrubEdit(ScrubSeverity.WARNING, "W001", "warning"),
        ]
        result = ScrubResult(passed=False, edits=edits)
        assert len(result.warnings) == 1
        assert result.warnings[0].code == "W001"


class TestDemographicCompleteness:
    def test_missing_member_id_produces_scr001(self):
        claim = _minimal_valid_claim()
        del claim["member_id"]
        result = scrub_claim(claim)
        assert result.passed is False
        codes = [e.code for e in result.edits]
        assert "SCR-001" in codes

    def test_missing_date_of_service_produces_scr001(self):
        claim = _minimal_valid_claim()
        del claim["date_of_service"]
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-001" and "date_of_service" in e.field for e in result.edits)

    def test_missing_billing_npi_produces_scr001(self):
        claim = _minimal_valid_claim()
        del claim["billing_npi"]
        result = scrub_claim(claim)
        assert not result.passed

    def test_empty_member_id_produces_scr001(self):
        claim = _minimal_valid_claim()
        claim["member_id"] = ""
        result = scrub_claim(claim)
        assert not result.passed


class TestNpiValidation:
    def test_invalid_billing_npi_produces_scr002(self):
        claim = _minimal_valid_claim()
        claim["billing_npi"] = "1234567890"  # wrong Luhn
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-002" for e in result.edits)

    def test_invalid_rendering_npi_produces_scr002(self):
        claim = _minimal_valid_claim()
        claim["rendering_npi"] = "9999999999"
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-002" and "rendering_npi" in e.field for e in result.edits)

    def test_valid_rendering_npi_passes(self):
        claim = _minimal_valid_claim()
        claim["rendering_npi"] = "1234567893"
        result = scrub_claim(claim)
        assert result.passed

    def test_missing_rendering_npi_no_error(self):
        claim = _minimal_valid_claim()
        # rendering_npi not provided — no error
        result = scrub_claim(claim)
        assert result.passed


class TestDateValidation:
    def test_invalid_date_format_produces_scr003(self):
        claim = _minimal_valid_claim()
        claim["date_of_service"] = "01/01/2026"
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-003" for e in result.edits)

    def test_valid_yyyymmdd_passes(self):
        claim = _minimal_valid_claim()
        claim["date_of_service"] = "20260315"
        result = scrub_claim(claim)
        assert result.passed


class TestPlaceOfServiceValidation:
    def test_invalid_pos_produces_scr004(self):
        claim = _minimal_valid_claim()
        claim["place_of_service"] = "00"
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-004" for e in result.edits)

    def test_missing_pos_no_error(self):
        claim = _minimal_valid_claim()
        del claim["place_of_service"]
        result = scrub_claim(claim)
        assert result.passed


class TestClaimFrequencyValidation:
    def test_invalid_frequency_produces_scr005(self):
        claim = _minimal_valid_claim()
        claim["claim_frequency"] = "Z"
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-005" for e in result.edits)

    def test_valid_frequency_1(self):
        claim = _minimal_valid_claim()
        claim["claim_frequency"] = "1"
        result = scrub_claim(claim)
        assert result.passed

    def test_missing_frequency_no_error(self):
        claim = _minimal_valid_claim()
        result = scrub_claim(claim)
        assert result.passed


class TestDiagnosisValidation:
    def test_invalid_principal_dx_produces_scr006(self):
        claim = _minimal_valid_claim()
        claim["principal_diagnosis"] = "123"
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-006" for e in result.edits)

    def test_invalid_other_dx_produces_scr007(self):
        claim = _minimal_valid_claim()
        claim["other_diagnoses"] = ["A09", "BADCODE"]
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-007" and "[1]" in e.field for e in result.edits)

    def test_valid_other_dx_passes(self):
        claim = _minimal_valid_claim()
        claim["other_diagnoses"] = ["A09", "M54.5"]
        result = scrub_claim(claim)
        assert result.passed

    def test_missing_principal_dx_no_error(self):
        claim = _minimal_valid_claim()
        del claim["principal_diagnosis"]
        result = scrub_claim(claim)
        assert result.passed


class TestServiceLineValidation:
    def test_no_service_lines_produces_scr008(self):
        claim = _minimal_valid_claim()
        claim["service_lines"] = []
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-008" for e in result.edits)

    def test_invalid_procedure_code_produces_scr009(self):
        claim = _minimal_valid_claim()
        claim["service_lines"] = [{"procedure_code": "XXXXX", "qualifier": "HC", "charge_amount": "100"}]
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-009" for e in result.edits)

    def test_invalid_ndc_produces_scr010(self):
        claim = _minimal_valid_claim()
        claim["service_lines"] = [
            {"procedure_code": "99213", "qualifier": "HC", "charge_amount": "100", "ndc": "12345"}
        ]
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-010" for e in result.edits)

    def test_valid_ndc_11_digits(self):
        claim = _minimal_valid_claim()
        claim["service_lines"][0]["ndc"] = "12345678901"
        result = scrub_claim(claim)
        assert result.passed

    def test_zero_charge_produces_scr011(self):
        claim = _minimal_valid_claim()
        claim["service_lines"] = [{"procedure_code": "99213", "charge_amount": "0.00"}]
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-011" for e in result.edits)

    def test_negative_charge_produces_scr011(self):
        claim = _minimal_valid_claim()
        claim["service_lines"] = [{"procedure_code": "99213", "charge_amount": "-10.00"}]
        result = scrub_claim(claim)
        assert not result.passed

    def test_non_numeric_charge_produces_scr011(self):
        claim = _minimal_valid_claim()
        claim["service_lines"] = [{"procedure_code": "99213", "charge_amount": "abc"}]
        result = scrub_claim(claim)
        assert not result.passed

    def test_zero_units_produces_scr012_warning(self):
        claim = _minimal_valid_claim()
        claim["service_lines"] = [
            {"procedure_code": "99213", "charge_amount": "100", "units": "0"}
        ]
        result = scrub_claim(claim)
        assert any(e.code == "SCR-012" and e.severity == ScrubSeverity.WARNING for e in result.edits)

    def test_incompatible_modifiers_produces_scr013(self):
        claim = _minimal_valid_claim()
        claim["service_lines"] = [
            {"procedure_code": "99213", "charge_amount": "100", "modifiers": ["LT", "RT"]}
        ]
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-013" for e in result.edits)

    def test_single_modifier_no_error(self):
        claim = _minimal_valid_claim()
        claim["service_lines"][0]["modifiers"] = ["25"]
        result = scrub_claim(claim)
        assert result.passed

    def test_non_numeric_units_no_exception(self):
        claim = _minimal_valid_claim()
        claim["service_lines"] = [
            {"procedure_code": "99213", "charge_amount": "100", "units": "bad"}
        ]
        result = scrub_claim(claim)
        # No crash, units warning skipped for unparseable


class TestTotalChargeValidation:
    def test_zero_total_charge_produces_scr014(self):
        claim = _minimal_valid_claim()
        claim["charge_amount"] = "0.00"
        result = scrub_claim(claim)
        assert not result.passed
        assert any(e.code == "SCR-014" for e in result.edits)

    def test_non_numeric_total_charge_produces_scr014(self):
        claim = _minimal_valid_claim()
        claim["charge_amount"] = "invalid"
        result = scrub_claim(claim)
        assert any(e.code == "SCR-014" for e in result.edits)

    def test_missing_total_charge_no_error(self):
        claim = _minimal_valid_claim()
        del claim["charge_amount"]
        result = scrub_claim(claim)
        assert result.passed
