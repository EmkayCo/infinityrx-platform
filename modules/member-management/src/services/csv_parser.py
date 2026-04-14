"""CSV/Excel enrollment parser with configurable field mapping.

Per-client field mapping makes any column layout work without code changes.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from typing import IO

from src.services.edi_834_parser import (
    EnrollmentAction,
    EnrollmentRecord,
)


_ACTION_MAP: dict[str, EnrollmentAction] = {
    "ADD": EnrollmentAction.ADD,
    "CHG": EnrollmentAction.CHANGE,
    "CHANGE": EnrollmentAction.CHANGE,
    "TRM": EnrollmentAction.TERMINATE,
    "TERMINATE": EnrollmentAction.TERMINATE,
    "TERM": EnrollmentAction.TERMINATE,
}


@dataclass
class FieldMapping:
    """Maps logical enrollment fields to actual CSV column names."""
    member_id: str
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    effective_date: str
    rx_bin: str
    # optional columns
    rx_pcn: str = ""
    rx_group: str = ""
    action: str = ""
    termination_date: str = ""
    middle_name: str = ""
    suffix: str = ""
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    phone: str = ""
    email: str = ""
    ssn: str = ""
    relationship_code: str = ""
    person_code: str = ""


@dataclass
class ParseError:
    row: int
    field: str
    error: str
    value: str = ""


@dataclass
class ParseResult:
    valid_records: list[EnrollmentRecord] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)


def _parse_date(val: str, field_name: str, row: int) -> tuple[date | None, ParseError | None]:
    val = val.strip()
    if not val:
        return None, None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y%m%d"):
        try:
            from datetime import datetime
            return datetime.strptime(val, fmt).date(), None
        except ValueError:
            continue
    return None, ParseError(row=row, field=field_name, error=f"Invalid date: {val!r}", value=val)


class CsvEnrollmentParser:
    """Parses CSV enrollment files using a configurable FieldMapping."""

    def __init__(self, mapping: FieldMapping) -> None:
        self._m = mapping

    def parse(self, stream: IO[str]) -> list[EnrollmentRecord]:
        """Parse all records; raises ValueError on any validation error."""
        result = self.parse_with_errors(stream)
        if result.errors:
            raise ValueError(f"{len(result.errors)} validation error(s) in CSV")
        return result.valid_records

    def parse_with_errors(self, stream: IO[str]) -> ParseResult:
        """Parse, collecting validation errors without raising."""
        content = stream.read()
        reader = csv.DictReader(io.StringIO(content))
        result = ParseResult()

        for row_idx, row in enumerate(reader, start=2):  # row 1 is header
            record, errors = self._parse_row(row, row_idx)
            if errors:
                result.errors.extend(errors)
            else:
                result.valid_records.append(record)

        return result

    def _get(self, row: dict[str, str], col_name: str, default: str = "") -> str:
        if not col_name:
            return default
        return row.get(col_name, default) or default

    def _parse_row(
        self, row: dict[str, str], row_idx: int
    ) -> tuple[EnrollmentRecord, list[ParseError]]:
        m = self._m
        errors: list[ParseError] = []
        record = EnrollmentRecord()

        # Required: member_id
        member_id = self._get(row, m.member_id)
        if not member_id:
            errors.append(ParseError(row=row_idx, field="member_id", error="Missing member_id"))
        record.member_id = member_id

        # Required: first_name
        first_name = self._get(row, m.first_name)
        if not first_name:
            errors.append(ParseError(row=row_idx, field="first_name", error="Missing first_name"))
        record.first_name = first_name

        # Required: last_name
        last_name = self._get(row, m.last_name)
        if not last_name:
            errors.append(ParseError(row=row_idx, field="last_name", error="Missing last_name"))
        record.last_name = last_name

        # Required: date_of_birth — check column exists
        if m.date_of_birth not in row:
            errors.append(ParseError(
                row=row_idx, field="date_of_birth",
                error=f"Column '{m.date_of_birth}' not found"
            ))
        else:
            dob, dob_err = _parse_date(row[m.date_of_birth], "date_of_birth", row_idx)
            if dob_err:
                errors.append(dob_err)
            record.date_of_birth = dob

        # Required: gender
        gender = self._get(row, m.gender).upper()
        if gender not in ("M", "F", "U", ""):
            errors.append(ParseError(row=row_idx, field="gender", error=f"Invalid gender: {gender!r}"))
        record.gender = gender

        # Required: effective_date
        if m.effective_date not in row:
            errors.append(ParseError(
                row=row_idx, field="effective_date",
                error=f"Column '{m.effective_date}' not found"
            ))
        else:
            eff, eff_err = _parse_date(row[m.effective_date], "effective_date", row_idx)
            if eff_err:
                errors.append(eff_err)
            record.effective_date = eff

        # Required: rx_bin — check column exists
        if m.rx_bin not in row:
            errors.append(ParseError(
                row=row_idx, field="rx_bin",
                error=f"Column '{m.rx_bin}' not found in file"
            ))
        else:
            record.rx_bin = self._get(row, m.rx_bin)

        # Optional fields
        record.rx_pcn = self._get(row, m.rx_pcn)
        record.rx_group = self._get(row, m.rx_group)
        record.middle_name = self._get(row, m.middle_name)
        record.suffix = self._get(row, m.suffix)
        record.address_line_1 = self._get(row, m.address_line_1)
        record.address_line_2 = self._get(row, m.address_line_2)
        record.city = self._get(row, m.city)
        record.state = self._get(row, m.state)
        record.zip_code = self._get(row, m.zip_code)
        record.phone = self._get(row, m.phone)
        record.email = self._get(row, m.email)
        record.ssn = self._get(row, m.ssn)
        record.relationship_code = self._get(row, m.relationship_code)
        record.person_code = self._get(row, m.person_code) or "01"

        # Action
        action_raw = self._get(row, m.action, "ADD").upper()
        record.action = _ACTION_MAP.get(action_raw, EnrollmentAction.ADD)

        # Optional termination date
        if m.termination_date:
            term_val = self._get(row, m.termination_date)
            if term_val:
                term, term_err = _parse_date(term_val, "termination_date", row_idx)
                if term_err:
                    errors.append(term_err)
                record.termination_date = term

        return record, errors
