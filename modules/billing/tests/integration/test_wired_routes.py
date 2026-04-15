"""Integration tests for Wave 2F wired billing router handlers.

Covers: list, get-by-id, tenant isolation, and financial-precision checks
for all 27 newly wired routes. Uses a StaticPool SQLite engine so all
sessions share the same connection.

Journal routes are verified as READ-ONLY (no POST/PUT/DELETE).
Batch-total tests verify sum(payment_amounts) == batch_total.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.models.tables import (
    APRecord,
    ARRecord,
    BankAccount,
    BillingBase,
    ClaimRecord,
    FeeConfig,
    FundingConfig,
    Invoice,
    InvoiceLineItem,
    InvoicingConfig,
    JournalEntry,
    Payment,
    PaymentBatch,
    PaymentVendorConfig,
    PrefundLedger,
    ProgramBudget,
    ProgramBudgetAlert,
    ProgramBudgetSnapshot,
    RemittanceConfig,
    RoutingRule,
    SFTPConfig,
)

TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
CLIENT_A = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PROGRAM_A = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

HEADERS_A = {"X-Tenant-Id": str(TENANT_A)}
HEADERS_B = {"X-Tenant-Id": str(TENANT_B)}


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _wired_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    for table in BillingBase.metadata.tables.values():
        table.schema = None

    BillingBase.metadata.create_all(engine)
    yield engine
    BillingBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="module")
def wired_client(_wired_engine) -> TestClient:
    from src.api.dependencies import get_db
    from src.db.session import set_engine
    from src.main import app

    set_engine(_wired_engine)

    SessionLocal = sessionmaker(bind=_wired_engine, expire_on_commit=False)

    def override_db() -> Iterator[Session]:
        session = SessionLocal()
        try:
            yield session
            session.rollback()
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def populated_db(_wired_engine):
    """Seed both tenants with representative data once for the module."""
    SessionLocal = sessionmaker(bind=_wired_engine, expire_on_commit=False)
    session = SessionLocal()

    # --- ClaimRecord ---
    claim_a = ClaimRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        source_type="api",
        auth_number="AUTH-WIRED-001",
        claim_type="new",
        pharmacy_npi="1234567890",
        date_of_service=date(2026, 1, 15),
        date_received=_now(),
        net_amount=Decimal("123.45"),
        ingredient_cost=Decimal("100.00"),
        dispensing_fee=Decimal("10.00"),
        patient_pay=Decimal("5.00"),
        plan_pay=Decimal("108.45"),
        other_payer_amount=Decimal("0.00"),
        under_reimbursement=Decimal("0.00"),
        client_id=CLIENT_A,
        program_id=PROGRAM_A,
        status="adjudicated",
        created_at=_now(),
    )
    claim_b = ClaimRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_B,
        source_type="api",
        auth_number="AUTH-WIRED-002",
        claim_type="new",
        pharmacy_npi="0987654321",
        date_of_service=date(2026, 1, 15),
        date_received=_now(),
        net_amount=Decimal("200.00"),
        ingredient_cost=Decimal("180.00"),
        dispensing_fee=Decimal("10.00"),
        patient_pay=Decimal("10.00"),
        plan_pay=Decimal("180.00"),
        other_payer_amount=Decimal("0.00"),
        under_reimbursement=Decimal("0.00"),
        client_id=uuid.uuid4(),
        program_id=uuid.uuid4(),
        status="adjudicated",
        created_at=_now(),
    )
    session.add_all([claim_a, claim_b])
    session.flush()

    # --- RoutingRule ---
    rule_a = RoutingRule(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        name="Test Rule A",
        priority=100,
        payment_route="ach",
        is_active=True,
        created_at=_now(),
    )
    rule_b = RoutingRule(
        id=uuid.uuid4(),
        tenant_id=TENANT_B,
        name="Test Rule B",
        priority=50,
        payment_route="check",
        is_active=True,
        created_at=_now(),
    )
    session.add_all([rule_a, rule_b])
    session.flush()

    # --- APRecord ---
    ap_a = APRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        claim_record_id=claim_a.id,
        client_id=CLIENT_A,
        pay_to_entity_id=uuid.uuid4(),
        pay_to_entity_name="Main St Pharmacy",
        amount=Decimal("123.45"),
        payment_route="ach",
        status="created",
        created_at=_now(),
        updated_at=_now(),
    )
    ap_b = APRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_B,
        claim_record_id=claim_b.id,
        client_id=uuid.uuid4(),
        pay_to_entity_id=uuid.uuid4(),
        pay_to_entity_name="Other Pharmacy",
        amount=Decimal("200.00"),
        payment_route="check",
        status="created",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add_all([ap_a, ap_b])
    session.flush()

    # --- PaymentBatch + Payments ---
    batch_a = PaymentBatch(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        batch_number="BATCH-WIRED-001",
        payment_route="ach",
        total_amount=Decimal("300.00"),
        payment_count=2,
        ap_count=3,
        status="generated",
        generated_at=_now(),
        created_at=_now(),
        updated_at=_now(),
        version=1,
    )
    session.add(batch_a)
    session.flush()

    pay1 = Payment(
        id=uuid.uuid4(),
        payment_batch_id=batch_a.id,
        tenant_id=TENANT_A,
        pay_to_entity_id=uuid.uuid4(),
        pay_to_entity_name="Pharmacy One",
        amount=Decimal("175.00"),
        claim_count=2,
        status="pending",
        created_at=_now(),
        updated_at=_now(),
    )
    pay2 = Payment(
        id=uuid.uuid4(),
        payment_batch_id=batch_a.id,
        tenant_id=TENANT_A,
        pay_to_entity_id=uuid.uuid4(),
        pay_to_entity_name="Pharmacy Two",
        amount=Decimal("125.00"),
        claim_count=1,
        status="pending",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add_all([pay1, pay2])
    session.flush()

    # --- InvoicingConfig ---
    inv_config = InvoicingConfig(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        client_id=CLIENT_A,
        name="Monthly Billing",
        frequency="monthly",
        automation_level="semi_automatic",
        delivery_method="email",
        payment_terms_days=30,
        include_fees=True,
        is_active=True,
        created_at=_now(),
    )
    session.add(inv_config)
    session.flush()

    # --- Invoice + LineItems ---
    invoice_a = Invoice(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        invoice_number="INV-WIRED-001",
        invoice_type="combined",
        client_id=CLIENT_A,
        client_name="Test Client",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        claims_subtotal=Decimal("500.00"),
        fees_subtotal=Decimal("50.00"),
        adjustments=Decimal("0.00"),
        late_fees=Decimal("0.00"),
        total=Decimal("550.00"),
        claim_count=5,
        status="draft",
        due_date=date(2026, 2, 28),
        payment_terms_days=30,
        paid_amount=Decimal("0.00"),
        data_lock=False,
        version=1,
        created_at=_now(),
        updated_at=_now(),
    )
    invoice_b = Invoice(
        id=uuid.uuid4(),
        tenant_id=TENANT_B,
        invoice_number="INV-WIRED-002",
        invoice_type="combined",
        client_id=uuid.uuid4(),
        client_name="Other Client",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        claims_subtotal=Decimal("999.99"),
        fees_subtotal=Decimal("0.00"),
        adjustments=Decimal("0.00"),
        late_fees=Decimal("0.00"),
        total=Decimal("999.99"),
        claim_count=10,
        status="draft",
        due_date=date(2026, 2, 28),
        payment_terms_days=30,
        paid_amount=Decimal("0.00"),
        data_lock=False,
        version=1,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add_all([invoice_a, invoice_b])
    session.flush()

    line_item = InvoiceLineItem(
        id=uuid.uuid4(),
        invoice_id=invoice_a.id,
        tenant_id=TENANT_A,
        line_type="claims",
        description="Jan 2026 Claims",
        amount=Decimal("500.00"),
        sort_order=1,
        created_at=_now(),
    )
    session.add(line_item)
    session.flush()

    # --- ARRecord ---
    ar_a = ARRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        invoice_id=invoice_a.id,
        client_id=CLIENT_A,
        amount_due=Decimal("550.00"),
        amount_paid=Decimal("0.00"),
        amount_outstanding=Decimal("550.00"),
        status="open",
        due_date=date(2026, 2, 28),
        days_outstanding=0,
        aging_bucket="current",
        created_at=_now(),
        updated_at=_now(),
    )
    ar_overdue = ARRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        invoice_id=invoice_a.id,
        client_id=CLIENT_A,
        amount_due=Decimal("200.00"),
        amount_paid=Decimal("0.00"),
        amount_outstanding=Decimal("200.00"),
        status="open",
        due_date=date(2025, 11, 30),
        days_outstanding=45,
        aging_bucket="30",
        created_at=_now(),
        updated_at=_now(),
    )
    ar_b = ARRecord(
        id=uuid.uuid4(),
        tenant_id=TENANT_B,
        invoice_id=invoice_b.id,
        client_id=uuid.uuid4(),
        amount_due=Decimal("999.99"),
        amount_paid=Decimal("0.00"),
        amount_outstanding=Decimal("999.99"),
        status="open",
        due_date=date(2026, 2, 28),
        days_outstanding=0,
        aging_bucket="current",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add_all([ar_a, ar_overdue, ar_b])
    session.flush()

    # --- JournalEntry ---
    je_a = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        entry_date=date(2026, 1, 15),
        entry_timestamp=_now(),
        entry_type="ap_created",
        amount=Decimal("123.45"),
        category="payment_out",
        description="AP created for AUTH-WIRED-001",
        client_id=CLIENT_A,
        program_id=PROGRAM_A,
        exported_to_accounting=False,
        created_at=_now(),
    )
    je_b = JournalEntry(
        id=uuid.uuid4(),
        tenant_id=TENANT_B,
        entry_date=date(2026, 1, 15),
        entry_timestamp=_now(),
        entry_type="ap_created",
        amount=Decimal("200.00"),
        category="payment_out",
        description="AP created for AUTH-WIRED-002",
        exported_to_accounting=False,
        created_at=_now(),
    )
    session.add_all([je_a, je_b])
    session.flush()

    # --- FeeConfig ---
    fee_a = FeeConfig(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        name="Per Claim Fee",
        fee_code="PER_CLAIM",
        calculation_type="per_claim_flat",
        amount=Decimal("2.5000"),
        effective_date=date(2026, 1, 1),
        is_active=True,
        created_at=_now(),
    )
    session.add(fee_a)
    session.flush()

    # --- ProgramBudget + Alert + Snapshot ---
    budget_a = ProgramBudget(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        client_id=CLIENT_A,
        program_id=PROGRAM_A,
        budget_type="annual",
        budget_amount=Decimal("100000.00"),
        spent_to_date=Decimal("25000.00"),
        remaining=Decimal("75000.00"),
        utilization_percentage=Decimal("25.00"),
        burn_rate_daily=Decimal("833.33"),
        burn_rate_weekly=Decimal("5833.33"),
        burn_rate_monthly=Decimal("25000.00"),
        burn_rate_7day_avg=Decimal("833.33"),
        burn_rate_30day_avg=Decimal("833.33"),
        spend_increase_alert_pct=Decimal("25"),
        budget_remaining_alert_pct=Decimal("20"),
        depletion_alert_days=30,
        projected_over_budget=False,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(budget_a)
    session.flush()

    alert_a = ProgramBudgetAlert(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        program_budget_id=budget_a.id,
        alert_type="budget_low",
        severity="warning",
        message="Budget at 25%",
        metric_value=Decimal("25.00"),
        threshold_value=Decimal("20.00"),
        created_at=_now(),
    )
    snapshot_a = ProgramBudgetSnapshot(
        id=uuid.uuid4(),
        program_budget_id=budget_a.id,
        tenant_id=TENANT_A,
        snapshot_date=date(2026, 1, 14),
        spent_to_date=Decimal("24000.00"),
        daily_spend=Decimal("833.33"),
        claim_count=10,
    )
    session.add_all([alert_a, snapshot_a])
    session.flush()

    # --- PaymentVendorConfig ---
    vendor_a = PaymentVendorConfig(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        vendor_type="echo",
        name="Echo Health",
        expected_settlement_days=2,
        is_active=True,
        created_at=_now(),
    )
    session.add(vendor_a)
    session.flush()

    # --- BankAccount ---
    bank_a = BankAccount(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        account_name="Main Operating",
        bank_name="First National",
        routing_number="021000021",
        account_number="123456789012",
        account_type="checking",
        is_active=True,
        created_at=_now(),
    )
    session.add(bank_a)
    session.flush()

    # --- RemittanceConfig ---
    remit_a = RemittanceConfig(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        entity_type="pharmacy",
        delivery_method="sftp",
        format_type="hipaa_835",
        include_pos_adjustment=False,
        is_active=True,
        created_at=_now(),
    )
    session.add(remit_a)
    session.flush()

    # --- SFTPConfig ---
    sftp_a = SFTPConfig(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        name="Pharmacy SFTP",
        host="sftp.pharmacy.com",
        port=22,
        username="billing",
        auth_type="key",
        is_active=True,
        created_at=_now(),
    )
    session.add(sftp_a)
    session.flush()

    # --- FundingConfig + PrefundLedger ---
    funding_a = FundingConfig(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        client_id=CLIENT_A,
        funding_model="prefund",
        prefund_balance=Decimal("50000.00"),
        alert_threshold=Decimal("10000.00"),
        critical_threshold=Decimal("5000.00"),
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(funding_a)
    session.flush()

    ledger_a = PrefundLedger(
        id=uuid.uuid4(),
        funding_config_id=funding_a.id,
        tenant_id=TENANT_A,
        transaction_type="deposit",
        amount=Decimal("50000.00"),
        running_balance=Decimal("50000.00"),
        description="Initial deposit",
        created_at=_now(),
    )
    session.add(ledger_a)
    session.flush()

    session.commit()
    session.close()

    # Expose IDs for assertions
    return {
        "claim_a_id": claim_a.id,
        "claim_b_id": claim_b.id,
        "ap_a_id": ap_a.id,
        "ap_b_id": ap_b.id,
        "batch_a_id": batch_a.id,
        "pay1_amount": pay1.amount,
        "pay2_amount": pay2.amount,
        "batch_total": batch_a.total_amount,
        "invoice_a_id": invoice_a.id,
        "invoice_b_id": invoice_b.id,
        "invoice_a_total": invoice_a.total,
        "ar_a_id": ar_a.id,
        "je_a_id": je_a.id,
        "fee_a_id": fee_a.id,
        "fee_a_amount": fee_a.amount,
        "budget_a_id": budget_a.id,
        "alert_a_id": alert_a.id,
        "vendor_a_id": vendor_a.id,
        "bank_a_id": bank_a.id,
        "remit_a_id": remit_a.id,
        "sftp_a_id": sftp_a.id,
        "funding_a_id": funding_a.id,
        "ledger_a_id": ledger_a.id,
    }


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


class TestWiredClaimsRoutes:
    def test_list_claims_returns_tenant_a_only(self, wired_client, populated_db):
        resp = wired_client.get("/api/v1/billing/claims", headers=HEADERS_A)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(r["auth_number"] == "AUTH-WIRED-001" for r in data)
        assert not any(r["auth_number"] == "AUTH-WIRED-002" for r in data)

    def test_list_claims_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/claims", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/claims", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b), "Tenant isolation violated: claims overlap"

    def test_get_claim_by_id(self, wired_client, populated_db):
        claim_id = populated_db["claim_a_id"]
        resp = wired_client.get(f"/api/v1/billing/claims/{claim_id}", headers=HEADERS_A)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(claim_id)
        assert data["auth_number"] == "AUTH-WIRED-001"

    def test_get_claim_wrong_tenant_returns_404(self, wired_client, populated_db):
        """Tenant B cannot access Tenant A's claim."""
        claim_id = populated_db["claim_a_id"]
        resp = wired_client.get(f"/api/v1/billing/claims/{claim_id}", headers=HEADERS_B)
        assert resp.status_code == 404

    def test_get_claim_financial_precision(self, wired_client, populated_db):
        """net_amount must serialize as Decimal string, not float."""
        claim_id = populated_db["claim_a_id"]
        resp = wired_client.get(f"/api/v1/billing/claims/{claim_id}", headers=HEADERS_A)
        data = resp.json()
        # Verify it's a string representation of a valid Decimal
        net = Decimal(data["net_amount"])
        assert net == Decimal("123.45")
        assert data["net_amount"] == str(net)


