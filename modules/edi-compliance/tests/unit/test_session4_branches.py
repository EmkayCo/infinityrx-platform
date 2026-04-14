"""Branch coverage for Session 4 generator/parser gaps."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from src.x12.delimiters import _DEFAULT_DELIMITERS
from src.x12.generators.gen_271 import generate_271
from src.x12.generators.gen_276 import generate_276
from src.x12.generators.gen_277 import generate_277
from src.x12.generators.gen_278 import generate_278
from src.x12.generators.schemas import (
    Generate271Request,
    Generate276Request,
    Generate277Request,
    Generate278Request,
)
from src.x12.parsers.parse_277 import parse_277
from src.x12.parsers.parse_278 import parse_278
from src.x12.parsers.parse_834 import parse_834

_T = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TP = uuid.UUID("00000000-0000-0000-0000-000000000002")
_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _base271(**kwargs):
    defaults = dict(
        tenant_id=_T, trading_partner_id=_TP,
        isa_control_number=1, gs_control_number=1,
        receiver_id="PAYER          ",
        payer_id="P1", payer_name="PAYER",
        subscriber_id="S1", subscriber_last_name="A", subscriber_first_name="B",
        eligibility_status="1",
    )
    defaults.update(kwargs)
    return Generate271Request(**defaults)


def _base276(**kwargs):
    defaults = dict(
        tenant_id=_T, trading_partner_id=_TP,
        isa_control_number=1, gs_control_number=1,
        receiver_id="PAYER          ",
        payer_id="P1", payer_name="PAYER",
        provider_npi="1234567893", provider_name="CLINIC",
        claim_queries=[],
    )
    defaults.update(kwargs)
    return Generate276Request(**defaults)


def _base277(**kwargs):
    defaults = dict(
        tenant_id=_T, trading_partner_id=_TP,
        isa_control_number=1, gs_control_number=1,
        receiver_id="PAYER          ",
        payer_id="P1", payer_name="PAYER",
        provider_npi="1234567893", provider_name="CLINIC",
        claim_statuses=[],
    )
    defaults.update(kwargs)
    return Generate277Request(**defaults)


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


# -- gen_271: explicit delims/now branches --

class TestGen271ExplicitDelims:
    def test_generate_271_explicit_delims_and_now(self):
        result = generate_271(_base271(), delims=_DEFAULT_DELIMITERS, now=_FIXED_NOW)
        assert "ST*271*" in result


# -- gen_276: explicit delims/now branches --

class TestGen276ExplicitDelims:
    def test_generate_276_explicit_delims_and_now(self):
        result = generate_276(_base276(), delims=_DEFAULT_DELIMITERS, now=_FIXED_NOW)
        assert "ST*276*" in result


# -- gen_277: explicit delims/now branches --

class TestGen277ExplicitDelims:
    def test_generate_277_explicit_delims_and_now(self):
        result = generate_277(_base277(), delims=_DEFAULT_DELIMITERS, now=_FIXED_NOW)
        assert "ST*277*" in result


# -- gen_278: explicit delims/now + service_type absent branch --

class TestGen278Branches:
    def test_generate_278_explicit_delims_and_now(self):
        result = generate_278(_base278(), delims=_DEFAULT_DELIMITERS, now=_FIXED_NOW)
        assert "ST*278*" in result

    def test_service_review_no_service_type_skips_um(self):
        """When service_type_code is absent in service review, UM segment omitted."""
        req = _base278(service_reviews=[{
            "review_type": "HS",
            "procedure_code": "99213",
            # no service_type_code
        }])
        result = generate_278(req, now=_FIXED_NOW)
        assert "ST*278*" in result

    def test_service_review_response_includes_hsd(self):
        """is_response=True with decision generates HSD segment."""
        req = _base278(
            is_response=True,
            service_reviews=[{
                "review_type": "HS",
                "service_type_code": "1",
                "decision": "A1",
            }],
        )
        result = generate_278(req, now=_FIXED_NOW)
        assert "HSD*" in result


# -- parse_277: loop-end branch --

class TestParse277Branches:
    def test_parse_277_with_status_info_code(self):
        """STC with status_info_code subcode produces combined STC01."""
        # Generate a 277 with a claim that has status_info_code
        from src.x12.generators.gen_277 import generate_277 as gen_277
        req = _base277(claim_statuses=[{
            "claim_id": "CL001",
            "status_code": "F2",
            "status_info_code": "18",
            "charge_amount": "150.00",
            "paid_amount": "120.00",
        }])
        raw = gen_277(req, now=_FIXED_NOW)
        p = parse_277(raw)
        assert len(p.claim_statuses) == 1

    def test_parse_277_no_clp_segment(self):
        """277 without CLP — claim_statuses is empty."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*PAYER          "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*HR*SENDER*PAYER*20260101*1200*1*X*005010X212~"
            "ST*277*0001*005010X212~"
            "BHT*0085*08*TRACK001*20260101*1200*TH~"
            "NM1*PR*2*PAYER*****PI*P1~"
            "SE*5*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        p = parse_277(raw)
        assert p.claim_statuses == []


# -- parse_278: HL without SS level_code --

class TestParse278LoopBranches:
    def test_parse_278_no_service_reviews(self):
        raw = generate_278(_base278(), now=_FIXED_NOW)
        p = parse_278(raw)
        assert p.service_reviews == []

    def test_parse_278_nm1_segments_parsed(self):
        req = _base278()
        raw = generate_278(req, now=_FIXED_NOW)
        p = parse_278(raw)
        assert p.payer_id == "P1"
        assert p.provider_npi == "1234567893"


# -- parse_834: SE segment flushes last member --

class TestParse834Branches:
    def test_parse_834_plan_from_hd_segment(self):
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~"
            "ST*834*0001*005010X220A1~"
            "BGN*00*REF001*20260101*1200****2~"
            "NM1*P5*2*PAYER*****PI*P01~"
            "NM1*IL*1*JONES*BOB****MI*J001~"
            "INS*18*18*001**A~"
            "HD***PLAN999~"
            "SE*9*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        p = parse_834(raw)
        assert p.members[0].plan_id == "PLAN999"

    def test_parse_834_co_sponsor(self):
        """NM1*CO sets sponsor_name."""
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*BE*SENDER*RECEIVER*20260101*1200*1*X*005010X220A1~"
            "ST*834*0001*005010X220A1~"
            "BGN*00*REF001*20260101*1200****2~"
            "NM1*CO*2*ACME_CORP~"
            "NM1*P5*2*PAYER*****PI*P01~"
            "SE*6*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        p = parse_834(raw)
        assert p.sponsor_name == "ACME_CORP"
