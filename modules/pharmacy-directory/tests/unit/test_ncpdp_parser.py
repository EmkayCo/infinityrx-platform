"""RED tests: NCPDP provider file parser."""
from __future__ import annotations

import io


from src.services.ncpdp_parser import NcpdpRecord, parse_ncpdp_fixture


SAMPLE_NCPDP_CSV = """\
npi,nabp_number,ncpdp_id,legal_name,dba_name,pharmacy_type,chain_name,chain_code,store_number,address_line_1,address_line_2,city,state,zip_code,phone,fax,hours_monday,hours_tuesday,hours_wednesday,hours_thursday,hours_friday,hours_saturday,hours_sunday,is_24_hour,accepts_electronic_rx,dispenses_controlled,offers_delivery,offers_compounding,offers_specialty,offers_340b,status
1234567890,1234567,1234567890,CVS Pharmacy #1234,CVS,chain,CVS,CVS,1234,100 Main St,,Springfield,IL,62701,2175551234,2175551235,09:00-21:00,09:00-21:00,09:00-21:00,09:00-21:00,09:00-21:00,10:00-18:00,,False,True,True,False,False,False,False,active
"""


class TestNcpdpParser:
    def test_parse_single_record(self) -> None:
        records = parse_ncpdp_fixture(io.StringIO(SAMPLE_NCPDP_CSV))
        assert len(records) == 1

    def test_parsed_record_has_npi(self) -> None:
        records = parse_ncpdp_fixture(io.StringIO(SAMPLE_NCPDP_CSV))
        assert records[0].npi == "1234567890"

    def test_parsed_record_has_nabp(self) -> None:
        records = parse_ncpdp_fixture(io.StringIO(SAMPLE_NCPDP_CSV))
        assert records[0].nabp_number == "1234567"

    def test_parsed_record_has_legal_name(self) -> None:
        records = parse_ncpdp_fixture(io.StringIO(SAMPLE_NCPDP_CSV))
        assert records[0].legal_name == "CVS Pharmacy #1234"

    def test_parsed_record_is_ncpdp_record(self) -> None:
        records = parse_ncpdp_fixture(io.StringIO(SAMPLE_NCPDP_CSV))
        assert isinstance(records[0], NcpdpRecord)

    def test_empty_file_returns_empty_list(self) -> None:
        header = SAMPLE_NCPDP_CSV.split("\n")[0] + "\n"
        records = parse_ncpdp_fixture(io.StringIO(header))
        assert records == []