# ---------------------------------------------------------------------------
# AP Records
# ---------------------------------------------------------------------------


class TestWiredAPRoutes:
    def test_list_ap_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/ap", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/ap", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_get_ap_by_id(self, wired_client, populated_db):
        ap_id = populated_db["ap_a_id"]
        resp = wired_client.get(f"/api/v1/billing/ap/{ap_id}", headers=HEADERS_A)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(ap_id)
        assert Decimal(data["amount"]) == Decimal("123.45")

    def test_get_ap_wrong_tenant_returns_404(self, wired_client, populated_db):
        ap_id = populated_db["ap_a_id"]
        resp = wired_client.get(f"/api/v1/billing/ap/{ap_id}", headers=HEADERS_B)
        assert resp.status_code == 404

    def test_ap_summary_returns_decimal_totals(self, wired_client, populated_db):
        resp = wired_client.get("/api/v1/billing/ap/summary", headers=HEADERS_A)
        assert resp.status_code == 200
        data = resp.json()
        for row in data:
            # total_amount must be parseable as Decimal
            total = Decimal(row["total_amount"])
            assert total >= Decimal("0.00")

    def test_ap_summary_tenant_isolation(self, wired_client, populated_db):
        resp = wired_client.get("/api/v1/billing/ap/summary", headers=HEADERS_A)
        # Should only contain Tenant A entities
        for row in resp.json():
            assert row["pay_to_entity_name"] != "Other Pharmacy"


