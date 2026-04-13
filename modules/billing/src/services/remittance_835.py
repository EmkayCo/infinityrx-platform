"""HIPAA 005010X221A1 — 835 Health Care Claim Payment/Advice generator.

Generates one 835 per payee per payment per the NCPDP standard.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from src.utils.money import money


@dataclass
class Remittance835Claim:
    claim_id: uuid.UUID
    auth_number: str
    paid_amount: Decimal
    patient_pay: Decimal
    plan_pay: Decimal
    ndc: str
    npi: str
    date_of_service: str  # YYYYMMDD
    drug_name: str = ""
    quantity: str = ""


@dataclass
class Remittance835Payment:
    payment_id: uuid.UUID
    amount: Decimal
    payee_name: str
    payee_npi: str
    claims: list[Remittance835Claim] = field(default_factory=list)


class Remittance835Generator:
    def __init__(
        self,
        payer_id: str,
        payer_name: str,
        production_date: str,  # YYYYMMDD
        interchange_control_number: str = "000000001",
        group_control_number: str = "1",
        transaction_control_number: str = "0001",
    ) -> None:
        self._payer_id = payer_id
        self._payer_name = payer_name
        self._production_date = production_date
        self._icn = interchange_control_number
        self._gcn = group_control_number
        self._tcn = transaction_control_number

    def generate(self, payment: Remittance835Payment) -> str:
        """Generate a HIPAA 005010X221A1 835 document for one payment."""
        segments: list[str] = []
        segments.append(self._isa())
        segments.append(self._gs())
        segments.append(self._st())
        segments.append(self._bpr(payment))
        segments.append(self._trn(payment))
        segments.append(self._dtm())
        segments.append(self._n1_pr())
        segments.append(self._n1_pe(payment))

        for claim in payment.claims:
            segments.extend(self._clp_loop(claim))

        segment_count = len(segments) - 2 + 1  # ST to SE, not ISA/GS
        segments.append(self._se(segment_count + 1))
        segments.append(self._ge())
        segments.append(self._iea())

        return "~\n".join(segments) + "~"

    def _isa(self) -> str:
        date_part = self._production_date[:8]
        yymmdd = date_part[2:8] if len(date_part) >= 8 else "260101"
        return (
            f"ISA*00*          *00*          *ZZ*{self._payer_id:<15}*ZZ*"
            f"PAYEE          *{yymmdd}*0000*^*00501*{self._icn.zfill(9)}*0*P*:"
        )

    def _gs(self) -> str:
        date_part = self._production_date[:8] if len(self._production_date) >= 8 else "20260101"
        return f"GS*HP*{self._payer_id}*PAYEE*{date_part}*0000*{self._gcn}*X*005010X221A1"

    def _st(self) -> str:
        return f"ST*835*{self._tcn.zfill(4)}"

    def _bpr(self, payment: Remittance835Payment) -> str:
        amount = money(payment.amount)
        return f"BPR*I*{amount}*C*ACH*CCP*01*021000021*DA*12345678*1234567890***01*021000021*DA*PAYEEACCT*{self._production_date[:8]}"

    def _trn(self, payment: Remittance835Payment) -> str:
        return f"TRN*1*{str(payment.payment_id)[:30]}*{self._payer_id}"

    def _dtm(self) -> str:
        return f"DTM*405*{self._production_date[:8]}"

    def _n1_pr(self) -> str:
        return f"N1*PR*{self._payer_name[:60]}*XX*{self._payer_id}"

    def _n1_pe(self, payment: Remittance835Payment) -> str:
        return f"N1*PE*{payment.payee_name[:60]}*XX*{payment.payee_npi}"

    def _clp_loop(self, claim: Remittance835Claim) -> list[str]:
        paid = money(claim.paid_amount)
        plan_pay = money(claim.plan_pay)
        patient_pay = money(claim.patient_pay)
        segments = [
            f"CLP*{claim.auth_number}*1*{paid}*{paid}*0*NC*{claim.auth_number}*11",
            f"NM1*QC*1**{claim.npi}****XX*{claim.npi}",
            f"DTM*472*{claim.date_of_service}",
            f"SVC*N4:{claim.ndc}*{paid}*{paid}",
            f"DTM*150*{claim.date_of_service}",
            f"CAS*PR*3*{patient_pay}",
        ]
        return segments

    def _se(self, segment_count: int) -> str:
        return f"SE*{segment_count}*{self._tcn.zfill(4)}"

    def _ge(self) -> str:
        return f"GE*1*{self._gcn}"

    def _iea(self) -> str:
        return f"IEA*1*{self._icn.zfill(9)}"
