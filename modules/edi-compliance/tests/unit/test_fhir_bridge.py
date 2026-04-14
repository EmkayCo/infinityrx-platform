"""Tests for FHIR R4 ↔ X12 bridge."""

from __future__ import annotations



from src.services.fhir_bridge import (
    fhir_coverage_request_to_270,
    fhir_prior_auth_to_278,
    parsed_271_to_fhir,
    parsed_278_to_fhir,
)
from src.x12.parsers.parse_271 import Parsed271, Parsed271Benefit
from src.x12.parsers.parse_278 import Parsed278, Parsed278ServiceReview


class TestFhirCoverageRequestTo270:
    def _fhir_request(self, **kwargs) -> dict:
        base = {
            "patient": {
                "name": [{"family": "SMITH", "given": ["ALICE"]}],
                "birthDate": "1980-06-15",
            },
            "coverage": {"subscriberId": "SUB001"},
            "insurer": {"identifier": {"value": "PAYER01"}, "display": "AETNA"},
            "servicedDate": "2026-01-15",
        }
        base.update(kwargs)
        return base

    def test_extracts_subscriber_last_name(self):
        result = fhir_coverage_request_to_270(self._fhir_request())
        assert result["subscriber_last_name"] == "SMITH"

    def test_extracts_subscriber_first_name(self):
        result = fhir_coverage_request_to_270(self._fhir_request())
        assert result["subscriber_first_name"] == "ALICE"

    def test_extracts_dob_stripped_hyphens(self):
        result = fhir_coverage_request_to_270(self._fhir_request())
        assert result["subscriber_dob"] == "19800615"

    def test_extracts_subscriber_id(self):
        result = fhir_coverage_request_to_270(self._fhir_request())
        assert result["subscriber_id"] == "SUB001"

    def test_extracts_payer_id(self):
        result = fhir_coverage_request_to_270(self._fhir_request())
        assert result["payer_id"] == "PAYER01"

    def test_extracts_payer_name(self):
        result = fhir_coverage_request_to_270(self._fhir_request())
        assert result["payer_name"] == "AETNA"

    def test_extracts_date_of_service(self):
        result = fhir_coverage_request_to_270(self._fhir_request())
        assert result["date_of_service"] == "20260115"

    def test_missing_patient_name_defaults_empty(self):
        req = {"patient": {}, "coverage": {"subscriberId": ""}, "insurer": {}}
        result = fhir_coverage_request_to_270(req)
        assert result["subscriber_last_name"] == ""

    def test_payer_name_fallback_to_name_field(self):
        req = self._fhir_request()
        req["insurer"] = {"identifier": {"value": "P2"}, "name": "CIGNA"}
        result = fhir_coverage_request_to_270(req)
        assert result["payer_name"] == "CIGNA"


class TestFhirPriorAuthTo278:
    def _fhir_claim(self, **kwargs) -> dict:
        base = {
            "_patientName": {"family": "DOE", "given": ["JANE"]},
            "_memberId": "SUB002",
            "insurer": {"identifier": {"value": "P01"}, "display": "HUMANA"},
            "provider": {"identifier": {"value": "1234567893"}, "display": "CLINIC"},
            "item": [
                {
                    "productOrService": {"coding": [{"code": "99213"}]},
                    "diagnosisSequence": [1],
                    "quantity": {"value": 2},
                    "servicedDate": "2026-02-01",
                    "category": {"coding": [{"code": "1"}]},
                }
            ],
        }
        base.update(kwargs)
        return base

    def test_extracts_payer_id(self):
        result = fhir_prior_auth_to_278(self._fhir_claim())
        assert result["payer_id"] == "P01"

    def test_extracts_payer_name(self):
        result = fhir_prior_auth_to_278(self._fhir_claim())
        assert result["payer_name"] == "HUMANA"

    def test_extracts_provider_npi(self):
        result = fhir_prior_auth_to_278(self._fhir_claim())
        assert result["provider_npi"] == "1234567893"

    def test_extracts_subscriber_last_name(self):
        result = fhir_prior_auth_to_278(self._fhir_claim())
        assert result["subscriber_last_name"] == "DOE"

    def test_extracts_member_id(self):
        result = fhir_prior_auth_to_278(self._fhir_claim())
        assert result["subscriber_id"] == "SUB002"

    def test_extracts_service_review_procedure_code(self):
        result = fhir_prior_auth_to_278(self._fhir_claim())
        assert result["service_reviews"][0]["procedure_code"] == "99213"

    def test_extracts_service_review_units(self):
        result = fhir_prior_auth_to_278(self._fhir_claim())
        assert result["service_reviews"][0]["units"] == "2"

    def test_extracts_service_review_from_date(self):
        result = fhir_prior_auth_to_278(self._fhir_claim())
        assert result["service_reviews"][0]["from_date"] == "20260201"

    def test_empty_items_list(self):
        claim = self._fhir_claim()
        claim["item"] = []
        result = fhir_prior_auth_to_278(claim)
        assert result["service_reviews"] == []

    def test_item_without_coding(self):
        claim = self._fhir_claim()
        claim["item"][0]["productOrService"] = {}
        result = fhir_prior_auth_to_278(claim)
        assert result["service_reviews"][0]["procedure_code"] == ""


