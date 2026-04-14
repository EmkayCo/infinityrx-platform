"""999 Implementation Acknowledgment and TA1 parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..delimiters import detect_delimiters
from ..segments import parse_segments


@dataclass
class Parsed999:
    sender_id: str
    receiver_id: str
    isa_control_number: str
    original_transaction_type: str
    original_gs_control: str
    ack_code: str           # A=accepted, R=rejected, E=accepted with errors
    error_codes: List[str] = field(default_factory=list)


@dataclass
class ParsedTA1:
    sender_id: str
    receiver_id: str
    isa_control_number: str
    ack_control_number: str
    ack_date: str
    ack_time: str
    ack_code: str
    error_code: str


def parse_999(raw: str) -> Parsed999:
    """Parse a 999 implementation acknowledgment."""
    delims = detect_delimiters(raw)
    segs = parse_segments(raw, delims)

    isa = next((s for s in segs if s[0] == "ISA"), None)
    if isa is None:
        raise ValueError("No ISA segment found")

    sender_id = isa[6]
    receiver_id = isa[8]
    isa_control = isa[13]

    original_type = ""
    original_gs = ""
    ack_code = "A"
    error_codes: List[str] = []

    for seg in segs:
        sid = seg[0]
        if sid == "AK1":
            original_type = seg[1] if len(seg) > 1 else ""
            original_gs = seg[2] if len(seg) > 2 else ""
        elif sid == "IK5":
            ack_code = seg[1] if len(seg) > 1 else "A"
        elif sid == "CTX":
            error_codes.append(seg[1] if len(seg) > 1 else "")

    return Parsed999(
        sender_id=sender_id,
        receiver_id=receiver_id,
        isa_control_number=isa_control,
        original_transaction_type=original_type,
        original_gs_control=original_gs,
        ack_code=ack_code,
        error_codes=error_codes,
    )


def parse_ta1(raw: str) -> ParsedTA1:
    """Parse a TA1 interchange acknowledgment."""
    delims = detect_delimiters(raw)
    segs = parse_segments(raw, delims)

    isa = next((s for s in segs if s[0] == "ISA"), None)
    if isa is None:
        raise ValueError("No ISA segment found")

    sender_id = isa[6]
    receiver_id = isa[8]
    isa_control = isa[13]

    ta1 = next((s for s in segs if s[0] == "TA1"), None)
    if ta1 is None:
        raise ValueError("No TA1 segment found")

    return ParsedTA1(
        sender_id=sender_id,
        receiver_id=receiver_id,
        isa_control_number=isa_control,
        ack_control_number=ta1[1] if len(ta1) > 1 else "",
        ack_date=ta1[2] if len(ta1) > 2 else "",
        ack_time=ta1[3] if len(ta1) > 3 else "",
        ack_code=ta1[4] if len(ta1) > 4 else "",
        error_code=ta1[5] if len(ta1) > 5 else "",
    )
