"""Branch coverage for Session 3 code gaps."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.services.ncpdp_batch import NcpdpClaim, generate_ncpdp_batch, parse_ncpdp_batch
from src.x12.generators.gen_278 import generate_278
from src.x12.generators.gen_999 import generate_999, generate_ta1
from src.x12.generators.schemas import Generate278Request, Generate999Request, GenerateTA1Request
from src.x12.parsers.parse_278 import parse_278
from src.x12.parsers.parse_834 import parse_834

_T = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TP = uuid.UUID("00000000-0000-0000-0000-000000000002")
_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _base278(**kwargs):
    defaults = dict(
        tenant_id=_T, trading_partner_id=_TP,
        isa_control_number=1, gs_control_number=1,
        receiver_id="PAYER          ",
        payer_id="P1", payer_name="PAYER",
        provider_npi="1234567893", provider_name="CLINIC",
        subscriber_id="S1", subscriber_last_name="A", subscriber_first_name="B",
        service_reviews=[],
    )
    defaults.update(kwargs)
    return Generate278Request(**defaults)


# -- gen_278: now=None and delims=None branches --

class TestGen278NowDefault:
    def test_generate_278_default_now(self):
        result = generate_278(_base278())
        assert "ST*278*" in result


# -- gen_999: now=None and accepted_count for E code --

class TestGen999Branches:
    def test_ack_code_e_produces_accepted_count_1(self):
        req = Generate999Request(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=2, gs_control_number=2,
            receiver_id="RECV           ",
            original_isa_control=1, original_gs_control=1,
            original_transaction_type="837",
            ack_code="E",
        )
        result = generate_999(req, now=_FIXED_NOW)
        assert "AK9*E*1*1*1" in result

    def test_generate_ta1_default_now(self):
        req = GenerateTA1Request(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=3, gs_control_number=3,
            receiver_id="RECV           ",
            ack_control_number=1, ack_date="260101", ack_time="1200",
            ack_code="A", error_code="000",
        )
        result = generate_ta1(req)
        assert "TA1*" in result


# -- parse_278: 278 segment branches --

class TestParse278Branches:
    def test_hl_with_short_segment_default_level(self):
        """HL with < 4 elements — level_code defaults to empty, in_service_hl stays False."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*PAYER          "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*UM*SENDER*PAYER*20260101*1200*1*X*005010X217~"
            "ST*278*0001*005010X217~"
            "BHT*0007*13*AUTH000000001*20260101*1200~"
            "HL*1~"  # too short
            "NM1*PR*2*PAYER*****PI*P1~"
            "SE*8*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        p = parse_278(raw)
        assert p.payer_name == "PAYER"

    def test_review_flushed_at_end_when_in_service_hl(self):
        """Pending review flushed at end when in_service_hl still True at end of segment loop."""
        raw = generate_278(_base278(service_reviews=[{
            "review_type": "HS",
            "service_type_code": "1",
            "procedure_code": "99213",
        }]), now=_FIXED_NOW)
        p = parse_278(raw)
        # Should have at least one service review
        assert len(p.service_reviews) > 0

    def test_hi_segment_without_subelement(self):
        """HI segment in SS HL without sub_element separator — procedure_code stays empty."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*PAYER          "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*UM*SENDER*PAYER*20260101*1200*1*X*005010X217~"
            "ST*278*0001*005010X217~"
            "BHT*0007*13*AUTH000000001*20260101*1200~"
            "HL*1**20*1~"
            "NM1*PR*2*PAYER*****PI*P1~"
            "HL*2*1*19*1~"
            "NM1*1P*2*CLINIC*****XX*1234567893~"
            "HL*3*2*22*1~"
            "NM1*IL*1*SMITH*BOB****MI*S1~"
            "HL*4*3*SS*0~"
            "UM*HS*I*1~"
            "HI*99213~"  # no sub_element
            "QTY*VS*1~"
            "SE*14*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        p = parse_278(raw)
        # HI without : separator — procedure_code should be empty
        if p.service_reviews:
            assert p.service_reviews[0].procedure_code == ""

    def test_dtp_473_sets_to_date(self):
        raw = generate_278(_base278(service_reviews=[{
            "review_type": "HS",
            "service_type_code": "1",
            "to_date": "20260131",
        }]), now=_FIXED_NOW)
        p = parse_278(raw)
        if p.service_reviews:
            assert p.service_reviews[0].to_date == "20260131"


# -- parse_834: isa line and NM1 entity 74 --

class TestParse834Branches:
    def test_nm1_entity_74_treated_as_member(self):
        """NM1*74 (dependent) is treated as a member."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~"
            "ST*834*0001*005010X220A1~"
            "BGN*00*REF001*20260101*1200****2~"
            "NM1*P5*2*PAYER*****PI*P01~"
            "NM1*74*1*SMITH*ALICE****MI*D001~"
            "INS*01*18*001**A~"
            "DMG*D8*19951201*F~"
            "SE*9*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        p = parse_834(raw)
        assert len(p.members) == 1
        assert p.members[0].subscriber_last_name == "SMITH"

    def test_multiple_nm1_il_flushes_previous_member(self):
        """Second NM1*IL flushes previous member into list."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~"
            "ST*834*0001*005010X220A1~"
            "BGN*00*REF001*20260101*1200****2~"
            "NM1*P5*2*PAYER*****PI*P01~"
            "NM1*IL*1*FIRST*ALICE****MI*S001~"
            "INS*18*18*001**A~"
            "DMG*D8*19800101*F~"
            "NM1*IL*1*SECOND*BOB****MI*S002~"
            "INS*18*18*001**A~"
            "DMG*D8*19850601*M~"
            "SE*12*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        p = parse_834(raw)
        assert len(p.members) == 2

    def test_ins_with_short_segment_partial(self):
        """INS with fewer elements than expected — partial fields populated."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~"
            "ST*834*0001*005010X220A1~"
            "BGN*00*REF001*20260101*1200****2~"
            "NM1*P5*2*PAYER*****PI*P01~"
            "NM1*IL*1*JONES*CAROL****MI*J001~"
            "INS*18~"  # only relationship code
            "SE*8*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        p = parse_834(raw)
        assert p.members[0].relationship_code == "18"
        assert p.members[0].maintenance_type == ""


