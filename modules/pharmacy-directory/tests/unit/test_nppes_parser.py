"""RED tests: NPPES V2 pharmacy-filter parser."""
from __future__ import annotations

import io


from src.services.nppes_parser import parse_nppes_fixture


SAMPLE_NPPES_CSV = """\
NPI,Entity Type Code,Provider Organization Name (Legal Business Name),Provider Last Name (Legal Name),Provider First Name,Provider Business Mailing Address First Line,Provider Business Mailing Address Second Line,Provider Business Mailing Address City Name,Provider Business Mailing Address State Name,Provider Business Mailing Address Postal Code,Provider Business Practice Location Address First Line,Provider Business Practice Location Address City Name,Provider Business Practice Location Address State Name,Provider Business Practice Location Address Postal Code,Provider Business Practice Location Address Telephone Number,Healthcare Provider Taxonomy Code_1,NPI Deactivation Date
1234567890,2,Walgreens Pharmacy,,,1 Pharmacy Way,,Chicago,IL,60601,1 Pharmacy Way,Chicago,IL,60601,3125551234,333600000X,
9876543210,2,Inactive Pharmacy,,,2 Inactive Way,,Chicago,IL,60601,2 Inactive Way,Chicago,IL,60601,3125550000,333600000X,01/15/2025
"""


class TestNppesParser:
    def test_active_pharmacy_parsed(self) -> None:
        records = parse_nppes_fixture(io.StringIO(SAMPLE_NPPES_CSV))
        npis = [r.npi for r in records]
        assert "1234567890" in npis

    def test_deactivated_pharmacy_marked_inactive(self) -> None:
        records = parse_nppes_fixture(io.StringIO(SAMPLE_NPPES_CSV))
        inactive = next(r for r in records if r.npi == "9876543210")
        assert inactive.is_active is False

    def test_non_pharmacy_taxonomy_excluded(self) -> None:
        non_pharm_csv = (
            "NPI,Entity Type Code,Provider Organization Name (Legal Business Name),"
            "Provider Last Name (Legal Name),Provider First Name,"
            "Provider Business Mailing Address First Line,"
            "Provider Business Mailing Address Second Line,"
            "Provider Business Mailing Address City Name,"
            "Provider Business Mailing Address State Name,"
            "Provider Business Mailing Address Postal Code,"
            "Provider Business Practice Location Address First Line,"
            "Provider Business Practice Location Address City Name,"
            "Provider Business Practice Location Address State Name,"
            "Provider Business Practice Location Address Postal Code,"
            "Provider Business Practice Location Address Telephone Number,"
            "Healthcare Provider Taxonomy Code_1,NPI Deactivation Date\n"
            "1111111111,1,,Smith,John,100 Dr Way,,Boston,MA,02101,"
            "100 Dr Way,Boston,MA,02101,6175550000,207Q00000X,\n"
        )
        records = parse_nppes_fixture(io.StringIO(non_pharm_csv))
        assert records == []

    def test_record_has_taxonomy_type(self) -> None:
        records = parse_nppes_fixture(io.StringIO(SAMPLE_NPPES_CSV))
        active = next(r for r in records if r.npi == "1234567890")
        assert active.taxonomy_code == "333600000X"
