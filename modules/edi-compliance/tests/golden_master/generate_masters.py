"""Script to regenerate golden master reference files.

Run this once to create the reference files, then commit them.
Tests compare against these committed files byte-for-byte.

Usage: python tests/golden_master/generate_masters.py
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

# Add parent to path for standalone execution
sys.path.insert(0, str(Path(__file__).parents[4]))

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
    SvcLine,
    TrnTrace,
)

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")
TENANT_ID = "11111111-1111-1111-1111-111111111111"
PARTNER_ID = "22222222-2222-2222-2222-222222222222"
OUT_DIR = Path(__file__).parent


def make_835() -> str:
    req = Generate835Request(
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
                pharmacy_npi="1234567893",
                bin_number="610014",
                ncpdp_number="NCPDP12345",
                adjustments=[CasAdjustment(group_code="CO", reason_code="45", amount=Decimal("30.00"))],
                service_lines=[
                    SvcLine(
                        procedure_code="00228203230",
                        procedure_qualifier="N4",
                        charge_amount=Decimal("200.00"),
                        paid_amount=Decimal("170.00"),
                        ndc="00228203230",
                        rx_number="RX12345678",
                        quantity=Decimal("30"),
                    )
                ],
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
    return generate_835(req, _DELIMS)


def make_837p() -> str:
    req = Generate837PRequest(
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
                    },
                    {
                        "procedure_code": "85025",
                        "charge_amount": "250.00",
                        "units": "1",
                        "place_of_service": "11",
                        "date_of_service": "20260101",
                    },
                ],
            }
        ],
    )
    return generate_837p(req, _DELIMS)


def make_270() -> str:
    req = Generate270Request(
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
    return generate_270(req, _DELIMS)


if __name__ == "__main__":
    content_835 = make_835()
    (OUT_DIR / "835_golden.edi").write_text(content_835)
    print(f"Generated 835: {len(content_835)} chars")

    content_837p = make_837p()
    (OUT_DIR / "837p_golden.edi").write_text(content_837p)
    print(f"Generated 837P: {len(content_837p)} chars")

    content_270 = make_270()
    (OUT_DIR / "270_golden.edi").write_text(content_270)
    print(f"Generated 270: {len(content_270)} chars")
