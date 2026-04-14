"""835 Remittance Advice parser.

Extracts CLP loops, SVC lines, CAS adjustments, and BPR/TRN headers.
All amounts returned as Decimal with ROUND_HALF_UP.
ISA06/ISA08 are preserved with trailing spaces (not stripped).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from ..delimiters import detect_delimiters
from ..segments import parse_segments


def _dec(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class Parsed835Adjustment:
    group_code: str
    reason_code: str
    amount: Decimal


@dataclass
class Parsed835SvcLine:
    procedure_qualifier: str
    procedure_code: str
    charge_amount: Decimal
    paid_amount: Decimal
    quantity: Decimal
    adjustments: list[Parsed835Adjustment] = field(default_factory=list)
    rx_number: str | None = None


@dataclass
class Parsed835Claim:
    claim_id: str
    status_code: str
    charge_amount: Decimal
    paid_amount: Decimal
    patient_responsibility: Decimal
    claim_filing_indicator: str
    payer_claim_ref: str
    adjustments: list[Parsed835Adjustment] = field(default_factory=list)
    service_lines: list[Parsed835SvcLine] = field(default_factory=list)
    pharmacy_npi: str | None = None
    bin_number: str | None = None
    ncpdp_number: str | None = None
    chain_code: str | None = None


@dataclass
class Parsed835:
    """Complete parsed 835 remittance."""
    sender_id: str                 # ISA06 — NOT stripped (preserves trailing spaces)
    receiver_id: str               # ISA08 — NOT stripped
    isa_control_number: str
    payment_amount: Decimal
    payment_date: str
    credit_debit_flag: str
    payment_method: str
    check_eft_number: str
    payer_id: str
    claims: list[Parsed835Claim] = field(default_factory=list)
    total_claim_paid: Decimal = Decimal("0")


def parse_835(raw: str) -> Parsed835:
    """Parse a complete 835 EDI string into a Parsed835 object."""
    delims = detect_delimiters(raw)
    segs = parse_segments(raw, delims)

    isa = next((s for s in segs if s[0] == "ISA"), None)
    if isa is None:
        raise ValueError("No ISA segment found")

    # ISA06/ISA08 are NOT stripped — preserved per PRD §3.18
    sender_id = isa[6]
    receiver_id = isa[8]
    isa_control = isa[13]

    # BPR — financial data
    bpr = next((s for s in segs if s[0] == "BPR"), None)
    payment_amount = _dec(bpr[2]) if bpr and len(bpr) > 2 else Decimal("0")
    credit_debit_flag = bpr[3] if bpr and len(bpr) > 3 else ""
    payment_method = bpr[4] if bpr and len(bpr) > 4 else ""
    # BPR16 is the effective date; fall back to DTM*405 if BPR16 is empty
    payment_date = bpr[16] if bpr and len(bpr) > 16 and bpr[16] else ""
    if not payment_date:
        dtm = next((s for s in segs if s[0] == "DTM" and len(s) > 2 and s[1] == "405"), None)
        if dtm:
            payment_date = dtm[2]

    # TRN — trace
    trn = next((s for s in segs if s[0] == "TRN"), None)
    check_eft_number = trn[2] if trn and len(trn) > 2 else ""
    payer_id = trn[3] if trn and len(trn) > 3 else ""

    # Parse CLP loops
    claims: list[Parsed835Claim] = []
    current_claim: Parsed835Claim | None = None
    current_svc: Parsed835SvcLine | None = None

    for seg in segs:
        seg_id = seg[0]

        if seg_id == "CLP":
            if current_svc and current_claim:
                current_claim.service_lines.append(current_svc)
                current_svc = None
            if current_claim:
                claims.append(current_claim)
            current_claim = Parsed835Claim(
                claim_id=seg[1] if len(seg) > 1 else "",
                status_code=seg[2] if len(seg) > 2 else "",
                charge_amount=_dec(seg[3]) if len(seg) > 3 else Decimal("0"),
                paid_amount=_dec(seg[4]) if len(seg) > 4 else Decimal("0"),
                patient_responsibility=_dec(seg[5]) if len(seg) > 5 else Decimal("0"),
                claim_filing_indicator=seg[6] if len(seg) > 6 else "",
                payer_claim_ref=seg[7] if len(seg) > 7 else "",
            )

        elif seg_id == "CAS" and current_claim is not None:
            adj = Parsed835Adjustment(
                group_code=seg[1] if len(seg) > 1 else "",
                reason_code=seg[2] if len(seg) > 2 else "",
                amount=_dec(seg[3]) if len(seg) > 3 else Decimal("0"),
            )
            if current_svc:
                current_svc.adjustments.append(adj)
            else:
                current_claim.adjustments.append(adj)

        elif seg_id == "REF" and current_claim is not None:
            qualifier = seg[1] if len(seg) > 1 else ""
            value = seg[2] if len(seg) > 2 else ""
            if qualifier == "HPI":
                current_claim.pharmacy_npi = value
            elif qualifier == "G1":
                current_claim.bin_number = value
            elif qualifier == "EO":
                current_claim.ncpdp_number = value
            elif qualifier == "PQ":
                current_claim.chain_code = value
            elif qualifier == "1D" and current_svc:
                current_svc.rx_number = value

        elif seg_id == "SVC" and current_claim is not None:
            if current_svc:
                current_claim.service_lines.append(current_svc)
            # SVC01 is composite: qualifier*code
            svc01 = seg[1] if len(seg) > 1 else ""
            if delims.sub_element in svc01:
                parts = svc01.split(delims.sub_element, 1)
                qualifier = parts[0]
                code = parts[1]
            else:
                qualifier = ""
                code = svc01
            current_svc = Parsed835SvcLine(
                procedure_qualifier=qualifier,
                procedure_code=code,
                charge_amount=_dec(seg[2]) if len(seg) > 2 else Decimal("0"),
                paid_amount=_dec(seg[3]) if len(seg) > 3 else Decimal("0"),
                quantity=Decimal(seg[6]) if len(seg) > 6 and seg[6] else Decimal("1"),
            )

    # Flush last SVC and claim
    if current_svc and current_claim:
        current_claim.service_lines.append(current_svc)
    if current_claim:
        claims.append(current_claim)

    total_paid = sum((c.paid_amount for c in claims), Decimal("0"))

    return Parsed835(
        sender_id=sender_id,
        receiver_id=receiver_id,
        isa_control_number=isa_control,
        payment_amount=payment_amount,
        payment_date=payment_date,
        credit_debit_flag=credit_debit_flag,
        payment_method=payment_method,
        check_eft_number=check_eft_number,
        payer_id=payer_id,
        claims=claims,
        total_claim_paid=total_paid.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    )
