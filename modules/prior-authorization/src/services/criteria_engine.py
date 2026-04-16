"""Clinical criteria evaluation engine for prior authorization.

Evaluates a PA request against a PACriteriaSet and returns a CriteriaResult
indicating whether the request can be auto-approved or must be routed to
a human reviewer.

All criteria checks are deterministic on identical inputs. GLP-1 criteria
follow current clinical guidelines (BMI threshold, comorbidity requirements,
prior lifestyle intervention evidence).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.models.tables import PACriteriaSet, PARequest

logger = logging.getLogger(__name__)

# Configurable defaults -- overridden via criteria set JSONB
DEFAULT_STEP_THERAPY_LOOKBACK_DAYS = 90
DEFAULT_GLP1_LIFESTYLE_INTERVENTION_DAYS = 180


@dataclass(frozen=True, slots=True)
class CriteriaResult:
    """Outcome of evaluating clinical criteria against a PA request."""

    auto_approve: bool
    reasons: list[str] = field(default_factory=list)
    missing_info: list[str] = field(default_factory=list)


def evaluate_criteria(
    pa_request: PARequest,
    criteria_set: PACriteriaSet,
    *,
    member_age: int | None = None,
    member_diagnoses: list[str] | None = None,
    step_therapy_history: list[dict] | None = None,
    lab_results: dict[str, float] | None = None,
    member_bmi: float | None = None,
    member_comorbidities: list[str] | None = None,
    lifestyle_intervention_date: date | None = None,
    reference_date: date | None = None,
) -> CriteriaResult:
    """Evaluate a PA request against clinical criteria.

    Parameters
    ----------
    pa_request:
        The PA request being evaluated.
    criteria_set:
        The criteria set to evaluate against (locked to version at submission).
    member_age:
        Patient age in years at time of request.
    member_diagnoses:
        List of ICD-10 diagnosis codes on file for the member.
    step_therapy_history:
        Prior medication trials: [{"drug_ndc": "...", "start_date": "...", "end_date": "..."}]
    lab_results:
        Lab values keyed by test name, e.g. {"HbA1c": 8.5, "eGFR": 72}.
    member_bmi:
        Current BMI if available (required for GLP-1 criteria).
    member_comorbidities:
        ICD-10 prefix codes for comorbid conditions (for GLP-1 criteria).
    lifestyle_intervention_date:
        Date when lifestyle intervention was documented.
    reference_date:
        Date to use as "today" for lookback calculations. Defaults to date.today().

    Returns
    -------
    CriteriaResult
        auto_approve=True if ALL criteria met, else False with reasons/missing_info.
    """
    reasons: list[str] = []
    missing_info: list[str] = []
    ref_date = reference_date or date.today()

    criteria = criteria_set.criteria

    # 1. Diagnosis match
    _check_diagnosis(criteria, member_diagnoses, reasons, missing_info)

    # 2. Step therapy evidence
    _check_step_therapy(criteria, step_therapy_history, ref_date, reasons, missing_info)

    # 3. Lab values
    _check_lab_values(criteria, lab_results, reasons, missing_info)

    # 4. Age range
    _check_age_range(criteria, member_age, reasons, missing_info)

    # 5. Quantity justification
    _check_quantity_justification(criteria, pa_request, reasons, missing_info)

    # 6. GLP-1 specific criteria
    if criteria.get("glp1_bmi_threshold") is not None:
        _check_glp1_criteria(
            criteria,
            member_bmi,
            member_comorbidities,
            lifestyle_intervention_date,
            ref_date,
            reasons,
            missing_info,
        )

    auto_approve = len(reasons) == 0 and len(missing_info) == 0

    if auto_approve:
        logger.info(
            "PA criteria auto-approve",
            extra={
                "pa_request_id": str(pa_request.id),
                "criteria_version": criteria_set.version,
            },
        )
    else:
        logger.info(
            "PA criteria requires review",
            extra={
                "pa_request_id": str(pa_request.id),
                "criteria_version": criteria_set.version,
                "pa_reason_count": len(reasons),
                "pa_missing_count": len(missing_info),
            },
        )

    return CriteriaResult(
        auto_approve=auto_approve,
        reasons=reasons,
        missing_info=missing_info,
    )


def _check_diagnosis(
    criteria: dict,
    member_diagnoses: list[str] | None,
    reasons: list[str],
    missing_info: list[str],
) -> None:
    """Check if member has a qualifying diagnosis."""
    required_codes = criteria.get("diagnosis_codes", [])
    if not required_codes:
        return

    if member_diagnoses is None:
        missing_info.append("diagnosis_codes")
        return

    # Match on prefix: "E11" matches "E11.9", "E11.65", etc.
    has_match = any(
        any(diag.startswith(req) for req in required_codes)
        for diag in member_diagnoses
    )
    if not has_match:
        reasons.append(
            f"No qualifying diagnosis found. Required one of: {', '.join(required_codes)}"
        )


def _check_step_therapy(
    criteria: dict,
    step_therapy_history: list[dict] | None,
    ref_date: date,
    reasons: list[str],
    missing_info: list[str],
) -> None:
    """Check if step therapy (prior trial) requirement is met."""
    lookback_days = criteria.get("step_therapy_lookback_days")
    if lookback_days is None:
        return

    if step_therapy_history is None:
        missing_info.append("step_therapy_history")
        return

    cutoff = ref_date - timedelta(days=int(lookback_days))
    has_prior_trial = False
    for trial in step_therapy_history:
        trial_end = trial.get("end_date")
        if trial_end is None:
            continue
        if isinstance(trial_end, str):
            trial_end = date.fromisoformat(trial_end)
        if trial_end >= cutoff:
            has_prior_trial = True
            break

    if not has_prior_trial:
        reasons.append(
            f"Step therapy requirement not met. No prior trial within {lookback_days} days."
        )


def _check_lab_values(
    criteria: dict,
    lab_results: dict[str, float] | None,
    reasons: list[str],
    missing_info: list[str],
) -> None:
    """Check required lab values against thresholds."""
    required_labs = criteria.get("lab_values", {})
    if not required_labs:
        return

    if lab_results is None:
        missing_info.append("lab_values")
        return

    for lab_name, thresholds in required_labs.items():
        if lab_name not in lab_results:
            missing_info.append(f"lab_value:{lab_name}")
            continue

        value = lab_results[lab_name]
        min_val = thresholds.get("min")
        max_val = thresholds.get("max")

        if min_val is not None and value < min_val:
            reasons.append(f"{lab_name} value {value} below minimum {min_val}")
        if max_val is not None and value > max_val:
            reasons.append(f"{lab_name} value {value} above maximum {max_val}")


def _check_age_range(
    criteria: dict,
    member_age: int | None,
    reasons: list[str],
    missing_info: list[str],
) -> None:
    """Check if member age falls within required range."""
    age_range = criteria.get("age_range", {})
    if not age_range:
        return

    if member_age is None:
        missing_info.append("member_age")
        return

    min_age = age_range.get("min")
    max_age = age_range.get("max")

    if min_age is not None and member_age < min_age:
        reasons.append(f"Member age {member_age} below minimum {min_age}")
    if max_age is not None and member_age > max_age:
        reasons.append(f"Member age {member_age} above maximum {max_age}")


def _check_quantity_justification(
    criteria: dict,
    pa_request: PARequest,
    reasons: list[str],
    missing_info: list[str],
) -> None:
    """Check if quantity justification is required and provided."""
    if not criteria.get("quantity_justification_required"):
        return

    clinical_data = pa_request.clinical_data or {}
    if not clinical_data.get("quantity_justification"):
        missing_info.append("quantity_justification")


def _check_glp1_criteria(
    criteria: dict,
    member_bmi: float | None,
    member_comorbidities: list[str] | None,
    lifestyle_intervention_date: date | None,
    ref_date: date,
    reasons: list[str],
    missing_info: list[str],
) -> None:
    """Evaluate GLP-1 specific criteria (BMI, comorbidities, lifestyle intervention).

    GLP-1 agents require:
    1. BMI at or above threshold (typically 30, or 27 with comorbidities)
    2. Qualifying comorbidity (T2DM, HTN, dyslipidemia, etc.)
    3. Prior lifestyle intervention documented within lookback period
    """
    bmi_threshold = criteria.get("glp1_bmi_threshold")
    required_comorbidities = criteria.get("glp1_comorbidities", [])
    intervention_lookback = criteria.get(
        "glp1_lifestyle_intervention_days",
        DEFAULT_GLP1_LIFESTYLE_INTERVENTION_DAYS,
    )

    # BMI check
    if member_bmi is None:
        missing_info.append("member_bmi")
    elif bmi_threshold is not None and member_bmi < bmi_threshold:
        reasons.append(
            f"BMI {member_bmi} below threshold {bmi_threshold}"
        )

    # Comorbidity check (required if specified)
    if required_comorbidities:
        if member_comorbidities is None:
            missing_info.append("member_comorbidities")
        else:
            has_comorbidity = any(
                any(comorb.startswith(req) for req in required_comorbidities)
                for comorb in member_comorbidities
            )
            if not has_comorbidity:
                reasons.append(
                    f"No qualifying comorbidity. Required one of: {', '.join(required_comorbidities)}"
                )

    # Lifestyle intervention check
    if intervention_lookback:
        if lifestyle_intervention_date is None:
            missing_info.append("lifestyle_intervention_date")
        else:
            cutoff = ref_date - timedelta(days=int(intervention_lookback))
            if lifestyle_intervention_date < cutoff:
                reasons.append(
                    f"Lifestyle intervention too old ({lifestyle_intervention_date}). "
                    f"Must be within {intervention_lookback} days."
                )
