"""Tests for the NCPDP D.0 parser and response builder.

Covers: parse B1 request correctly, parse all segments, build valid
D.0 response, handle malformed input gracefully.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.services.ncpdp_parser import (
    FIELD_SEPARATOR,
    SEGMENT_SEPARATOR,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
    ClaimResponseData,
    ParsedClaim,
    build_d0_response,
    parse_d0_request,
    _safe_decimal,
    _safe_int,
)


# ---------------------------------------------------------------------------
# Helpers to build raw NCPDP bytes
# ---------------------------------------------------------------------------


def _build_header(
    bin_number: str = "999999",
    version: str = "D0",
    transaction_code: str = "B1",
    pcn: str = "TESTPCN",
) -> bytes:
    """Build a D.0 header segment."""
    return f"{bin_number}{version}{transaction_code}{pcn}".encode("ascii")


def _build_segment(segment_id: str, fields: dict[str, str]) -> bytes:
    """Build a D.0 segment from segment ID and field dict."""
    parts = [f"AM{segment_id}"]
    for fid, fval in fields.items():
        parts.append(f"{fid}{fval}")
    return FIELD_SEPARATOR.join(p.encode("ascii") for p in parts)


def _build_full_request(
    header: bytes | None = None,
    segments: list[bytes] | None = None,
) -> bytes:
    """Build a complete D.0 request with header and segments."""
    if header is None:
        header = _build_header()
    parts = [header]
    if segments:
        for seg in segments:
            parts.append(SEGMENT_SEPARATOR)
            parts.append(seg)
    return b"".join(parts)


# ---------------------------------------------------------------------------
# Test: Parse B1 request correctly
# ---------------------------------------------------------------------------


class TestParseB1Request:
    """Tests for parsing a standard B1 billing request."""

    def test_parse_b1_extracts_header_fields(self):
        raw = _build_full_request()
        result = parse_d0_request(raw)
        assert result.header.bin_number == "999999"
        assert result.header.version == "D0"
        assert result.header.transaction_code == "B1"

    def test_parse_b1_extracts_pcn(self):
        raw = _build_full_request(
            header=_build_header(pcn="MYPCN")
        )
        result = parse_d0_request(raw)
        assert result.header.pcn == "MYPCN"

    def test_parse_b2_transaction(self):
        raw = _build_full_request(
            header=_build_header(transaction_code="B2")
        )
        result = parse_d0_request(raw)
        assert result.header.transaction_code == "B2"
        assert len(result.parse_errors) == 0

    def test_parse_b3_transaction(self):
        raw = _build_full_request(
            header=_build_header(transaction_code="B3")
        )
        result = parse_d0_request(raw)
        assert result.header.transaction_code == "B3"
        assert len(result.parse_errors) == 0

    def test_parse_e1_transaction(self):
        raw = _build_full_request(
            header=_build_header(transaction_code="E1")
        )
        result = parse_d0_request(raw)
        assert result.header.transaction_code == "E1"
        assert len(result.parse_errors) == 0


# ---------------------------------------------------------------------------
# Test: Parse all segments
# ---------------------------------------------------------------------------


class TestParseAllSegments:
    """Tests for parsing each segment type."""

    def test_parse_patient_segment(self):
        patient_seg = _build_segment("01", {
            "C2": "CARD12345",
            "C4": "19800115",
            "C5": "1",
            "C6": "01",
            "CA": "John",
            "CB": "Smith",
        })
        raw = _build_full_request(segments=[patient_seg])
        result = parse_d0_request(raw)
        assert result.patient.cardholder_id == "CARD12345"
        assert result.patient.date_of_birth == "19800115"
        assert result.patient.gender_code == "1"
        assert result.patient.person_code == "01"
        assert result.patient.first_name == "John"
        assert result.patient.last_name == "Smith"

    def test_parse_insurance_segment(self):
        insurance_seg = _build_segment("04", {
            "C2": "CARD12345",
            "C1": "GRP001",
            "FO": "PLAN001",
            "C3": "03",
            "C8": "1",
        })
        raw = _build_full_request(segments=[insurance_seg])
        result = parse_d0_request(raw)
        assert result.insurance.cardholder_id == "CARD12345"
        assert result.insurance.group_id == "GRP001"
        assert result.insurance.plan_id == "PLAN001"
        assert result.insurance.eligibility_clarification_code == "03"
        assert result.insurance.other_coverage_code == "1"

    def test_parse_claim_segment(self):
        claim_seg = _build_segment("07", {
            "D2": "RX123456",
            "D7": "12345678901",
            "E7": "30.0000",
            "D5": "30",
            "D6": "0",
            "D8": "0",
            "DE": "20260101",
            "D3": "2",
        })
        raw = _build_full_request(segments=[claim_seg])
        result = parse_d0_request(raw)
        assert result.claim.prescription_number == "RX123456"
        assert result.claim.ndc == "12345678901"
        assert result.claim.quantity_dispensed == Decimal("30.00")
        assert result.claim.days_supply == 30
        assert result.claim.compound_code == "0"
        assert result.claim.daw_code == "0"
        assert result.claim.refill_number == 2

    def test_parse_pricing_segment(self):
        pricing_seg = _build_segment("11", {
            "D9": "100.00",
            "DC": "5.50",
            "DX": "25.00",
            "DQ": "130.00",
            "DU": "105.50",
            "DN": "01",
        })
        raw = _build_full_request(segments=[pricing_seg])
        result = parse_d0_request(raw)
        assert result.pricing.ingredient_cost_submitted == Decimal("100.00")
        assert result.pricing.dispensing_fee_submitted == Decimal("5.50")
        assert result.pricing.patient_paid_amount == Decimal("25.00")
        assert result.pricing.usual_and_customary == Decimal("130.00")
        assert result.pricing.gross_amount_due == Decimal("105.50")
        assert result.pricing.basis_of_cost == "01"

    def test_parse_prescriber_segment(self):
        prescriber_seg = _build_segment("03", {
            "DB": "1234567890",
            "DY": "01",
            "DR": "Jones",
            "2J": "Mary",
            "PM": "5551234567",
        })
        raw = _build_full_request(segments=[prescriber_seg])
        result = parse_d0_request(raw)
        assert result.prescriber.prescriber_id == "1234567890"
        assert result.prescriber.prescriber_id_qualifier == "01"
        assert result.prescriber.prescriber_last_name == "Jones"
        assert result.prescriber.prescriber_first_name == "Mary"
        assert result.prescriber.prescriber_phone == "5551234567"

    def test_parse_dur_segment(self):
        dur_seg = _build_segment("08", {
            "7E": "1",
            "E4": "TD",
            "E5": "M0",
            "E6": "1A",
        })
        raw = _build_full_request(segments=[dur_seg])
        result = parse_d0_request(raw)
        assert result.dur.dur_pps_code_counter == 1
        assert result.dur.reason_for_service_code == "TD"
        assert result.dur.professional_service_code == "M0"
        assert result.dur.result_of_service_code == "1A"

    def test_parse_multiple_segments(self):
        patient_seg = _build_segment("01", {"C2": "CARD999", "CA": "Jane"})
        claim_seg = _build_segment("07", {"D7": "99999999999", "D5": "90"})
        raw = _build_full_request(segments=[patient_seg, claim_seg])
        result = parse_d0_request(raw)
        assert result.patient.cardholder_id == "CARD999"
        assert result.patient.first_name == "Jane"
        assert result.claim.ndc == "99999999999"
        assert result.claim.days_supply == 90

    def test_raw_segments_stored(self):
        patient_seg = _build_segment("01", {"C2": "CARD123"})
        raw = _build_full_request(segments=[patient_seg])
        result = parse_d0_request(raw)
        assert "01" in result.raw_segments
        assert result.raw_segments["01"]["C2"] == "CARD123"


# ---------------------------------------------------------------------------
# Test: Build valid D.0 response
# ---------------------------------------------------------------------------


class TestBuildD0Response:
    """Tests for building NCPDP D.0 response bytes."""

    def test_build_accepted_response(self):
        resp_data = ClaimResponseData(
            transaction_code="B1",
            status=STATUS_ACCEPTED,
            bin_number="999999",
            version="D0",
            ingredient_cost_paid=Decimal("100.00"),
            dispensing_fee_paid=Decimal("5.00"),
            patient_pay=Decimal("25.00"),
            plan_pay=Decimal("80.00"),
            total_amount=Decimal("105.00"),
        )
        response = build_d0_response(resp_data)
        assert isinstance(response, bytes)
        assert b"999999" in response
        assert b"D0" in response
        # Status segment should contain 'A' for accepted
        decoded = response.decode("ascii", errors="replace")
        assert "ANA" in decoded  # AN{status_code}

    def test_build_rejected_response_includes_codes(self):
        resp_data = ClaimResponseData(
            transaction_code="B1",
            status=STATUS_REJECTED,
            bin_number="999999",
            reject_codes=["75", "76"],
            reject_messages=["Prior authorization required", "Plan limits exceeded"],
        )
        response = build_d0_response(resp_data)
        decoded = response.decode("ascii", errors="replace")
        assert "ANR" in decoded  # status = rejected
        assert "FA75" in decoded  # reject code
        assert "FA76" in decoded

    def test_build_response_has_pricing_segment_when_paid(self):
        resp_data = ClaimResponseData(
            status=STATUS_ACCEPTED,
            ingredient_cost_paid=Decimal("50.00"),
            dispensing_fee_paid=Decimal("3.00"),
            patient_pay=Decimal("10.00"),
            plan_pay=Decimal("43.00"),
            total_amount=Decimal("53.00"),
        )
        response = build_d0_response(resp_data)
        decoded = response.decode("ascii", errors="replace")
        # Should contain pricing response segment (AM22)
        assert "AM22" in decoded
        # Should contain formatted money values
        assert "50.00" in decoded
        assert "10.00" in decoded

    def test_rejected_response_omits_pricing_segment(self):
        resp_data = ClaimResponseData(
            status=STATUS_REJECTED,
            reject_codes=["70"],
        )
        response = build_d0_response(resp_data)
        decoded = response.decode("ascii", errors="replace")
        # Should NOT contain pricing response segment
        assert "AM22" not in decoded

    def test_build_response_with_dur_results(self):
        resp_data = ClaimResponseData(
            status=STATUS_ACCEPTED,
            dur_responses=[
                {"E4": "TD", "E5": "M0", "E6": "1A"},
            ],
        )
        response = build_d0_response(resp_data)
        decoded = response.decode("ascii", errors="replace")
        assert "AM24" in decoded  # DUR response segment
        assert "E4TD" in decoded


# ---------------------------------------------------------------------------
# Test: Handle malformed input gracefully
# ---------------------------------------------------------------------------


class TestMalformedInput:
    """Tests for graceful handling of malformed NCPDP data."""

    def test_empty_input_returns_parse_error(self):
        result = parse_d0_request(b"")
        assert len(result.parse_errors) > 0
        assert "Empty request" in result.parse_errors[0]

    def test_too_short_input_returns_parse_error(self):
        result = parse_d0_request(b"SHORT")
        assert len(result.parse_errors) > 0
        assert "too short" in result.parse_errors[0].lower()

    def test_invalid_transaction_code_flagged(self):
        raw = _build_full_request(
            header=_build_header(transaction_code="XX")
        )
        result = parse_d0_request(raw)
        assert any("Invalid transaction code" in e for e in result.parse_errors)

    def test_missing_field_values_default_gracefully(self):
        """Segments with missing fields get empty/zero defaults."""
        # Build a claim segment missing quantity and days supply
        claim_seg = _build_segment("07", {"D7": "12345678901"})
        raw = _build_full_request(segments=[claim_seg])
        result = parse_d0_request(raw)
        assert result.claim.ndc == "12345678901"
        assert result.claim.quantity_dispensed == Decimal("0.00")
        assert result.claim.days_supply == 0

    def test_non_ascii_bytes_handled(self):
        """Non-ASCII bytes don't crash the parser."""
        raw = b"\x999999D0B1TEST" + SEGMENT_SEPARATOR + b"\xff\xfe\xfd"
        result = parse_d0_request(raw)
        # Should not raise — errors collected in parse_errors
        assert isinstance(result, ParsedClaim)

    def test_empty_segment_skipped(self):
        """Empty segments between separators don't crash."""
        raw = _build_header() + SEGMENT_SEPARATOR + b"" + SEGMENT_SEPARATOR + _build_segment("01", {"C2": "TEST"})
        result = parse_d0_request(raw)
        assert result.patient.cardholder_id == "TEST"


# ---------------------------------------------------------------------------
# Test: Helper functions
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Tests for parser helper functions."""

    def test_safe_int_valid(self):
        assert _safe_int("42") == 42
        assert _safe_int("0") == 0

    def test_safe_int_invalid_returns_default(self):
        assert _safe_int("abc") == 0
        assert _safe_int("") == 0
        assert _safe_int("abc", 99) == 99

    def test_safe_decimal_with_explicit_decimal(self):
        assert _safe_decimal("100.00") == Decimal("100.00")
        assert _safe_decimal("0.50") == Decimal("0.50")

    def test_safe_decimal_with_implied_decimal(self):
        assert _safe_decimal("10000") == Decimal("100.00")
        assert _safe_decimal("50") == Decimal("0.50")

    def test_safe_decimal_empty_returns_zero(self):
        assert _safe_decimal("") == Decimal("0.00")
        assert _safe_decimal("  ") == Decimal("0.00")

    def test_safe_decimal_negative(self):
        result = _safe_decimal("-25.00")
        assert result == Decimal("-25.00")

    def test_safe_decimal_invalid_returns_zero(self):
        assert _safe_decimal("INVALID") == Decimal("0.00")
