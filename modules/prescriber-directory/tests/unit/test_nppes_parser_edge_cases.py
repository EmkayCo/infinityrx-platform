"""NPPES parser edge case tests — alternative date formats, extreme inputs."""

from __future__ import annotations

import io
import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from src.services.nppes_parser import NppesParser, _parse_date_mmddyyyy, _or_none, _build_display_name


class TestParseDateMmddyyyy:
    def test_valid_date(self):
        assert _parse_date_mmddyyyy("01/15/2025") is not None

    def test_empty_returns_none(self):
        assert _parse_date_mmddyyyy("") is None

    def test_none_string_returns_none(self):
        assert _parse_date_mmddyyyy(None) is None  # type: ignore[arg-type]

    def test_invalid_format_returns_none(self):
        assert _parse_date_mmddyyyy("not-a-date") is None

    def test_invalid_parts_returns_none(self):
        assert _parse_date_mmddyyyy("99/99/9999") is None

    def test_whitespace_only_returns_none(self):
        assert _parse_date_mmddyyyy("   ") is None


class TestOrNone:
    def test_empty_string_returns_none(self):
        assert _or_none("") is None

    def test_whitespace_returns_none(self):
        assert _or_none("   ") is None

    def test_value_returns_value(self):
        assert _or_none("hello") == "hello"

    def test_none_returns_none(self):
        assert _or_none(None) is None  # type: ignore[arg-type]


class TestBuildDisplayName:
    def test_individual_with_all_fields(self):
        row = {
            "Provider Name Prefix Text": "DR.",
            "Provider First Name": "JOHN",
            "Provider Middle Name": "A",
            "Provider Last Name (Legal Name)": "SMITH",
            "Provider Name Suffix Text": "",
            "Provider Credential Text": "MD",
        }
        name = _build_display_name(row, "1")
        assert "DR." in name
        assert "JOHN" in name
        assert "SMITH" in name
        assert "MD" in name

    def test_individual_no_prefix(self):
        row = {
            "Provider Name Prefix Text": "",
            "Provider First Name": "JANE",
            "Provider Middle Name": "",
            "Provider Last Name (Legal Name)": "DOE",
            "Provider Name Suffix Text": "PhD",
            "Provider Credential Text": "",
        }
        name = _build_display_name(row, "1")
        assert name.startswith("JANE")
        assert "PhD" in name

    def test_organization_returns_org_name(self):
        row = {
            "Provider Organization Name (Legal Business Name)": "ACME HEALTH",
        }
        name = _build_display_name(row, "2")
        assert name == "ACME HEALTH"

    def test_organization_empty_name_returns_empty(self):
        row = {
            "Provider Organization Name (Legal Business Name)": "",
        }
        name = _build_display_name(row, "2")
        assert name == ""


class TestNppesParserMorePaths:
    def test_taxonomy_up_to_15_slots(self):
        """Parser should break on first empty taxonomy slot."""
        header = [
            "NPI", "Entity Type Code",
            "Provider Last Name (Legal Name)", "Provider First Name",
            "Provider Middle Name", "Provider Name Prefix Text",
            "Provider Name Suffix Text", "Provider Credential Text",
            "Provider Organization Name (Legal Business Name)",
            "Provider Other Organization Name", "Provider Other Organization Name Type Code",
            "Provider Other Last Name", "Provider Other First Name", "Provider Other Middle Name",
            "Provider Other Name Prefix Text", "Provider Other Name Suffix Text",
            "Provider Other Credential Text", "Provider Other Last Name Type Code",
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
            "Provider Enumeration Date", "Last Update Date",
            "NPI Deactivation Reason Code", "NPI Deactivation Date", "NPI Reactivation Date",
            "Provider Gender Code",
            "Authorized Official Last Name", "Authorized Official First Name",
            "Authorized Official Middle Name", "Authorized Official Title or Position",
            "Authorized Official Telephone Number",
            "Healthcare Provider Taxonomy Code_1", "Provider License Number_1",
            "Provider License Number State Code_1", "Healthcare Provider Primary Taxonomy Switch_1",
            "Is Sole Proprietor", "Is Organization Subpart",
            "Parent Organization LBN", "Parent Organization TIN",
            "Authorized Official Name Prefix Text", "Authorized Official Name Suffix Text",
            "Authorized Official Credential Text",
            "Healthcare Provider Taxonomy Group_1",
        ]
        row = {h: "" for h in header}
        row["NPI"] = "1234567893"
        row["Entity Type Code"] = "1"
        row["Provider Last Name (Legal Name)"] = "TEST"
        row["Provider First Name"] = "USER"
        row["Healthcare Provider Taxonomy Code_1"] = "207Q00000X"
        row["Healthcare Provider Primary Taxonomy Switch_1"] = "Y"
        row["Provider License Number_1"] = "12345"
        row["Provider License Number State Code_1"] = "IL"

        buf = io.StringIO()
        import csv
        writer = csv.DictWriter(buf, fieldnames=header)
        writer.writeheader()
        writer.writerow(row)
        buf.seek(0)

        parser = NppesParser()
        results = list(parser.parse(buf))
        assert len(results) == 1
        p = results[0]
        assert p.primary_taxonomy_code == "207Q00000X"
        assert len(p.taxonomy_codes) == 1