# ---------------------------------------------------------------------------
# Payment Batches
# ---------------------------------------------------------------------------


class TestWiredBatchRoutes:
    def test_list_batches_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/payment-batches", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/payment-batches", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_get_batch_by_id(self, wired_client, populated_db):
        batch_id = populated_db["batch_a_id"]
        resp = wired_client.get(f"/api/v1/billing/payment-batches/{batch_id}", headers=HEADERS_A)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(batch_id)
        assert Decimal(data["total_amount"]) == Decimal("300.00")

    def test_get_batch_wrong_tenant_returns_404(self, wired_client, populated_db):
        batch_id = populated_db["batch_a_id"]
        resp = wired_client.get(f"/api/v1/billing/payment-batches/{batch_id}", headers=HEADERS_B)
        assert resp.status_code == 404

    def test_list_batch_payments_returns_correct_payments(self, wired_client, populated_db):
        batch_id = populated_db["batch_a_id"]
        resp = wired_client.get(
            f"/api/v1/billing/payment-batches/{batch_id}/payments", headers=HEADERS_A
        )
        assert resp.status_code == 200
        payments = resp.json()
        assert len(payments) == 2

    def test_batch_total_equals_sum_of_payments(self, wired_client, populated_db):
        """Financial invariant: batch total == sum(payment amounts)."""
        batch_id = populated_db["batch_a_id"]
        batch_resp = wired_client.get(
            f"/api/v1/billing/payment-batches/{batch_id}", headers=HEADERS_A
        )
        pay_resp = wired_client.get(
            f"/api/v1/billing/payment-batches/{batch_id}/payments", headers=HEADERS_A
        )
        batch_total = Decimal(batch_resp.json()["total_amount"])
        payment_sum = sum(Decimal(p["amount"]) for p in pay_resp.json())
        assert batch_total == payment_sum.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def test_list_unmatched_payments(self, wired_client, populated_db):
        resp = wired_client.get("/api/v1/billing/settlement/unmatched", headers=HEADERS_A)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Invoicing Configs & Invoices
