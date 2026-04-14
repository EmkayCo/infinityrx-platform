"""NCPDP Provider Database file parser.

Parses a monthly NCPDP data file (CSV fixture format) into NcpdpRecord
objects. Actual subscription download is stubbed — only parser + upsert
pipeline is implemented per PRD section 3.1.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import IO


@dataclass
class NcpdpRecord:
    npi: str
    nabp_number: str
    ncpdp_id: str
    legal_name: str
    dba_name: str
    pharmacy_type: str
    chain_name: str
    chain_code: str
    store_number: str
    address_line_1: str
    address_line_2: str
    city: str
    state: str
    zip_code: str
    phone: str
    fax: str
    hours_monday: str
    hours_tuesday: str
    hours_wednesday: str
    hours_thursday: str
    hours_friday: str
    hours_saturday: str
    hours_sunday: str
    is_24_hour: bool
    accepts_electronic_rx: bool
    dispenses_controlled: bool
    offers_delivery: bool
    offers_compounding: bool
    offers_specialty: bool
    offers_340b: bool
    status: str


def _bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def parse_ncpdp_fixture(source: IO[str]) -> list[NcpdpRecord]:
    """Parse NCPDP CSV fixture. Returns list of NcpdpRecord."""
    reader = csv.DictReader(source)
    records: list[NcpdpRecord] = []
    for row in reader:
        records.append(
            NcpdpRecord(
                npi=row["npi"].strip(),
                nabp_number=row["nabp_number"].strip(),
                ncpdp_id=row["ncpdp_id"].strip(),
                legal_name=row["legal_name"].strip(),
                dba_name=row.get("dba_name", "").strip(),
                pharmacy_type=row["pharmacy_type"].strip(),
                chain_name=row.get("chain_name", "").strip(),
                chain_code=row.get("chain_code", "").strip(),
                store_number=row.get("store_number", "").strip(),
                address_line_1=row["address_line_1"].strip(),
                address_line_2=row.get("address_line_2", "").strip(),
                city=row["city"].strip(),
                state=row["state"].strip(),
                zip_code=row["zip_code"].strip(),
                phone=row.get("phone", "").strip(),
                fax=row.get("fax", "").strip(),
                hours_monday=row.get("hours_monday", "").strip(),
                hours_tuesday=row.get("hours_tuesday", "").strip(),
                hours_wednesday=row.get("hours_wednesday", "").strip(),
                hours_thursday=row.get("hours_thursday", "").strip(),
                hours_friday=row.get("hours_friday", "").strip(),
                hours_saturday=row.get("hours_saturday", "").strip(),
                hours_sunday=row.get("hours_sunday", "").strip(),
                is_24_hour=_bool(row.get("is_24_hour", "False")),
                accepts_electronic_rx=_bool(row.get("accepts_electronic_rx", "True")),
                dispenses_controlled=_bool(row.get("dispenses_controlled", "True")),
                offers_delivery=_bool(row.get("offers_delivery", "False")),
                offers_compounding=_bool(row.get("offers_compounding", "False")),
                offers_specialty=_bool(row.get("offers_specialty", "False")),
                offers_340b=_bool(row.get("offers_340b", "False")),
                status=row.get("status", "active").strip(),
            )
        )
    return records
