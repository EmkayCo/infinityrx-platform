"""NACHA ACH file generator — compliant with NACHA standard.

Generates CCD (Cash Concentration or Disbursement) files for pharmacy payments.
Record length: exactly 94 characters per record.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from src.utils.constants import NACHA_SAME_DAY_ACH_LIMIT
from src.utils.money import money


@dataclass
class NACHAPayment:
    payment_id: uuid.UUID
    amount: Decimal
    routing_number: str  # 9 digits
    account_number: str
    account_type: str  # checking, savings
    payee_name: str
    individual_id: str
    addenda: str = ""


class NACHAGenerator:
    def __init__(
        self,
        originator_name: str,
        company_id: str,
        company_entry_description: str,
        originating_dfi_id: str,  # 8 digits
        effective_date: str,  # YYMMDD
        file_creation_date: str = "",
        file_creation_time: str = "0000",
        file_id_modifier: str = "A",
        reference_code: str = "        ",
    ) -> None:
        self._originator_name = originator_name
        self._company_id = company_id
        self._company_entry_description = company_entry_description
        self._originating_dfi_id = originating_dfi_id
        self._effective_date = effective_date
        self._file_creation_date = file_creation_date or "260101"
        self._file_creation_time = file_creation_time
        self._file_id_modifier = file_id_modifier
        self._reference_code = reference_code

    def validate_same_day_limit(self, payments: list[NACHAPayment]) -> None:
        for p in payments:
            if money(p.amount) > NACHA_SAME_DAY_ACH_LIMIT:
                raise ValueError(
                    f"Payment {p.payment_id} amount {p.amount} exceeds same-day ACH limit"
                    f" of {NACHA_SAME_DAY_ACH_LIMIT}. Route to standard ACH."
                )

    def generate(self, payments: list[NACHAPayment]) -> str:
        """Generate a NACHA-compliant ACH file as a string."""
        lines: list[str] = []
        lines.append(self._file_header())
        lines.append(self._batch_header())
        trace_seq = 1
        for p in payments:
            lines.append(self._entry_detail(p, trace_seq))
            trace_seq += 1
        lines.append(self._batch_control(payments))
        lines.append(self._file_control(payments))
        return "\n".join(lines)

    def _file_header(self) -> str:
        record = (
            "1"  # record type
            "01"  # priority code
            " "
            + self._originating_dfi_id[:8].ljust(9)  # immediate destination (space + 8 digits)
            + self._company_id.ljust(10)[:10]  # immediate origin
            + self._file_creation_date[:6]  # file creation date YYMMDD
            + self._file_creation_time[:4]  # file creation time HHMM
            + self._file_id_modifier[:1]  # file id modifier
            + "094"  # record size
            + "10"  # blocking factor
            + "1"  # format code
            + self._originator_name[:23].ljust(23)  # immediate destination name
            + "InfinityRx            "[:23]  # immediate origin name
            + self._reference_code[:8].ljust(8)  # reference code
        )
        return record[:94].ljust(94)

    def _batch_header(self) -> str:
        record = (
            "5"  # record type
            "200"  # service class code (credits only)
            + self._originator_name[:16].ljust(16)  # company name
            + "          "  # company discretionary data
            + self._company_id[:10].ljust(10)  # company identification
            + "CCD"  # standard entry class code
            + self._company_entry_description[:10].ljust(10)  # company entry description
            + "      "  # company descriptive date
            + self._effective_date[:6]  # effective entry date
            + "   "  # settlement date (bank-filled)
            + "1"  # originator status code
            + self._originating_dfi_id[:8]  # originating DFI identification
            + "0000001"  # batch number
        )
        return record[:94].ljust(94)

    def _entry_detail(self, payment: NACHAPayment, seq: int) -> str:
        account_type_code = "22" if payment.account_type.lower() == "checking" else "32"
        amount_cents = int(money(payment.amount) * 100)
        routing_8 = payment.routing_number[:8]
        check_digit = payment.routing_number[8] if len(payment.routing_number) >= 9 else "0"
        record = (
            "6"  # record type
            + account_type_code  # transaction code
            + routing_8  # routing transit number (8 digits)
            + check_digit  # check digit
            + payment.account_number[:17].ljust(17)  # DFI account number
            + str(amount_cents).zfill(10)  # amount in cents
            + payment.individual_id[:15].ljust(15)  # individual identification number
            + payment.payee_name[:22].ljust(22)  # individual name
            + "  "  # discretionary data
            + "0"  # addenda record indicator
            + self._originating_dfi_id[:8]  # trace number (DFI)
            + str(seq).zfill(7)  # trace sequence
        )
        return record[:94].ljust(94)

    def _batch_control(self, payments: list[NACHAPayment]) -> str:
        # NACHA batch control: 94 chars
        # Pos 1: record type "8"
        # Pos 2-4: service class code (3)
        # Pos 5-10: entry/addenda count (6)
        # Pos 11-20: entry hash (10) — sum of first 8 digits of routing numbers, last 10 digits
        # Pos 21-32: total debit dollar amount (12) — in cents
        # Pos 33-44: total credit dollar amount (12)
        # Pos 45-54: company identification (10)
        # Pos 55-73: message authentication code (19)
        # Pos 74-79: reserved (6)
        # Pos 80-87: originating DFI identification (8)
        # Pos 88-94: batch number (7)
        entry_count = len(payments)
        total_cents = int(sum(money(p.amount) for p in payments) * 100)
        routing_hash = sum(int(p.routing_number[:8]) for p in payments)
        routing_hash_str = str(routing_hash % 10_000_000_000).zfill(10)

        record = (
            "8"  # 1
            + "200"  # 2-4
            + str(entry_count).zfill(6)  # 5-10
            + routing_hash_str  # 11-20
            + str(total_cents).zfill(12)  # 21-32
            + "000000000000"  # 33-44
            + self._company_id[:10].ljust(10)  # 45-54
            + " " * 19  # 55-73
            + " " * 6  # 74-79
            + self._originating_dfi_id[:8]  # 80-87
            + "0000001"  # 88-94
        )
        return record[:94].ljust(94)

    def _file_control(self, payments: list[NACHAPayment]) -> str:
        # NACHA file control: 94 chars
        # Pos 1: record type "9"
        # Pos 2-7: batch count (6)
        # Pos 8-13: block count (6)
        # Pos 14-21: entry/addenda count (8)
        # Pos 22-31: entry hash (10)
        # Pos 32-43: total debit dollar amount (12) — in cents
        # Pos 44-55: total credit dollar amount (12)
        # Pos 56-94: reserved (39)
        block_count = 1
        entry_count = len(payments)
        total_cents = int(sum(money(p.amount) for p in payments) * 100)
        routing_hash = sum(int(p.routing_number[:8]) for p in payments)
        routing_hash_str = str(routing_hash % 10_000_000_000).zfill(10)

        record = (
            "9"  # 1
            + "000001"  # 2-7
            + str(block_count).zfill(6)  # 8-13
            + str(entry_count).zfill(8)  # 14-21
            + routing_hash_str  # 22-31
            + str(total_cents).zfill(12)  # 32-43
            + "000000000000"  # 44-55
            + " " * 39  # 56-94
        )
        return record[:94].ljust(94)
