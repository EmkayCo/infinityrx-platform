"""271 Eligibility/Benefit Information Response parser per 005010X279A1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..delimiters import detect_delimiters
from ..segments import parse_segments


@dataclass
class Parsed271Benefit:
    eligibility_code: str
    coverage_level: str
    service_type_code: str
    insurance_type_code: str = ""
    plan_coverage_description: str = ""
    time_period_qualifier: str = ""
    monetary_amount: str = ""
    percent: str = ""
    quantity_qualifier: str = ""
    quantity: str = ""
    authorization_required: bool = False
    in_plan_network: str = ""


@dataclass
class Parsed271:
    sender_id: str
    receiver_id: str
    isa_control_number: str
    payer_id: str
    payer_name: str
    subscriber_id: str
    subscriber_last_name: str
    subscriber_first_name: str
    subscriber_dob: str
    eligibility_status: str          # from EB01
    plan_begin_date: str = ""
    plan_end_date: str = ""
    benefits: List[Parsed271Benefit] = field(default_factory=list)


def parse_271(raw: str) -> Parsed271:
    """Parse a 271 eligibility response into a structured object."""
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
    subscriber_id = ""
    sub_last = ""
    sub_first = ""
    sub_dob = ""
    eligibility_status = ""
    plan_begin = ""
    plan_end = ""
    benefits: List[Parsed271Benefit] = []

    in_subscriber_hl = False

    for seg in segs:
        sid = seg[0]

        if sid == "HL":
            level_code = seg[3] if len(seg) > 3 else ""
            in_subscriber_hl = level_code == "22"

        elif sid == "NM1" and len(seg) > 4:
            entity = seg[1]
            if entity == "PR":
                payer_name = seg[3] if len(seg) > 3 else ""
                payer_id = seg[9] if len(seg) > 9 else ""
            elif entity == "IL" and in_subscriber_hl:
                sub_last = seg[3] if len(seg) > 3 else ""
                sub_first = seg[4] if len(seg) > 4 else ""
                subscriber_id = seg[9] if len(seg) > 9 else ""

        elif sid == "DMG" and in_subscriber_hl:
            sub_dob = seg[2] if len(seg) > 2 else ""

        elif sid == "DTP":
            qualifier = seg[1] if len(seg) > 1 else ""
            date_val = seg[3] if len(seg) > 3 else ""
            if qualifier == "346":
                plan_begin = date_val
            elif qualifier == "347":
                plan_end = date_val

        elif sid == "EB" and len(seg) > 1:
            if not eligibility_status:
                eligibility_status = seg[1]
            benefit = Parsed271Benefit(
                eligibility_code=seg[1] if len(seg) > 1 else "",
                coverage_level=seg[2] if len(seg) > 2 else "",
                service_type_code=seg[3] if len(seg) > 3 else "",
                insurance_type_code=seg[4] if len(seg) > 4 else "",
                plan_coverage_description=seg[5] if len(seg) > 5 else "",
                time_period_qualifier=seg[6] if len(seg) > 6 else "",
                monetary_amount=seg[7] if len(seg) > 7 else "",
                percent=seg[8] if len(seg) > 8 else "",
                quantity_qualifier=seg[9] if len(seg) > 9 else "",
                quantity=seg[10] if len(seg) > 10 else "",
                in_plan_network=seg[12] if len(seg) > 12 else "",
            )
            benefits.append(benefit)

    return Parsed271(
        sender_id=sender_id,
        receiver_id=receiver_id,
        isa_control_number=isa_control,
        payer_id=payer_id,
        payer_name=payer_name,
        subscriber_id=subscriber_id,
        subscriber_last_name=sub_last,
        subscriber_first_name=sub_first,
        subscriber_dob=sub_dob,
        eligibility_status=eligibility_status,
        plan_begin_date=plan_begin,
        plan_end_date=plan_end,
        benefits=benefits,
    )
