"""Unit tests for AR engine — 100% coverage on financial paths."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from src.services.ar import (
    ARService,
    FeeConfigData,
    InvoiceRequest,
)
from src.utils.constants import (
    AR_STATUS_DISPUTED,
    AR_STATUS_OPEN,
    AR_STATUS_PAID,
    AR_STATUS_PARTIALLY_PAID,
    AR_STATUS_WRITTEN_OFF,
    FEE_FLAT_MONTHLY,
    FEE_PER_CLAIM_FLAT,
    FEE_PER_CLAIM_PERCENTAGE,
    FEE_PERCENTAGE_OF_INGREDIENT_COST,
    FEE_TIERED_VOLUME,
    INVOICE_STATUS_DRAFT,
)
from src.utils.money import money

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CLIENT = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROGRAM = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
USER = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _svc(events=None) -> ARService:
    return ARService(db=MagicMock(), events=events or MagicMock())


def _fee_flat(amount: Decimal = Decimal("1.50")) -> FeeConfigData:
    return FeeConfigData(
        id=uuid.uuid4(),
        fee_code="PROC",
        calculation_type=FEE_PER_CLAIM_FLAT,
        amount=amount,
        percentage=None,
        tiers=None,
    )


def _fee_pct(percentage: Decimal = Decimal("2.00")) -> FeeConfigData:
    return FeeConfigData(
        id=uuid.uuid4(),
        fee_code="MGMT",
        calculation_type=FEE_PER_CLAIM_PERCENTAGE,
        amount=None,
        percentage=percentage,
        tiers=None,
    )


def _claim(
    amount: Decimal = Decimal("100.00"), ingredient_cost: Decimal = Decimal("80.00")
) -> dict:
    return {
        "id": uuid.uuid4(),
        "net_amount": amount,
        "ingredient_cost": ingredient_cost,
        "program_id": PROGRAM,
        "claim_type": "new",
    }


class TestFeeCalculation:
    def test_per_claim_flat_fee(self) -> None:
        svc = _svc()
        claims = [_claim(), _claim(), _claim()]
        fee = svc.calculate_fee(_fee_flat(Decimal("1.50")), claims)
        assert fee == money("4.50")

    def test_per_claim_flat_fee_zero_claims(self) -> None:
        svc = _svc()
        fee = svc.calculate_fee(_fee_flat(Decimal("1.50")), [])
        assert fee == money("0.00")

    def test_per_claim_percentage_of_net(self) -> None:
        svc = _svc()
        claims = [_claim(amount=Decimal("100.00")), _claim(amount=Decimal("200.00"))]
        fee_config = _fee_pct(percentage=Decimal("10.00"))
        fee_config.calculation_type = FEE_PER_CLAIM_PERCENTAGE
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == money("30.00")

    def test_percentage_of_ingredient_cost(self) -> None:
        svc = _svc()
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="IC",
            calculation_type=FEE_PERCENTAGE_OF_INGREDIENT_COST,
            amount=None,
            percentage=Decimal("5.00"),
            tiers=None,
        )
        claims = [
            _claim(ingredient_cost=Decimal("100.00")),
            _claim(ingredient_cost=Decimal("200.00")),
        ]
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == money("15.00")

    def test_flat_monthly_fee(self) -> None:
        svc = _svc()
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="MONTHLY",
            calculation_type=FEE_FLAT_MONTHLY,
            amount=Decimal("500.00"),
            percentage=None,
            tiers=None,
        )
        claims = [_claim(), _claim()]  # count doesn't matter for flat monthly
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == money("500.00")

    def test_tiered_volume_fee_first_tier(self) -> None:
        svc = _svc()
        tiers = [
            {"min_claims": 0, "max_claims": 100, "fee_per_claim": "1.00"},
            {"min_claims": 101, "max_claims": 500, "fee_per_claim": "0.80"},
            {"min_claims": 501, "max_claims": None, "fee_per_claim": "0.60"},
        ]
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="TIER",
            calculation_type=FEE_TIERED_VOLUME,
            amount=None,
            percentage=None,
            tiers=tiers,
        )
        claims = [_claim() for _ in range(50)]
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == money("50.00")

    def test_tiered_volume_fee_second_tier(self) -> None:
        svc = _svc()
        tiers = [
            {"min_claims": 0, "max_claims": 100, "fee_per_claim": "1.00"},
            {"min_claims": 101, "max_claims": 500, "fee_per_claim": "0.80"},
        ]
        fee_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="TIER",
            calculation_type=FEE_TIERED_VOLUME,
            amount=None,
            percentage=None,
            tiers=tiers,
        )
        claims = [_claim() for _ in range(200)]
        fee = svc.calculate_fee(fee_config, claims)
        assert fee == money("160.00")

    def test_fee_result_is_decimal(self) -> None:
        svc = _svc()
        fee = svc.calculate_fee(_fee_flat(Decimal("1.00")), [_claim()])
        assert isinstance(fee, Decimal)

    def test_unknown_fee_type_raises(self) -> None:
        svc = _svc()
        bad_config = FeeConfigData(
            id=uuid.uuid4(),
            fee_code="BAD",
            calculation_type="unknown_type",
            amount=Decimal("1.00"),
            percentage=None,
            tiers=None,
        )
        with pytest.raises(ValueError, match="Unknown fee calculation type"):
            svc.calculate_fee(bad_config, [_claim()])


class TestInvoiceGeneration:
    def test_invoice_total_equals_subtotals(self) -> None:
        svc = _svc()
        claims = [_claim(Decimal("100.00")), _claim(Decimal("200.00"))]
        fees = [_fee_flat(Decimal("2.00"))]
        req = InvoiceRequest(
            tenant_id=TENANT,
            client_id=CLIENT,
            client_name="Test Client",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            invoice_number="INV-001",
            payment_terms_days=30,
        )
        invoice = svc.generate_invoice(req, claims, fees)
        # total = claims_subtotal + fees_subtotal + adjustments + late_fees
        expected_total = (
            invoice.claims_subtotal
            + invoice.fees_subtotal
            + invoice.adjustments
            + invoice.late_fees
        )
        assert invoice.total == expected_total

    def test_invoice_total_is_decimal(self) -> None:
        svc = _svc()
        claims = [_claim()]
        req = InvoiceRequest(
            tenant_id=TENANT,
            client_id=CLIENT,
            client_name="Test Client",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            invoice_number="INV-001",
            payment_terms_days=30,
        )
        invoice = svc.generate_invoice(req, claims, [])
        assert isinstance(invoice.total, Decimal)

    def test_invoice_status_is_draft(self) -> None:
        svc = _svc()
        req = InvoiceRequest(
            tenant_id=TENANT,
            client_id=CLIENT,
            client_name="Test Client",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            invoice_number="INV-001",
            payment_terms_days=30,
        )
        invoice = svc.generate_invoice(req, [_claim()], [])
        assert invoice.status == INVOICE_STATUS_DRAFT

    def test_invoice_publishes_event(self) -> None:
        events = MagicMock()
        svc = _svc(events=events)
        req = InvoiceRequest(
            tenant_id=TENANT,
            client_id=CLIENT,
            client_name="Test Client",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            invoice_number="INV-001",
            payment_terms_days=30,
        )
        svc.generate_invoice(req, [_claim()], [])
        topics = [c[0][0] for c in events.publish.call_args_list]
        assert "invoice.generated" in topics

    def test_invoice_due_date_set_from_payment_terms(self) -> None:
        svc = _svc()
        req = InvoiceRequest(
            tenant_id=TENANT,
            client_id=CLIENT,
            client_name="Test Client",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            invoice_number="INV-001",
            payment_terms_days=30,
        )
        invoice = svc.generate_invoice(req, [_claim()], [])
        assert invoice.due_date is not None


class TestARRecord:
    def test_create_ar_record_from_invoice(self) -> None:
        svc = _svc()
        invoice_id = uuid.uuid4()
        ar = svc.create_ar_record(
            tenant_id=TENANT,
            invoice_id=invoice_id,
            client_id=CLIENT,
            amount_due=Decimal("500.00"),
            due_date=date(2026, 2, 28),
        )
        assert ar.status == AR_STATUS_OPEN
        assert ar.amount_due == money("500.00")
        assert ar.amount_outstanding == money("500.00")

    def test_record_payment_partial(self) -> None:
        svc = _svc()
        ar = svc.create_ar_record(
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            client_id=CLIENT,
            amount_due=Decimal("500.00"),
            due_date=date(2026, 2, 28),
        )
        svc.record_payment(ar, amount=Decimal("200.00"), payment_date=date(2026, 2, 15))
        assert ar.amount_paid == money("200.00")
        assert ar.amount_outstanding == money("300.00")
        assert ar.status == AR_STATUS_PARTIALLY_PAID

    def test_record_payment_full(self) -> None:
        svc = _svc()
        ar = svc.create_ar_record(
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            client_id=CLIENT,
            amount_due=Decimal("500.00"),
            due_date=date(2026, 2, 28),
        )
        svc.record_payment(ar, amount=Decimal("500.00"), payment_date=date(2026, 2, 15))
        assert ar.status == AR_STATUS_PAID
        assert ar.amount_outstanding == money("0.00")

    def test_outstanding_never_below_zero(self) -> None:
        svc = _svc()
        ar = svc.create_ar_record(
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            client_id=CLIENT,
            amount_due=Decimal("100.00"),
            due_date=date(2026, 2, 28),
        )
        svc.record_payment(ar, amount=Decimal("150.00"), payment_date=date(2026, 2, 15))
        assert ar.amount_outstanding == money("0.00")

    def test_payment_amount_is_decimal(self) -> None:
        svc = _svc()
        ar = svc.create_ar_record(
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            client_id=CLIENT,
            amount_due=Decimal("100.00"),
            due_date=date(2026, 2, 28),
        )
        svc.record_payment(ar, amount=Decimal("50.00"), payment_date=date(2026, 2, 15))
        assert isinstance(ar.amount_paid, Decimal)
        assert isinstance(ar.amount_outstanding, Decimal)

    def test_open_dispute(self) -> None:
        svc = _svc()
        ar = svc.create_ar_record(
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            client_id=CLIENT,
            amount_due=Decimal("100.00"),
            due_date=date(2026, 2, 28),
        )
        svc.open_dispute(ar, reason="Incorrect fee calculation")
        assert ar.status == AR_STATUS_DISPUTED
        assert ar.dispute_reason == "Incorrect fee calculation"

    def test_write_off(self) -> None:
        svc = _svc()
        ar = svc.create_ar_record(
            tenant_id=TENANT,
            invoice_id=uuid.uuid4(),
            client_id=CLIENT,
            amount_due=Decimal("100.00"),
            due_date=date(2026, 2, 28),
        )
        events = MagicMock()
        svc._events = events
        svc.write_off(ar, approved_by=USER)
        assert ar.status == AR_STATUS_WRITTEN_OFF
        topics = [c[0][0] for c in events.publish.call_args_list]
        assert "ar.written_off" in topics


class TestARAgingBuckets:
    """Standard AR aging: current(0), 30(1-30), 60(31-60), 90(61-90), 120_plus(91+)."""

    def test_current_bucket_zero_days(self) -> None:
        svc = _svc()
        bucket = svc.aging_bucket(days_outstanding=0)
        assert bucket == "current"

    def test_30_day_bucket(self) -> None:
        svc = _svc()
        bucket = svc.aging_bucket(days_outstanding=30)
        assert bucket == "30"

    def test_60_day_bucket(self) -> None:
        svc = _svc()
        bucket = svc.aging_bucket(days_outstanding=60)
        assert bucket == "60"

    def test_90_day_bucket(self) -> None:
        svc = _svc()
        bucket = svc.aging_bucket(days_outstanding=90)
        assert bucket == "90"

    def test_120_plus_bucket(self) -> None:
        svc = _svc()
        bucket = svc.aging_bucket(days_outstanding=121)
        assert bucket == "120_plus"

    def test_boundary_1_is_30_bucket(self) -> None:
        svc = _svc()
        assert svc.aging_bucket(1) == "30"

    def test_boundary_31_is_60_bucket(self) -> None:
        svc = _svc()
        assert svc.aging_bucket(31) == "60"

    def test_boundary_61_is_90_bucket(self) -> None:
        svc = _svc()
        assert svc.aging_bucket(61) == "90"

    def test_boundary_91_is_120_plus(self) -> None:
        svc = _svc()
        assert svc.aging_bucket(91) == "120_plus"

    def test_boundary_90_is_90_bucket(self) -> None:
        svc = _svc()
        assert svc.aging_bucket(90) == "90"

    def test_boundary_120_is_120_plus(self) -> None:
        svc = _svc()
        assert svc.aging_bucket(120) == "120_plus"
