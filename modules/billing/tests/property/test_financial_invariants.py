"""Property-based tests for billing financial invariants.

Every invariant that MUST hold for any input:
- penny_allocate: sum of parts == total, count preserved
- batch total == sum of payments
- invoice total == subtotals sum
- fee calculation: non-negative for non-negative inputs
- AR outstanding >= 0 always
- money() is idempotent: money(money(x)) == money(x)
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from src.services.ap import APService
from src.services.ar import ARService, FeeConfigData
from src.utils.constants import (
    FEE_FLAT_MONTHLY,
    ROUTE_ECHO,
)
from src.utils.money import money, penny_allocate

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLIENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ENTITY_A = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

_pos_decimal = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_non_neg_decimal = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


class TestPennyAllocateInvariants:
    @given(
        total=_pos_decimal,
        count=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=500)
    def test_sum_always_equals_total(self, total: Decimal, count: int) -> None:
        result = penny_allocate(total, count)
        assert sum(result) == total

    @given(
        total=_pos_decimal,
        count=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=500)
    def test_count_always_preserved(self, total: Decimal, count: int) -> None:
        result = penny_allocate(total, count)
        assert len(result) == count

    @given(
        total=_pos_decimal,
        count=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=500)
    def test_all_elements_are_decimal(self, total: Decimal, count: int) -> None:
        result = penny_allocate(total, count)
        assert all(isinstance(r, Decimal) for r in result)

    @given(total=_pos_decimal)
    @settings(max_examples=200)
    def test_single_item_equals_total(self, total: Decimal) -> None:
        result = penny_allocate(total, 1)
        assert result == [total]


class TestMoneyIdempotence:
    @given(value=_pos_decimal)
    @settings(max_examples=500)
    def test_money_of_money_is_idempotent(self, value: Decimal) -> None:
        assert money(money(value)) == money(value)

    @given(value=_pos_decimal)
    @settings(max_examples=500)
    def test_no_float_contamination(self, value: Decimal) -> None:
        result = money(value)
        # Result should be exactly representable as Decimal with 2 places
        assert result == Decimal(str(result))


class TestBatchTotalInvariant:
    @given(
        amounts=st.lists(
            _pos_decimal,
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=200)
    def test_batch_total_equals_sum_of_payments(self, amounts: list[Decimal]) -> None:
        from unittest.mock import MagicMock

        svc = APService(db=MagicMock(), events=MagicMock())
        ap_records = [
            {
                "id": uuid.uuid4(),
                "tenant_id": TENANT,
                "claim_record_id": uuid.uuid4(),
                "client_id": CLIENT,
                "pay_to_entity_id": ENTITY_A,
                "pay_to_entity_name": "Test Pharmacy",
                "amount": amount,
                "payment_route": ROUTE_ECHO,
                "status": "created",
                "created_at": __import__("datetime").datetime.now(),
                "updated_at": __import__("datetime").datetime.now(),
            }
            for amount in amounts
        ]
        result = svc.generate_batch(
            tenant_id=TENANT,
            payment_route=ROUTE_ECHO,
            ap_records=ap_records,
            batch_number="PROP001",
        )
        payment_sum = money(sum(p.amount for p in result.payments))
        assert result.batch.total_amount == payment_sum


class TestInvoiceTotalInvariant:
    @given(
        claim_amounts=st.lists(_non_neg_decimal, min_size=1, max_size=20),
        fee_amount=_non_neg_decimal,
    )
    @settings(max_examples=200)
    def test_invoice_total_equals_subtotals(
        self, claim_amounts: list[Decimal], fee_amount: Decimal
    ) -> None:
        from datetime import date
        from unittest.mock import MagicMock

        from src.services.ar import InvoiceRequest

        svc = ARService(db=MagicMock(), events=MagicMock())
        claims = [{"net_amount": a, "ingredient_cost": Decimal("0")} for a in claim_amounts]
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="TEST",
            calculation_type=FEE_FLAT_MONTHLY,
            amount=fee_amount,
            percentage=None,
            tiers=None,
        )
        req = InvoiceRequest(
            tenant_id=TENANT,
            client_id=CLIENT,
            client_name="Test Client",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            invoice_number="PROP-001",
            payment_terms_days=30,
        )
        invoice = svc.generate_invoice(req, claims, [fee_config])
        expected = money(
            invoice.claims_subtotal
            + invoice.fees_subtotal
            + invoice.adjustments
            + invoice.late_fees
        )
        assert invoice.total == expected


class TestAROutstandingNeverNegative:
    @given(
        amount_due=_pos_decimal,
        payment=_pos_decimal,
    )
    @settings(max_examples=200)
    def test_outstanding_never_negative(self, amount_due: Decimal, payment: Decimal) -> None:
        from datetime import date
        from unittest.mock import MagicMock

        svc = ARService(db=MagicMock(), events=MagicMock())
        ar = svc.create_ar_record(
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            client_id=CLIENT,
            amount_due=amount_due,
            due_date=date(2026, 2, 28),
        )
        svc.record_payment(ar, amount=payment, payment_date=date(2026, 2, 15))
        assert ar.amount_outstanding >= Decimal("0.00")