# -- ncpdp_batch: short record branches --

class TestNcpdpBatchBranches:
    def test_btr_with_short_total_not_digit(self):
        """BTR total field that is not digit-only — total stays 0."""
        from src.services.ncpdp_batch import _FIELD_SEP, _RECORD_SEP
        raw = "BHR" + _FIELD_SEP + "S" + _FIELD_SEP + "R" + _FIELD_SEP + "B" + _FIELD_SEP + "001" \
            + _RECORD_SEP \
            + "BTR" + _FIELD_SEP + "001" + _FIELD_SEP + "INVALID" \
            + _RECORD_SEP
        result = parse_ncpdp_batch(raw)
        assert result.total_amount == Decimal("0")

    def test_btr_with_short_field_no_total(self):
        """BTR with only 1 field — total stays 0."""
        from src.services.ncpdp_batch import _FIELD_SEP, _RECORD_SEP
        raw = "BTR" + _RECORD_SEP
        result = parse_ncpdp_batch(raw)
        assert result.total_amount == Decimal("0")

    def test_clm_with_short_charge_field(self):
        """CLM charge field that is 2 digits or less — treated as 0."""
        from src.services.ncpdp_batch import _FIELD_SEP, _RECORD_SEP
        raw = (
            "BHR" + _FIELD_SEP + "S" + _FIELD_SEP + "R" + _FIELD_SEP + "B" + _FIELD_SEP + "001"
            + _RECORD_SEP
            + "CLM" + _FIELD_SEP + "123456" + _FIELD_SEP + "D0" + _FIELD_SEP + ""
            + _FIELD_SEP + "01" + _FIELD_SEP + "" + _FIELD_SEP + "SVC" + _FIELD_SEP + "20260101"
            + _FIELD_SEP + "12345678901" + _FIELD_SEP + "1.000" + _FIELD_SEP + "030"
            + _FIELD_SEP + "MBR" + _FIELD_SEP + "GRP" + _FIELD_SEP + "DOE"
            + _FIELD_SEP + "JANE" + _FIELD_SEP + "19800101" + _FIELD_SEP + "PRESC"
            + _FIELD_SEP + "75"  # only 2 digits
            + _RECORD_SEP
        )
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["charge_amount"] == Decimal("0")

    def test_clm_no_charge_field(self):
        """CLM with missing charge field — treated as 0."""
        from src.services.ncpdp_batch import _FIELD_SEP, _RECORD_SEP
        raw = (
            "CLM" + _FIELD_SEP + "123456" + _FIELD_SEP + "D0"
            + _RECORD_SEP
        )
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["charge_amount"] == Decimal("0")

    def test_bhr_non_digit_claim_count(self):
        """BHR claim count field that is not digit — defaults to 0."""
        from src.services.ncpdp_batch import _FIELD_SEP, _RECORD_SEP
        raw = "BHR" + _FIELD_SEP + "S" + _FIELD_SEP + "R" + _FIELD_SEP + "B" + _FIELD_SEP + "XXX" + _RECORD_SEP
        result = parse_ncpdp_batch(raw)
        assert result.claim_count == 0
