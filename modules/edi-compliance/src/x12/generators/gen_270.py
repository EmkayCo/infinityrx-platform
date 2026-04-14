"""270 Eligibility Inquiry generator per 005010X279A1."""

from __future__ import annotations

from datetime import datetime, timezone

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import Generate270Request


def _build_isa(req: Generate270Request, delims: Delimiters, now: datetime) -> str:
    sender_id = pad_isa_id(req.sender_id)
    receiver_id = pad_isa_id(req.receiver_id)
    control = pad_isa_control(req.isa_control_number)
    usage = "T" if req.test_mode else "P"
    elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, sender_id,
        req.receiver_qualifier, receiver_id,
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", control, "1", usage, delims.sub_element,
    ]
    return build_segment("ISA", elements, delims)


def generate_270(req: Generate270Request, delims: Delimiters | None = None, now: datetime | None = None) -> str:
    """Generate a complete 270 eligibility inquiry EDI string."""
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)
    segments: list[str] = []

    segments.append(_build_isa(req, delims, now))
    segments.append(build_gs(
        functional_id="HS",
        sender_id=req.sender_id.strip(),
        receiver_id=req.receiver_id.strip(),
        gs_control_number=req.gs_control_number,
        now=now,
        version=req.implementation_guide,
        delims=delims,
    ))

    st_num = req.st_control_number
    segments.append(build_st("270", st_num, req.implementation_guide, delims))

    # BHT
    segments.append(build_segment("BHT", ["0022", "13", f"INQ{st_num}", now.strftime("%Y%m%d"), now.strftime("%H%M")], delims))

    hier_id = 0

    # HL — information source (payer)
    hier_id += 1
    segments.append(build_segment("HL", [str(hier_id), "", "20", "1"], delims))
    segments.append(build_segment("NM1", ["PR", "2", req.payer_name, "", "", "", "", "PI", req.payer_id], delims))

    # HL — information receiver (us)
    hier_id += 1
    segments.append(build_segment("HL", [str(hier_id), "1", "21", "1"], delims))
    segments.append(build_segment("NM1", [
        "1P", "2", "INFINITYRX", "", "", "", "",
        req.receiver_id_qualifier, req.receiver_npi,
    ], delims))

    # HL — subscriber
    hier_id += 1
    segments.append(build_segment("HL", [str(hier_id), "2", "22", "0"], delims))
    segments.append(build_segment("TRN", ["1", f"TRN{st_num}", req.receiver_npi], delims))
    nm1_elems = [
        "IL", "1",
        req.subscriber_last_name,
        req.subscriber_first_name,
        "", "", "",
        "MI", req.subscriber_id,
    ]
    segments.append(build_segment("NM1", nm1_elems, delims))

    if req.subscriber_dob:
        segments.append(build_segment("DMG", ["D8", req.subscriber_dob], delims))

    if req.date_of_service:
        segments.append(build_segment("DTP", ["291", "D8", req.date_of_service], delims))

    # EQ — eligibility benefit inquiry
    for svc_code in req.service_type_codes:
        segments.append(build_segment("EQ", [svc_code], delims))

    body_seg_count = len(segments) - 2
    segments.append(build_se(body_seg_count + 1, st_num, delims))
    segments.append(build_ge(1, req.gs_control_number, delims))
    segments.append(build_iea(req.isa_control_number, 1, delims))

    return "".join(segments)
