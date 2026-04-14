"""271 Eligibility/Benefit Information Response generator per 005010X279A1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import Generate271Request


def _build_isa(req: Generate271Request, delims: Delimiters, now: datetime) -> str:
    elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, pad_isa_id(req.sender_id),
        req.receiver_qualifier, pad_isa_id(req.receiver_id),
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", pad_isa_control(req.isa_control_number),
        "0", "T" if req.test_mode else "P", delims.sub_element,
    ]
    return build_segment("ISA", elements, delims)


def generate_271(
    req: Generate271Request,
    delims: Optional[Delimiters] = None,
    now: Optional[datetime] = None,
) -> str:
    """Generate a 271 eligibility response."""
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)

    segs: List[str] = []

    segs.append(_build_isa(req, delims, now))
    segs.append(build_gs("HB", req.sender_id.strip(), req.receiver_id.strip(),
                         req.gs_control_number, now, req.implementation_guide, delims))
    st_num = req.st_control_number
    segs.append(build_st("271", st_num, req.implementation_guide, delims))

    # BHT
    segs.append(build_segment("BHT", [
        "0022", "11",
        f"ELIG{req.isa_control_number:09d}",
        now.strftime("%Y%m%d"), now.strftime("%H%M"),
    ], delims))

    hl_counter = 0

    # HL 1 — information source (payer)
    hl_counter += 1
    segs.append(build_segment("HL", [str(hl_counter), "", "20", "1"], delims))
    segs.append(build_segment("NM1", [
        "PR", "2",
        req.payer_name, "", "", "", "",
        "PI", req.payer_id,
    ], delims))

    # HL 2 — information receiver (originally the requester)
    hl_counter += 1
    segs.append(build_segment("HL", [str(hl_counter), "1", "21", "1"], delims))
    segs.append(build_segment("NM1", [
        "1P", "2",
        "INFINITYRX", "", "", "", "",
        "XX", "0000000000",
    ], delims))

    # HL 3 — subscriber
    hl_counter += 1
    segs.append(build_segment("HL", [str(hl_counter), "2", "22", "0"], delims))
    segs.append(build_segment("TRN", [
        "2", req.original_270_control or req.subscriber_id,
        req.payer_id,
    ], delims))
    segs.append(build_segment("NM1", [
        "IL", "1",
        req.subscriber_last_name, req.subscriber_first_name, "", "", "",
        "MI", req.subscriber_id,
    ], delims))
    if req.subscriber_dob:
        segs.append(build_segment("DMG", ["D8", req.subscriber_dob], delims))

    # DTP — eligibility dates
    if req.plan_begin_date:
        segs.append(build_segment("DTP", ["346", "D8", req.plan_begin_date], delims))
    if req.plan_end_date:
        segs.append(build_segment("DTP", ["347", "D8", req.plan_end_date], delims))

    # EB — eligibility/benefit info
    segs.append(build_segment("EB", [
        req.eligibility_status,    # EB01: 1=active, 6=inactive
        "IND",                     # EB02: individual
        "30",                      # EB03: health benefit plan coverage
        "HM",                      # EB04: health maintenance organization
    ], delims))

    # Additional benefit info
    for benefit in req.benefit_info:
        eb_code = benefit.get("eligibility_code", "1")
        coverage = benefit.get("coverage_level", "IND")
        svc_type = benefit.get("service_type_code", benefit.get("service_type", "30"))
        monetary = benefit.get("monetary_amount", "")
        in_network = benefit.get("in_plan_network", "")
        eb_elems = [eb_code, coverage, svc_type, "", "", "", monetary, "", "", "", "", in_network]
        segs.append(build_segment("EB", eb_elems, delims))

    body_count = len(segs) - 2
    segs.append(build_se(body_count + 1, st_num, delims))
    segs.append(build_ge(1, req.gs_control_number, delims))
    segs.append(build_iea(req.isa_control_number, 1, delims))

    return "".join(segs)
