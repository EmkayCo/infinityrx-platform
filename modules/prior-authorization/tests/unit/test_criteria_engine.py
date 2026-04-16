"""Unit tests for the PA clinical criteria evaluation engine.

Tests cover: auto-approve, diagnosis match, step therapy, GLP-1 criteria,
age range, lab values, quantity justification, and criteria versioning.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from src.models.tables import PACriteriaSet, PARequest
from src.services.criteria_engine import CriteriaResult, evaluate_criteria

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
PLAN = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
MEMBER = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TODAY = date(2026, 4, 16)


def _make_pa(
    *,
    drug_ndc: str = "00000000001",
    clinical_data: dict | None = None,
) -> PARequest:
    return PARequest(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        member_id=MEMBER,
        prescriber_npi="1234567890",
        drug_ndc=drug_ndc,
        drug_name="Test Drug",
        source="manual",
        status="submitted",
        priority="routine",
        plan_id=PLAN,
        program_id=None,
        clinical_data=clinical_data,
        criteria_set_version=1,
    )


def _make_criteria(
    criteria: dict,
    *,
    version: int = 1,
    drug_ndc: str = "00000000001",
) -> PACriteriaSet:
    return PACriteriaSet(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        drug_ndc=drug_ndc,
        drug_class=None,
        plan_id=PLAN,
        criteria=criteria,
        version=version,
        effective_date=date(2026, 1, 1),
    )


# ---------------------------------------------------------------------------
# Test: Auto-approve when all criteria met
# ---------------------------------------------------------------------------


class TestAutoApprove:
    def test_all_criteria_met_returns_auto_approve(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "diagnosis_codes": ["E11"],
            "age_range": {"min": 18, "max": 75},
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_age=45,
            member_diagnoses=["E11.9"],
            reference_date=TODAY,
        )

        assert result.auto_approve is True
        assert result.reasons == []
        assert result.missing_info == []

    def test_empty_criteria_auto_approves(self):
        pa = _make_pa()
        criteria_set = _make_criteria({})

        result = evaluate_criteria(pa, criteria_set, reference_date=TODAY)

        assert result.auto_approve is True


# ---------------------------------------------------------------------------
# Test: Diagnosis match
# ---------------------------------------------------------------------------


class TestDiagnosisMatch:
    def test_deny_when_diagnosis_does_not_match(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "diagnosis_codes": ["E11", "E66"],
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_diagnoses=["J45.20"],  # Asthma, not diabetes
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert any("No qualifying diagnosis" in r for r in result.reasons)

    def test_approve_with_prefix_match(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "diagnosis_codes": ["E11"],
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_diagnoses=["E11.65"],  # T2DM with hyperglycemia
            reference_date=TODAY,
        )

        assert result.auto_approve is True

    def test_missing_diagnosis_data_pends(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "diagnosis_codes": ["E11"],
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_diagnoses=None,
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert "diagnosis_codes" in result.missing_info


# ---------------------------------------------------------------------------
# Test: Step therapy
# ---------------------------------------------------------------------------


class TestStepTherapy:
    def test_approve_with_prior_trial_evidence(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "step_therapy_lookback_days": 90,
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            step_therapy_history=[
                {
                    "drug_ndc": "99999999999",
                    "start_date": str(TODAY - timedelta(days=60)),
                    "end_date": str(TODAY - timedelta(days=30)),
                },
            ],
            reference_date=TODAY,
        )

        assert result.auto_approve is True

    def test_deny_without_prior_trial(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "step_therapy_lookback_days": 90,
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            step_therapy_history=[],
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert any("Step therapy" in r for r in result.reasons)

    def test_deny_when_trial_too_old(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "step_therapy_lookback_days": 90,
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            step_therapy_history=[
                {
                    "drug_ndc": "99999999999",
                    "start_date": str(TODAY - timedelta(days=200)),
                    "end_date": str(TODAY - timedelta(days=150)),
                },
            ],
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert any("Step therapy" in r for r in result.reasons)

    def test_missing_step_therapy_data_pends(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "step_therapy_lookback_days": 90,
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            step_therapy_history=None,
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert "step_therapy_history" in result.missing_info


# ---------------------------------------------------------------------------
# Test: GLP-1 criteria
# ---------------------------------------------------------------------------


class TestGLP1Criteria:
    def test_bmi_above_threshold_approves(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "glp1_bmi_threshold": 30,
            "glp1_comorbidities": ["E11", "I10"],
            "glp1_lifestyle_intervention_days": 180,
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_bmi=32.5,
            member_comorbidities=["E11.9"],
            lifestyle_intervention_date=TODAY - timedelta(days=90),
            reference_date=TODAY,
        )

        assert result.auto_approve is True

    def test_bmi_below_threshold_denies(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "glp1_bmi_threshold": 30,
            "glp1_comorbidities": ["E11"],
            "glp1_lifestyle_intervention_days": 180,
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_bmi=24.5,
            member_comorbidities=["E11.9"],
            lifestyle_intervention_date=TODAY - timedelta(days=90),
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert any("BMI" in r for r in result.reasons)

    def test_missing_bmi_pends(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "glp1_bmi_threshold": 30,
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_bmi=None,
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert "member_bmi" in result.missing_info

    def test_missing_comorbidity_denies(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "glp1_bmi_threshold": 27,
            "glp1_comorbidities": ["E11", "I10"],
            "glp1_lifestyle_intervention_days": 180,
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_bmi=28.0,
            member_comorbidities=["J45"],  # Asthma, not qualifying
            lifestyle_intervention_date=TODAY - timedelta(days=90),
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert any("comorbidity" in r.lower() for r in result.reasons)

    def test_old_lifestyle_intervention_denies(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "glp1_bmi_threshold": 30,
            "glp1_comorbidities": ["E11"],
            "glp1_lifestyle_intervention_days": 180,
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_bmi=35.0,
            member_comorbidities=["E11.9"],
            lifestyle_intervention_date=TODAY - timedelta(days=365),
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert any("Lifestyle intervention" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# Test: Age range
# ---------------------------------------------------------------------------


class TestAgeRange:
    def test_age_within_range_passes(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "age_range": {"min": 18, "max": 75},
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_age=45,
            reference_date=TODAY,
        )

        assert result.auto_approve is True

    def test_age_below_minimum_fails(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "age_range": {"min": 18, "max": 75},
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_age=16,
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert any("age 16 below minimum 18" in r for r in result.reasons)

    def test_age_above_maximum_fails(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "age_range": {"min": 18, "max": 75},
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_age=80,
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert any("age 80 above maximum 75" in r for r in result.reasons)

    def test_missing_age_pends(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "age_range": {"min": 18},
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            member_age=None,
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert "member_age" in result.missing_info


# ---------------------------------------------------------------------------
# Test: Lab values
# ---------------------------------------------------------------------------


class TestLabValues:
    def test_lab_value_within_range_passes(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "lab_values": {"HbA1c": {"min": 7.0}},
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            lab_results={"HbA1c": 8.5},
            reference_date=TODAY,
        )

        assert result.auto_approve is True

    def test_lab_value_below_minimum_fails(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "lab_values": {"HbA1c": {"min": 7.0}},
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            lab_results={"HbA1c": 5.5},
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert any("HbA1c" in r for r in result.reasons)

    def test_missing_required_lab_value_pends(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "lab_values": {"HbA1c": {"min": 7.0}, "eGFR": {"min": 30}},
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            lab_results={"HbA1c": 8.5},  # eGFR missing
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert "lab_value:eGFR" in result.missing_info

    def test_no_lab_results_at_all_pends(self):
        pa = _make_pa()
        criteria_set = _make_criteria({
            "lab_values": {"HbA1c": {"min": 7.0}},
        })

        result = evaluate_criteria(
            pa,
            criteria_set,
            lab_results=None,
            reference_date=TODAY,
        )

        assert result.auto_approve is False
        assert "lab_values" in result.missing_info


# ---------------------------------------------------------------------------
# Test: Quantity justification
# ---------------------------------------------------------------------------


class TestQuantityJustification:
    def test_quantity_justification_provided_passes(self):
        pa = _make_pa(clinical_data={"quantity_justification": "Documented need for 90-day supply"})
        criteria_set = _make_criteria({
            "quantity_justification_required": True,
        })

        result = evaluate_criteria(pa, criteria_set, reference_date=TODAY)

        assert result.auto_approve is True

    def test_quantity_justification_missing_pends(self):
        pa = _make_pa(clinical_data={})
        criteria_set = _make_criteria({
            "quantity_justification_required": True,
        })

        result = evaluate_criteria(pa, criteria_set, reference_date=TODAY)

        assert result.auto_approve is False
        assert "quantity_justification" in result.missing_info


# ---------------------------------------------------------------------------
# Test: Criteria versioning
# ---------------------------------------------------------------------------


class TestCriteriaVersioning:
    def test_old_pa_uses_version_at_submission_time(self):
        """Criteria sets are versioned. A PA submitted under v1 should be
        evaluated against v1 criteria, even if v2 is now current."""
        pa = _make_pa()

        # v1 criteria: lenient (BMI >= 27)
        criteria_v1 = _make_criteria(
            {"glp1_bmi_threshold": 27, "glp1_lifestyle_intervention_days": 0},
            version=1,
        )
        # v2 criteria: stricter (BMI >= 30) -- not used for this PA
        criteria_v2 = _make_criteria(
            {"glp1_bmi_threshold": 30, "glp1_lifestyle_intervention_days": 0},
            version=2,
        )

        # BMI 28 passes v1 but would fail v2
        result_v1 = evaluate_criteria(
            pa,
            criteria_v1,
            member_bmi=28.0,
            reference_date=TODAY,
        )
        result_v2 = evaluate_criteria(
            pa,
            criteria_v2,
            member_bmi=28.0,
            reference_date=TODAY,
        )

        assert result_v1.auto_approve is True
        assert result_v2.auto_approve is False
        assert any("BMI" in r for r in result_v2.reasons)


# ---------------------------------------------------------------------------
# Test: CriteriaResult dataclass
# ---------------------------------------------------------------------------


class TestCriteriaResult:
    def test_result_is_immutable(self):
        result = CriteriaResult(auto_approve=True)
        with pytest.raises(AttributeError):
            result.auto_approve = False  # type: ignore[misc]

    def test_default_empty_lists(self):
        result = CriteriaResult(auto_approve=True)
        assert result.reasons == []
        assert result.missing_info == []
