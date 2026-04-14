"""Tests for X12 270/271 eligibility transaction parser/builder.

RED tests written before implementation (TDD).
HIPAA 270 = eligibility inquiry (inbound)
HIPAA 271 = eligibility response (outbound)
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.services.x12_270_271 import (
    X12EligibilityInquiry,
    X12ParseError,
    X12Parser,
    X12ResponseBuilder,
    X12ServiceTypeCode,
)


TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBER_UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


# ---------------------------------------------------------------------------
# Minimal 270 fixture
# ---------------------------------------------------------------------------

MINIMAL_270 = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260413*1200*^*00501*000000001*0*T*:~"
    "GS*HS*SENDER*RECEIVER*20260413*1200*1*X*005010X279A1~"
    "ST*270*0001*005010X279A1~"
    "BHT*0022*13*10001234*20260413*1200~"
    "HL*1**20*1~"
    "NM1*PR*2*INFINITYRX*****PI*610014~"
    "HL*2*1*21*1~"
    "NM1*1P*1*DOE*JOHN****XX*1234567893~"
    "HL*3*2*22*0~"
    "TRN*1*ABC123*9INFINITYRX~"
    "NM1*IL*1*SMITH*JANE****MI*M123456~"
    "DMG*D8*19800101*F~"
    "DTP*291*D8*20260413~"
    "EQ*96~"
    "SE*13*0001~"
    "GE*1*1~"
    "IEA*1*000000001~"
)


# ---------------------------------------------------------------------------
# X12Parser — parse 270
# ---------------------------------------------------------------------------

class TestX12Parser270:
    def test_parse_minimal_270(self):
        parser = X12Parser()
        inquiry = parser.parse_270(MINIMAL_270)
        assert isinstance(inquiry, X12EligibilityInquiry)

    def test_parsed_member_id_extracted(self):
        parser = X12Parser()
        inquiry = parser.parse_270(MINIMAL_270)
        assert inquiry.member_id == "M123456"

    def test_parsed_date_of_service_extracted(self):
        parser = X12Parser()
        inquiry = parser.parse_270(MINIMAL_270)
        assert inquiry.date_of_service == date(2026, 4, 13)

    def test_parsed_date_of_birth_extracted(self):
        parser = X12Parser()
        inquiry = parser.parse_270(MINIMAL_270)
        assert inquiry.date_of_birth == date(1980, 1, 1)

    def test_parsed_payer_id_extracted(self):
        parser = X12Parser()
        inquiry = parser.parse_270(MINIMAL_270)
        assert inquiry.payer_id == "610014"

    def test_parsed_service_type_code_extracted(self):
        parser = X12Parser()
        inquiry = parser.parse_270(MINIMAL_270)
        assert X12ServiceTypeCode.PRESCRIPTION_DRUG in inquiry.service_type_codes

    def test_parsed_trace_number_extracted(self):
        parser = X12Parser()
        inquiry = parser.parse_270(MINIMAL_270)
        assert inquiry.trace_number == "ABC123"

    def test_invalid_transaction_type_raises(self):
        bad_270 = MINIMAL_270.replace("ST*270", "ST*837")
        parser = X12Parser()
        with pytest.raises(X12ParseError, match="transaction"):
            parser.parse_270(bad_270)

    def test_missing_hl_member_segment_raises(self):
        # Strip the member NM1 line
        stripped = MINIMAL_270.replace("NM1*IL*1*SMITH*JANE****MI*M123456~", "")
        parser = X12Parser()
        with pytest.raises(X12ParseError):
            parser.parse_270(stripped)

    def test_malformed_270_raises(self):
        parser = X12Parser()
        with pytest.raises(X12ParseError):
            parser.parse_270("NOT A 270 TRANSACTION")


# ---------------------------------------------------------------------------
# X12ResponseBuilder — build 271
# ---------------------------------------------------------------------------

class TestX12ResponseBuilder271:
    def _make_inquiry(self) -> X12EligibilityInquiry:
        return X12EligibilityInquiry(
            member_id="M123456",
            date_of_service=date(2026, 4, 13),
            date_of_birth=date(1980, 1, 1),
            first_name="JANE",
            last_name="SMITH",
            gender="F",
            payer_id="610014",
            trace_number="ABC123",
            service_type_codes=[X12ServiceTypeCode.PRESCRIPTION_DRUG],
        )

    def test_build_271_eligible_response(self):
        builder = X12ResponseBuilder()
        inquiry = self._make_inquiry()
        response_271 = builder.build_eligible_271(
            inquiry=inquiry,
            plan_name="Basic Rx Plan",
            coverage_type="pharmacy",
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
            cob_records=[],
            control_number=1,
        )
        assert isinstance(response_271, str)
        assert "271" in response_271
        assert "M123456" in response_271

    def test_build_271_ineligible_response(self):
        builder = X12ResponseBuilder()
        inquiry = self._make_inquiry()
        response_271 = builder.build_ineligible_271(
            inquiry=inquiry,
            rejection_reason="MEMBER_NOT_FOUND",
            control_number=1,
        )
        assert isinstance(response_271, str)
        assert "271" in response_271

    def test_271_contains_isa_header(self):
        builder = X12ResponseBuilder()
        inquiry = self._make_inquiry()
        response_271 = builder.build_eligible_271(
            inquiry=inquiry,
            plan_name="Basic Rx Plan",
            coverage_type="pharmacy",
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
            cob_records=[],
            control_number=1,
        )
        assert response_271.startswith("ISA*")

    def test_271_contains_transaction_set_header(self):
        builder = X12ResponseBuilder()
        inquiry = self._make_inquiry()
        response_271 = builder.build_eligible_271(
            inquiry=inquiry,
            plan_name="Plan",
            coverage_type="pharmacy",
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
            cob_records=[],
            control_number=1,
        )
        assert "ST*271" in response_271

    def test_271_ends_with_iea(self):
        builder = X12ResponseBuilder()
        inquiry = self._make_inquiry()
        response_271 = builder.build_eligible_271(
            inquiry=inquiry,
            plan_name="Plan",
            coverage_type="pharmacy",
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
            cob_records=[],
            control_number=1,
        )
        assert "IEA*" in response_271

    def test_271_trace_number_echoed(self):
        builder = X12ResponseBuilder()
        inquiry = self._make_inquiry()
        response_271 = builder.build_eligible_271(
            inquiry=inquiry,
            plan_name="Plan",
            coverage_type="pharmacy",
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
            cob_records=[],
            control_number=1,
        )
        assert "ABC123" in response_271

    def test_271_with_cob_info(self):
        from src.services.cob_service import CobSequence, PayerRecord
        builder = X12ResponseBuilder()
        inquiry = self._make_inquiry()
        cob = PayerRecord(
            sequence=CobSequence.SECONDARY,
            other_payer_name="Medicare",
            other_payer_bin="600428",
            other_payer_type="medicare",
            effective_date=date(2026, 1, 1),
        )
        response_271 = builder.build_eligible_271(
            inquiry=inquiry,
            plan_name="Plan",
            coverage_type="pharmacy",
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
            cob_records=[cob],
            control_number=1,
        )
        assert "Medicare" in response_271 or "600428" in response_271


# ---------------------------------------------------------------------------
# X12ServiceTypeCode
# ---------------------------------------------------------------------------

class TestX12ServiceTypeCode:
    def test_prescription_drug_code(self):
        assert X12ServiceTypeCode.PRESCRIPTION_DRUG.value == "96"

    def test_medical_code(self):
        assert X12ServiceTypeCode.MEDICAL.value == "30"


class TestX12270ParserEdgeCases:
    """Cover branches not hit by happy-path tests."""

    def _base_270(self) -> str:
        return """\
ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260101*1200*^*00501*000000001*0*P*:~
GS*HS*SENDER*RECEIVER*20260101*1200*1*X*005010X279A1~
ST*270*0001*005010X279A1~
BHT*0022*13*TRACE001*20260101*1200~
HL*1**20*1~
NM1*PR*2*BIG INSURER*****46*INSURER01~
HL*2*1*21*1~
NM1*1P*2*ACME PHARMACY*****SV*1234567~
HL*3*2*22*0~
TRN*1*TRACE001*SENDER01~
NM1*IL*1*DOE*JOHN****MI*MEM001~
DMG*D8*19850315*M~
DTP*291*D8*20260101~
EQ*30~
SE*16*0001~
GE*1*1~
IEA*1*000000001~
"""

    def test_hl_unknown_level_no_reset(self):
        """HL segment with level other than 20/21/22 doesn't set in_member_hl."""
        edi = self._base_270().replace("HL*1**20*1~", "HL*1**99*1~")
        from src.services.x12_270_271 import X12Parser as X12InquiryParser
        parser = X12InquiryParser()
        # HL*99 shouldn't crash; member HL*3*2*22*0 still sets in_member_hl
        inquiry = parser.parse_270(edi)
        assert inquiry.member_id == "MEM001"

    def test_dtp_non_291_qualifier_ignored(self):
        """DTP with qualifier other than 291 is ignored (no date_of_service override)."""
        # Add an extra DTP with different qualifier before the valid one
        edi = self._base_270().replace(
            "DTP*291*D8*20260101~",
            "DTP*348*D8*20260201~\nDTP*291*D8*20260101~"
        )
        from src.services.x12_270_271 import X12Parser as X12InquiryParser
        from datetime import date
        parser = X12InquiryParser()
        inquiry = parser.parse_270(edi)
        assert inquiry.date_of_service == date(2026, 1, 1)

    def test_eq_unknown_service_code_ignored(self):
        """EQ segment with unrecognized service type code is silently ignored."""
        edi = self._base_270().replace("EQ*30~", "EQ*ZZ*30~")
        from src.services.x12_270_271 import X12Parser as X12InquiryParser
        parser = X12InquiryParser()
        inquiry = parser.parse_270(edi)
        # Code "ZZ" is unknown; "30" is known — service_codes should have MEDICAL
        assert X12ServiceTypeCode.MEDICAL in inquiry.service_type_codes

    def test_dmg_no_gender_field(self):
        """DMG segment with only 3 fields (no gender) is handled gracefully."""
        edi = self._base_270().replace("DMG*D8*19850315*M~", "DMG*D8*19850315~")
        from src.services.x12_270_271 import X12Parser as X12InquiryParser
        parser = X12InquiryParser()
        inquiry = parser.parse_270(edi)
        assert inquiry.member_id == "MEM001"  # parsed without crashing
