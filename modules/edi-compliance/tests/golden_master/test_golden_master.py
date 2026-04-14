"""Golden master tests — byte-for-byte comparison against committed reference files.

The reference files were generated with known-good test inputs and a fixed
timestamp (2026-01-01T12:00:00Z) and committed to the repository.  Any
change to the generator that alters the output will fail these tests,
forcing a conscious decision before merging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


from src.x12.delimiters import Delimiters
from src.x12.generators.gen_270 import generate_270
from src.x12.generators.gen_835 import generate_835
from src.x12.generators.gen_837p import generate_837p
from src.x12.generators.schemas import (
    CasAdjustment,
    ClpClaim,
    Generate270Request,
    Generate835Request,
    Generate837PRequest,
    N1Party,
    TrnTrace,
)
from src.x12.parsers.parse_835 import parse_835
from src.x12.validators.validator import validate_x12

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")
_GOLDEN_DIR = Path(__file__).parent
_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

TENANT_ID = "11111111-1111-1111-1111-111111111111"
PARTNER_ID = "22222222-2222-2222-2222-222222222222"


def _make_835_req() -> Generate835Request:
    return Generate835Request(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        payment_date="20260101",
        payment_amount=Decimal("285.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="GLDMASTER001",
        payer=N1Party(entity_qualifier="PR", name="INFINITYRX HEALTH PLAN", id_qualifier="PI", id_code="IRXHP001"),
        payee=N1Party(entity_qualifier="PE", name="GOLDEN PHARMACY", id_qualifier="XX", id_code="1234567893"),
        trace=TrnTrace(check_eft_number="GLDMASTER001", payer_id="IRXHP001"),
        claims=[
            ClpClaim(
                claim_id="GOLD835CLAIM001",
                status_code="1",
                charge_amount=Decimal("200.00"),
                paid_amount=Decimal("170.00"),
                patient_responsibility=Decimal("30.00"),
                claim_filing_indicator="HM",
                adjustments=[CasAdjustment(group_code="CO", reason_code="45", amount=Decimal("30.00"))],
            ),
            ClpClaim(
                claim_id="GOLD835CLAIM002",
                status_code="1",
                charge_amount=Decimal("150.00"),
                paid_amount=Decimal("115.00"),
                patient_responsibility=Decimal("35.00"),
                claim_filing_indicator="HM",
                adjustments=[CasAdjustment(group_code="CO", reason_code="45", amount=Decimal("35.00"))],
            ),
        ],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )


def _make_837p_req() -> Generate837PRequest:
    return Generate837PRequest(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        receiver_id="PAYER001       ",
        test_mode=True,
        implementation_guide="005010X222A2",
        billing_provider_npi="1234567893",
        billing_provider_name="GOLDEN MEDICAL GROUP",
        billing_provider_ein="123456789",
        subscriber_id="MEMBER001",
        subscriber_last_name="SMITH",
        subscriber_first_name="JOHN",
        subscriber_dob="19750615",
        subscriber_gender="M",
        payer_id="PAYER001",
        payer_name="BLUE CROSS",
        claims=[
            {
                "claim_id": "GOLD837CLAIM001",
                "charge_amount": "500.00",
                "facility_code": "11",
                "claim_frequency": "1",
                "principal_diagnosis": "J06.9",
                "service_lines": [
                    {
                        "procedure_code": "99213",
                        "charge_amount": "250.00",
                        "units": "1",
                        "place_of_service": "11",
                        "date_of_service": "20260101",
                    }
                ],
            }
        ],
    )


def _make_270_req() -> Generate270Request:
    return Generate270Request(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        receiver_id="PAYER001       ",
        test_mode=True,
        implementation_guide="005010X279A1",
        payer_id="PAYER001",
        payer_name="BLUE CROSS",
        receiver_id_qualifier="XX",
        receiver_npi="1234567893",
        subscriber_id="MEMBER001",
        subscriber_last_name="SMITH",
        subscriber_first_name="JOHN",
        subscriber_dob="19750615",
        service_type_codes=["30"],
        date_of_service="20260101",
    )


def test_835_golden_master():
    """Generated 835 must match committed reference file byte-for-byte."""
    golden = (_GOLDEN_DIR / "835_golden.edi").read_text()
    result = generate_835(_make_835_req(), _DELIMS, _FIXED_NOW)
    assert result == golden, (
        "835 output changed from golden master.\n"
        f"Expected length: {len(golden)}, got: {len(result)}"
    )


def test_837p_golden_master():
    """Generated 837P must match committed reference file byte-for-byte."""
    golden = (_GOLDEN_DIR / "837p_golden.edi").read_text()
    result = generate_837p(_make_837p_req(), _DELIMS, _FIXED_NOW)
    assert result == golden, (
        "837P output changed from golden master.\n"
        f"Expected length: {len(golden)}, got: {len(result)}"
    )


def test_270_golden_master():
    """Generated 270 must match committed reference file byte-for-byte."""
    golden = (_GOLDEN_DIR / "270_golden.edi").read_text()
    result = generate_270(_make_270_req(), _DELIMS, _FIXED_NOW)
    assert result == golden


def test_835_parse_golden_master_amounts():
    """Parse golden 835 and verify extracted amounts are Decimal-exact."""
    golden = (_GOLDEN_DIR / "835_golden.edi").read_text()
    parsed = parse_835(golden)
    assert parsed.payment_amount == Decimal("285.00")
    assert len(parsed.claims) == 2
    claim1 = next(c for c in parsed.claims if c.claim_id == "GOLD835CLAIM001")
    assert claim1.charge_amount == Decimal("200.00")
    assert claim1.paid_amount == Decimal("170.00")
    assert claim1.patient_responsibility == Decimal("30.00")


def test_835_golden_passes_validation():
    """Golden 835 file must pass all 4 levels of validation."""
    golden = (_GOLDEN_DIR / "835_golden.edi").read_text()
    result = validate_x12(golden)
    assert result.is_valid, f"Golden 835 failed validation: {[e.message for e in result.errors]}"


def test_837p_golden_passes_validation():
    """Golden 837P file must pass all 4 levels of validation."""
    golden = (_GOLDEN_DIR / "837p_golden.edi").read_text()
    result = validate_x12(golden)
    assert result.is_valid, f"Golden 837P failed validation: {[e.message for e in result.errors]}"
