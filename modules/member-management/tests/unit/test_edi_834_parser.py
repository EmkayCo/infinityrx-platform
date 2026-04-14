"""RED tests for X12 834 enrollment transaction parser."""
from __future__ import annotations

import pytest

from src.services.edi_834_parser import (
    Edi834Parser,
    EnrollmentAction,
)


MINIMAL_834 = """\
ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260101*1200*^*00501*000000001*0*P*:~
GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~
ST*834*0001*005010X220A1~
BGN*00*REF001*20260101*1200****2~
N1*P5*ACME CORP*FI*123456789~
N1*IN*BIG INSURER*XV*12345~
L1000A~
N1*P5*ACME CORP*FI*123456789~
L1000B~
N1*IN*BIG INSURER*XV*12345~
L2000*1*1*ADD~
INS*Y*18*030*XN*A*E**FT~
REF*0F*MEM001~
REF*1L*GRP001~
DTP*356*D8*20260101~
NM1*IL*1*DOE*JOHN*M**MR*34*123456789~
PER*IP**TE*5555551234*EM*john.doe@example.com~
N3*123 MAIN ST*APT 4~
N4*ANYTOWN*NY*10001*US~
DMG*D8*19850315*M~
HD*030**HLT*PLAN001~
DTP*348*D8*20260101~
SE*21*0001~
GE*1*1~
IEA*1*000000001~
"""


