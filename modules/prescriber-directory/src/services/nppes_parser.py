"""NPPES V2 CSV parser — streaming, 329-column format.

Design for 7.8M rows: stream-parse, never load full file into memory.
Yields ParsedNpi dataclass instances; caller handles bulk upsert.

Column names follow the NPPES V2 data dictionary exactly.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from io import StringIO
from typing import Any, Iterator, IO



def _parse_date_mmddyyyy(value: str) -> date | None:
    if not value or not value.strip():
        return None
    try:
        parts = value.strip().split("/")
        if len(parts) == 3:
            return date(int(parts[2]), int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None
    return None


@dataclass
class ParsedNpi:
    npi: str
    entity_type: str

    # Individual name fields
    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    credential: str | None = None
    display_name: str = ""

    # Organization fields
    organization_name: str | None = None
    authorized_official_name: str | None = None
    authorized_official_title: str | None = None

    # Practice address
    practice_address_line_1: str | None = None
    practice_address_line_2: str | None = None
    practice_city: str | None = None
    practice_state: str | None = None
    practice_zip: str | None = None
    practice_phone: str | None = None
    practice_fax: str | None = None

    # Mailing address
    mailing_address_line_1: str | None = None
    mailing_address_line_2: str | None = None
    mailing_city: str | None = None
    mailing_state: str | None = None
    mailing_zip: str | None = None

    # Taxonomy
    primary_taxonomy_code: str | None = None
    taxonomy_codes: list[dict[str, Any]] = field(default_factory=list)

    # State license (from primary taxonomy slot)
    state_license_number: str | None = None
    state_license_state: str | None = None

    # Gender (individual only)
    gender: str | None = None

    # Dates
    enumeration_date: date | None = None
    last_update_date: date | None = None
    deactivation_date: date | None = None
    deactivation_reason: str | None = None
    reactivation_date: date | None = None

    status: str = "active"


def _or_none(value: str) -> str | None:
    v = value.strip() if value else ""
    return v if v else None


def _build_display_name(row: dict[str, str], entity_type: str) -> str:
    if entity_type == "2":
        org = row.get("Provider Organization Name (Legal Business Name)", "").strip()
        return org if org else ""
    parts = []
    prefix = row.get("Provider Name Prefix Text", "").strip()
    first = row.get("Provider First Name", "").strip()
    middle = row.get("Provider Middle Name", "").strip()
    last = row.get("Provider Last Name (Legal Name)", "").strip()
    suffix = row.get("Provider Name Suffix Text", "").strip()
    credential = row.get("Provider Credential Text", "").strip()
    if prefix:
        parts.append(prefix)
    if first:
        parts.append(first)
    if middle:
        parts.append(middle)
    if last:
        parts.append(last)
    if suffix:
        parts.append(suffix)
    if credential:
        parts.append(credential)
    return " ".join(parts)


def _extract_taxonomy_codes(row: dict[str, str]) -> tuple[str | None, list[dict[str, Any]]]:
    """Extract up to 15 taxonomy code slots from NPPES V2 row."""
    codes = []
    primary_code = None
    for i in range(1, 16):
        code_key = f"Healthcare Provider Taxonomy Code_{i}"
        primary_key = f"Healthcare Provider Primary Taxonomy Switch_{i}"
        license_key = f"Provider License Number_{i}"
        license_state_key = f"Provider License Number State Code_{i}"
        code = row.get(code_key, "").strip()
        if not code:
            break
        is_primary = row.get(primary_key, "").strip().upper() == "Y"
        entry: dict[str, Any] = {
            "code": code,
            "is_primary": is_primary,
            "license_number": _or_none(row.get(license_key, "")),
            "license_state": _or_none(row.get(license_state_key, "")),
        }
        codes.append(entry)
        if is_primary:
            primary_code = code
    return primary_code, codes


class NppesParser:
    """Stream-parse NPPES V2 CSV files.

    Designed for the 7.8M-row full file: yields records one at a time,
    never loads entire file. Caller handles bulk insert/upsert.
    """

    def parse(self, source: IO[str] | StringIO) -> Iterator[ParsedNpi]:
        reader = csv.DictReader(source)
        for row in reader:
            npi = row.get("NPI", "").strip()
            if not npi:
                continue

            entity_type = row.get("Entity Type Code", "1").strip() or "1"

            deactivation_date = _parse_date_mmddyyyy(row.get("NPI Deactivation Date", ""))
            reactivation_date = _parse_date_mmddyyyy(row.get("NPI Reactivation Date", ""))
            deactivation_reason = _or_none(row.get("NPI Deactivation Reason Code", ""))

            if deactivation_date and not reactivation_date:
                status = "deactivated"
            else:
                status = "active"

            primary_taxonomy_code, taxonomy_codes = _extract_taxonomy_codes(row)

            # State license from primary taxonomy slot
            state_license_number = None
            state_license_state = None
            for tc in taxonomy_codes:
                if tc["is_primary"]:
                    state_license_number = tc["license_number"]
                    state_license_state = tc["license_state"]
                    break

            authorized_official_name = None
            ao_last = row.get("Authorized Official Last Name", "").strip()
            ao_first = row.get("Authorized Official First Name", "").strip()
            ao_mid = row.get("Authorized Official Middle Name", "").strip()
            if ao_last or ao_first:
                parts = [p for p in [ao_first, ao_mid, ao_last] if p]
                authorized_official_name = " ".join(parts)

            yield ParsedNpi(
                npi=npi,
                entity_type=entity_type,
                last_name=_or_none(row.get("Provider Last Name (Legal Name)", "")),
                first_name=_or_none(row.get("Provider First Name", "")),
                middle_name=_or_none(row.get("Provider Middle Name", "")),
                prefix=_or_none(row.get("Provider Name Prefix Text", "")),
                suffix=_or_none(row.get("Provider Name Suffix Text", "")),
                credential=_or_none(row.get("Provider Credential Text", "")),
                display_name=_build_display_name(row, entity_type),
                organization_name=_or_none(row.get("Provider Organization Name (Legal Business Name)", "")),
                authorized_official_name=authorized_official_name,
                authorized_official_title=_or_none(row.get("Authorized Official Title or Position", "")),
                practice_address_line_1=_or_none(row.get("Provider First Line Business Practice Location Address", "")),
                practice_address_line_2=_or_none(row.get("Provider Second Line Business Practice Location Address", "")),
                practice_city=_or_none(row.get("Provider Business Practice Location Address City Name", "")),
                practice_state=_or_none(row.get("Provider Business Practice Location Address State Name", "")),
                practice_zip=_or_none(row.get("Provider Business Practice Location Address Postal Code", "")),
                practice_phone=_or_none(row.get("Provider Business Practice Location Address Telephone Number", "")),
                practice_fax=_or_none(row.get("Provider Business Practice Location Address Fax Number", "")),
                mailing_address_line_1=_or_none(row.get("Provider First Line Business Mailing Address", "")),
                mailing_address_line_2=_or_none(row.get("Provider Second Line Business Mailing Address", "")),
                mailing_city=_or_none(row.get("Provider Business Mailing Address City Name", "")),
                mailing_state=_or_none(row.get("Provider Business Mailing Address State Name", "")),
                mailing_zip=_or_none(row.get("Provider Business Mailing Address Postal Code", "")),
                primary_taxonomy_code=primary_taxonomy_code,
                taxonomy_codes=taxonomy_codes,
                state_license_number=state_license_number,
                state_license_state=state_license_state,
                gender=_or_none(row.get("Provider Gender Code", "")),
                enumeration_date=_parse_date_mmddyyyy(row.get("Provider Enumeration Date", "")),
                last_update_date=_parse_date_mmddyyyy(row.get("Last Update Date", "")),
                deactivation_date=deactivation_date,
                deactivation_reason=deactivation_reason,
                reactivation_date=reactivation_date,
                status=status,
            )
