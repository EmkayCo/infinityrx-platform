"""834 Benefit Enrollment and Maintenance parser per 005010X220A1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..delimiters import detect_delimiters
from ..segments import parse_segments


@dataclass
class Parsed834Member:
    subscriber_id: str
    subscriber_last_name: str
    subscriber_first_name: str
    subscriber_dob: str = ""
    subscriber_gender: str = ""
    maintenance_type: str = ""    # 001=add, 002=change, 021=reinstate, 024=term
    maintenance_reason: str = ""
    benefit_status: str = ""      # A=active, T=terminated, C=COBRA
    employment_status: str = ""
    student_status: str = ""
    relationship_code: str = ""   # 18=self, 19=spouse, 01=child
    plan_id: str = ""


@dataclass
class Parsed834:
    sender_id: str
    receiver_id: str
    isa_control_number: str
    payer_id: str
    payer_name: str
    sponsor_name: str = ""
    reference_number: str = ""
    members: List[Parsed834Member] = field(default_factory=list)


def parse_834(raw: str) -> Parsed834:
    """Parse an 834 benefit enrollment transaction."""
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
    sponsor_name = ""
    reference_number = ""
    members: List[Parsed834Member] = []

    current_sub_id = ""
    current_sub_last = ""
    current_sub_first = ""
    current_dob = ""
    current_gender = ""
    current_maint_type = ""
    current_maint_reason = ""
    current_benefit_status = ""
    current_employment = ""
    current_student = ""
    current_relationship = ""
    current_plan_id = ""
    in_member_loop = False

    for seg in segs:
        sid = seg[0]

        if sid == "BGN":
            reference_number = seg[2] if len(seg) > 2 else ""

        elif sid == "NM1" and len(seg) > 3:
            entity = seg[1]
            if entity == "P5":
                payer_name = seg[3] if len(seg) > 3 else ""
                payer_id = seg[9] if len(seg) > 9 else ""
            elif entity == "CO":
                sponsor_name = seg[3] if len(seg) > 3 else ""
            elif entity in ("IL", "74"):
                if in_member_loop:
                    _flush_member(members, current_sub_id, current_sub_last, current_sub_first,
                                  current_dob, current_gender, current_maint_type,
                                  current_maint_reason, current_benefit_status,
                                  current_employment, current_student, current_relationship,
                                  current_plan_id)
                current_sub_last = seg[3] if len(seg) > 3 else ""
                current_sub_first = seg[4] if len(seg) > 4 else ""
                current_sub_id = seg[9] if len(seg) > 9 else ""
                current_dob = ""
                current_gender = ""
                current_maint_type = ""
                current_maint_reason = ""
                current_benefit_status = ""
                current_employment = ""
                current_student = ""
                current_relationship = ""
                current_plan_id = ""
                in_member_loop = True

        elif sid == "INS" and in_member_loop:
            current_relationship = seg[1] if len(seg) > 1 else ""
            current_maint_type = seg[3] if len(seg) > 3 else ""
            current_maint_reason = seg[4] if len(seg) > 4 else ""
            current_benefit_status = seg[5] if len(seg) > 5 else ""
            current_employment = seg[9] if len(seg) > 9 else ""
            current_student = seg[10] if len(seg) > 10 else ""

        elif sid == "DMG" and in_member_loop:
            current_dob = seg[2] if len(seg) > 2 else ""
            current_gender = seg[3] if len(seg) > 3 else ""

        elif sid == "HD" and in_member_loop:
            current_plan_id = seg[3] if len(seg) > 3 else ""

    if in_member_loop:
        _flush_member(members, current_sub_id, current_sub_last, current_sub_first,
                      current_dob, current_gender, current_maint_type, current_maint_reason,
                      current_benefit_status, current_employment, current_student,
                      current_relationship, current_plan_id)

    return Parsed834(
        sender_id=sender_id,
        receiver_id=receiver_id,
        isa_control_number=isa_control,
        payer_id=payer_id,
        payer_name=payer_name,
        sponsor_name=sponsor_name,
        reference_number=reference_number,
        members=members,
    )


def _flush_member(
    members: List[Parsed834Member],
    sub_id: str, last: str, first: str, dob: str, gender: str,
    maint_type: str, maint_reason: str, benefit_status: str,
    employment: str, student: str, relationship: str, plan_id: str,
) -> None:
    members.append(Parsed834Member(
        subscriber_id=sub_id,
        subscriber_last_name=last,
        subscriber_first_name=first,
        subscriber_dob=dob,
        subscriber_gender=gender,
        maintenance_type=maint_type,
        maintenance_reason=maint_reason,
        benefit_status=benefit_status,
        employment_status=employment,
        student_status=student,
        relationship_code=relationship,
        plan_id=plan_id,
    ))
