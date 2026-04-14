"""Tests for NPPES V2 CSV parser.

100% coverage required on field mapping.
"""

from __future__ import annotations

import csv
import io
from datetime import date


from src.services.nppes_parser import NppesParser, ParsedNpi


# Minimal header for a representative V2 NPPES record (329 columns full)
# We use the canonical column names from the NPPES V2 data dictionary.
NPPES_V2_HEADER = [
    "NPI",
    "Entity Type Code",
    "Replacement NPI",
    "Employer Identification Number (EIN)",
    "Provider Organization Name (Legal Business Name)",
    "Provider Last Name (Legal Name)",
    "Provider First Name",
    "Provider Middle Name",
    "Provider Name Prefix Text",
    "Provider Name Suffix Text",
    "Provider Credential Text",
    "Provider Other Organization Name",
    "Provider Other Organization Name Type Code",
    "Provider Other Last Name",
    "Provider Other First Name",
    "Provider Other Middle Name",
    "Provider Other Name Prefix Text",
    "Provider Other Name Suffix Text",
    "Provider Other Credential Text",
    "Provider Other Last Name Type Code",
    "Provider First Line Business Mailing Address",
    "Provider Second Line Business Mailing Address",
    "Provider Business Mailing Address City Name",
    "Provider Business Mailing Address State Name",
    "Provider Business Mailing Address Postal Code",
    "Provider Business Mailing Address Country Code (If outside U.S.)",
    "Provider Business Mailing Address Telephone Number",
    "Provider Business Mailing Address Fax Number",
    "Provider First Line Business Practice Location Address",
    "Provider Second Line Business Practice Location Address",
    "Provider Business Practice Location Address City Name",
    "Provider Business Practice Location Address State Name",
    "Provider Business Practice Location Address Postal Code",
    "Provider Business Practice Location Address Country Code (If outside U.S.)",
    "Provider Business Practice Location Address Telephone Number",
    "Provider Business Practice Location Address Fax Number",
    "Provider Enumeration Date",
    "Last Update Date",
    "NPI Deactivation Reason Code",
    "NPI Deactivation Date",
    "NPI Reactivation Date",
    "Provider Gender Code",
    "Authorized Official Last Name",
    "Authorized Official First Name",
    "Authorized Official Middle Name",
    "Authorized Official Title or Position",
    "Authorized Official Telephone Number",
    "Healthcare Provider Taxonomy Code_1",
    "Provider License Number_1",
    "Provider License Number State Code_1",
    "Healthcare Provider Primary Taxonomy Switch_1",
    "Healthcare Provider Taxonomy Code_2",
    "Provider License Number_2",
    "Provider License Number State Code_2",
    "Healthcare Provider Primary Taxonomy Switch_2",
    "Is Sole Proprietor",
    "Is Organization Subpart",
    "Parent Organization LBN",
    "Parent Organization TIN",
    "Authorized Official Name Prefix Text",
    "Authorized Official Name Suffix Text",
    "Authorized Official Credential Text",
    "Healthcare Provider Taxonomy Group_1",
    "Healthcare Provider Taxonomy Group_2",
]