# ---------------------------------------------------------------------------


class TestWiredInvoiceRoutes:
    def test_list_invoicing_configs_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/invoicing-configs", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/invoicing-configs", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_list_invoices_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/invoices", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/invoices", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_get_invoice_by_id(self, wired_client, populated_db):
        invoice_id = populated_db["invoice_a_id"]
        resp = wired_client.get(f"/api/v1/billing/invoices/{invoice_id}", headers=HEADERS_A)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(invoice_id)
        assert Decimal(data["total"]) == Decimal("550.00")

    def test_get_invoice_wrong_tenant_returns_404(self, wired_client, populated_db):
        invoice_id = populated_db["invoice_a_id"]
        resp = wired_client.get(f"/api/v1/billing/invoices/{invoice_id}", headers=HEADERS_B)
        assert resp.status_code == 404

    def test_invoice_total_financial_precision(self, wired_client, populated_db):
        """Invoice total must equal claims_subtotal + fees_subtotal + adjustments + late_fees."""
        invoice_id = populated_db["invoice_a_id"]
        resp = wired_client.get(f"/api/v1/billing/invoices/{invoice_id}", headers=HEADERS_A)
        data = resp.json()
        expected_total = (
            Decimal(data["claims_subtotal"])
            + Decimal(data["fees_subtotal"])
            + Decimal(data["adjustments"])
            + Decimal(data["late_fees"])
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert Decimal(data["total"]) == expected_total

    def test_list_invoice_line_items_tenant_scoped(self, wired_client, populated_db):
        invoice_id = populated_db["invoice_a_id"]
        resp = wired_client.get(
            f"/api/v1/billing/invoices/{invoice_id}/line-items", headers=HEADERS_A
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        for item in items:
            assert Decimal(item["amount"]) > Decimal("0.00")

    def test_line_items_wrong_tenant_returns_empty(self, wired_client, populated_db):
        """Tenant B querying Tenant A's invoice line items gets empty list."""
        invoice_id = populated_db["invoice_a_id"]
        resp = wired_client.get(
            f"/api/v1/billing/invoices/{invoice_id}/line-items", headers=HEADERS_B
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# AR Records
# ---------------------------------------------------------------------------


class TestWiredARRoutes:
    def test_list_ar_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/ar", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/ar", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_ar_amounts_are_decimal_strings(self, wired_client, populated_db):
        resp = wired_client.get("/api/v1/billing/ar", headers=HEADERS_A)
        for row in resp.json():
            Decimal(row["amount_due"])
            Decimal(row["amount_paid"])
            Decimal(row["amount_outstanding"])

    def test_ar_aging_buckets_sum_to_total(self, wired_client, populated_db):
        """AR aging total_outstanding == sum of buckets — financial invariant."""
        resp = wired_client.get("/api/v1/billing/ar/aging", headers=HEADERS_A)
        assert resp.status_code == 200
        data = resp.json()
        bucket_sum = (
            Decimal(data["current"])
            + Decimal(data["days_30"])
            + Decimal(data["days_60"])
            + Decimal(data["days_90"])
            + Decimal(data["days_120_plus"])
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert Decimal(data["total_outstanding"]) == bucket_sum

    def test_ar_aging_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/ar/aging", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/ar/aging", headers=HEADERS_B)
        total_a = Decimal(resp_a.json()["total_outstanding"])
        total_b = Decimal(resp_b.json()["total_outstanding"])
        # Tenant A has 550 + 200 = 750 outstanding; Tenant B has 999.99
        assert total_a == Decimal("750.00")
        assert total_b == Decimal("999.99")


# ---------------------------------------------------------------------------
# Journal (READ-ONLY verification)
# ---------------------------------------------------------------------------


class TestWiredJournalRoutes:
    def test_query_journal_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/journal", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/journal", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_journal_amounts_are_decimal_strings(self, wired_client, populated_db):
        resp = wired_client.get("/api/v1/billing/journal", headers=HEADERS_A)
        for entry in resp.json():
            Decimal(entry["amount"])

    def test_journal_summary_financial_precision(self, wired_client, populated_db):
        resp = wired_client.get("/api/v1/billing/journal/summary", headers=HEADERS_A)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_amount" in data
        # Must be a valid Decimal
        Decimal(data["total_amount"])

    def test_journal_no_post_route_exists(self, wired_client, populated_db):
        """Journal is read-only — there must be NO POST /journal endpoint."""
        # Attempting POST should get 405 (Method Not Allowed) or 404
        resp = wired_client.post("/api/v1/billing/journal", json={}, headers=HEADERS_A)
        assert resp.status_code in (404, 405)

    def test_journal_no_delete_route_exists(self, wired_client, populated_db):
        """Journal is append-only — DELETE must not exist."""
        je_id = populated_db["je_a_id"]
        resp = wired_client.delete(f"/api/v1/billing/journal/{je_id}", headers=HEADERS_A)
        assert resp.status_code in (404, 405)

    def test_journal_no_put_route_exists(self, wired_client, populated_db):
        """Journal is immutable — PUT must not exist."""
        je_id = populated_db["je_a_id"]
        resp = wired_client.put(f"/api/v1/billing/journal/{je_id}", json={}, headers=HEADERS_A)
        assert resp.status_code in (404, 405)

    def test_journal_filter_by_unexported_only(self, wired_client, populated_db):
        resp = wired_client.get(
            "/api/v1/billing/journal?unexported_only=true", headers=HEADERS_A
        )
        assert resp.status_code == 200
        for entry in resp.json():
            assert entry["exported_to_accounting"] is False


# ---------------------------------------------------------------------------
# Fee Configs
# ---------------------------------------------------------------------------


class TestWiredFeeRoutes:
    def test_list_fees_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/fees", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/fees", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_fee_amount_decimal_precision(self, wired_client, populated_db):
        """Fee amounts must be Decimal strings (NUMERIC(12,4) stored)."""
        resp = wired_client.get("/api/v1/billing/fees", headers=HEADERS_A)
        for fee in resp.json():
            if fee["amount"] is not None:
                amt = Decimal(fee["amount"])
                assert amt >= Decimal("0")


# ---------------------------------------------------------------------------
# Program Budgets
# ---------------------------------------------------------------------------


class TestWiredBudgetRoutes:
    def test_list_budgets_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/program-budgets", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/program-budgets", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_budget_dashboard_by_id(self, wired_client, populated_db):
        budget_id = populated_db["budget_a_id"]
        resp = wired_client.get(
            f"/api/v1/billing/program-budgets/{budget_id}/dashboard", headers=HEADERS_A
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(budget_id)
        assert Decimal(data["budget_amount"]) == Decimal("100000.00")
        assert Decimal(data["spent_to_date"]) == Decimal("25000.00")

    def test_budget_dashboard_remaining_financial_precision(self, wired_client, populated_db):
        """remaining = budget_amount - spent_to_date (ROUND_HALF_UP)."""
        budget_id = populated_db["budget_a_id"]
        resp = wired_client.get(
            f"/api/v1/billing/program-budgets/{budget_id}/dashboard", headers=HEADERS_A
        )
        data = resp.json()
        expected = (Decimal(data["budget_amount"]) - Decimal(data["spent_to_date"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        assert Decimal(data["remaining"]) == expected

    def test_budget_dashboard_wrong_tenant_returns_404(self, wired_client, populated_db):
        budget_id = populated_db["budget_a_id"]
        resp = wired_client.get(
            f"/api/v1/billing/program-budgets/{budget_id}/dashboard", headers=HEADERS_B
        )
        assert resp.status_code == 404

    def test_list_budget_snapshots(self, wired_client, populated_db):
        budget_id = populated_db["budget_a_id"]
        resp = wired_client.get(
            f"/api/v1/billing/program-budgets/{budget_id}/snapshots", headers=HEADERS_A
        )
        assert resp.status_code == 200
        snapshots = resp.json()
        assert len(snapshots) >= 1
        for s in snapshots:
            Decimal(s["spent_to_date"])
            Decimal(s["daily_spend"])

    def test_list_budget_alerts(self, wired_client, populated_db):
        budget_id = populated_db["budget_a_id"]
        resp = wired_client.get(
            f"/api/v1/billing/program-budgets/{budget_id}/alerts", headers=HEADERS_A
        )
        assert resp.status_code == 200
        alerts = resp.json()
        assert len(alerts) >= 1
        for a in alerts:
            if a["metric_value"] is not None:
                Decimal(a["metric_value"])


# ---------------------------------------------------------------------------
# Config routes: Payment Vendors, Bank Accounts, Remittance, SFTP
# ---------------------------------------------------------------------------


class TestWiredConfigRoutes:
    def test_list_payment_vendors_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/payment-vendors", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/payment-vendors", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_list_bank_accounts_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/bank-accounts", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/bank-accounts", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_bank_account_number_masked(self, wired_client, populated_db):
        """Only last 4 digits of account number are returned."""
        resp = wired_client.get("/api/v1/billing/bank-accounts", headers=HEADERS_A)
        for account in resp.json():
            assert "account_number_last4" in account
            assert len(account["account_number_last4"]) == 4
            assert "account_number" not in account  # full number never exposed

    def test_list_remittance_configs_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/remittance-configs", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/remittance-configs", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_list_sftp_configs_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/sftp-configs", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/sftp-configs", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------


class TestWiredRoutingRulesRoutes:
    def test_list_routing_rules_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/routing-rules", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/routing-rules", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_routing_rules_ordered_by_priority(self, wired_client, populated_db):
        resp = wired_client.get("/api/v1/billing/routing-rules", headers=HEADERS_A)
        priorities = [r["priority"] for r in resp.json()]
        assert priorities == sorted(priorities)


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


class TestWiredFundingRoutes:
    def test_list_funding_configs_tenant_isolation(self, wired_client, populated_db):
        resp_a = wired_client.get("/api/v1/billing/funding", headers=HEADERS_A)
        resp_b = wired_client.get("/api/v1/billing/funding", headers=HEADERS_B)
        ids_a = {r["id"] for r in resp_a.json()}
        ids_b = {r["id"] for r in resp_b.json()}
        assert ids_a.isdisjoint(ids_b)

    def test_funding_balance_is_decimal(self, wired_client, populated_db):
        resp = wired_client.get("/api/v1/billing/funding", headers=HEADERS_A)
        for config in resp.json():
            Decimal(config["prefund_balance"])

    def test_list_funding_ledger(self, wired_client, populated_db):
        funding_id = populated_db["funding_a_id"]
        resp = wired_client.get(f"/api/v1/billing/funding/{funding_id}/ledger", headers=HEADERS_A)
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) >= 1
        for entry in entries:
            Decimal(entry["amount"])
            Decimal(entry["running_balance"])

    def test_funding_ledger_wrong_tenant_returns_empty(self, wired_client, populated_db):
        funding_id = populated_db["funding_a_id"]
        resp = wired_client.get(f"/api/v1/billing/funding/{funding_id}/ledger", headers=HEADERS_B)
        assert resp.status_code == 200
        assert resp.json() == []
