"""Branch coverage for Session 2 code gaps."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


from src.services.scrubbing import scrub_claim
from src.x12.generators.gen_271 import generate_271
from src.x12.generators.gen_276 import generate_276
from src.x12.generators.gen_277 import generate_277
from src.x12.generators.gen_837d import generate_837d
from src.x12.generators.gen_837i import generate_837i
from src.x12.generators.schemas import (
    Generate271Request,
    Generate276Request,
    Generate277Request,
    Generate837DRequest,
    Generate837IRequest,
)
from src.x12.parsers.parse_271 import parse_271
from src.x12.parsers.parse_277 import parse_277
from src.x12.validators.validator import (
    validate_837d_basic,
    validate_837i_basic,
)

_T = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TP = uuid.UUID("00000000-0000-0000-0000-000000000002")


# -- generators: now=None branch (uses real datetime.now) --

class TestGeneratorNowDefault:
    def test_271_uses_real_now(self):
        req = Generate271Request(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=1, gs_control_number=1,
            receiver_id="RECV           ",
            payer_id="P1", payer_name="PAYER",
            subscriber_id="S1", subscriber_last_name="A", subscriber_first_name="B",
        )
        result = generate_271(req)
        assert "ST*271*" in result

    def test_276_uses_real_now(self):
        req = Generate276Request(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=1, gs_control_number=1,
            receiver_id="RECV           ",
            payer_id="P1", payer_name="PAYER",
            provider_npi="1234567893", provider_name="CLINIC",
        )
        result = generate_276(req)
        assert "ST*276*" in result

    def test_277_uses_real_now(self):
        req = Generate277Request(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=1, gs_control_number=1,
            receiver_id="RECV           ",
            payer_id="P1", payer_name="PAYER",
        )
        result = generate_277(req)
        assert "ST*277*" in result

    def test_837i_uses_real_now(self):
        req = Generate837IRequest(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=1, gs_control_number=1,
            receiver_id="RECV           ",
            billing_provider_npi="1234567893",
            billing_provider_name="HOSP",
            subscriber_id="S1", subscriber_last_name="A", subscriber_first_name="B",
            subscriber_dob="19700101", subscriber_gender="M",
            payer_id="P1", payer_name="PAYER",
            claims=[{
                "claim_id": "C1", "charge_amount": "100",
                "revenue_lines": [{"revenue_code": "0120", "charge_amount": "100"}],
            }],
        )
        result = generate_837i(req)
        assert "ST*837*" in result

    def test_837d_uses_real_now(self):
        req = Generate837DRequest(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=1, gs_control_number=1,
            receiver_id="RECV           ",
            billing_provider_npi="1234567893",
            billing_provider_name="DENT",
            subscriber_id="S1", subscriber_last_name="A", subscriber_first_name="B",
            subscriber_dob="19800101", subscriber_gender="F",
            payer_id="P1", payer_name="PAYER",
            claims=[{
                "claim_id": "D1", "charge_amount": "100",
                "service_lines": [{"procedure_code": "D0120", "charge_amount": "100"}],
            }],
        )
        result = generate_837d(req)
        assert "ST*837*" in result


# -- parse_271 branch: NM1 not in subscriber HL, DMG outside subscriber HL --

class TestParse271Branches:
    def test_nm1_pr_outside_subscriber_hl(self):
        from src.x12.generators.gen_271 import generate_271
        req = Generate271Request(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=1, gs_control_number=1,
            receiver_id="RECV           ",
            payer_id="P1", payer_name="BIG_PAYER",
            subscriber_id="S1", subscriber_last_name="X", subscriber_first_name="Y",
            benefit_info=[{"eligibility_code": "1", "coverage_level": "IND", "service_type_code": "30"}],
        )
        raw = generate_271(req, now=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        parsed = parse_271(raw)
        assert parsed.payer_name == "BIG_PAYER"

    def test_nm1_il_outside_subscriber_hl_skipped(self):
        # Manually craft a 271 where NM1*IL appears before any HL*22
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*HB*SENDER*RECEIVER*20260101*1200*1*X*005010X279A1~"
            "ST*271*0001*005010X279A1~"
            "BHT*0022*11*ELIG000000001*20260101*1200~"
            "HL*1**20*1~"
            "NM1*PR*2*PAYER*****PI*P01~"
            "NM1*IL*1*SMITH*JOHN****MI*S01~"  # IL before any HL*22
            "HL*2*1*21*1~"
            "NM1*1P*2*PROV*******XX*0000000000~"
            "HL*3*2*22*0~"
            "NM1*IL*1*DOE*JANE****MI*S02~"
            "EB*1*IND*30*HM~"
            "SE*13*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        parsed = parse_271(raw)
        # Only the NM1*IL inside HL*22 should be captured
        assert parsed.subscriber_last_name == "DOE"


# -- parse_277 branch: provider NM1 with short segments --

class TestParse277Branches:
    def test_status_without_charge_or_paid(self):
        from src.x12.generators.gen_277 import generate_277
        req = Generate277Request(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=1, gs_control_number=1,
            receiver_id="RECV           ",
            payer_id="P1", payer_name="PAYER",
            claim_statuses=[{"status_category_code": "A0"}],
        )
        raw = generate_277(req, now=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        parsed = parse_277(raw)
        assert parsed.claim_statuses[0].charge_amount == ""
        assert parsed.claim_statuses[0].paid_amount == ""


# -- validator: 837I/D guide validators --

class TestValidator837ID:
    def _minimal_837i(self):
        req = Generate837IRequest(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=1, gs_control_number=1,
            receiver_id="RECV           ",
            billing_provider_npi="1234567893",
            billing_provider_name="HOSP",
            subscriber_id="S1", subscriber_last_name="A", subscriber_first_name="B",
            subscriber_dob="19700101", subscriber_gender="M",
            payer_id="P1", payer_name="PAYER",
            claims=[{
                "claim_id": "C1", "charge_amount": "100",
                "revenue_lines": [{"revenue_code": "0120", "charge_amount": "100"}],
            }],
        )
        return generate_837i(req, now=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    def _minimal_837d(self):
        req = Generate837DRequest(
            tenant_id=_T, trading_partner_id=_TP,
            isa_control_number=1, gs_control_number=1,
            receiver_id="RECV           ",
            billing_provider_npi="1234567893",
            billing_provider_name="DENT",
            subscriber_id="S1", subscriber_last_name="A", subscriber_first_name="B",
            subscriber_dob="19800101", subscriber_gender="F",
            payer_id="P1", payer_name="PAYER",
            claims=[{
                "claim_id": "D1", "charge_amount": "100",
                "service_lines": [{"procedure_code": "D0120", "charge_amount": "100"}],
            }],
        )
        return generate_837d(req, now=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    def test_validate_837i_basic_valid_returns_empty(self):
        from src.x12.delimiters import detect_delimiters
        raw = self._minimal_837i()
        delims = detect_delimiters(raw)
        errors = validate_837i_basic(raw, delims)
        assert errors == []

    def test_validate_837d_basic_valid_returns_empty(self):
        from src.x12.delimiters import detect_delimiters
        raw = self._minimal_837d()
        delims = detect_delimiters(raw)
        errors = validate_837d_basic(raw, delims)
        assert errors == []

    def test_validate_837i_basic_missing_clm(self):
        from src.x12.delimiters import detect_delimiters
        # Build a 837-like string missing CLM
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECV           "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*HC*SENDER*RECV*20260101*1200*1*X*005010X223A3~"
            "ST*837*0001*005010X223A3~"
            "BHT*0019*00*BATCH000000001*20260101*120000*RP~"
            "HL*1**20*1~"
            "NM1*85*2*HOSP*****XX*1234567893~"
            "SE*7*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        delims = detect_delimiters(raw)
        errors = validate_837i_basic(raw, delims)
        assert any("CLM" in e for e in errors)

    def test_validate_837d_basic_missing_clm(self):
        from src.x12.delimiters import detect_delimiters
        raw = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECV           "
            "*260101*1200*^*00501*000000001*0*T*:~"
            "GS*HC*SENDER*RECV*20260101*1200*1*X*005010X224A3~"
            "ST*837*0001*005010X224A3~"
            "BHT*0019*00*DENT000000001*20260101*120000*CH~"
            "HL*1**20*1~"
            "NM1*85*2*DENT*****XX*1234567893~"
            "SE*7*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        delims = detect_delimiters(raw)
        errors = validate_837d_basic(raw, delims)
        assert any("CLM" in e for e in errors)


# -- scrubbing: uncovered branches --

class TestScrubbingBranches:
    def test_zero_rendering_npi_length_not_10(self):
        claim = {
            "member_id": "M1",
            "date_of_service": "20260101",
            "billing_npi": "1234567893",
            "rendering_npi": "12345",  # too short, fails Luhn fullmatch early
            "service_lines": [{"procedure_code": "99213", "charge_amount": "100"}],
        }
        result = scrub_claim(claim)
        assert any(e.code == "SCR-002" for e in result.edits)

    def test_empty_other_diagnoses_list_no_error(self):
        claim = {
            "member_id": "M1",
            "date_of_service": "20260101",
            "billing_npi": "1234567893",
            "other_diagnoses": [],
            "service_lines": [{"procedure_code": "99213", "charge_amount": "100"}],
        }
        result = scrub_claim(claim)
        assert result.passed

    def test_service_line_without_procedure_no_scr009(self):
        claim = {
            "member_id": "M1",
            "date_of_service": "20260101",
            "billing_npi": "1234567893",
            "service_lines": [{"charge_amount": "100"}],  # no procedure_code
        }
        result = scrub_claim(claim)
        assert not any(e.code == "SCR-009" for e in result.edits)

    def test_service_line_without_ndc_no_scr010(self):
        claim = {
            "member_id": "M1",
            "date_of_service": "20260101",
            "billing_npi": "1234567893",
            "service_lines": [{"procedure_code": "99213", "charge_amount": "100"}],
        }
        result = scrub_claim(claim)
        assert not any(e.code == "SCR-010" for e in result.edits)

    def test_service_line_without_charge_no_scr011(self):
        claim = {
            "member_id": "M1",
            "date_of_service": "20260101",
            "billing_npi": "1234567893",
            "service_lines": [{"procedure_code": "99213"}],  # no charge
        }
        result = scrub_claim(claim)
        assert not any(e.code == "SCR-011" for e in result.edits)
