"""278 Health Care Services Review parser per 005010X217."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..delimiters import detect_delimiters
from ..segments import parse_segments


@dataclass
class Parsed278ServiceReview:
    review_type: str
    service_type_code: str
    procedure_code: str = ""
    diagnosis_code: str = ""
    units: str = ""
    from_date: str = ""
    to_date: str = ""
    authorization_number: str = ""
    decision: str = ""


@dataclass
class Parsed278:
    sender_id: str
    receiver_id: str
    isa_control_number: str
    payer_id: str
    payer_name: str
    provider_npi: str
    provider_name: str
    subscriber_id: str
    subscriber_last_name: str
    subscriber_first_name: str
    subscriber_dob: str = ""
    is_response: bool = False
    service_reviews: List[Parsed278ServiceReview] = field(default_factory=list)


def parse_278(raw: str) -> Parsed278:
    """Parse a 278 prior authorization request or response."""
    delims = detect_delimiters(raw)
    segs = parse_segments(raw, delims)

    isa = next((s for s in segs if s[0] == "ISA"), None)
    if isa is None:
        raise ValueError("No ISA segment found")

    sender_id = isa[6]
    receiver_id = isa[8]
    isa_control = isa[13]

    payer_id = ""
    payer_name = ""
    provider_npi = ""
    provider_name = ""
    subscriber_id = ""
    sub_last = ""
    sub_first = ""
    sub_dob = ""
    is_response = False
    service_reviews: List[Parsed278ServiceReview] = []

    current_review_type = ""
    current_svc_type = ""
    current_proc = ""
    current_dx = ""
    current_units = ""
    current_from = ""
    current_to = ""
    current_auth = ""
    current_decision = ""
    in_service_hl = False

    for seg in segs:
        sid = seg[0]

        if sid == "BHT":
            purpose = seg[2] if len(seg) > 2 else ""
            is_response = purpose == "11"

        elif sid == "HL":
            level_code = seg[3] if len(seg) > 3 else ""
            in_service_hl = level_code == "SS"
            if in_service_hl:
                current_review_type = ""
                current_svc_type = ""
                current_proc = ""
                current_dx = ""
                current_units = ""
                current_from = ""
                current_to = ""
                current_auth = ""
                current_decision = ""

        elif sid == "NM1" and len(seg) > 3:
            entity = seg[1]
            if entity == "PR":
                payer_name = seg[3] if len(seg) > 3 else ""
                payer_id = seg[9] if len(seg) > 9 else ""
            elif entity == "1P":
                provider_name = seg[3] if len(seg) > 3 else ""
                provider_npi = seg[9] if len(seg) > 9 else ""
            elif entity == "IL":
                sub_last = seg[3] if len(seg) > 3 else ""
                sub_first = seg[4] if len(seg) > 4 else ""
                subscriber_id = seg[9] if len(seg) > 9 else ""

        elif sid == "DMG":
            sub_dob = seg[2] if len(seg) > 2 else ""

        elif sid == "UM" and in_service_hl:
            current_review_type = seg[1] if len(seg) > 1 else ""
            current_svc_type = seg[3] if len(seg) > 3 else ""

        elif sid == "HI" and in_service_hl:
            composite = seg[1] if len(seg) > 1 else ""
            if delims.sub_element in composite:
                qualifier, code = composite.split(delims.sub_element, 1)
                if qualifier == "BJ":
                    current_proc = code
                elif qualifier == "BK":
                    current_dx = code

        elif sid == "DTP" and in_service_hl:
            qualifier = seg[1] if len(seg) > 1 else ""
            date_val = seg[3] if len(seg) > 3 else ""
            if qualifier == "472":
                current_from = date_val
            elif qualifier == "473":
                current_to = date_val

        elif sid == "QTY" and in_service_hl:
            current_units = seg[2] if len(seg) > 2 else ""

        elif sid == "REF" and in_service_hl:
            qualifier = seg[1] if len(seg) > 1 else ""
            if qualifier == "BB":
                current_auth = seg[2] if len(seg) > 2 else ""

        elif sid == "HSD" and in_service_hl:
            current_decision = seg[8] if len(seg) > 8 else ""

        elif sid == "SE" and in_service_hl:
            service_reviews.append(Parsed278ServiceReview(
                review_type=current_review_type,
                service_type_code=current_svc_type,
                procedure_code=current_proc,
                diagnosis_code=current_dx,
                units=current_units,
                from_date=current_from,
                to_date=current_to,
                authorization_number=current_auth,
                decision=current_decision,
            ))
            in_service_hl = False

    # Flush any pending review if SE appeared before last HL closed
    if in_service_hl and current_review_type:
        service_reviews.append(Parsed278ServiceReview(
            review_type=current_review_type,
            service_type_code=current_svc_type,
            procedure_code=current_proc,
            diagnosis_code=current_dx,
            units=current_units,
            from_date=current_from,
            to_date=current_to,
            authorization_number=current_auth,
            decision=current_decision,
        ))

    return Parsed278(
        sender_id=sender_id,
        receiver_id=receiver_id,
        isa_control_number=isa_control,
        payer_id=payer_id,
        payer_name=payer_name,
        provider_npi=provider_npi,
        provider_name=provider_name,
        subscriber_id=subscriber_id,
        subscriber_last_name=sub_last,
        subscriber_first_name=sub_first,
        subscriber_dob=sub_dob,
        is_response=is_response,
        service_reviews=service_reviews,
    )