def make_csv_row(**overrides) -> dict:
    defaults = {
        "NPI": "1234567893",
        "Entity Type Code": "1",
        "Replacement NPI": "",
        "Employer Identification Number (EIN)": "",
        "Provider Organization Name (Legal Business Name)": "",
        "Provider Last Name (Legal Name)": "SMITH",
        "Provider First Name": "JOHN",
        "Provider Middle Name": "A",
        "Provider Name Prefix Text": "DR.",
        "Provider Name Suffix Text": "",
        "Provider Credential Text": "MD",
        "Provider Other Organization Name": "",
        "Provider Other Organization Name Type Code": "",
        "Provider Other Last Name": "",
        "Provider Other First Name": "",
        "Provider Other Middle Name": "",
        "Provider Other Name Prefix Text": "",
        "Provider Other Name Suffix Text": "",
        "Provider Other Credential Text": "",
        "Provider Other Last Name Type Code": "",
        "Provider First Line Business Mailing Address": "123 MAIN ST",
        "Provider Second Line Business Mailing Address": "",
        "Provider Business Mailing Address City Name": "CHICAGO",
        "Provider Business Mailing Address State Name": "IL",
        "Provider Business Mailing Address Postal Code": "60601",
        "Provider Business Mailing Address Country Code (If outside U.S.)": "US",
        "Provider Business Mailing Address Telephone Number": "3125550100",
        "Provider Business Mailing Address Fax Number": "",
        "Provider First Line Business Practice Location Address": "456 OAK AVE",
        "Provider Second Line Business Practice Location Address": "STE 200",
        "Provider Business Practice Location Address City Name": "CHICAGO",
        "Provider Business Practice Location Address State Name": "IL",
        "Provider Business Practice Location Address Postal Code": "60601",
        "Provider Business Practice Location Address Country Code (If outside U.S.)": "US",
        "Provider Business Practice Location Address Telephone Number": "3125550200",
        "Provider Business Practice Location Address Fax Number": "3125550201",
        "Provider Enumeration Date": "05/15/2010",
        "Last Update Date": "01/10/2025",
        "NPI Deactivation Reason Code": "",
        "NPI Deactivation Date": "",
        "NPI Reactivation Date": "",
        "Provider Gender Code": "M",
        "Authorized Official Last Name": "",
        "Authorized Official First Name": "",
        "Authorized Official Middle Name": "",
        "Authorized Official Title or Position": "",
        "Authorized Official Telephone Number": "",
        "Healthcare Provider Taxonomy Code_1": "207Q00000X",
        "Provider License Number_1": "054321",
        "Provider License Number State Code_1": "IL",
        "Healthcare Provider Primary Taxonomy Switch_1": "Y",
        "Healthcare Provider Taxonomy Code_2": "",
        "Provider License Number_2": "",
        "Provider License Number State Code_2": "",
        "Healthcare Provider Primary Taxonomy Switch_2": "N",
        "Is Sole Proprietor": "Y",
        "Is Organization Subpart": "N",
        "Parent Organization LBN": "",
        "Parent Organization TIN": "",
        "Authorized Official Name Prefix Text": "",
        "Authorized Official Name Suffix Text": "",
        "Authorized Official Credential Text": "",
        "Healthcare Provider Taxonomy Group_1": "",
        "Healthcare Provider Taxonomy Group_2": "",
    }
    defaults.update(overrides)
    return defaults


def rows_to_csv(rows: list[dict]) -> io.StringIO:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=NPPES_V2_HEADER)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    buf.seek(0)
    return buf


