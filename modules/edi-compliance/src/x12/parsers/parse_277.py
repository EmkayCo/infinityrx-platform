"""277 Health Care Claim Status Response parser per 005010X212."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..delimiters import detect_delimiters
from ..segments import parse_segments


@dataclass
class Parsed277ClaimStatus:
    claim_id: str
    subscriber_id: str
    subscriber_last_name: str
    subscriber_first_name: str
    provider_npi: str
    provider_name: str
    status_category_code: str     # A0-A8, F0-F3, P1-P3
    status_code: str              # detailed status code from STC
    status_date: str
    charge_amount: str = ""
    paid_amount: str = ""
    date_of_service: str = ""


@dataclass
class Parsed277:
    sender_id: str
    receiver_id: str
    isa_control_number: str
    payer_id: str
    payer_name: str
    claim_statuses: List[Parsed277ClaimStatus] = field(default_factory=list)


def parse_277(raw: str) -> Parsed277:
    """Parse a 277 claim status response."""
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
    claim_statuses: List[Parsed277ClaimStatus] = []

    current_provider_npi = ""
    current_provider_name = ""
    current_sub_id = ""
    current_sub_last = ""
    current_sub_first = ""
    current_claim_id = ""
    current_dos = ""
    in_claim_hl = False

    for seg in segs:
        sid = seg[0]

        if sid == "HL":
            level_code = seg[3] if len(seg) > 3 else ""
            in_claim_hl = level_code == "23"

        elif sid == "NM1" and len(seg) > 3:
            entity = seg[1]
            if entity == "PR":
                payer_name = seg[3] if len(seg) > 3 else ""
                payer_id = seg[9] if len(seg) > 9 else ""
            elif entity == "1P":
                current_provider_name = seg[3] if len(seg) > 3 else ""
                current_provider_npi = seg[9] if len(seg) > 9 else ""
            elif entity == "IL":
                current_sub_last = seg[3] if len(seg) > 3 else ""
                current_sub_first = seg[4] if len(seg) > 4 else ""
                current_sub_id = seg[9] if len(seg) > 9 else ""

        elif sid == "DTP" and in_claim_hl:
            qualifier = seg[1] if len(seg) > 1 else ""
            if qualifier == "472":
                current_dos = seg[3] if len(seg) > 3 else ""

        elif sid == "REF" and in_claim_hl:
            qualifier = seg[1] if len(seg) > 1 else ""
            if qualifier == "1K":
                current_claim_id = seg[2] if len(seg) > 2 else ""

        elif sid == "STC" and len(seg) > 1:
            stc01 = seg[1] if len(seg) > 1 else ""
            status_date = seg[2] if len(seg) > 2 else ""
            # STC01 may be composite: category_code:status_code
            if delims.sub_element in stc01:
                parts = stc01.split(delims.sub_element, 1)
                cat_code = parts[0]
                detail_code = parts[1]
            else:
                cat_code = stc01
                detail_code = ""

            charge_amt = seg[4] if len(seg) > 4 else ""
            paid_amt = seg[9] if len(seg) > 9 else ""

            claim_statuses.append(Parsed277ClaimStatus(
                claim_id=current_claim_id,
                subscriber_id=current_sub_id,
                subscriber_last_name=current_sub_last,
                subscriber_first_name=current_sub_first,
                provider_npi=current_provider_npi,
                provider_name=current_provider_name,
                status_category_code=cat_code,
                status_code=detail_code,
                status_date=status_date,
                charge_amount=charge_amt,
                paid_amount=paid_amt,
                date_of_service=current_dos,
            ))
            current_claim_id = ""
            current_dos = ""

    return Parsed277(
        sender_id=sender_id,
        receiver_id=receiver_id,
        isa_control_number=isa_control,
        payer_id=payer_id,
        payer_name=payer_name,
        claim_statuses=claim_statuses,
    )
