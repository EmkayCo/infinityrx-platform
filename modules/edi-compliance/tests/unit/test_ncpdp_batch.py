"""Tests for NCPDP Batch 1.2 generator and parser."""

from __future__ import annotations

from decimal import Decimal


from src.services.ncpdp_batch import (
    NcpdpClaim,
    generate_ncpdp_batch,
    parse_ncpdp_batch,
)


def _minimal_claim(**kwargs) -> NcpdpClaim:
    defaults = dict(
        bin_number="123456",
        service_provider_id="PROV001",
        ndc="12345678901",
        date_of_service="20260101",
        member_id="MBR001",
        charge_amount=Decimal("25.00"),
    )
    defaults.update(kwargs)
    return NcpdpClaim(**defaults)


class TestGenerateNcpdpBatch:
    def test_produces_output(self):
        raw = generate_ncpdp_batch("SENDER", "RECEIVER", "BCH001", [_minimal_claim()])
        assert len(raw) > 0

    def test_contains_bhr(self):
        raw = generate_ncpdp_batch("SENDER", "RECEIVER", "BCH001", [_minimal_claim()])
        assert "BHR" in raw

    def test_contains_clm(self):
        raw = generate_ncpdp_batch("SENDER", "RECEIVER", "BCH001", [_minimal_claim()])
        assert "CLM" in raw

    def test_contains_btr(self):
        raw = generate_ncpdp_batch("SENDER", "RECEIVER", "BCH001", [_minimal_claim()])
        assert "BTR" in raw

    def test_empty_claims_list(self):
        raw = generate_ncpdp_batch("SENDER", "RECEIVER", "BCH002", [])
        assert "BHR" in raw
        assert "BTR" in raw

    def test_multiple_claims(self):
        claims = [_minimal_claim(charge_amount=Decimal("10.00")),
                  _minimal_claim(charge_amount=Decimal("20.00"))]
        raw = generate_ncpdp_batch("S", "R", "B001", claims)
        assert raw.count("CLM") == 2

    def test_bhr_contains_sender_id(self):
        raw = generate_ncpdp_batch("MY_SENDER_ID", "RECEIVER", "BCH001", [])
        assert "MY_SENDER_ID" in raw

    def test_bhr_contains_batch_control_number(self):
        raw = generate_ncpdp_batch("SENDER", "RECEIVER", "MYBATCH123", [])
        assert "MYBATCH123" in raw

    def test_clm_contains_ndc(self):
        raw = generate_ncpdp_batch("S", "R", "B", [_minimal_claim(ndc="99999999901")])
        assert "99999999901" in raw

    def test_clm_contains_bin_number(self):
        raw = generate_ncpdp_batch("S", "R", "B", [_minimal_claim(bin_number="654321")])
        assert "654321" in raw


class TestParseNcpdpBatch:
    def test_roundtrip_sender_id(self):
        raw = generate_ncpdp_batch("SENDER_1", "RECV_1", "BCH001", [])
        result = parse_ncpdp_batch(raw)
        assert result.sender_id == "SENDER_1"

    def test_roundtrip_receiver_id(self):
        raw = generate_ncpdp_batch("SENDER", "RECV_2", "BCH001", [])
        result = parse_ncpdp_batch(raw)
        assert result.receiver_id == "RECV_2"

    def test_roundtrip_batch_control_number(self):
        raw = generate_ncpdp_batch("S", "R", "MYCTRL", [])
        result = parse_ncpdp_batch(raw)
        assert result.batch_control_number == "MYCTRL"

    def test_roundtrip_claim_count(self):
        claims = [_minimal_claim(), _minimal_claim()]
        raw = generate_ncpdp_batch("S", "R", "B", claims)
        result = parse_ncpdp_batch(raw)
        assert result.claim_count == 2

    def test_roundtrip_total_amount(self):
        claims = [_minimal_claim(charge_amount=Decimal("10.00")),
                  _minimal_claim(charge_amount=Decimal("15.50"))]
        raw = generate_ncpdp_batch("S", "R", "B", claims)
        result = parse_ncpdp_batch(raw)
        assert result.total_amount == Decimal("25.50")

    def test_roundtrip_claim_ndc(self):
        raw = generate_ncpdp_batch("S", "R", "B", [_minimal_claim(ndc="11111111111")])
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["ndc"] == "11111111111"

    def test_roundtrip_claim_member_id(self):
        raw = generate_ncpdp_batch("S", "R", "B", [_minimal_claim(member_id="M001")])
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["member_id"] == "M001"

    def test_roundtrip_claim_charge_amount(self):
        raw = generate_ncpdp_batch("S", "R", "B", [_minimal_claim(charge_amount=Decimal("99.99"))])
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["charge_amount"] == Decimal("99.99")

    def test_empty_claims_parses(self):
        raw = generate_ncpdp_batch("S", "R", "B", [])
        result = parse_ncpdp_batch(raw)
        assert result.claims == []
        assert result.claim_count == 0

    def test_claim_date_of_service(self):
        raw = generate_ncpdp_batch("S", "R", "B", [_minimal_claim(date_of_service="20260315")])
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["date_of_service"] == "20260315"

    def test_claim_days_supply(self):
        raw = generate_ncpdp_batch("S", "R", "B", [_minimal_claim(days_supply=90)])
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["days_supply"] == 90

    def test_claim_service_provider_id(self):
        raw = generate_ncpdp_batch("S", "R", "B", [_minimal_claim(service_provider_id="NPI001")])
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["service_provider_id"] == "NPI001"

    def test_claim_patient_name(self):
        raw = generate_ncpdp_batch("S", "R", "B", [
            _minimal_claim(),
        ])
        # NcpdpClaim dataclass has defaults for patient_last/first
        result = parse_ncpdp_batch(raw)
        assert "patient_last" in result.claims[0]

    def test_pcn_in_claim(self):
        claim = _minimal_claim()
        claim.pcn = "PCN123"
        raw = generate_ncpdp_batch("S", "R", "B", [claim])
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["pcn"] == "PCN123"

    def test_parse_empty_string(self):
        result = parse_ncpdp_batch("")
        assert result.sender_id == ""
        assert result.claims == []

    def test_roundtrip_with_copay(self):
        claim = _minimal_claim(charge_amount=Decimal("50.00"), copay_amount=Decimal("10.00"))
        raw = generate_ncpdp_batch("S", "R", "B", [claim])
        result = parse_ncpdp_batch(raw)
        assert result.total_amount == Decimal("50.00")

    def test_decimal_formatting_two_places(self):
        claim = _minimal_claim(charge_amount=Decimal("7.50"))
        raw = generate_ncpdp_batch("S", "R", "B", [claim])
        result = parse_ncpdp_batch(raw)
        assert result.claims[0]["charge_amount"] == Decimal("7.50")
