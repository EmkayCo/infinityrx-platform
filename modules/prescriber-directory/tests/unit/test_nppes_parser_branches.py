"""Tests for NPPES parser branch coverage — name-building edge cases, taxonomy loop."""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from src.services.nppes_parser import NppesParser, _build_display_name, _extract_taxonomy_codes


class TestBuildDisplayNameBranches:
    def test_no_prefix_no_middle_no_suffix_no_credential(self):
        row = {
            "Provider Name Prefix Text": "",
            "Provider First Name": "ALICE",
            "Provider Middle Name": "",
            "Provider Last Name (Legal Name)": "CHEN",
            "Provider Name Suffix Text": "",
            "Provider Credential Text": "",
        }
        name = _build_display_name(row, "1")
        assert name == "ALICE CHEN"

    def test_no_first_name(self):
        row = {
            "Provider Name Prefix Text": "DR.",
            "Provider First Name": "",
            "Provider Middle Name": "",
            "Provider Last Name (Legal Name)": "JOHNSON",
            "Provider Name Suffix Text": "",
            "Provider Credential Text": "MD",
        }
        name = _build_display_name(row, "1")
        assert "JOHNSON" in name
        assert "DR." in name

    def test_all_empty_individual(self):
        row = {
            "Provider Name Prefix Text": "",
            "Provider First Name": "",
            "Provider Middle Name": "",
            "Provider Last Name (Legal Name)": "",
            "Provider Name Suffix Text": "",
            "Provider Credential Text": "",
        }
        name = _build_display_name(row, "1")
        assert name == ""

    def test_taxonomy_loop_with_non_primary_slot(self):
        row = {
            "Healthcare Provider Taxonomy Code_1": "207Q00000X",
            "Healthcare Provider Primary Taxonomy Switch_1": "N",  # NOT primary
            "Provider License Number_1": "12345",
            "Provider License Number State Code_1": "IL",
        }
        primary, codes = _extract_taxonomy_codes(row)
        assert primary is None  # No primary found
        assert len(codes) == 1
        assert codes[0]["is_primary"] is False

    def test_taxonomy_loop_breaks_on_missing_slot(self):
        row = {
            "Healthcare Provider Taxonomy Code_1": "207Q00000X",
            "Healthcare Provider Primary Taxonomy Switch_1": "Y",
            "Provider License Number_1": "",
            "Provider License Number State Code_1": "",
            # _2 is missing entirely — loop should break
        }
        primary, codes = _extract_taxonomy_codes(row)
        assert primary == "207Q00000X"
        assert len(codes) == 1


class TestNppesParserSuffix:
    def test_parse_suffix_field(self):
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
        row["Provider Last Name (Legal Name)"] = "GARCIA"
        row["Provider First Name"] = "MARIA"
        row["Provider Name Suffix Text"] = "III"
        row["Provider Credential Text"] = "DO"

        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=header)
        writer.writeheader()
        writer.writerow(row)
        buf.seek(0)

        parser = NppesParser()
        results = list(parser.parse(buf))
        assert len(results) == 1
        p = results[0]
        assert "III" in p.display_name
        assert "DO" in p.display_name
