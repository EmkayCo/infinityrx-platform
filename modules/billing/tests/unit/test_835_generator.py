"""Unit tests for HIPAA 835 remittance file generator."""

from __future__ import annotations

import uuid
from decimal import Decimal

from src.services.remittance_835 import (
    Remittance835Claim,
    Remittance835Generator,
    Remittance835Payment,
)

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _claim(
    auth_number: str = "AUTH001",
    paid_amount: Decimal = Decimal("100.00"),
    patient_pay: Decimal = Decimal("10.00"),
    plan_pay: Decimal = Decimal("90.00"),
    ndc: str = "12345678901",
    npi: str = "1234567890",
    date_of_service: str = "20260115",
) -> Remittance835Claim:
    return Remittance835Claim(
        claim_id=uuid.uuid4(),
        auth_number=auth_number,
        paid_amount=paid_amount,
        patient_pay=patient_pay,
        plan_pay=plan_pay,
        ndc=ndc,
        npi=npi,
        date_of_service=date_of_service,
    )


def _payment(
    payment_id: uuid.UUID | None = None,
    amount: Decimal = Decimal("200.00"),
    payee_name: str = "Test Pharmacy",
    payee_npi: str = "1234567890",
    claims: list | None = None,
) -> Remittance835Payment:
    return Remittance835Payment(
        payment_id=payment_id or uuid.uuid4(),
        amount=amount,
        payee_name=payee_name,
        payee_npi=payee_npi,
        claims=claims or [_claim()],
    )


class TestRemittance835Generator:
    def _gen(self) -> Remittance835Generator:
        return Remittance835Generator(
            payer_id="INFTX",
            payer_name="InfinityRx LLC",
            production_date="20260115",
        )

    def test_generate_returns_string(self) -> None:
        gen = self._gen()
        result = gen.generate(_payment())
        assert isinstance(result, str)

    def test_isa_segment_present(self) -> None:
        gen = self._gen()
        result = gen.generate(_payment())
        assert result.startswith("ISA")

    def test_gs_segment_present(self) -> None:
        gen = self._gen()
        result = gen.generate(_payment())
        assert "GS*" in result

    def test_st_segment_with_835(self) -> None:
        gen = self._gen()
        result = gen.generate(_payment())
        assert "ST*835*" in result

    def test_bpr_segment_contains_payment_amount(self) -> None:
        gen = self._gen()
        result = gen.generate(_payment(amount=Decimal("1234.56")))
        assert "BPR*" in result
        assert "1234.56" in result

    def test_clp_segment_per_claim(self) -> None:
        gen = self._gen()
        claims = [_claim("AUTH001"), _claim("AUTH002")]
        result = gen.generate(_payment(claims=claims))
        assert result.count("CLP*") == 2

    def test_se_segment_closes_transaction(self) -> None:
        gen = self._gen()
        result = gen.generate(_payment())
        assert "SE*" in result

    def test_ge_segment_closes_functional_group(self) -> None:
        gen = self._gen()
        result = gen.generate(_payment())
        assert "GE*" in result

    def test_iea_segment_closes_interchange(self) -> None:
        gen = self._gen()
        result = gen.generate(_payment())
        assert "IEA*" in result

    def test_amounts_are_decimal_formatted(self) -> None:
        gen = self._gen()
        result = gen.generate(_payment(amount=Decimal("500.00")))
        assert "500.00" in result
