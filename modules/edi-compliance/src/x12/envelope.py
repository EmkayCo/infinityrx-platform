"""X12 interchange/functional group envelope builder and parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .delimiters import Delimiters
from .segments import build_segment, pad_isa_control, pad_isa_id


@dataclass
class EnvelopeConfig:
    sender_qualifier: str        # ISA05
    sender_id: str               # ISA06 — will be padded to 15 chars
    receiver_qualifier: str      # ISA07
    receiver_id: str             # ISA08 — will be padded to 15 chars
    isa_control_number: int
    gs_control_number: int
    test_mode: bool = True       # ISA15: T=test, P=production
    version_id: str = "00501"    # ISA12
    gs_sender_id: str = ""       # GS02 — defaults to sender_id if empty
    gs_receiver_id: str = ""     # GS03 — defaults to receiver_id if empty


@dataclass
class TransactionSet:
    """A single ST…SE transaction set."""
    transaction_id: str          # e.g. "835"
    st_control_number: int
    implementation_guide: str    # e.g. "005010X221A1"
    segments: list[str] = field(default_factory=list)


def build_isa(config: EnvelopeConfig, delims: Delimiters, now: datetime | None = None) -> str:
    """Build the ISA interchange control header segment."""
    if now is None:
        now = datetime.now(timezone.utc)
    date_str = now.strftime("%y%m%d")
    time_str = now.strftime("%H%M")
    sender_id = pad_isa_id(config.sender_id)
    receiver_id = pad_isa_id(config.receiver_id)
    control = pad_isa_control(config.isa_control_number)
    usage = "T" if config.test_mode else "P"
    elements = [
        "00",                        # ISA01 auth info qualifier
        "          ",                # ISA02 auth info (10 spaces)
        "00",                        # ISA03 security info qualifier
        "          ",                # ISA04 security info (10 spaces)
        config.sender_qualifier,     # ISA05
        sender_id,                   # ISA06 — 15 chars
        config.receiver_qualifier,   # ISA07
        receiver_id,                 # ISA08 — 15 chars
        date_str,                    # ISA09
        time_str,                    # ISA10
        "^",                         # ISA11 repetition separator
        config.version_id,           # ISA12
        control,                     # ISA13 — 9 digits
        "0",                         # ISA14 ack requested
        usage,                       # ISA15
        delims.sub_element,          # ISA16 sub-element separator
    ]
    return build_segment("ISA", elements, delims)


def build_iea(isa_control_number: int, functional_group_count: int, delims: Delimiters) -> str:
    return build_segment("IEA", [functional_group_count, pad_isa_control(isa_control_number)], delims)


def build_gs(
    functional_id: str,
    sender_id: str,
    receiver_id: str,
    gs_control_number: int,
    now: datetime | None = None,
    version: str = "005010X221A1",
    delims: Delimiters | None = None,
) -> str:
    if delims is None:
        from .delimiters import _DEFAULT_DELIMITERS
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)
    elements = [
        functional_id,
        sender_id,
        receiver_id,
        now.strftime("%Y%m%d"),
        now.strftime("%H%M"),
        str(gs_control_number),
        "X",
        version,
    ]
    return build_segment("GS", elements, delims)


def build_ge(transaction_count: int, gs_control_number: int, delims: Delimiters) -> str:
    return build_segment("GE", [transaction_count, str(gs_control_number)], delims)


def build_st(
    transaction_id: str,
    st_control_number: int,
    implementation_guide: str,
    delims: Delimiters,
) -> str:
    return build_segment("ST", [transaction_id, str(st_control_number).zfill(4), implementation_guide], delims)


def build_se(segment_count: int, st_control_number: int, delims: Delimiters) -> str:
    return build_segment("SE", [segment_count, str(st_control_number).zfill(4)], delims)


@dataclass
class ParsedEnvelope:
    """Parsed ISA/GS/ST header fields for a single transaction set."""
    sender_qualifier: str
    sender_id: str
    receiver_qualifier: str
    receiver_id: str
    isa_control_number: str
    test_mode: bool
    functional_id: str
    gs_control_number: str
    transaction_id: str
    st_control_number: str
    implementation_guide: str | None
    body_segments: list[list[str]]


def parse_envelope(raw: str, delims: Delimiters) -> ParsedEnvelope:
    """Parse a single-transaction X12 interchange into a ParsedEnvelope."""
    from .segments import parse_segments
    segs = parse_segments(raw, delims)

    isa = next((s for s in segs if s[0] == "ISA"), None)
    gs = next((s for s in segs if s[0] == "GS"), None)
    st = next((s for s in segs if s[0] == "ST"), None)

    if isa is None or gs is None or st is None:
        raise ValueError("Missing ISA, GS, or ST segment in EDI content")

    # ISA06/ISA08 intentionally NOT stripped — preserve fixed-width
    sender_id = isa[6]
    receiver_id = isa[8]

    body_start = next(i for i, s in enumerate(segs) if s[0] == "ST")
    body_end = next(i for i, s in enumerate(segs) if s[0] == "SE")
    body_segments = segs[body_start + 1:body_end]

    return ParsedEnvelope(
        sender_qualifier=isa[5],
        sender_id=sender_id,
        receiver_qualifier=isa[7],
        receiver_id=receiver_id,
        isa_control_number=isa[13],
        test_mode=(isa[15] == "T"),
        functional_id=gs[1],
        gs_control_number=gs[6],
        transaction_id=st[1],
        st_control_number=st[2],
        implementation_guide=st[3] if len(st) > 3 else None,
        body_segments=body_segments,
    )