class TestParsed271ToFhir:
    def _make_parsed271(self, eligibility_status="1", benefits=None) -> Parsed271:
        return Parsed271(
            sender_id="SENDER",
            receiver_id="RECEIVER",
            isa_control_number="000000001",
            payer_id="PAYER01",
            payer_name="AETNA",
            subscriber_id="SUB001",
            subscriber_last_name="HILL",
            subscriber_first_name="MARY",
            subscriber_dob="19800101",
            eligibility_status=eligibility_status,
            benefits=benefits or [],
        )

    def test_resource_type(self):
        result = parsed_271_to_fhir(self._make_parsed271())
        assert result["resourceType"] == "CoverageEligibilityResponse"

    def test_inforce_true_when_active(self):
        result = parsed_271_to_fhir(self._make_parsed271(eligibility_status="1"))
        assert result["insurance"][0]["inforce"] is True

    def test_inforce_false_when_inactive(self):
        result = parsed_271_to_fhir(self._make_parsed271(eligibility_status="6"))
        assert result["insurance"][0]["inforce"] is False

    def test_outcome_complete_when_active(self):
        result = parsed_271_to_fhir(self._make_parsed271())
        assert result["outcome"] == "complete"

    def test_outcome_error_when_inactive(self):
        result = parsed_271_to_fhir(self._make_parsed271(eligibility_status="6"))
        assert result["outcome"] == "error"

    def test_patient_reference(self):
        result = parsed_271_to_fhir(self._make_parsed271())
        assert result["patient"]["reference"] == "Patient/SUB001"

    def test_insurer_display(self):
        result = parsed_271_to_fhir(self._make_parsed271())
        assert result["insurer"]["display"] == "AETNA"

    def test_benefit_with_monetary_amount(self):
        benefit = Parsed271Benefit(
            eligibility_code="1", coverage_level="IND", service_type_code="30",
            monetary_amount="500.00",
        )
        result = parsed_271_to_fhir(self._make_parsed271(benefits=[benefit]))
        item = result["insurance"][0]["item"][0]
        assert "benefit" in item
        # Value is a str (not float) to preserve Decimal precision (H-01 fix)
        assert item["benefit"][0]["allowedMoney"]["value"] == "500.00"

    def test_benefit_without_monetary_amount(self):
        benefit = Parsed271Benefit(
            eligibility_code="1", coverage_level="IND", service_type_code="30",
        )
        result = parsed_271_to_fhir(self._make_parsed271(benefits=[benefit]))
        item = result["insurance"][0]["item"][0]
        assert "benefit" not in item


class TestParsed278ToFhir:
    def _make_parsed278(self, reviews=None) -> Parsed278:
        return Parsed278(
            sender_id="SENDER",
            receiver_id="RECEIVER",
            isa_control_number="000000001",
            payer_id="PAYER01",
            payer_name="CIGNA",
            provider_npi="1234567893",
            provider_name="CLINIC",
            subscriber_id="SUB001",
            subscriber_last_name="REED",
            subscriber_first_name="TOM",
            is_response=True,
            service_reviews=reviews or [],
        )

    def test_resource_type(self):
        result = parsed_278_to_fhir(self._make_parsed278())
        assert result["resourceType"] == "ClaimResponse"

    def test_use_preauthorization(self):
        result = parsed_278_to_fhir(self._make_parsed278())
        assert result["use"] == "preauthorization"

    def test_patient_reference(self):
        result = parsed_278_to_fhir(self._make_parsed278())
        assert result["patient"]["reference"] == "Patient/SUB001"

    def test_approved_decision(self):
        review = Parsed278ServiceReview(review_type="HS", service_type_code="1", decision="A1")
        result = parsed_278_to_fhir(self._make_parsed278(reviews=[review]))
        adj = result["item"][0]["adjudication"][0]
        assert adj["category"]["coding"][0]["code"] == "approved"

    def test_denied_decision(self):
        review = Parsed278ServiceReview(review_type="HS", service_type_code="1", decision="A3")
        result = parsed_278_to_fhir(self._make_parsed278(reviews=[review]))
        adj = result["item"][0]["adjudication"][0]
        assert adj["category"]["coding"][0]["code"] == "denied"

    def test_pending_decision(self):
        review = Parsed278ServiceReview(review_type="HS", service_type_code="1", decision="A4")
        result = parsed_278_to_fhir(self._make_parsed278(reviews=[review]))
        adj = result["item"][0]["adjudication"][0]
        assert adj["category"]["coding"][0]["code"] == "pending"

    def test_auth_number_in_preauth_ref(self):
        review = Parsed278ServiceReview(
            review_type="HS", service_type_code="1", decision="A1",
            authorization_number="AUTH42",
        )
        result = parsed_278_to_fhir(self._make_parsed278(reviews=[review]))
        assert result["preAuthRef"] == "AUTH42"

    def test_no_auth_number_empty_string(self):
        result = parsed_278_to_fhir(self._make_parsed278())
        assert result["preAuthRef"] == ""

    def test_multiple_reviews(self):
        reviews = [
            Parsed278ServiceReview(review_type="HS", service_type_code="1", decision="A1"),
            Parsed278ServiceReview(review_type="HS", service_type_code="2", decision="A3"),
        ]
        result = parsed_278_to_fhir(self._make_parsed278(reviews=reviews))
        assert len(result["item"]) == 2
