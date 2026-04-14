"""FHIR R4 ↔ X12 bridge.

Converts FHIR R4 resources to X12 270/271 and 278 request structures,
and converts X12 271/278 responses back to FHIR CoverageEligibilityResponse
and ClaimResponse resources.

No PHI is logged. FHIR resources are dicts (json.loads output).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---- FHIR → X12 ----

def fhir_coverage_request_to_270(
    fhir_request: Dict[str, Any],
) -> Dict[str, Any]:
    """Convert a FHIR CoverageEligibilityRequest to a 270 request dict.

    Returns a dict suitable for constructing a Generate270Request.
    """
    patient = fhir_request.get("patient", {})
    patient_name = patient.get("name", [{}])[0] if isinstance(patient.get("name"), list) else {}
    family = patient_name.get("family", "")
    given = (patient_name.get("given") or [""])[0]
    dob = patient.get("birthDate", "").replace("-", "")

    coverage = fhir_request.get("coverage", {})
    member_id = coverage.get("subscriberId", "")

    payer = fhir_request.get("insurer", {})
    payer_id = payer.get("identifier", {}).get("value", "")
    payer_name = payer.get("display", payer.get("name", ""))

    service_date = fhir_request.get("servicedDate", "").replace("-", "")

    return {
        "subscriber_last_name": family,
        "subscriber_first_name": given,
        "subscriber_dob": dob,
        "subscriber_id": member_id,
        "payer_id": payer_id,
        "payer_name": payer_name,
        "date_of_service": service_date,
    }


def fhir_prior_auth_to_278(
    fhir_claim: Dict[str, Any],
) -> Dict[str, Any]:
    """Convert a FHIR Claim (prior-auth) to a 278 request dict.

    Returns a dict suitable for constructing a Generate278Request.
    """
    patient_ref = fhir_claim.get("patient", {}).get("reference", "")
    patient_name = fhir_claim.get("_patientName", {})
    family = patient_name.get("family", "")
    given = (patient_name.get("given") or [""])[0]

    insurer = fhir_claim.get("insurer", {})
    payer_id = insurer.get("identifier", {}).get("value", "")
    payer_name = insurer.get("display", "")

    provider = fhir_claim.get("provider", {})
    provider_npi = provider.get("identifier", {}).get("value", "")
    provider_name = provider.get("display", "")

    member_id = fhir_claim.get("_memberId", "")

    items = fhir_claim.get("item", [])
    service_reviews = []
    for item in items:
        product_service = item.get("productOrService", {})
        procedure_code = ""
        if "coding" in product_service:
            codings = product_service["coding"]
            if codings:
                procedure_code = codings[0].get("code", "")

        dx_codes = []
        for dx in item.get("diagnosisSequence", []):
            dx_codes.append(str(dx))

        service_reviews.append({
            "review_type": "HS",
            "service_type_code": item.get("category", {}).get("coding", [{}])[0].get("code", ""),
            "procedure_code": procedure_code,
            "diagnosis_code": dx_codes[0] if dx_codes else "",
            "units": str(item.get("quantity", {}).get("value", 1)),
            "from_date": item.get("servicedDate", "").replace("-", ""),
        })

    return {
        "payer_id": payer_id,
        "payer_name": payer_name,
        "provider_npi": provider_npi,
        "provider_name": provider_name,
        "subscriber_id": member_id,
        "subscriber_last_name": family,
        "subscriber_first_name": given,
        "service_reviews": service_reviews,
    }


# ---- X12 → FHIR ----

def parsed_271_to_fhir(parsed_271: Any) -> Dict[str, Any]:
    """Convert a Parsed271 to a FHIR CoverageEligibilityResponse resource."""
    benefits = []
    for b in parsed_271.benefits:
        item: Dict[str, Any] = {
            "category": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/ex-benefitcategory",
                             "code": b.service_type_code}]
            },
            "network": {"text": b.in_plan_network or "unknown"},
        }
        if b.monetary_amount:
            item["benefit"] = [{"type": {"text": "benefit"},
                                 "allowedMoney": {"value": float(b.monetary_amount), "currency": "USD"}}]
        benefits.append(item)

    return {
        "resourceType": "CoverageEligibilityResponse",
        "status": "active",
        "purpose": ["benefits"],
        "patient": {"reference": f"Patient/{parsed_271.subscriber_id}"},
        "insurer": {"display": parsed_271.payer_name},
        "outcome": "complete" if parsed_271.eligibility_status == "1" else "error",
        "insurance": [
            {
                "coverage": {"reference": f"Coverage/{parsed_271.subscriber_id}"},
                "inforce": parsed_271.eligibility_status == "1",
                "item": benefits,
            }
        ],
    }


def parsed_278_to_fhir(parsed_278: Any) -> Dict[str, Any]:
    """Convert a Parsed278 to a FHIR ClaimResponse resource."""
    items = []
    for i, review in enumerate(parsed_278.service_reviews):
        outcome = "complete"
        if review.decision == "A1":
            adjudication_value = "approved"
        elif review.decision == "A3":
            adjudication_value = "denied"
            outcome = "error"
        else:
            adjudication_value = "pending"

        items.append({
            "itemSequence": i + 1,
            "adjudication": [
                {
                    "category": {"coding": [{"code": adjudication_value}]},
                    "reason": {"text": f"Prior authorization decision: {review.decision}"},
                }
            ],
        })

    auth_ref = ""
    for review in parsed_278.service_reviews:
        if review.authorization_number:
            auth_ref = review.authorization_number
            break

    return {
        "resourceType": "ClaimResponse",
        "status": "active",
        "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type",
                              "code": "professional"}]},
        "use": "preauthorization",
        "patient": {"reference": f"Patient/{parsed_278.subscriber_id}"},
        "insurer": {"display": parsed_278.payer_name},
        "outcome": "complete",
        "preAuthRef": auth_ref,
        "item": items,
    }
