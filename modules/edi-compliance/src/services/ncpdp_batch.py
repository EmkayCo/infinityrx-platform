"""NCPDP Batch 1.2 claim submission generator and parser.

NCPDP Batch uses a fixed-width / pipe-delimited format. This implementation
generates the standard Batch Header (BHR), Claim (CLM), and Batch Trailer (BTR)
records per the NCPDP Batch Standard version 1.2.

Record types:
  BHR — Batch Header Record
  CLM — Claim Transaction (wraps NCPDP D.0 transaction)
  BTR — Batch Trailer Record
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List


# NCPDP Batch field separator
_FIELD_SEP = "\x1c"   # ASCII 28 (File Separator)
_GROUP_SEP = "\x1d"   # ASCII 29 (Group Separator)
_RECORD_SEP = "\x1e"  # ASCII 30 (Record Separator)
_SEGMENT_SEP = "\x1f" # ASCII 31 (Unit Separator)


@dataclass
class NcpdpClaim:
    """A single NCPDP D.0 claim within a batch."""
    bin_number: str         # 6-digit BIN
    version: str = "D0"     # processor control number / version
    pcn: str = ""           # processor control number
    transaction_count: int = 1
    service_provider_id: str = ""
    date_of_service: str = ""  # CCYYMMDD
    ndc: str = ""
    quantity: Decimal = Decimal("1")
    days_supply: int = 30
    member_id: str = ""
    group_id: str = ""
    patient_last: str = ""
    patient_first: str = ""
    patient_dob: str = ""
    prescriber_id: str = ""  # DEA or NPI
    charge_amount: Decimal = Decimal("0")
    copay_amount: Decimal = Decimal("0")


@dataclass
class NcpdpBatchResult:
    """Parsed batch contents."""
    sender_id: str
    receiver_id: str
    batch_control_number: str
    claim_count: int
    total_amount: Decimal
    claims: List[Dict[str, Any]] = field(default_factory=list)


def _fmt_decimal(amount: Decimal, width: int = 10, decimals: int = 2) -> str:
    quantized = amount.quantize(Decimal(f"0.{'0' * decimals}"), rounding=ROUND_HALF_UP)
    value = str(quantized).replace(".", "").replace("-", "")
    return value.zfill(width)


def generate_ncpdp_batch(
    sender_id: str,
    receiver_id: str,
    batch_control_number: str,
    claims: List[NcpdpClaim],
) -> str:
    """Generate an NCPDP Batch 1.2 file string."""
    lines = []

    # Batch Header Record
    bhr = (
        "BHR"
        + _FIELD_SEP + sender_id.ljust(30)[:30]
        + _FIELD_SEP + receiver_id.ljust(30)[:30]
        + _FIELD_SEP + batch_control_number.ljust(20)[:20]
        + _FIELD_SEP + str(len(claims)).zfill(6)
    )
    lines.append(bhr)

    total = Decimal("0")

    for claim in claims:
        total += claim.charge_amount
        clm = (
            "CLM"
            + _FIELD_SEP + claim.bin_number.ljust(6)[:6]
            + _FIELD_SEP + claim.version.ljust(2)[:2]
            + _FIELD_SEP + claim.pcn.ljust(10)[:10]
            + _FIELD_SEP + str(claim.transaction_count).zfill(2)
            + _FIELD_SEP + claim.service_provider_id.ljust(15)[:15]
            + _FIELD_SEP + claim.date_of_service.ljust(8)[:8]
            + _FIELD_SEP + claim.ndc.ljust(11)[:11]
            + _FIELD_SEP + str(claim.quantity.quantize(Decimal("0.000"), rounding=ROUND_HALF_UP))
            + _FIELD_SEP + str(claim.days_supply).zfill(3)
            + _FIELD_SEP + claim.member_id.ljust(20)[:20]
            + _FIELD_SEP + claim.group_id.ljust(15)[:15]
            + _FIELD_SEP + claim.patient_last.ljust(15)[:15]
            + _FIELD_SEP + claim.patient_first.ljust(10)[:10]
            + _FIELD_SEP + claim.patient_dob.ljust(8)[:8]
            + _FIELD_SEP + claim.prescriber_id.ljust(10)[:10]
            + _FIELD_SEP + _fmt_decimal(claim.charge_amount)
            + _FIELD_SEP + _fmt_decimal(claim.copay_amount)
        )
        lines.append(clm)

    # Batch Trailer Record
    btr = (
        "BTR"
        + _FIELD_SEP + str(len(claims)).zfill(6)
        + _FIELD_SEP + _fmt_decimal(total)
    )
    lines.append(btr)

    return _RECORD_SEP.join(lines) + _RECORD_SEP


def parse_ncpdp_batch(raw: str) -> NcpdpBatchResult:
    """Parse an NCPDP Batch 1.2 file.

    Returns a NcpdpBatchResult with claim data extracted from CLM records.
    """
    records = raw.split(_RECORD_SEP)
    sender_id = ""
    receiver_id = ""
    batch_control_number = ""
    claim_count = 0
    total_amount = Decimal("0")
    claims: List[Dict[str, Any]] = []

    for record in records:
        if not record.strip():
            continue
        parts = record.split(_FIELD_SEP)
        record_type = parts[0][:3]

        if record_type == "BHR":
            sender_id = parts[1].strip() if len(parts) > 1 else ""
            receiver_id = parts[2].strip() if len(parts) > 2 else ""
            batch_control_number = parts[3].strip() if len(parts) > 3 else ""
            claim_count = int(parts[4]) if len(parts) > 4 and parts[4].strip().isdigit() else 0

        elif record_type == "CLM":
            claim_dict: Dict[str, Any] = {
                "bin_number": parts[1].strip() if len(parts) > 1 else "",
                "version": parts[2].strip() if len(parts) > 2 else "",
                "pcn": parts[3].strip() if len(parts) > 3 else "",
                "service_provider_id": parts[5].strip() if len(parts) > 5 else "",
                "date_of_service": parts[6].strip() if len(parts) > 6 else "",
                "ndc": parts[7].strip() if len(parts) > 7 else "",
                "quantity": parts[8].strip() if len(parts) > 8 else "",
                "days_supply": int(parts[9]) if len(parts) > 9 and parts[9].strip().isdigit() else 0,
                "member_id": parts[10].strip() if len(parts) > 10 else "",
                "group_id": parts[11].strip() if len(parts) > 11 else "",
                "patient_last": parts[12].strip() if len(parts) > 12 else "",
                "patient_first": parts[13].strip() if len(parts) > 13 else "",
                "patient_dob": parts[14].strip() if len(parts) > 14 else "",
                "prescriber_id": parts[15].strip() if len(parts) > 15 else "",
            }
            if len(parts) > 16:
                raw_charge = parts[16].strip()
                if raw_charge.isdigit() and len(raw_charge) >= 3:
                    dollars = raw_charge[:-2]
                    cents = raw_charge[-2:]
                    claim_dict["charge_amount"] = Decimal(f"{dollars}.{cents}")
                else:
                    claim_dict["charge_amount"] = Decimal("0")
            else:
                claim_dict["charge_amount"] = Decimal("0")
            claims.append(claim_dict)

        elif record_type == "BTR":
            if len(parts) > 2:
                raw_total = parts[2].strip()
                if raw_total.isdigit() and len(raw_total) >= 3:
                    dollars = raw_total[:-2]
                    cents = raw_total[-2:]
                    total_amount = Decimal(f"{dollars}.{cents}")

    return NcpdpBatchResult(
        sender_id=sender_id,
        receiver_id=receiver_id,
        batch_control_number=batch_control_number,
        claim_count=claim_count,
        total_amount=total_amount,
        claims=claims,
    )
