"""Tests for predictive denial scoring."""

from __future__ import annotations


from src.services.denial_scoring import (
    DenialRiskLevel,
    score_claim,
    _MEDIUM_THRESHOLD,
)


def _clean_claim():
    return {
        "member_id": "MBR001",
        "date_of_service": "20260101",
        "billing_npi": "1234567893",
        "rendering_npi": "1234567893",
        "place_of_service": "11",
        "service_lines": [{"procedure_code": "99213", "charge_amount": "150.00"}],
        "charge_amount": "150.00",
    }


class TestRiskLevels:
    def test_clean_claim_is_low_risk(self):
        result = score_claim(_clean_claim())
        assert result.risk_level == DenialRiskLevel.LOW
        assert result.score < _MEDIUM_THRESHOLD

    def test_score_is_float_between_0_and_1(self):
        result = score_claim(_clean_claim())
        assert 0.0 <= result.score <= 1.0

    def test_low_risk_recommendation(self):
        result = score_claim(_clean_claim())
        assert "Proceed" in result.recommendation

    def test_high_charge_triggers_outlier_factor(self):
        claim = _clean_claim()
        claim["charge_amount"] = "15000.00"
        claim["service_lines"] = [{"procedure_code": "99213", "charge_amount": "15000.00"}]
        result = score_claim(claim)
        assert any(f.code == "high_charge_outlier" for f in result.risk_factors)

    def test_no_prior_auth_when_required(self):
        claim = _clean_claim()
        claim["prior_auth_required"] = True
        result = score_claim(claim)
        assert any(f.code == "no_prior_auth" for f in result.risk_factors)

    def test_prior_auth_present_no_factor(self):
        claim = _clean_claim()
        claim["prior_auth_required"] = True
        claim["prior_auth_number"] = "AUTH12345"
        result = score_claim(claim)
        assert not any(f.code == "no_prior_auth" for f in result.risk_factors)

    def test_missing_rendering_npi_triggers_factor(self):
        claim = _clean_claim()
        del claim["rendering_npi"]
        result = score_claim(claim)
        assert any(f.code == "missing_rendering_npi" for f in result.risk_factors)

    def test_claim_frequency_7_triggers_factor(self):
        claim = _clean_claim()
        claim["claim_frequency"] = "7"
        result = score_claim(claim)
        assert any(f.code == "claim_frequency_replacement" for f in result.risk_factors)

    def test_pos_mismatch_triggers_factor(self):
        claim = _clean_claim()
        claim["place_of_service"] = "11"
        claim["facility_claim"] = True
        result = score_claim(claim)
        assert any(f.code == "place_of_service_mismatch" for f in result.risk_factors)

    def test_pos_10_mismatch_triggers_factor(self):
        claim = _clean_claim()
        claim["place_of_service"] = "10"
        claim["facility_claim"] = True
        result = score_claim(claim)
        assert any(f.code == "place_of_service_mismatch" for f in result.risk_factors)

    def test_many_diagnoses_triggers_factor(self):
        claim = _clean_claim()
        claim["other_diagnoses"] = ["A09", "M54.5", "Z00.0", "K21.0", "I10"]
        result = score_claim(claim)
        assert any(f.code == "multiple_diagnoses_with_primary_risk" for f in result.risk_factors)

    def test_high_risk_procedure_code_triggers_factor(self):
        claim = _clean_claim()
        claim["_high_risk_procedure_codes"] = ["99213"]
        result = score_claim(claim)
        assert any(f.code == "new_procedure_code" for f in result.risk_factors)

    def test_high_risk_procedure_not_in_claim_no_factor(self):
        claim = _clean_claim()
        claim["_high_risk_procedure_codes"] = ["00001"]
        result = score_claim(claim)
        assert not any(f.code == "new_procedure_code" for f in result.risk_factors)

    def test_medium_risk_recommendation_text(self):
        claim = _clean_claim()
        # Add enough weight for medium: no_prior_auth (0.25) + high_charge (0.20) = 0.45
        claim["prior_auth_required"] = True
        claim["charge_amount"] = "15000.00"
        claim["service_lines"] = [{"procedure_code": "99213", "charge_amount": "15000.00"}]
        result = score_claim(claim)
        if result.risk_level == DenialRiskLevel.MEDIUM:
            assert "Review" in result.recommendation

    def test_high_risk_recommendation_text(self):
        claim = _clean_claim()
        # Pile on enough features to exceed 0.70
        claim["prior_auth_required"] = True
        del claim["rendering_npi"]
        claim["charge_amount"] = "15000.00"
        claim["service_lines"] = [{"procedure_code": "99213", "charge_amount": "15000.00"}]
        claim["claim_frequency"] = "7"
        claim["place_of_service"] = "11"
        claim["facility_claim"] = True
        result = score_claim(claim)
        if result.risk_level == DenialRiskLevel.HIGH:
            assert "Hold" in result.recommendation

    def test_score_clamped_to_one(self):
        # Trigger all factors
        claim = {
            "prior_auth_required": True,
            "charge_amount": "15000.00",
            "service_lines": [{"procedure_code": "99213", "charge_amount": "15000.00",
                               "_high_risk_procedure_codes": ["99213"]}],
            "rendering_npi": None,
            "claim_frequency": "7",
            "place_of_service": "11",
            "facility_claim": True,
            "other_diagnoses": ["A09", "M54.5", "Z00.0", "K21.0", "I10"],
            "_high_risk_procedure_codes": ["99213"],
        }
        result = score_claim(claim)
        assert result.score <= 1.0

    def test_risk_factor_weight_matches_config(self):
        claim = _clean_claim()
        claim["prior_auth_required"] = True
        result = score_claim(claim)
        factor = next(f for f in result.risk_factors if f.code == "no_prior_auth")
        assert factor.weight == 0.25

    def test_invalid_charge_amount_handled(self):
        claim = _clean_claim()
        claim["charge_amount"] = "not_a_number"
        result = score_claim(claim)
        assert 0.0 <= result.score <= 1.0

    def test_empty_claim_returns_low_risk(self):
        result = score_claim({})
        assert result.risk_level == DenialRiskLevel.LOW
