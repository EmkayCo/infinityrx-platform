"""X12 834 enrollment transaction set parser.

Pluggable loop handler design: each loop (2000, 2100, 2300, etc.) has a
dedicated handler registered on the parser. This avoids a monolithic parse
function and allows adding new segment types without modifying core logic.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class Edi834ParseError(ValueError):
    """Raised when the 834 file is malformed or missing required structure."""


class EnrollmentAction(str, Enum):
    ADD = "add"
    CHANGE = "change"
    TERMINATE = "terminate"


# INS03 maintenance type codes → action mapping
_MAINTENANCE_CODE_MAP: dict[str, EnrollmentAction] = {
    "030": EnrollmentAction.ADD,       # Addition
    "001": EnrollmentAction.CHANGE,    # Change
    "024": EnrollmentAction.TERMINATE, # Cancellation
    "025": EnrollmentAction.TERMINATE, # Termination
}

# L2000 loop action qualifiers
_LOOP_ACTION_MAP: dict[str, EnrollmentAction] = {
    "ADD": EnrollmentAction.ADD,
    "CHG": EnrollmentAction.CHANGE,
    "TRM": EnrollmentAction.TERMINATE,
    "XCL": EnrollmentAction.TERMINATE,
}


@dataclass
class EnrollmentRecord:
    member_id: str = ""
    group_number: str = ""
    action: EnrollmentAction = EnrollmentAction.ADD
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    suffix: str = ""
    gender: str = ""
    date_of_birth: date | None = None
    ssn: str = ""
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = "US"
    phone: str = ""
    email: str = ""
    effective_date: date | None = None
    termination_date: date | None = None
    relationship_code: str = ""
    person_code: str = "01"
    rx_bin: str = ""
    rx_pcn: str = ""
    rx_group: str = ""
    plan_id: str = ""


def _parse_date(dt_str: str) -> date | None:
    """Parse D8 format (YYYYMMDD) or ISO date."""
    dt_str = dt_str.strip()
    if not dt_str:
        return None
    if re.fullmatch(r"\d{8}", dt_str):
        return date(int(dt_str[:4]), int(dt_str[4:6]), int(dt_str[6:8]))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", dt_str):
        return date.fromisoformat(dt_str)
    return None


def _split_segments(raw: str) -> list[str]:
    """Split 834 text into segments, stripping tilde terminator."""
    # Detect element separator from ISA segment
    lines = raw.strip()
    # Find ISA segment
    isa_match = re.search(r"ISA(.{103})", lines, re.DOTALL)
    if not isa_match:
        raise Edi834ParseError("ISA segment not found — not a valid X12 document")
    isa_full = "ISA" + isa_match.group(1)
    # ISA element separator is character at position 3 (index 3 of the ISA segment)
    element_sep = isa_full[3]
    # Segment terminator is the last character of the ISA segment (position 105).
    # The regex above guarantees isa_full is exactly 106 chars, so index 105 always exists.
    seg_terminator = isa_full[105]
    segments = [s.strip() for s in lines.split(seg_terminator) if s.strip()]
    return segments


def _parse_elements(segment: str, element_sep: str = "*") -> list[str]:
    return segment.split(element_sep)


class BaseLoopHandler(ABC):
    """Base class for pluggable 834 loop handlers."""

    loop_id: str = ""

    @abstractmethod
    def handle(self, segments: list[list[str]]) -> None:
        """Process a list of parsed segment element lists for this loop."""


class _Loop2000Handler(BaseLoopHandler):
    """Handles LOOP 2000 — member-level loop (INS, REF, DTP, NM1, PER, N3, N4, DMG, HD)."""

    loop_id = "2000"

    def __init__(self) -> None:
        self.records: list[EnrollmentRecord] = []

    def handle(self, segments: list[list[str]]) -> None:
        record = EnrollmentRecord()
        for els in segments:
            seg_id = els[0] if els else ""

            if seg_id == "L2000":
                # L2000*member_seq*count*action_qualifier
                if len(els) > 3 and els[3] in _LOOP_ACTION_MAP:
                    record.action = _LOOP_ACTION_MAP[els[3]]

            elif seg_id == "INS":
                # INS*subscriber*relationship*maint_type*...
                if len(els) > 3:
                    maint = els[3]
                    if maint in _MAINTENANCE_CODE_MAP:
                        record.action = _MAINTENANCE_CODE_MAP[maint]
                if len(els) > 2:
                    rel = els[2]
                    # 18=self/subscriber, 01=spouse, 19=child
                    _rel_map = {"18": "self", "01": "spouse", "19": "child"}
                    record.relationship_code = _rel_map.get(rel, rel)

            elif seg_id == "REF":
                # REF*qualifier*value
                if len(els) > 2:
                    qual, val = els[1], els[2]
                    if qual == "0F":  # subscriber number / member ID
                        record.member_id = val
                    elif qual == "1L":  # group or policy number
                        record.group_number = val

            elif seg_id == "DTP":
                # DTP*qualifier*format*date
                if len(els) > 3:
                    qual, fmt, dt = els[1], els[2], els[3]
                    parsed = _parse_date(dt) if fmt == "D8" else None
                    if qual == "356":  # enrollment date
                        record.effective_date = parsed
                    elif qual == "357":  # termination date
                        record.termination_date = parsed

            elif seg_id == "NM1":
                # NM1*entity_id*type*last*first*middle*prefix*suffix*id_qual*id
                if len(els) > 1 and els[1] in ("IL", "74"):  # insured person
                    record.last_name = els[3] if len(els) > 3 else ""
                    record.first_name = els[4] if len(els) > 4 else ""
                    record.middle_name = els[5] if len(els) > 5 else ""
                    record.suffix = els[7] if len(els) > 7 else ""
                    if len(els) > 9 and els[8] == "34":  # SSN
                        record.ssn = els[9]

            elif seg_id == "PER":
                # PER*role*name*comm_qual1*comm_num1*comm_qual2*comm_num2...
                # comm pairs start at index 3 (after role=1, name=2)
                for i in range(3, len(els) - 1, 2):
                    qual = els[i]
                    val = els[i + 1]
                    if qual == "TE":
                        record.phone = val
                    elif qual == "EM":
                        record.email = val

            elif seg_id == "N3":
                record.address_line_1 = els[1] if len(els) > 1 else ""
                record.address_line_2 = els[2] if len(els) > 2 else ""

            elif seg_id == "N4":
                record.city = els[1] if len(els) > 1 else ""
                record.state = els[2] if len(els) > 2 else ""
                record.zip_code = els[3] if len(els) > 3 else ""
                record.country = els[4] if len(els) > 4 else "US"

            elif seg_id == "DMG":
                # DMG*format*dob*gender
                if len(els) > 2 and els[1] == "D8":
                    record.date_of_birth = _parse_date(els[2])
                if len(els) > 3:
                    record.gender = els[3]

            elif seg_id == "HD":
                # HD*maint_type**coverage_type*plan_id
                if len(els) > 4:
                    record.plan_id = els[4]

        if record.member_id:
            self.records.append(record)


class Edi834Parser:
    """X12 834 transaction set parser with pluggable loop handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[BaseLoopHandler]] = {}
        self._default_2000 = _Loop2000Handler()
        self.register_handler(self._default_2000)

    def register_handler(self, handler: BaseLoopHandler) -> None:
        """Register a handler for a loop ID. Multiple handlers per loop are supported."""
        self._handlers.setdefault(handler.loop_id, []).append(handler)

    def parse(self, raw: str) -> list[EnrollmentRecord]:
        """Parse raw 834 EDI text and return a list of EnrollmentRecord objects."""
        segments = _split_segments(raw)

        # ISA element separator is always at position 3 of the first ISA segment
        isa_seg = next(s for s in segments if s.startswith("ISA"))
        element_sep = isa_seg[3]

        parsed: list[list[str]] = [_parse_elements(s, element_sep) for s in segments]

        # Find ST/SE boundaries (transaction set)
        in_transaction = False
        current_2000_segments: list[list[str]] = []
        in_2000_loop = False

        for els in parsed:
            seg_id = els[0] if els else ""

            if seg_id == "ST":
                in_transaction = True
                continue
            if seg_id == "SE":
                # Flush last 2000 loop
                if in_2000_loop and current_2000_segments:
                    self._dispatch("2000", current_2000_segments)
                    current_2000_segments = []
                    in_2000_loop = False
                in_transaction = False
                continue

            if not in_transaction:
                continue

            # L2000 starts a new member block
            if seg_id == "L2000":
                if in_2000_loop and current_2000_segments:
                    self._dispatch("2000", current_2000_segments)
                    current_2000_segments = []
                in_2000_loop = True
                current_2000_segments.append(els)
            elif in_2000_loop:
                current_2000_segments.append(els)

        # Collect results from default handler
        return list(self._default_2000.records)

    def _dispatch(self, loop_id: str, segments: list[list[str]]) -> None:
        for handler in self._handlers.get(loop_id, []):
            handler.handle(segments)
