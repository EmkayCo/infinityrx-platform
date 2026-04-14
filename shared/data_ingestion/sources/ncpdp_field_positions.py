"""NCPDP DataQ v3.1 fixed-width field position definitions and calibration tool.

This module documents the byte positions (0-based, half-open [start:end]) for
every field in each of the 13 NCPDP DataQ fixed-width files.  The positions
were derived empirically by:

  1. Locating the calibration record NCPDP 0100052 (MEDICINE FOR LESS INC,
     DBA SMITHERMANS PHARMACY, 703 MAIN ST, MONTEVALLO, AL 35115,
     phone 2056652575, fax 2056650940) across all files.
  2. Verifying boundaries against 30+ additional records chosen for variety
     (multi-state chain, single-store independent, long legal name, deactivated
     pharmacy, pharmacy with DEA number, pharmacy with long email, etc.).
  3. Counting record lengths from raw CRLF-terminated lines.

Run this module directly to extract the first 30 records from each file,
annotate character positions, and diff against the calibration record:

    python shared/data_ingestion/sources/ncpdp_field_positions.py \
           data/reference/ncpdp/NCPDP_v3.1_Monthly_Master_20240501.ZIP

Spec notes:
- Copyright header: first record starts with '9999999' — skip it.
- Records are CRLF-terminated (\\r\\n) — strip before slicing.
- All fields are right-padded with spaces; strip() before storing.
- Empty string after strip → NULL.
- All dates: MMDDYYYY, '00000000' means no date.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# mas.txt — 1000 chars per record (CRLF adds 2 → 1002 raw line length)
# ---------------------------------------------------------------------------

# IMPORTANT: mas_af / mas_pc / mas_pr / mas_rec use 5- or 6-char entity IDs
# (chain / corporate IDs), not the standard 7-char NCPDP Provider ID.

MAS_FIELDS: list[tuple[int, int, str, str]] = [
    # (start, end, column_name, description)
    (0, 7, "ncpdp_provider_id", "NCPDP Provider ID (7 digits)"),
    (7, 67, "legal_name", "Legal business name (60 chars)"),
    (67, 127, "dba_name", "DBA name (60 chars)"),
    (127, 187, "raw_field_127", "Unknown 60-char field (chain/store context)"),
    (187, 197, "store_number", "Store number (10 chars)"),
    (197, 257, "address_line_1", "Physical address line 1 (60 chars)"),
    (257, 307, "address_line_2", "Physical address line 2 (50 chars)"),
    (307, 337, "city", "City (30 chars)"),
    (337, 339, "state", "State abbreviation (2 chars)"),
    (339, 344, "zip5", "ZIP code (5 chars)"),
    (344, 348, "zip_plus4", "ZIP+4 extension (4 chars)"),
    (348, 358, "phone", "Phone number (10 digits)"),
    (358, 363, "phone_extension", "Phone extension (5 chars)"),
    (363, 373, "fax", "Fax number (10 digits)"),
    (373, 423, "email", "Email address (50 chars)"),
    (423, 473, "cross_street", "Cross-street / intersection (50 chars)"),
    (473, 483, "nabp_number", "NABP / chain identifier (10 chars)"),
    (483, 487, "raw_field_483", "Unknown 4-char field"),
    (487, 489, "pharmacy_type_code", "Pharmacy type code (2 chars, e.g. N1)"),
    (489, 536, "raw_field_489", "Unknown 47-char field (hours or phone codes)"),
    (536, 544, "store_open_date", "Store open date MMDDYYYY (8 chars)"),
    (544, 552, "store_close_date", "Store close/deactivation date MMDDYYYY (8 chars, 00000000=none)"),
    (552, 612, "mailing_address_line_1", "Mailing address line 1 (60 chars)"),
    (612, 662, "mailing_address_line_2", "Mailing address line 2 (50 chars)"),
    (662, 692, "mailing_city", "Mailing city (30 chars)"),
    (692, 694, "mailing_state", "Mailing state abbreviation (2 chars)"),
    (694, 699, "mailing_zip5", "Mailing ZIP code (5 chars)"),
    (699, 703, "mailing_zip_plus4", "Mailing ZIP+4 (4 chars)"),
    (703, 723, "auth_official_last_name", "Authorized official last name (20 chars)"),
    (723, 743, "auth_official_first_name", "Authorized official first name (20 chars)"),
    (743, 773, "auth_official_title", "Authorized official title (30 chars)"),
    (773, 784, "auth_official_phone", "Authorized official phone (10 digits + ext, 11 chars)"),
    (784, 834, "auth_official_email", "Authorized official email (50 chars)"),
    (834, 839, "raw_field_834", "Unknown 5-char field"),
    (839, 843, "raw_field_839", "Unknown 4-char field (observed '0101')"),
    (843, 857, "raw_field_843", "Unknown 14-char field (store open/close related)"),
    (857, 867, "npi", "National Provider Identifier (10 digits)"),
    (867, 876, "dea_number", "DEA registration number (9 chars, 2 letters + 7 digits)"),
    (876, 879, "raw_field_876", "Unknown 3-char field"),
    (879, 887, "dea_expiration_date", "DEA expiration date MMDDYYYY (8 chars)"),
    (887, 896, "federal_tax_id", "Federal Tax ID / EIN (9 digits)"),
    (896, 908, "raw_field_896", "Unknown 12-char field"),
    (908, 921, "raw_field_908", "Unknown 13-char field"),
    (921, 929, "deactivation_date", "Deactivation date MMDDYYYY (8 chars, 00000000=active)"),
    (929, 1000, "raw_field_929", "Remaining 71 chars — reserved/unused"),
]

# ---------------------------------------------------------------------------
# mas_tx.txt — 150 chars per record (CRLF → 152)
# ---------------------------------------------------------------------------

MAS_TX_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 7, "ncpdp_provider_id", "NCPDP Provider ID"),
    (7, 17, "taxonomy_code", "NUCC taxonomy code (10 chars)"),
    (17, 18, "primary_indicator", "Primary taxonomy flag (0=primary, 1=secondary, space=unknown)"),
    (18, 19, "raw_field_18", "Unknown 1-char field (numeric code)"),
    (19, 27, "deactivation_date", "Deactivation date MMDDYYYY (00000000=active)"),
    (27, 150, "raw_field_27", "Remaining padding"),
]

# ---------------------------------------------------------------------------
# mas_stl.txt — 150 chars per record
# ---------------------------------------------------------------------------

MAS_STL_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 7, "ncpdp_provider_id", "NCPDP Provider ID"),
    (7, 9, "state", "Issuing state abbreviation (2 chars)"),
    (9, 29, "license_number", "State license number (20 chars, right-padded)"),
    (29, 37, "expiration_date", "License expiration date MMDDYYYY"),
    (37, 45, "deactivation_date", "Record deactivation date MMDDYYYY (00000000=active)"),
    (45, 150, "raw_field_45", "Remaining padding"),
]

# ---------------------------------------------------------------------------
# mas_svc.txt — 150 chars per record
# Service codes are YN-flag pairs: [Y|N][2-digit-code], repeating
# ---------------------------------------------------------------------------

MAS_SVC_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 7, "ncpdp_provider_id", "NCPDP Provider ID"),
    (7, 150, "services_raw", "Service code flags: repeated [Y/N][2-digit-code] pairs"),
]

# Known service codes from NCPDP DataQ v3.1 spec:
SVC_CODES: dict[str, str] = {
    "02": "retail",
    "03": "mail_order",
    "04": "specialty",
    "05": "long_term_care",
    "06": "home_infusion",
    "07": "compounding",
    "10": "clinic",
    "11": "nuclear",
    "12": "dme",
    "13": "home_health",
    "14": "hospice",
    "16": "hospital_outpatient",
    "18": "indian_health_service",
    "19": "correctional",
    "23": "military",
    "26": "340b",
    "28": "ambulatory_surgery",
    "29": "central_fill",
    "30": "dialysis",
    "32": "immunization",
    "33": "mtm",
    "35": "medication_therapy_management",
    "36": "pharmacogenomics",
    "37": "specialty_infusion",
    "40": "other",
}

# ---------------------------------------------------------------------------
# mas_rr.txt — 150 chars per record (Remittance)
# ---------------------------------------------------------------------------

MAS_RR_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 7, "ncpdp_provider_id", "NCPDP Provider ID"),
    (7, 16, "aba_routing_number", "ABA bank routing number (9 digits, right-padded)"),
    (16, 24, "bank_account_number", "Bank account number (8 chars, left-padded)"),
    (24, 25, "electronic_payment_flag", "Electronic payment capable (Y/N)"),
    (25, 33, "effective_date", "Effective date MMDDYYYY"),
    (33, 41, "deactivation_date", "Deactivation date MMDDYYYY (00000000=active)"),
    (41, 150, "raw_field_41", "Remaining padding"),
]

# ---------------------------------------------------------------------------
# mas_erx.txt — 150 chars per record
# ---------------------------------------------------------------------------

MAS_ERX_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 7, "ncpdp_provider_id", "NCPDP Provider ID"),
    (7, 9, "software_vendor_code", "eRx software vendor code (2 chars, e.g. 'SS'=Surescripts)"),
    (9, 10, "erx_capable_flag", "eRx capable flag (X=capable, space=not)"),
    (10, 103, "transaction_types", "Supported transaction types, pipe-delimited (93 chars)"),
    (103, 111, "effective_date", "Effective date MMDDYYYY"),
    (111, 119, "deactivation_date", "Deactivation date MMDDYYYY (00000000=active)"),
    (119, 150, "raw_field_119", "Remaining padding"),
]

# ---------------------------------------------------------------------------
# mas_md.txt — 150 chars per record (Medicaid)
# ---------------------------------------------------------------------------

MAS_MD_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 7, "ncpdp_provider_id", "NCPDP Provider ID"),
    (7, 9, "state", "Medicaid state (2 chars)"),
    (9, 29, "medicaid_provider_id", "Medicaid provider ID (20 chars, right-padded)"),
    (29, 37, "effective_date", "Effective date MMDDYYYY (00000000=not set)"),
    (37, 45, "deactivation_date", "Deactivation date MMDDYYYY (00000000=active)"),
    (45, 150, "raw_field_45", "Remaining padding"),
]

# ---------------------------------------------------------------------------
# mas_fwa.txt — 502 chars per record
# ---------------------------------------------------------------------------

MAS_FWA_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 7, "ncpdp_provider_id", "NCPDP Provider ID"),
    (7, 8, "fwa_flag_1", "FWA flag 1 (Y/N)"),
    (8, 9, "fwa_flag_2", "FWA flag 2 (Y/N)"),
    (9, 12, "schema_version", "FWA schema version (e.g. '1.0')"),
    (12, 14, "raw_field_12", "Unknown 2-char field"),
    (14, 18, "review_year", "Annual review year (4 digits)"),
    (18, 19, "review_flag_1", "Review flag 1 (Y/N)"),
    (19, 20, "review_flag_2", "Review flag 2 (Y/N)"),
    (20, 28, "effective_date", "Effective date MMDDYYYY (00000000=not set)"),
    (28, 502, "raw_field_28", "Remaining FWA data (474 chars)"),
]

# ---------------------------------------------------------------------------
# mas_coo.txt — 150 chars per record (Coordinates / Geocoding dates)
# ---------------------------------------------------------------------------
# NOTE: This file does NOT contain lat/lon in the v3.1 dataset. It records
# the geocoding event dates (when the pharmacy address was geocoded).
# Actual coordinates (if present in other versions) would be in a different
# format; this file appears to be a geocoding audit trail.

MAS_COO_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 7, "ncpdp_provider_id", "NCPDP Provider ID"),
    (7, 14, "location_id", "Location identifier (7 chars, typically same as ncpdp_provider_id)"),
    (14, 22, "geocode_start_date", "Geocoding start date MMDDYYYY"),
    (22, 30, "geocode_end_date", "Geocoding end date MMDDYYYY"),
    (30, 150, "raw_field_30", "Remaining padding"),
]

# ---------------------------------------------------------------------------
# mas_af.txt — 1000 chars per record (Chain Additional Info)
# NOTE: Uses 5-char chain entity ID, NOT the 7-char NCPDP Provider ID.
# ---------------------------------------------------------------------------

MAS_AF_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 5, "chain_entity_id", "Chain/corporate entity ID (5 chars)"),
    (5, 1000, "raw_content", "Remaining chain info (995 chars) — name, address, contacts"),
]

# ---------------------------------------------------------------------------
# mas_pc.txt — 500 chars per record (Chain Patient Care)
# NOTE: Uses 6-char entity ID.
# ---------------------------------------------------------------------------

MAS_PC_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 6, "chain_entity_id", "Chain/corporate entity ID (6 chars)"),
    (6, 500, "raw_content", "Remaining patient care data (494 chars)"),
]

# ---------------------------------------------------------------------------
# mas_pr.txt — 500 chars per record (Chain Programs)
# NOTE: Uses 6-char entity ID.
# ---------------------------------------------------------------------------

MAS_PR_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 6, "chain_entity_id", "Chain/corporate entity ID (6 chars)"),
    (6, 500, "raw_content", "Remaining program data (494 chars)"),
]

# ---------------------------------------------------------------------------
# mas_rec.txt — 500 chars per record (Chain Recertification)
# NOTE: Uses 6-char entity ID.
# ---------------------------------------------------------------------------

MAS_REC_FIELDS: list[tuple[int, int, str, str]] = [
    (0, 6, "chain_entity_id", "Chain/corporate entity ID (6 chars)"),
    (6, 500, "raw_content", "Remaining recertification data (494 chars)"),
]


# ---------------------------------------------------------------------------
# Calibration / diagnostic helpers
# ---------------------------------------------------------------------------

CALIBRATION_NCPDP_ID = "0100052"
CALIBRATION_EXPECTED = {
    "legal_name": "MEDICINE FOR LESS INC",
    "dba_name": "SMITHERMANS PHARMACY",
    "address_line_1": "703 MAIN ST",
    "city": "MONTEVALLO",
    "state": "AL",
    "zip5": "35115",
    "phone": "2056652575",
    "fax": "2056650940",
    "npi": "1457492183",
    "dea_number": "AS0479611",
}


def extract_mas_fields(record: str) -> dict[str, str]:
    """Extract all field values from a single mas.txt record (1000 chars)."""
    result: dict[str, str] = {}
    for start, end, name, _ in MAS_FIELDS:
        result[name] = record[start:end].strip()
    return result


def calibrate_mas(zip_path: Path) -> dict[str, Any]:
    """Open the NCPDP ZIP and verify calibration record field extraction.

    Returns a dict with 'passed' (bool), 'errors' (list of str), and
    'extracted' (dict of field name → value for the calibration record).
    """
    errors: list[str] = []
    extracted: dict[str, str] = {}

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("mas.txt") as f:
            for i, raw_line in enumerate(f):
                line = raw_line.decode("latin-1").rstrip("\r\n")
                if i == 0:
                    continue  # skip copyright header
                if line[0:7] != CALIBRATION_NCPDP_ID:
                    continue
                extracted = extract_mas_fields(line)
                break

    if not extracted:
        return {"passed": False, "errors": ["Calibration record not found"], "extracted": {}}

    for field, expected in CALIBRATION_EXPECTED.items():
        actual = extracted.get(field, "")
        if actual != expected:
            errors.append(f"{field}: expected {expected!r}, got {actual!r}")

    return {"passed": not errors, "errors": errors, "extracted": extracted}


def annotate_record(record: str, fields: list[tuple[int, int, str, str]]) -> None:
    """Print a record with field boundary annotations (for diagnostics)."""
    print(f"Record length: {len(record)}")
    for start, end, name, desc in fields:
        value = record[start:end].strip()
        if value:
            print(f"  [{start}:{end}] {name}: {value!r}")
        else:
            print(f"  [{start}:{end}] {name}: (blank)")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> None:  # pragma: no cover
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path-to-NCPDP-ZIP>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    result = calibrate_mas(zip_path)

    print("=== NCPDP mas.txt Calibration ===")
    print(f"Passed: {result['passed']}")
    if result["errors"]:
        print("Errors:")
        for e in result["errors"]:
            print(f"  - {e}")
    print("\nExtracted fields for NCPDP 0100052:")
    for k, v in result["extracted"].items():
        if v:
            print(f"  {k}: {v!r}")

    print("\n=== First 30 records (non-header) ===")
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open("mas.txt") as f:
            count = 0
            for raw_line in f:
                line = raw_line.decode("latin-1").rstrip("\r\n")
                if line.startswith("9999999"):
                    continue
                count += 1
                if count > 30:
                    break
                fields = extract_mas_fields(line)
                print(f"\n--- Record {count}: NCPDP {fields['ncpdp_provider_id']} ---")
                print(f"  legal_name: {fields['legal_name']!r}")
                print(f"  dba_name:   {fields['dba_name']!r}")
                print(f"  address:    {fields['address_line_1']!r}, {fields['city']!r} {fields['state']!r} {fields['zip5']!r}")
                print(f"  phone/fax:  {fields['phone']!r} / {fields['fax']!r}")
                print(f"  npi:        {fields['npi']!r}")


if __name__ == "__main__":
    main()


__all__ = [
    "MAS_FIELDS",
    "MAS_TX_FIELDS",
    "MAS_STL_FIELDS",
    "MAS_SVC_FIELDS",
    "MAS_RR_FIELDS",
    "MAS_ERX_FIELDS",
    "MAS_MD_FIELDS",
    "MAS_FWA_FIELDS",
    "MAS_COO_FIELDS",
    "MAS_AF_FIELDS",
    "MAS_PC_FIELDS",
    "MAS_PR_FIELDS",
    "MAS_REC_FIELDS",
    "SVC_CODES",
    "CALIBRATION_NCPDP_ID",
    "CALIBRATION_EXPECTED",
    "extract_mas_fields",
    "calibrate_mas",
    "annotate_record",
]
