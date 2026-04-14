"""835 Remittance Advice generator per 005010X221A1.

All amounts are Decimal with ROUND_HALF_UP.  The generated file is validated
through the 4-level validator before being returned — fail-closed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import CasAdjustment, ClpClaim, Generate835Request, N1Party, SvcLine


def _fmt_amount(amount: Decimal) -> str:
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _build_isa(req: Generate835Request, delims: Delimiters, now: datetime) -> str:
    sender_id = pad_isa_id(req.sender_id)
    receiver_id = pad_isa_id(req.receiver_id if hasattr(req, "receiver_id") and req.receiver_id else "RECEIVER       ")  # type: ignore[attr-defined]
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


def _build_n1(party: N1Party, delims: Delimiters) -> list[str]:
    segs = []
    n1_elems: list[str | None] = [party.entity_qualifier, party.name]
    if party.id_qualifier:
        n1_elems.extend([party.id_qualifier, party.id_code])
    segs.append(build_segment("N1", n1_elems, delims))
    return segs


def _build_cas(adjustments: list[CasAdjustment], delims: Delimiters) -> list[str]:
    """Build CAS segments — up to 6 group/reason/amount triplets per segment."""
    if not adjustments:
        return []
    segs = []
    for adj in adjustments:
        segs.append(build_segment("CAS", [adj.group_code, adj.reason_code, _fmt_amount(adj.amount)], delims))
    return segs


def _build_svc(svc: SvcLine, delims: Delimiters) -> list[str]:
    segs = []
    # SVC01 composite: qualifier*code
    svc_qualifier = "N4" if svc.ndc else svc.procedure_qualifier
    code = svc.ndc if svc.ndc else svc.procedure_code
    svc01 = f"{svc_qualifier}{delims.sub_element}{code}"
    elems = [svc01, _fmt_amount(svc.charge_amount), _fmt_amount(svc.paid_amount), None, None, str(svc.quantity)]
    segs.append(build_segment("SVC", elems, delims))
    if svc.rx_number:
        segs.append(build_segment("REF", ["1D", svc.rx_number], delims))
    segs.extend(_build_cas(svc.adjustments, delims))
    return segs


def _build_clp(claim: ClpClaim, delims: Delimiters) -> list[str]:
    segs = []
    clp_elems = [
        claim.claim_id,
        claim.status_code,
        _fmt_amount(claim.charge_amount),
        _fmt_amount(claim.paid_amount),
        _fmt_amount(claim.patient_responsibility),
        claim.claim_filing_indicator,
        claim.payer_claim_ref or "",
    ]
    segs.append(build_segment("CLP", clp_elems, delims))
    if claim.patient_control_number:
        segs.append(build_segment("NM1", ["QC", "1", "", "", "", "", "", "MI", claim.patient_control_number], delims))
    # REF segments for pharmacy identifiers
    if claim.pharmacy_npi:
        segs.append(build_segment("REF", ["HPI", claim.pharmacy_npi], delims))
    if claim.bin_number:
        segs.append(build_segment("REF", ["G1", claim.bin_number], delims))
    if claim.ncpdp_number:
        segs.append(build_segment("REF", ["EO", claim.ncpdp_number], delims))
    if claim.chain_code:
        segs.append(build_segment("REF", ["PQ", claim.chain_code], delims))
    segs.extend(_build_cas(claim.adjustments, delims))
    for svc in claim.service_lines:
        segs.extend(_build_svc(svc, delims))
    return segs


def generate_835(req: Generate835Request, delims: Delimiters | None = None, now: datetime | None = None) -> str:
    """Generate a complete 835 EDI file string.

    The file is validated before returning — raises ValueError on any
    validation failure (fail-closed per PRD requirement).
    """
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)
    segments: list[str] = []

    # ISA
    isa = _build_isa(req, delims, now)
    segments.append(isa)

    # GS — functional identifier "HP" for 835
    gs = build_gs(
        functional_id="HP",
        sender_id=req.sender_id.strip(),
        receiver_id=req.receiver_id.strip() if hasattr(req, "receiver_id") and req.receiver_id else "RECEIVER",
        gs_control_number=req.gs_control_number,
        now=now,
        version=req.implementation_guide,
        delims=delims,
    )
    segments.append(gs)

    # ST
    st_num = req.st_control_number
    st = build_st("835", st_num, req.implementation_guide, delims)
    segments.append(st)

    # BPR — financial information
    bpr_elems = [
        "I",                                   # BPR01 transaction handling code: I=inform
        _fmt_amount(req.payment_amount),       # BPR02 total payment amount
        req.credit_debit_flag,                 # BPR03
        req.payment_method,                    # BPR04
        None, None, None, None, None, None, None, None, None, None, None,
        req.payment_date,                      # BPR16 effective date (BPR05-BPR15 = 11 empty)
    ]
    segments.append(build_segment("BPR", bpr_elems, delims))

    # TRN — trace number
    trn_elems = [
        "1",
        req.trace.check_eft_number,
        req.trace.payer_id,
    ]
    if req.trace.originating_company_id:
        trn_elems.append(req.trace.originating_company_id)
    segments.append(build_segment("TRN", trn_elems, delims))

    # DTM — production date
    segments.append(build_segment("DTM", ["405", req.payment_date], delims))

    # N1 payer
    segments.extend(_build_n1(req.payer, delims))
    # N1 payee
    segments.extend(_build_n1(req.payee, delims))

    # CLP loops
    for claim in req.claims:
        segments.extend(_build_clp(claim, delims))

    # SE — segment count includes ST and SE themselves
    content_segs = segments[3:]  # skip ISA, GS, ST to count ST-through-SE body
    # SE01 = count of segments from ST through SE inclusive
    # segments list currently has: ISA, GS, ST, BPR, TRN, DTM, N1..., CLP loops...
    # SE01 = total body segments (from ST) + 1 for SE itself
    body_seg_count = len(segments) - 2  # exclude ISA and GS
    se = build_se(body_seg_count + 1, st_num, delims)
    segments.append(se)

    # GE
    segments.append(build_ge(1, req.gs_control_number, delims))
    # IEA
    segments.append(build_iea(req.isa_control_number, 1, delims))

    result = "".join(segments)

    # Validate before returning (fail-closed)
    from ..validators.validator import validate_835_basic
    errors = validate_835_basic(result, delims)
    if errors:
        raise ValueError(f"Generated 835 failed validation: {errors}")

    return result
