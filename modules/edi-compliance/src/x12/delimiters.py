"""X12 delimiter detection and constants.

ISA is a fixed-width segment (106 chars including the 3 delimiter chars).
- Element separator:     ISA[3]  (char at index 3, between "ISA" and the 1st element)
- Sub-element separator: ISA[104] (typically `:` or `>`)
- Segment terminator:    char immediately after the 106-char ISA segment

Never assume `*~:` as defaults. Always read from the actual file bytes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Delimiters:
    element: str       # typically `*`
    sub_element: str   # typically `:` or `>`
    segment: str       # typically `~`

    def validate(self) -> None:
        for name, val in (
            ("element", self.element),
            ("sub_element", self.sub_element),
            ("segment", self.segment),
        ):
            if len(val) != 1:
                raise ValueError(f"Delimiter '{name}' must be exactly 1 character, got {val!r}")
        if len({self.element, self.sub_element, self.segment}) != 3:
            raise ValueError("All three delimiters must be distinct characters")


_DEFAULT_DELIMITERS = Delimiters(element="*", sub_element=":", segment="~")


def detect_delimiters(raw: str) -> Delimiters:
    """Read delimiters from the ISA segment.

    The ISA segment is ALWAYS the first segment.  Its structure is fixed-width:
      ISA<elem>...16 elements...<sub_elem><term>
    Positions (0-indexed in the raw ISA segment string, excluding leading 'ISA'):
      index 0:   element separator (first char after 'ISA')
      index 101: sub-element separator (ISA16 value)
      index 102: segment terminator (char right after ISA16)
    Counting from the very start of the file (including 'ISA'):
      char[3]:   element separator
      char[104]: sub-element separator
      char[105]: segment terminator
    """
    if len(raw) < 106:
        raise ValueError(
            f"Raw EDI content too short ({len(raw)} chars) to contain a complete ISA segment"
        )
    if not raw.startswith("ISA"):
        raise ValueError("EDI content must start with 'ISA'")

    element = raw[3]
    sub_element = raw[104]
    segment = raw[105]
    delims = Delimiters(element=element, sub_element=sub_element, segment=segment)
    delims.validate()
    return delims
