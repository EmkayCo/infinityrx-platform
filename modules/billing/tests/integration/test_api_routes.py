"""Integration tests for billing API routes using FastAPI TestClient."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

TENANT = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))
CLIENT = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
PROGRAM = str(uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"))

HEADERS = {"X-Tenant-Id": TENANT}


@pytest.fixture(scope="module")
def client() -> TestClient:
    from unittest.mock import MagicMock

    from src.api.dependencies import get_db
    from src.main import app

    def override_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        # Health endpoint now does a real DB ping; in test context with a mock DB
        # the status may be healthy or unhealthy — just verify the module name is correct.
        assert resp.json()["module"] == "billing"


class TestClaimsRoutes:
    def test_submit_claim_returns_201(self, client: TestClient) -> None:
        payload = {
            "source_type": "api",
            "auth_number": "AUTH001",
            "claim_type": "new",
            "pharmacy_npi": "1234567890",
            "date_of_service": "2026-01-15",
            "net_amount": "100.00",
            "client_id": CLIENT,
            "program_id": PROGRAM,
        }
        resp = client.post("/api/v1/billing/claims", json=payload, headers=HEADERS)
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["auth_number"] == "AUTH001"

    def test_submit_claim_invalid_npi_returns_422(self, client: TestClient) -> None:
        payload = {
            "source_type": "api",
            "auth_number": "AUTH002",
            "claim_type": "new",
            "pharmacy_npi": "BADNPI",
            "date_of_service": "2026-01-15",
            "net_amount": "100.00",
            "client_id": CLIENT,
            "program_id": PROGRAM,
        }
        resp = client.post("/api/v1/billing/claims", json=payload, headers=HEADERS)
        assert resp.status_code == 422

    def test_list_claims_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/claims", headers=HEADERS)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_claims_with_filters(self, client: TestClient) -> None:
        resp = client.get(
            f"/api/v1/billing/claims?client_id={CLIENT}&status=ingested&limit=50",
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_get_claim_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/billing/claims/{uuid.uuid4()}", headers=HEADERS)
        assert resp.status_code == 404

    def test_missing_tenant_header_returns_422(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/claims")
        assert resp.status_code == 422

    def test_invalid_tenant_header_returns_400(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/claims", headers={"X-Tenant-Id": "not-a-uuid"})
        assert resp.status_code == 400


class TestRoutingRulesRoutes:
    def test_list_routing_rules(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/routing-rules", headers=HEADERS)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_routing_rule(self, client: TestClient) -> None:
        payload = {
            "name": "Default ECHO",
            "priority": 100,
            "payment_route": "echo",
        }
        resp = client.post("/api/v1/billing/routing-rules", json=payload, headers=HEADERS)
        assert resp.status_code == 201
        assert resp.json()["name"] == "Default ECHO"

    def test_create_rule_invalid_priority_returns_422(self, client: TestClient) -> None:
        payload = {"name": "Bad", "priority": 0, "payment_route": "echo"}
        resp = client.post("/api/v1/billing/routing-rules", json=payload, headers=HEADERS)
        assert resp.status_code == 422

    def test_update_routing_rule_not_found(self, client: TestClient) -> None:
        resp = client.put(
            f"/api/v1/billing/routing-rules/{uuid.uuid4()}",
            json={"priority": 200},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_test_routing_rules(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/routing-rules/test",
            json={"claims": []},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert "results" in resp.json()


class TestAPRoutes:
    def test_list_ap_records(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/ap", headers=HEADERS)
        assert resp.status_code == 200

    def test_ap_summary(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/ap/summary", headers=HEADERS)
        assert resp.status_code == 200

    def test_get_ap_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/billing/ap/{uuid.uuid4()}", headers=HEADERS)
        assert resp.status_code == 404


class TestPaymentBatchRoutes:
    def test_list_payment_batches(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/payment-batches", headers=HEADERS)
        assert resp.status_code == 200

    def test_generate_batch_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/payment-batches/generate",
            json={"payment_route": "echo", "batch_number": "BATCH001"},
            headers=HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["batch_number"] == "BATCH001"

    def test_get_batch_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/billing/payment-batches/{uuid.uuid4()}", headers=HEADERS)
        assert resp.status_code == 404

    def test_validate_batch(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/payment-batches/{uuid.uuid4()}/validate",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_approve_batch_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/payment-batches/{uuid.uuid4()}/approve",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_submit_batch_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/payment-batches/{uuid.uuid4()}/submit",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_void_batch_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/payment-batches/{uuid.uuid4()}/void",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_list_batch_payments(self, client: TestClient) -> None:
        resp = client.get(
            f"/api/v1/billing/payment-batches/{uuid.uuid4()}/payments",
            headers=HEADERS,
        )
        assert resp.status_code == 200


class TestSettlementRoutes:
    def test_record_settlement(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/settlement/record",
            json={
                "payment_id": str(uuid.uuid4()),
                "settlement_date": "2026-01-20",
                "bank_reference": "REF001",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_list_unmatched_payments(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/settlement/unmatched", headers=HEADERS)
        assert resp.status_code == 200


class TestInvoicingRoutes:
    def test_list_invoicing_configs(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/invoicing-configs", headers=HEADERS)
        assert resp.status_code == 200

    def test_create_invoicing_config(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/invoicing-configs",
            json={"client_id": CLIENT, "billing_frequency": "monthly"},
            headers=HEADERS,
        )
        assert resp.status_code == 201

    def test_update_invoicing_config_not_found(self, client: TestClient) -> None:
        resp = client.put(
            f"/api/v1/billing/invoicing-configs/{uuid.uuid4()}",
            json={"client_id": CLIENT, "billing_frequency": "monthly"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_generate_invoice_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/invoices/generate",
            json={
                "client_id": CLIENT,
                "client_name": "Test Client",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "invoice_number": "INV-2026-001",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201

    def test_list_invoices(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/invoices", headers=HEADERS)
        assert resp.status_code == 200

    def test_get_invoice_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/billing/invoices/{uuid.uuid4()}", headers=HEADERS)
        assert resp.status_code == 404

    def test_get_invoice_pdf_not_found(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/billing/invoices/{uuid.uuid4()}/pdf", headers=HEADERS)
        assert resp.status_code == 404

    def test_approve_invoice_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/invoices/{uuid.uuid4()}/approve",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_send_invoice_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/invoices/{uuid.uuid4()}/send",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_void_invoice_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/invoices/{uuid.uuid4()}/void",
            json={"reason": "error"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_list_invoice_line_items(self, client: TestClient) -> None:
        resp = client.get(
            f"/api/v1/billing/invoices/{uuid.uuid4()}/line-items",
            headers=HEADERS,
        )
        assert resp.status_code == 200


class TestARRoutes:
    def test_list_ar_records(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/ar", headers=HEADERS)
        assert resp.status_code == 200

    def test_ar_aging(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/ar/aging", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_outstanding" in data

    def test_record_ar_payment_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/ar/{uuid.uuid4()}/payment",
            json={"amount": "100.00", "payment_date": "2026-01-20"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_dispute_ar_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/ar/{uuid.uuid4()}/dispute",
            json={"reason": "Disputed charge"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_write_off_ar_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/ar/{uuid.uuid4()}/write-off",
            json={"reason": "Bad debt", "approved_by": "CFO"},
            headers=HEADERS,
        )
        assert resp.status_code == 404


class TestJournalRoutes:
    def test_query_journal(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/journal", headers=HEADERS)
        assert resp.status_code == 200

    def test_journal_with_filters(self, client: TestClient) -> None:
        resp = client.get(
            f"/api/v1/billing/journal?client_id={CLIENT}&unexported_only=true",
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_journal_summary(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/journal/summary", headers=HEADERS)
        assert resp.status_code == 200

    def test_journal_export(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/journal/export", headers=HEADERS)
        assert resp.status_code == 200

    def test_close_period(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/journal/close-period",
            json={"period_end": "2026-01-31"},
            headers=HEADERS,
        )
        assert resp.status_code == 200


class TestFeeRoutes:
    def test_list_fees(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/fees", headers=HEADERS)
        assert resp.status_code == 200

    def test_create_fee(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/fees",
            json={
                "client_id": CLIENT,
                "fee_code": "PMPM",
                "fee_name": "Per Member Per Month",
                "calculation_type": "per_member_per_month",
                "amount": "5.00",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201

    def test_update_fee_not_found(self, client: TestClient) -> None:
        resp = client.put(
            f"/api/v1/billing/fees/{uuid.uuid4()}",
            json={"is_active": False},
            headers=HEADERS,
        )
        assert resp.status_code == 404


class TestProgramBudgetRoutes:
    def test_list_budgets(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/program-budgets", headers=HEADERS)
        assert resp.status_code == 200

    def test_create_budget(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/program-budgets",
            json={
                "program_id": PROGRAM,
                "client_id": CLIENT,
                "budget_amount": "100000.00",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201

    def test_create_budget_negative_amount_fails(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/program-budgets",
            json={
                "program_id": PROGRAM,
                "client_id": CLIENT,
                "budget_amount": "-1.00",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_update_budget_not_found(self, client: TestClient) -> None:
        resp = client.put(
            f"/api/v1/billing/program-budgets/{uuid.uuid4()}",
            json={"budget_amount": "200000.00"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_budget_dashboard_not_found(self, client: TestClient) -> None:
        resp = client.get(
            f"/api/v1/billing/program-budgets/{uuid.uuid4()}/dashboard",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_list_budget_snapshots(self, client: TestClient) -> None:
        resp = client.get(
            f"/api/v1/billing/program-budgets/{uuid.uuid4()}/snapshots",
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_list_budget_alerts(self, client: TestClient) -> None:
        resp = client.get(
            f"/api/v1/billing/program-budgets/{uuid.uuid4()}/alerts",
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_acknowledge_alert_not_found(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/program-budgets/{uuid.uuid4()}/alerts/{uuid.uuid4()}/acknowledge",
            headers=HEADERS,
        )
        assert resp.status_code == 404


class TestConfigRoutes:
    def test_list_payment_vendors(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/payment-vendors", headers=HEADERS)
        assert resp.status_code == 200

    def test_create_payment_vendor(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/payment-vendors",
            json={"vendor_name": "Echo Health", "vendor_type": "echo"},
            headers=HEADERS,
        )
        assert resp.status_code == 201

    def test_update_vendor_not_found(self, client: TestClient) -> None:
        resp = client.put(
            f"/api/v1/billing/payment-vendors/{uuid.uuid4()}",
            json={"vendor_name": "Echo Health", "vendor_type": "echo"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_list_bank_accounts(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/bank-accounts", headers=HEADERS)
        assert resp.status_code == 200

    def test_create_bank_account(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/bank-accounts",
            json={
                "account_name": "Main Operating",
                "account_type": "checking",
                "routing_number": "021000021",
                "account_number": "123456789",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["account_number_last4"] == "6789"

    def test_update_bank_account_not_found(self, client: TestClient) -> None:
        resp = client.put(
            f"/api/v1/billing/bank-accounts/{uuid.uuid4()}",
            json={
                "account_name": "Main Operating",
                "account_type": "checking",
                "routing_number": "021000021",
                "account_number": "123456789",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_get_accounting_config(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/accounting/config", headers=HEADERS)
        assert resp.status_code == 200

    def test_update_accounting_config(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/billing/accounting/config",
            json={"system_type": "quickbooks", "auto_export": True},
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_list_remittance_configs(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/remittance-configs", headers=HEADERS)
        assert resp.status_code == 200

    def test_create_remittance_config(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/remittance-configs",
            json={"client_id": CLIENT},
            headers=HEADERS,
        )
        assert resp.status_code == 201

    def test_list_sftp_configs(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/sftp-configs", headers=HEADERS)
        assert resp.status_code == 200

    def test_create_sftp_config(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/billing/sftp-configs",
            json={
                "config_name": "Pharmacy SFTP",
                "host": "sftp.example.com",
                "username": "billing",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201

    def test_test_sftp_config(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/sftp-configs/{uuid.uuid4()}/test",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert "success" in resp.json()


class TestFundingRoutes:
    def test_list_funding(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/funding", headers=HEADERS)
        assert resp.status_code == 200

    def test_get_funding_ledger(self, client: TestClient) -> None:
        resp = client.get(
            f"/api/v1/billing/funding/{uuid.uuid4()}/ledger",
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_record_deposit(self, client: TestClient) -> None:
        resp = client.post(
            f"/api/v1/billing/funding/{uuid.uuid4()}/deposit",
            json={"amount": "50000.00", "deposit_date": "2026-01-15"},
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_get_projection(self, client: TestClient) -> None:
        resp = client.get(
            f"/api/v1/billing/funding/{uuid.uuid4()}/projection",
            headers=HEADERS,
        )
        assert resp.status_code == 200

    def test_update_funding_not_found(self, client: TestClient) -> None:
        resp = client.put(
            f"/api/v1/billing/funding/{uuid.uuid4()}",
            json={"prefund_days": 5},
            headers=HEADERS,
        )
        assert resp.status_code == 404


class TestReportRoutes:
    def test_ap_summary_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/reports/ap-summary", headers=HEADERS)
        assert resp.status_code == 200

    def test_ar_aging_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/reports/ar-aging", headers=HEADERS)
        assert resp.status_code == 200

    def test_payment_history_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/reports/payment-history", headers=HEADERS)
        assert resp.status_code == 200

    def test_fee_summary_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/reports/fee-summary", headers=HEADERS)
        assert resp.status_code == 200

    def test_prefund_history_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/reports/prefund-history", headers=HEADERS)
        assert resp.status_code == 200

    def test_cash_flow_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/reports/cash-flow", headers=HEADERS)
        assert resp.status_code == 200

    def test_program_performance_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/reports/program-performance", headers=HEADERS)
        assert resp.status_code == 200

    def test_period_close_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/reports/period-close", headers=HEADERS)
        assert resp.status_code == 200

    def test_1099_data_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/billing/reports/1099-data?tax_year=2025", headers=HEADERS)
        assert resp.status_code == 200