class TestEdi834Parser:
    def test_parse_returns_enrollment_records(self):
        parser = Edi834Parser()
        records = parser.parse(MINIMAL_834)
        assert len(records) >= 1

    def test_parsed_record_has_member_id(self):
        parser = Edi834Parser()
        records = parser.parse(MINIMAL_834)
        assert records[0].member_id == "MEM001"

    def test_parsed_record_has_group_number(self):
        parser = Edi834Parser()
        records = parser.parse(MINIMAL_834)
        assert records[0].group_number == "GRP001"

    def test_parsed_record_has_action_add(self):
        parser = Edi834Parser()
        records = parser.parse(MINIMAL_834)
        assert records[0].action == EnrollmentAction.ADD

    def test_parsed_record_demographics(self):
        parser = Edi834Parser()
        records = parser.parse(MINIMAL_834)
        r = records[0]
        assert r.first_name == "JOHN"
        assert r.last_name == "DOE"
        assert r.date_of_birth.isoformat() == "1985-03-15"
        assert r.gender == "M"

    def test_parsed_record_effective_date(self):
        parser = Edi834Parser()
        records = parser.parse(MINIMAL_834)
        from datetime import date
        assert records[0].effective_date == date(2026, 1, 1)

    def test_parsed_record_address(self):
        parser = Edi834Parser()
        records = parser.parse(MINIMAL_834)
        r = records[0]
        assert r.address_line_1 == "123 MAIN ST"
        assert r.address_line_2 == "APT 4"
        assert r.city == "ANYTOWN"
        assert r.state == "NY"
        assert r.zip_code == "10001"

    def test_terminate_action_parsed(self):
        edi = MINIMAL_834.replace("L2000*1*1*ADD~", "L2000*1*1*TRM~")
        edi = edi.replace("INS*Y*18*030*XN*A*E**FT~", "INS*Y*18*024*XN*A*E**FT~")
        parser = Edi834Parser()
        records = parser.parse(edi)
        assert records[0].action == EnrollmentAction.TERMINATE

    def test_change_action_parsed(self):
        edi = MINIMAL_834.replace("L2000*1*1*ADD~", "L2000*1*1*CHG~")
        edi = edi.replace("INS*Y*18*030*XN*A*E**FT~", "INS*Y*18*001*XN*A*E**FT~")
        parser = Edi834Parser()
        records = parser.parse(edi)
        assert records[0].action == EnrollmentAction.CHANGE

    def test_malformed_edi_raises_parse_error(self):
        from src.services.edi_834_parser import Edi834ParseError
        parser = Edi834Parser()
        with pytest.raises(Edi834ParseError):
            parser.parse("NOT~VALID~EDI~DATA")

    def test_pluggable_loop_handler_can_be_registered(self):
        """The parser uses pluggable loop handlers — custom segment handler registers."""
        from src.services.edi_834_parser import BaseLoopHandler
        called = []

        class MyHandler(BaseLoopHandler):
            loop_id = "2000"
            def handle(self, segments):
                called.append(segments)

        parser = Edi834Parser()
        parser.register_handler(MyHandler())
        parser.parse(MINIMAL_834)
        assert len(called) >= 1

    def test_empty_document_raises(self):
        """An empty EDI document raises Edi834ParseError."""
        from src.services.edi_834_parser import Edi834ParseError
        parser = Edi834Parser()
        with pytest.raises(Edi834ParseError):
            parser.parse("   \n  ")

    def test_se_before_any_l2000_does_not_crash(self):
        """SE segment before any L2000 loop (in_2000_loop=False) is handled cleanly."""
        # Build a 834 with an ST/SE transaction that has no L2000, then a second one with a member
        edi = """\
ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260101*1200*^*00501*000000001*0*P*:~
GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~
ST*834*0001*005010X220A1~
BGN*00*REF001*20260101*1200****2~
SE*3*0001~
ST*834*0002*005010X220A1~
L2000*1*1*ADD~
INS*Y*18*030~
REF*0F*LATEMBER~
DTP*356*D8*20260101~
SE*5*0002~
GE*1*1~
IEA*1*000000001~
"""
        parser = Edi834Parser()
        records = parser.parse(edi)
        assert any(r.member_id == "LATEMBER" for r in records)

    def test_ref_unknown_qualifier_ignored(self):
        """REF with unknown qualifier is silently ignored."""
        edi = MINIMAL_834.replace("REF*1L*GRP001~", "REF*ZZ*UNKNOWN~\nREF*1L*GRP001~")
        parser = Edi834Parser()
        records = parser.parse(edi)
        assert records[0].group_number == "GRP001"

    def test_hd_short_segment_no_plan_id(self):
        """HD with < 5 elements does not set plan_id (stays as default empty string)."""
        edi = MINIMAL_834.replace("HD*030**HLT*PLAN001~", "HD*030**HLT~")
        parser = Edi834Parser()
        records = parser.parse(edi)
        assert records[0].plan_id == ""

    def test_per_odd_length_no_crash(self):
        """PER segment with odd number of comm pairs doesn't crash."""
        edi = MINIMAL_834.replace(
            "PER*IP**TE*5555551234*EM*john.doe@example.com~",
            "PER*IP**TE*5555551234*EM~"
        )
        parser = Edi834Parser()
        records = parser.parse(edi)
        assert records[0].member_id == "MEM001"

    def test_short_segments_are_skipped_gracefully(self):
        """Segments with too few elements don't crash the parser."""
        # L2000 with < 4 elements (no action qualifier)
        # INS with < 3 elements (no relationship)
        # DTP with < 4 elements
        # REF with < 3 elements
        # DMG with format != D8 and short array
        # HD with < 5 elements
        edi = """\
ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260101*1200*^*00501*000000001*0*P*:~
GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~
ST*834*0001*005010X220A1~
BGN*00*REF001*20260101*1200****2~
L2000*1~
INS*Y~
REF*0F~
DTP*356*D8~
DMG*RD8*~
HD*030**HLT~
REF*0F*MEM999~
SE*12*0001~
GE*1*1~
IEA*1*000000001~
"""
        parser = Edi834Parser()
        # Should not raise — short segments are just skipped
        records = parser.parse(edi)
        # MEM999 was set via a valid REF segment
        assert any(r.member_id == "MEM999" for r in records)

    def test_dmg_non_d8_format_no_dob(self):
        """DMG with format other than D8 does not set date_of_birth."""
        edi = MINIMAL_834.replace("DMG*D8*19850315*M~", "DMG*RD8*20260101-20260131*M~")
        parser = Edi834Parser()
        records = parser.parse(edi)
        assert records[0].date_of_birth is None

    def test_ins_unknown_maint_code_no_action(self):
        """INS with unrecognized maintenance code leaves action unchanged."""
        edi = MINIMAL_834.replace("INS*Y*18*030*XN*A*E**FT~", "INS*Y*18*ZZZ*XN*A*E**FT~")
        parser = Edi834Parser()
        records = parser.parse(edi)
        # L2000 ADD still sets the action
        assert records[0].action == EnrollmentAction.ADD

    def test_multiple_members_in_one_file(self):
        second_member = """\
L2000*2*1*ADD~
INS*Y*18*030*XN*A*E**FT~
REF*0F*MEM002~
REF*1L*GRP001~
DTP*356*D8*20260101~
NM1*IL*1*SMITH*JANE***MS*34*987654321~
PER*IP**TE*5555559876~
N3*456 OAK AVE~
N4*SOMETOWN*CA*90001*US~
DMG*D8*19900620*F~
HD*030**HLT*PLAN001~
DTP*348*D8*20260101~
"""
        edi = MINIMAL_834.replace(
            "SE*21*0001~",
            second_member + "SE*35*0001~",
        )
        parser = Edi834Parser()
        records = parser.parse(edi)
        assert len(records) == 2
        assert records[1].member_id == "MEM002"
        assert records[1].last_name == "SMITH"
