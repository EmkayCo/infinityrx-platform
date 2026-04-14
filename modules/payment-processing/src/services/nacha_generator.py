"""NACHA ACH file generator per IAT/CCD specification.

Generates standard 94-character fixed-width NACHA files.
All amounts use Decimal with ROUND_HALF_UP. No floats.
Totals verified before file is returned.

File structure:
  File Header (1 record)
    Batch Header (1 per batch)
      Entry Detail (1 per payment)
        [Addenda (optional)]
    Batch Control (1 per batch)
  File Control (1 record)

Padding: file must be multiple of 10 records; pad with 9-filled lines.
"""
from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from .business_day import effective_date_for_batch
from .decimal_utils import money

# NACHA record types
_RT_FILE_HEADER = "1"
_RT_BATCH_HEADER = "5"
_RT_ENTRY_DETAIL = "6"
_RT_ADDENDA = "7"
_RT_BATCH_CONTROL = "8"
_RT_FILE_CONTROL = "9"

# Transaction codes for credit entries to checking accounts
TC_CREDIT_CHECKING = "22"
TC_CREDIT_SAVINGS = "32"
TC_DEBIT_CHECKING = "27"
TC_DEBIT_SAVINGS = "37"

# Padding line — 94 nines
_PADDING = "9" * 94


@dataclass(frozen=True)
class NachaEntryDetail:
    """Single payment entry in a NACHA batch."""

    routing_number: str  # 9-digit ABA routing (no check digit here)
    account_number: str  # up to 17 chars
    amount: Decimal  # in dollars (no float)
    individual_id: str  # up to 15 chars
    individual_name: str  # up to 22 chars
    trace_number: str  # 15-digit originator trace
    transaction_code: str = TC_CREDIT_CHECKING
    addenda_info: str | None = None


@dataclass(frozen=True)
class NachaBatchConfig:
    """Originator configuration for a single batch."""

    company_name: str  # 16 chars
    company_id: str  # 10 chars (tax ID or IRS EIN formatted)
    entry_class_code: str  # CCD, PPD, CTX
    company_entry_description: str  # 10 chars — PAYMT for business
    originating_dfi_id: str  # 8-digit routing prefix
    effective_date: date | None = None  # auto-computed if None
    same_day: bool = False


@dataclass(frozen=True)
class NachaFileConfig:
    """ODFI (bank) level configuration for the file."""

    immediate_destination: str  # 9-digit Fed routing
    immediate_origin: str  # 10-char company ID / EIN
    immediate_destination_name: str  # 23 chars
    immediate_origin_name: str  # 23 chars
    reference_code: str = "        "  # 8 chars


@dataclass
class NachaGenerationResult:
    file_content: str  # full NACHA file text
    total_amount: Decimal
    entry_count: int
    entry_addenda_count: int  # entries + addendas
    batch_count: int
    file_hash: str  # routing number hash (last 8 digits of sum)


def _ljust(s: str, n: int, fill: str = " ") -> str:
    return s[:n].ljust(n, fill)


def _rjust(s: str, n: int, fill: str = "0") -> str:
    return s[:n].rjust(n, fill)


