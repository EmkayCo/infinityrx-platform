"""Tests for 834 Benefit Enrollment parser."""

from __future__ import annotations

import pytest

from src.x12.parsers.parse_834 import parse_834


def _make_834_raw(members=None) -> str:
    """Build a minimal 834 EDI string."""
    lines = [
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*260101*1200*^*00501*000000001*0*T*:~",
        "GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~",
        "ST*834*0001*005010X220A1~",
        "BGN*00*REF001*20260101*1200****2~",
        "NM1*CO*2*ACME CORP*****EI*123456789~",
        "NM1*P5*2*AETNA*****PI*PAYER01~",
    ]
    if members:
        for m in members:
            lines += [
                f"NM1*IL*1*{m.get('last','DOE')}*{m.get('first','JANE')}***"
                f"*MI*{m.get('id','S001')}~",
                f"INS*{m.get('rel','18')}*18*{m.get('maint','001')}*"
                f"{m.get('reason','')}*{m.get('benefit','A')}****"
                f"{m.get('employment','')}*{m.get('student','')}~",
                f"DMG*D8*{m.get('dob','19800101')}*{m.get('gender','F')}~",
                f"HD***{m.get('plan_id','')}"+"~" if m.get('plan_id') else "HD***~",
            ]
    lines += [
        "SE*10*0001~",
        "GE*1*1~",
        "IEA*1*000000001~",
    ]
    return "".join(lines)


class TestParse834:
    def test_no_members_returns_empty_list(self):
        raw = _make_834_raw()
        p = parse_834(raw)
        assert p.members == []

    def test_roundtrip_payer(self):
        raw = _make_834_raw()
        p = parse_834(raw)
        assert p.payer_name == "AETNA"
        assert p.payer_id == "PAYER01"

    def test_roundtrip_sponsor(self):
        raw = _make_834_raw()
        p = parse_834(raw)
        assert p.sponsor_name == "ACME CORP"

    def test_roundtrip_reference_number(self):
        raw = _make_834_raw()
        p = parse_834(raw)
        assert p.reference_number == "REF001"

    def test_single_member_parsed(self):
        raw = _make_834_raw(members=[{"last": "SMITH", "first": "JOHN", "id": "MBR001"}])
        p = parse_834(raw)
        assert len(p.members) == 1
        m = p.members[0]
        assert m.subscriber_last_name == "SMITH"
        assert m.subscriber_first_name == "JOHN"
        assert m.subscriber_id == "MBR001"

    def test_member_dob_and_gender(self):
        raw = _make_834_raw(members=[{"dob": "19901215", "gender": "M"}])
        p = parse_834(raw)
        assert p.members[0].subscriber_dob == "19901215"
        assert p.members[0].subscriber_gender == "M"

    def test_member_maintenance_type(self):
        raw = _make_834_raw(members=[{"maint": "024"}])
        p = parse_834(raw)
        assert p.members[0].maintenance_type == "024"

    def test_member_benefit_status(self):
        raw = _make_834_raw(members=[{"benefit": "T"}])
        p = parse_834(raw)
        assert p.members[0].benefit_status == "T"

    def test_member_relationship_code(self):
        raw = _make_834_raw(members=[{"rel": "01"}])
        p = parse_834(raw)
        assert p.members[0].relationship_code == "01"

    def test_member_plan_id(self):
        raw = _make_834_raw(members=[{"plan_id": "PLAN123"}])
        p = parse_834(raw)
        assert p.members[0].plan_id == "PLAN123"

    def test_multiple_members(self):
        raw = _make_834_raw(members=[
            {"last": "SMITH", "first": "ALICE", "id": "S001"},
            {"last": "JONES", "first": "BOB", "id": "J002"},
        ])
        p = parse_834(raw)
        assert len(p.members) == 2
        assert p.members[0].subscriber_id == "S001"
        assert p.members[1].subscriber_id == "J002"

    def test_no_isa_raises(self):
        with pytest.raises(ValueError):
            parse_834("NOT*VALID~")

    def test_sender_receiver(self):
        raw = _make_834_raw()
        p = parse_834(raw)
        assert p.sender_id.strip() == "SENDER"
        assert p.receiver_id.strip() == "RECEIVER"