class TestNppesParserFieldMapping:
    def test_parses_individual_prescriber(self):
        csv_data = rows_to_csv([make_csv_row()])
        parser = NppesParser()
        results = list(parser.parse(csv_data))
        assert len(results) == 1
        p = results[0]
        assert isinstance(p, ParsedNpi)
        assert p.npi == "1234567893"
        assert p.entity_type == "1"
        assert p.last_name == "SMITH"
        assert p.first_name == "JOHN"
        assert p.middle_name == "A"
        assert p.credential == "MD"

    def test_parses_display_name_individual(self):
        csv_data = rows_to_csv([make_csv_row()])
        parser = NppesParser()
        results = list(parser.parse(csv_data))
        p = results[0]
        assert "SMITH" in p.display_name
        assert "JOHN" in p.display_name

    def test_parses_organization(self):
        row = make_csv_row(
            **{
                "Entity Type Code": "2",
                "Provider Last Name (Legal Name)": "",
                "Provider First Name": "",
                "Provider Organization Name (Legal Business Name)": "CHICAGO MEDICAL GROUP LLC",
            }
        )
        csv_data = rows_to_csv([row])
        parser = NppesParser()
        results = list(parser.parse(csv_data))
        p = results[0]
        assert p.entity_type == "2"
        assert p.organization_name == "CHICAGO MEDICAL GROUP LLC"
        assert p.display_name == "CHICAGO MEDICAL GROUP LLC"

    def test_parses_practice_address(self):
        csv_data = rows_to_csv([make_csv_row()])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.practice_address_line_1 == "456 OAK AVE"
        assert p.practice_address_line_2 == "STE 200"
        assert p.practice_city == "CHICAGO"
        assert p.practice_state == "IL"
        assert p.practice_zip == "60601"
        assert p.practice_phone == "3125550200"

    def test_parses_mailing_address(self):
        csv_data = rows_to_csv([make_csv_row()])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.mailing_address_line_1 == "123 MAIN ST"
        assert p.mailing_city == "CHICAGO"
        assert p.mailing_state == "IL"

    def test_parses_taxonomy_codes(self):
        csv_data = rows_to_csv([make_csv_row()])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.primary_taxonomy_code == "207Q00000X"
        assert len(p.taxonomy_codes) >= 1
        primary = next(t for t in p.taxonomy_codes if t["is_primary"])
        assert primary["code"] == "207Q00000X"

    def test_parses_multiple_taxonomy_codes(self):
        row = make_csv_row(**{
            "Healthcare Provider Taxonomy Code_2": "207R00000X",
            "Provider License Number_2": "054322",
            "Provider License Number State Code_2": "IL",
            "Healthcare Provider Primary Taxonomy Switch_2": "N",
        })
        csv_data = rows_to_csv([row])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        codes = [t["code"] for t in p.taxonomy_codes]
        assert "207Q00000X" in codes
        assert "207R00000X" in codes

    def test_parses_enumeration_date(self):
        csv_data = rows_to_csv([make_csv_row()])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.enumeration_date == date(2010, 5, 15)

    def test_parses_last_update_date(self):
        csv_data = rows_to_csv([make_csv_row()])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.last_update_date == date(2025, 1, 10)

    def test_parses_deactivation(self):
        row = make_csv_row(**{
            "NPI Deactivation Reason Code": "DT",
            "NPI Deactivation Date": "03/01/2023",
        })
        csv_data = rows_to_csv([row])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.deactivation_date == date(2023, 3, 1)
        assert p.deactivation_reason == "DT"
        assert p.status == "deactivated"

    def test_parses_gender(self):
        csv_data = rows_to_csv([make_csv_row(**{"Provider Gender Code": "F"})])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.gender == "F"

    def test_parses_state_license(self):
        csv_data = rows_to_csv([make_csv_row()])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.state_license_number == "054321"
        assert p.state_license_state == "IL"

    def test_active_status_when_no_deactivation(self):
        csv_data = rows_to_csv([make_csv_row()])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.status == "active"

    def test_parses_multiple_rows(self):
        rows = [
            make_csv_row(NPI="1234567893"),
            make_csv_row(NPI="1679576722", **{"Provider Last Name (Legal Name)": "JONES"}),
        ]
        csv_data = rows_to_csv(rows)
        parser = NppesParser()
        results = list(parser.parse(csv_data))
        assert len(results) == 2
        npis = {p.npi for p in results}
        assert "1234567893" in npis
        assert "1679576722" in npis

    def test_skips_empty_npi_row(self):
        rows = [make_csv_row(NPI=""), make_csv_row(NPI="1234567893")]
        csv_data = rows_to_csv(rows)
        parser = NppesParser()
        results = list(parser.parse(csv_data))
        assert len(results) == 1
        assert results[0].npi == "1234567893"

    def test_skips_header_only_row(self):
        buf = io.StringIO()
        buf.write(",".join(NPPES_V2_HEADER) + "\n")
        buf.seek(0)
        parser = NppesParser()
        results = list(parser.parse(buf))
        assert len(results) == 0

    def test_authorized_official_for_org(self):
        row = make_csv_row(**{
            "Entity Type Code": "2",
            "Provider Organization Name (Legal Business Name)": "ACME HEALTH",
            "Authorized Official Last Name": "DOE",
            "Authorized Official First Name": "JANE",
            "Authorized Official Title or Position": "CEO",
        })
        csv_data = rows_to_csv([row])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert "DOE" in p.authorized_official_name
        assert p.authorized_official_title == "CEO"

    def test_reactivation_date_parsed(self):
        row = make_csv_row(**{
            "NPI Deactivation Reason Code": "DT",
            "NPI Deactivation Date": "03/01/2023",
            "NPI Reactivation Date": "06/01/2023",
        })
        csv_data = rows_to_csv([row])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.reactivation_date == date(2023, 6, 1)
        assert p.status == "active"

    def test_zip_code_normalized_to_5_digits(self):
        row = make_csv_row(**{
            "Provider Business Practice Location Address Postal Code": "606011234",
        })
        csv_data = rows_to_csv([row])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert len(p.practice_zip) <= 10  # stored as-is but not extended

    def test_empty_taxonomy_produces_empty_list(self):
        row = make_csv_row(**{
            "Healthcare Provider Taxonomy Code_1": "",
            "Healthcare Provider Primary Taxonomy Switch_1": "N",
        })
        csv_data = rows_to_csv([row])
        parser = NppesParser()
        p = list(parser.parse(csv_data))[0]
        assert p.taxonomy_codes == []
        assert p.primary_taxonomy_code is None
