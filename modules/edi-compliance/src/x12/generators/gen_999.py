"""999 Implementation Acknowledgment generator per 005010X231A1.

Acknowledges receipt and acceptance/rejection of a functional group.
TA1 acknowledgment is for interchange-level errors (separate function below).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import Generate999Request, GenerateTA1Request


def _build_isa(req: Generate999Request, delims: Delimiters, now: datetime) -> str:
    elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, pad_isa_id(req.sender_id),
        req.receiver_qualifier, pad_isa_id(req.receiver_id),
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", pad_isa_control(req.isa_control_number),
        "0", "T" if req.test_mode else "P", delims.sub_element,
    ]
    return build_segment("ISA", elements, delims)


def generate_999(
    req: Generate999Request,
    delims: Optional[Delimiters] = None,
    now: Optional[datetime] = None,
) -> str:
    """Generate a 999 functional acknowledgment."""
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)

    segs: List[str] = []

    segs.append(_build_isa(req, delims, now))
    segs.append(build_gs("FA", req.sender_id.strip(), req.receiver_id.strip(),
                         req.gs_control_number, now, req.implementation_guide, delims))
    st_num = req.st_control_number
    segs.append(build_st("999", st_num, req.implementation_guide, delims))

    # AK1 — functional group response header
    segs.append(build_segment("AK1", [
        req.original_transaction_type,
        str(req.original_gs_control),
        req.implementation_guide,
    ], delims))

    # AK2 — transaction set response header
    segs.append(build_segment("AK2", [
        req.original_transaction_type,
        "0001",
        req.implementation_guide,
    ], delims))

    # IK5 — transaction set acknowledgment
    segs.append(build_segment("IK5", [req.ack_code], delims))

    # Error segments if any
    for error_code in req.error_codes:
        segs.append(build_segment("CTX", [error_code], delims))

    # AK9 — functional group acknowledge trailer
    accepted_count = 1 if req.ack_code in ("A", "E") else 0
    error_count = len(req.error_codes)
    segs.append(build_segment("AK9", [
        req.ack_code,
        "1",                    # number of transaction sets included
        "1",                    # number of received
        str(accepted_count),    # number accepted
        str(error_count) if error_count > 0 else "",
    ], delims))

    body_count = len(segs) - 2
    segs.append(build_se(body_count + 1, st_num, delims))
    segs.append(build_ge(1, req.gs_control_number, delims))
    segs.append(build_iea(req.isa_control_number, 1, delims))

    return "".join(segs)


def generate_ta1(
    req: GenerateTA1Request,
    delims: Optional[Delimiters] = None,
    now: Optional[datetime] = None,
) -> str:
    """Generate a TA1 interchange acknowledgment (embedded directly in ISA/IEA envelope)."""
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)

    # TA1 is sent between ISA and IEA without GS/GE (interchange-level only)
    isa_elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, pad_isa_id(req.sender_id),
        req.receiver_qualifier, pad_isa_id(req.receiver_id),
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", pad_isa_control(req.isa_control_number),
        "0", "T" if req.test_mode else "P", delims.sub_element,
    ]
    isa_seg = build_segment("ISA", isa_elements, delims)

    ta1_seg = build_segment("TA1", [
        pad_isa_control(req.ack_control_number),
        req.ack_date,
        req.ack_time,
        req.ack_code,
        req.error_code,
    ], delims)

    iea_seg = build_segment("IEA", [
        "0",
        pad_isa_control(req.isa_control_number),
    ], delims)

    return isa_seg + ta1_seg + iea_seg
