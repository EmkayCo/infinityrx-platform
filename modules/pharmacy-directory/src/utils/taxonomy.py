"""NPPES taxonomy code -> pharmacy_type mapping (PRD section 3.12)."""
from __future__ import annotations

_TAXONOMY_MAP: dict[str, str] = {
    "333600000X": "retail",
    "3336C0003X": "retail",
    "3336C0004X": "compounding",
    "3336H0001X": "home_infusion",
    "3336I0012X": "institutional",
    "3336L0003X": "ltc",
    "3336M0002X": "mail_order",
    "3336N0007X": "nuclear",
    "3336S0011X": "specialty",
}


def classify_pharmacy_type(taxonomy_code: str) -> str:
    return _TAXONOMY_MAP.get(taxonomy_code, "retail")
