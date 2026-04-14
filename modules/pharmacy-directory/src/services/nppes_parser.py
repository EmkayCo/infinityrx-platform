"""NPPES V2 pharmacy-filter parser.

Filters NPPES download to pharmacy taxonomy codes (333600000X and subtypes).
Monthly full + weekly incremental. Marks records with an NPI Deactivation
Date as inactive.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import IO

from src.utils.taxonomy import classify_pharmacy_type

# Pharmacy taxonomy code prefix (333600000X and all 3336XXXXXXX subtypes)
_PHARMACY_TAXONOMY_PREFIX = "3336"
_PHARMACY_ROOT = "333600000X"


def _is_pharmacy_taxonomy(code: str) -> bool:
    c = code.strip()
    return c == _PHARMACY_ROOT or c.startswith(_PHARMACY_TAXONOMY_PREFIX)


@dataclass
class NppesRecord:
    npi: str
    organization_name: str
    address_line_1: str
    city: str
    state: str
    zip_code: str
    phone: str
    taxonomy_code: str
    pharmacy_type: str
    is_active: bool


def parse_nppes_fixture(source: IO[str]) -> list[NppesRecord]:
    """Parse NPPES V2 CSV, returning only pharmacy taxonomy records."""
    reader = csv.DictReader(source)
    records: list[NppesRecord] = []
    for row in reader:
        taxonomy = row.get("Healthcare Provider Taxonomy Code_1", "").strip()
        if not _is_pharmacy_taxonomy(taxonomy):
            continue
        deactivation = row.get("NPI Deactivation Date", "").strip()
        is_active = deactivation == ""
        records.append(
            NppesRecord(
                npi=row["NPI"].strip(),
                organization_name=row.get(
                    "Provider Organization Name (Legal Business Name)", ""
                ).strip(),
                address_line_1=row.get(
                    "Provider Business Practice Location Address First Line", ""
                ).strip(),
                city=row.get(
                    "Provider Business Practice Location Address City Name", ""
                ).strip(),
                state=row.get(
                    "Provider Business Practice Location Address State Name", ""
                ).strip(),
                zip_code=row.get(
                    "Provider Business Practice Location Address Postal Code", ""
                ).strip(),
                phone=row.get(
                    "Provider Business Practice Location Address Telephone Number", ""
                ).strip(),
                taxonomy_code=taxonomy,
                pharmacy_type=classify_pharmacy_type(taxonomy),
                is_active=is_active,
            )
        )
    return records
