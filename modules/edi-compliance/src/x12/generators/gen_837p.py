"""837P Professional Claim generator per 005010X222A2."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import Generate837PRequest


def _fmt_amount(amount: Decimal) -> str:
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _build_isa(req: Generate837PRequest, delims: Delimiters, now: datetime) -> str:
    sender_id = pad_isa_id(req.sender_id)
    receiver_id = pad_isa_id(req.receiver_id)
    control = pad_isa_control(req.isa_control_number)
    usage = "T" if req.test_mode else "P"
    elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, sender_id,
        req.receiver_qualifier, receiver_id,
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", control, "0", usage, delims.sub_element,
    ]
    return build_segment("ISA", elements, delims)


def _build_claim_segments(claim: dict[str, Any], delims: Delimiters) -> list[str]:
    segs = []
    claim_id = claim.get("claim_id", "")
    charge = Decimal(str(claim.get("charge_amount", "0")))
    facility_code = claim.get("facility_code", "11")
    claim_freq = claim.get("claim_frequency", "1")
    provider_signature = "Y"
    assignment = "A"
    benefits_assignment = "Y"
    release = "I"

    clm_elems = [
        claim_id,
        _fmt_amount(charge),
        None, None,
        f"{facility_code}{delims.sub_element}B{delims.sub_element}{claim_freq}",
        provider_signature,
        assignment,
        benefits_assignment,
        release,
    ]
    segs.append(build_segment("CLM", clm_elems, delims))

    # Principal diagnosis
    if "principal_diagnosis" in claim:
        segs.append(build_segment("HI", [f"ABK{delims.sub_element}{claim['principal_diagnosis']}"], delims))

    # Service lines
    for i, svc in enumerate(claim.get("service_lines", []), start=1):
        svc_date = svc.get("date_of_service", "")
        segs.append(build_segment("LX", [str(i)], delims))
        proc = svc.get("procedure_code", "")
        svc_charge = Decimal(str(svc.get("charge_amount", "0")))
        units = svc.get("units", "1")
        pos = svc.get("place_of_service", facility_code)
        sv1_elems = [
            f"HC{delims.sub_element}{proc}",
            _fmt_amount(svc_charge),
            "UN", str(units), pos, None, "1",
        ]
        segs.append(build_segment("SV1", sv1_elems, delims))
        if svc_date:
            segs.append(build_segment("DTP", ["472", "D8", svc_date], delims))

    return segs


def generate_837p(req: Generate837PRequest, delims: Delimiters | None = None, now: datetime | None = None) -> str:
    """Generate a complete 837P EDI file string.

    Validated before return — fail-closed.
    """
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)
    segments: list[str] = []

    segments.append(_build_isa(req, delims, now))
    segments.append(build_gs(
        functional_id="HC",
        sender_id=req.sender_id.strip(),
        receiver_id=req.receiver_id.strip(),
        gs_control_number=req.gs_control_number,
        now=now,
        version=req.implementation_guide,
        delims=delims,
    ))

    st_num = req.st_control_number
    segments.append(build_st("837", st_num, req.implementation_guide, delims))

    # BHT — beginning of hierarchical transaction
    segments.append(build_segment("BHT", ["0019", "00", "INFINITYRX837", now.strftime("%Y%m%d"), now.strftime("%H%M"), "CH"], delims))

    hier_id = 0

    # HL — submitter loop
    hier_id += 1
    segments.append(build_segment("HL", [str(hier_id), "", "20", "1"], delims))
    segments.append(build_segment("NM1", ["41", "2", req.billing_provider_name, "", "", "", "", "46", req.billing_provider_ein or req.billing_provider_npi], delims))

    # HL — receiver loop
    hier_id += 1
    segments.append(build_segment("HL", [str(hier_id), "1", "21", "1"], delims))
    segments.append(build_segment("NM1", ["40", "2", req.payer_name, "", "", "", "", "46", req.payer_id], delims))

    # HL — subscriber loop
    hier_id += 1
    segments.append(build_segment("HL", [str(hier_id), "2", "22", "0"], delims))
    segments.append(build_segment("SBR", ["P", "18", "", "", "", "", "", "", "HM"], delims))
    # NM1 subscriber — no PHI in logs but PHI IS in the EDI payload
    segments.append(build_segment("NM1", [
        "IL", "1",
        req.subscriber_last_name,
        req.subscriber_first_name,
        "", "", "",
        "MI", req.subscriber_id,
    ], delims))
    segments.append(build_segment("DMG", ["D8", req.subscriber_dob, req.subscriber_gender], delims))

    # Payer NM1
    segments.append(build_segment("NM1", ["PR", "2", req.payer_name, "", "", "", "", "PI", req.payer_id], delims))

    # Billing provider NM1
    segments.append(build_segment("NM1", ["85", "2", req.billing_provider_name, "", "", "", "", "XX", req.billing_provider_npi], delims))

    # Claims
    for claim in req.claims:
        segments.extend(_build_claim_segments(claim, delims))

    body_seg_count = len(segments) - 2  # exclude ISA and GS
    se = build_se(body_seg_count + 1, st_num, delims)
    segments.append(se)
    segments.append(build_ge(1, req.gs_control_number, delims))
    segments.append(build_iea(req.isa_control_number, 1, delims))

    result = "".join(segments)

    from ..validators.validator import validate_837p_basic
    errors = validate_837p_basic(result, delims)
    if errors:
        raise ValueError(f"Generated 837P failed validation: {errors}")

    return result
