"""X12 segment builder and low-level utilities."""

from __future__ import annotations

from typing import Any

from .delimiters import Delimiters


def build_segment(segment_id: str, elements: list[Any], delims: Delimiters) -> str:
    """Build a single X12 segment string with the given delimiter set.

    Elements are joined with the element separator; the segment terminator
    is appended at the end.  None values are rendered as empty strings.
    """
    parts = [segment_id] + [("" if e is None else str(e)) for e in elements]
    return delims.element.join(parts) + delims.segment


def pad_isa_id(value: str) -> str:
    """Pad ISA06/ISA08 to exactly 15 chars with trailing spaces (PRD §3.18).

    The ISA standard requires exactly 15 characters for interchange IDs.
    Parsers MUST NOT trim this field — the trailing spaces are structurally
    significant.
    """
    if len(value) > 15:
        raise ValueError(f"ISA ID exceeds 15 characters: {value!r}")
    return value.ljust(15)


def pad_isa_control(value: int) -> str:
    """Pad ISA13 to exactly 9 digits with leading zeros."""
    s = str(value)
    if len(s) > 9:
        raise ValueError(f"ISA control number exceeds 9 digits: {value}")
    return s.zfill(9)


def parse_segments(raw: str, delims: Delimiters) -> list[list[str]]:
    """Split raw X12 into a list of parsed segments.

    Returns a list where each element is [segment_id, element1, element2, ...].
    ISA06 and ISA08 are NOT stripped — callers that need the raw value get it.
    """
    segments: list[list[str]] = []
    for seg_str in raw.split(delims.segment):
        seg_str = seg_str.strip("\n\r ")
        if not seg_str:
            continue
        parts = seg_str.split(delims.element)
        segments.append(parts)
    return segments