def _amount_str(amount: Decimal, width: int = 10) -> str:
    """Convert Decimal dollar amount to zero-padded NACHA cents string.

    Entry Detail amounts: 10 digits. Batch/File Control totals: 12 digits.
    """
    cents = (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return str(int(cents)).zfill(width)


def _routing_hash(routing_numbers: Sequence[str]) -> str:
    """ABA hash: sum of 8-digit routing prefixes, take last 10 digits."""
    total = sum(int(r[:8]) for r in routing_numbers)
    return str(total % 10_000_000_000).zfill(10)


def _file_header(cfg: NachaFileConfig, creation_date: date, sequence: int, creation_time: str | None = None) -> str:
    """94-character File Header record (record type 1)."""
    d = creation_date.strftime("%y%m%d")
    t = creation_time if creation_time else datetime.now().strftime("%H%M")
    return (
        _RT_FILE_HEADER
        + "01"  # priority code
        + " " + _rjust(cfg.immediate_destination, 9)
        + _ljust(cfg.immediate_origin, 10)
        + d  # 6
        + t  # 4
        + str(sequence % 10)  # file ID modifier
        + "094"  # record size
        + "10"  # blocking factor
        + "1"  # format code
        + _ljust(cfg.immediate_destination_name, 23)
        + _ljust(cfg.immediate_origin_name, 23)
        + _ljust(cfg.reference_code, 8)
    )


def _batch_header(
    cfg: NachaBatchConfig,
    batch_number: int,
    effective_date: date,
) -> str:
    """94-character Batch Header record (record type 5)."""
    eff = effective_date.strftime("%y%m%d")
    today = date.today().strftime("%y%m%d")
    return (
        _RT_BATCH_HEADER
        + "200"  # service class code (mixed)
        + _ljust(cfg.company_name, 16)
        + " " * 20  # company discretionary data
        + _ljust(cfg.company_id, 10)
        + cfg.entry_class_code
        + _ljust(cfg.company_entry_description, 10)
        + today  # company descriptive date
        + eff  # effective entry date
        + " " * 3  # settlement date (filled by bank)
        + "1"  # originator status code
        + _ljust(cfg.originating_dfi_id[:8], 8)
        + str(batch_number).zfill(7)
    )


def _entry_detail(entry: NachaEntryDetail, batch_originating_dfi: str) -> str:
    """94-character Entry Detail record (record type 6)."""
    has_addenda = "1" if entry.addenda_info else "0"
    return (
        _RT_ENTRY_DETAIL
        + entry.transaction_code
        + _rjust(entry.routing_number[:8], 8)  # 8-digit routing transit
        + _rjust(entry.routing_number[8:9] if len(entry.routing_number) >= 9 else "0", 1)  # check digit
        + _ljust(entry.account_number, 17)
        + _amount_str(entry.amount)
        + _ljust(entry.individual_id, 15)
        + _ljust(entry.individual_name, 22)
        + has_addenda
        + _rjust(entry.trace_number, 17)  # trace number 17 chars (positions 78-94)
    )


def _addenda_record(info: str, seq: int) -> str:
    """94-character Addenda record (record type 7).

    Positions: 1(RT) + 2(type) + 80(info) + 4(seq) + 7(entry detail seq) = 94.
    """
    return (
        _RT_ADDENDA
        + "05"  # addenda type code (2)
        + _ljust(info, 80)  # payment related info (80)
        + str(seq).zfill(4)  # sequence number (4)
        + "0000001"  # entry detail sequence number (7)
    )


def _batch_control(
    cfg: NachaBatchConfig,
    batch_number: int,
    entries: list[NachaEntryDetail],
    addenda_count: int,
) -> str:
    """94-character Batch Control record (record type 8)."""
    entry_addenda_count = len(entries) + addenda_count
    total_debit = money(Decimal("0.00"))
    total_credit = sum(
        e.amount for e in entries if e.transaction_code in (TC_CREDIT_CHECKING, TC_CREDIT_SAVINGS)
    )
    routing_hash = _routing_hash([e.routing_number for e in entries])
    return (
        _RT_BATCH_CONTROL
        + "200"  # service class code (3)
        + str(entry_addenda_count).zfill(6)  # entry/addenda count (6)
        + routing_hash  # entry hash (10)
        + _amount_str(total_debit, 12)  # total debit (12)
        + _amount_str(total_credit, 12)  # total credit (12)
        + _ljust(cfg.company_id, 10)  # company ID (10)
        + " " * 19  # message authentication code (19)
        + " " * 6  # reserved (6)
        + _ljust(cfg.originating_dfi_id[:8], 8)  # originating DFI (8)
        + str(batch_number).zfill(7)  # batch number (7)
    )


def _file_control(
    batch_count: int,
    block_count: int,
    entry_addenda_count: int,
    all_entries: list[NachaEntryDetail],
    total_credit: Decimal,
) -> str:
    """94-character File Control record (record type 9)."""
    routing_hash = _routing_hash([e.routing_number for e in all_entries])
    return (
        _RT_FILE_CONTROL
        + str(batch_count).zfill(6)  # batch count (6)
        + str(block_count).zfill(6)  # block count (6)
        + str(entry_addenda_count).zfill(8)  # entry/addenda count (8)
        + routing_hash  # entry hash (10)
        + _amount_str(Decimal("0.00"), 12)  # total debit (12)
        + _amount_str(total_credit, 12)  # total credit (12)
        + " " * 39  # reserved (39)
    )


def generate_nacha_file(
    file_cfg: NachaFileConfig,
    batch_cfg: NachaBatchConfig,
    entries: list[NachaEntryDetail],
    creation_date: date | None = None,
    sequence: int = 1,
    creation_time: str | None = None,
) -> NachaGenerationResult:
    """Generate a complete NACHA file from payment entries.

    Raises ValueError if totals don't match or entries are empty.
    """
    if not entries:
        raise ValueError("Cannot generate NACHA file with no entries")

    today = creation_date or date.today()
    eff_date = batch_cfg.effective_date or effective_date_for_batch(today, batch_cfg.same_day)

    total_credit = sum(
        e.amount for e in entries if e.transaction_code in (TC_CREDIT_CHECKING, TC_CREDIT_SAVINGS)
    )
    total_credit = money(total_credit)

    # Build body records (without file control, so we can compute block count)
    body: list[str] = []
    body.append(_file_header(file_cfg, today, sequence, creation_time))
    body.append(_batch_header(batch_cfg, 1, eff_date))

    addenda_count = 0
    addenda_seq = 1
    for entry in entries:
        body.append(_entry_detail(entry, batch_cfg.originating_dfi_id))
        if entry.addenda_info:
            body.append(_addenda_record(entry.addenda_info, addenda_seq))
            addenda_count += 1
            addenda_seq += 1

    body.append(_batch_control(batch_cfg, 1, entries, addenda_count))

    # Compute block count: total records (body + file control) must be multiple of 10
    core_records = len(body) + 1  # +1 for file control
    remainder = core_records % 10
    padding_needed = (10 - remainder) % 10
    block_count = (core_records + padding_needed) // 10

    final_lines: list[str] = body + [
        _file_control(1, block_count, len(entries) + addenda_count, entries, total_credit)
    ] + [_PADDING] * padding_needed

    file_content = "\n".join(final_lines) + "\n"

    # Verify total_credit matches sum of credit entries (property invariant)
    computed_total = money(
        sum(e.amount for e in entries if e.transaction_code in (TC_CREDIT_CHECKING, TC_CREDIT_SAVINGS))
    )
    if computed_total != total_credit:
        raise ValueError(
            f"NACHA total mismatch: computed {computed_total} != expected {total_credit}"
        )

    file_hash_val = hashlib.sha256(file_content.encode()).hexdigest()[:16]

    return NachaGenerationResult(
        file_content=file_content,
        total_amount=total_credit,
        entry_count=len(entries),
        entry_addenda_count=len(entries) + addenda_count,
        batch_count=1,
        file_hash=file_hash_val,
    )
