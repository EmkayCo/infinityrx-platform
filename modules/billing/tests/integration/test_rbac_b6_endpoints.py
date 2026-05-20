"""B6 RBAC enforcement — previously unguarded mutating endpoints.

All endpoints are approver-only per spec §5.5:
  POST /ar/{id}/payment
  POST /ar/{id}/dispute
  POST /ar/{id}/write-off
  POST /journal/close-period
  POST /fees
  PUT  /fees/{id}
  POST /program-budgets
  PUT  /program-budgets/{id}
  POST /program-budgets/{id}/alerts/{id}/acknowledge
  POST /payment-vendors
  PUT  /payment-vendors/{id}
  POST /bank-accounts
  PUT  /bank-accounts/{id}
  PUT  /accounting/config
  POST /remittance-configs
  POST /sftp-configs
  POST /sftp-configs/{id}/test
  PUT  /funding/{id}
  POST /funding/{id}/deposit
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TENANT_A = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))

_UID_OP = uuid.UUID("11111111-1111-1111-1111-111111111111")
_UID_APP = uuid.UUID("22222222-2222-2222-2222-222222222222")
_UID_AUD = uuid.UUID("33333333-3333-3333-3333-333333333333")

OPERATOR_USER = MagicMock(
    id=_UID_OP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("operator",),
    has_role=lambda r: r == "operator",
    mfa_verified=True,
)
APPROVER_USER = MagicMock(
    id=_UID_APP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("approver",),
    has_role=lambda r: r == "approver",
    mfa_verified=True,
)
AUDITOR_USER = MagicMock(
    id=_UID_AUD,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("auditor",),
    has_role=lambda r: r == "auditor",
    mfa_verified=True,
)
MFA_UNVERIFIED_USER = MagicMock(
    id=_UID_APP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("approver",),
    has_role=lambda r: r == "approver",
    mfa_verified=False,
)


@pytest.fixture(scope="module")
def _engine():
    from src.models.tables import BillingBase

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in BillingBase.metadata.tables.values():
        table.schema = None
    BillingBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def _session_factory(_engine):
    return sessionmaker(bind=_engine, expire_on_commit=False)


@pytest.fixture()
def _client(_engine, _session_factory):
    from src.api.dependencies import get_db
    from src.db.session import set_engine
    from src.main import app

    set_engine(_engine)

    def override_db() -> Iterator[Session]:
        session = _session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _h(tenant: str = TENANT_A) -> dict[str, str]:
    return {"X-Tenant-Id": tenant, "Content-Type": "application/json"}


def _as(app, user):
    from shared.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


# Helper: run the 4-case RBAC matrix for an endpoint (auditor→403, operator→403,
# approver→2xx/404, mfa_unverified→403)
def _check_approver_only(client, method: str, path: str, body: dict | None = None):
    from src.main import app

    # Auditor blocked
    _as(app, AUDITOR_USER)
    r = getattr(client, method)(path, headers=_h(), json=body)
    assert r.status_code == 403, f"auditor must be blocked on {path}: {r.status_code} {r.text}"

    # Operator blocked (approver-only gate)
    _as(app, OPERATOR_USER)
    r = getattr(client, method)(path, headers=_h(), json=body)
    assert r.status_code == 403, f"operator must be blocked on approver-only {path}: {r.status_code} {r.text}"

    # Approver passes RBAC gate (may get 404 for non-existent resource — still passes auth)
    _as(app, APPROVER_USER)
    r = getattr(client, method)(path, headers=_h(), json=body)
    assert r.status_code in (200, 201, 404), f"approver must pass RBAC on {path}: {r.status_code} {r.text}"

    # MFA unverified blocked
    _as(app, MFA_UNVERIFIED_USER)
    r = getattr(client, method)(path, headers=_h(), json=body)
    assert r.status_code == 403, f"mfa_unverified must be blocked on {path}: {r.status_code} {r.text}"


# ---------------------------------------------------------------------------
# AR mutations
# ---------------------------------------------------------------------------

class TestArPaymentRbac:
    def test_ar_payment_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            f"/api/v1/billing/ar/{uuid.uuid4()}/payment",
            {"amount": "100.00", "payment_method": "check", "payment_date": "2026-05-01"},
        )


class TestArDisputeRbac:
    def test_ar_dispute_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            f"/api/v1/billing/ar/{uuid.uuid4()}/dispute",
            {"reason": "invalid_charge"},
        )


class TestArWriteOffRbac:
    def test_ar_write_off_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            f"/api/v1/billing/ar/{uuid.uuid4()}/write-off",
            {"reason": "uncollectable", "approved_by": str(uuid.uuid4())},
        )


# ---------------------------------------------------------------------------
# Journal close
# ---------------------------------------------------------------------------

class TestJournalClosePeriodRbac:
    def test_journal_close_period_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            "/api/v1/billing/journal/close-period",
            {"period_end": "2026-04-30"},
        )


# ---------------------------------------------------------------------------
# Fee configs
# ---------------------------------------------------------------------------

class TestFeesPostRbac:
    def test_fees_post_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            "/api/v1/billing/fees",
            {"client_id": str(uuid.uuid4()), "fee_code": "ADMIN", "fee_name": "Admin Fee", "calculation_type": "flat"},
        )


class TestFeesPutRbac:
    def test_fees_put_approver_only(self, _client):
        _check_approver_only(
            _client, "put",
            f"/api/v1/billing/fees/{uuid.uuid4()}",
            {"rate": "0.06"},
        )


# ---------------------------------------------------------------------------
# Program budgets
# ---------------------------------------------------------------------------

class TestProgramBudgetsPostRbac:
    def test_program_budgets_post_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            "/api/v1/billing/program-budgets",
            {"client_id": str(uuid.uuid4()), "program_id": str(uuid.uuid4()), "budget_type": "annual", "budget_amount": "100000.00"},
        )


class TestProgramBudgetsPutRbac:
    def test_program_budgets_put_approver_only(self, _client):
        _check_approver_only(
            _client, "put",
            f"/api/v1/billing/program-budgets/{uuid.uuid4()}",
            {"budget_amount": "120000.00"},
        )


class TestBudgetAlertAcknowledgeRbac:
    def test_budget_alert_acknowledge_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            f"/api/v1/billing/program-budgets/{uuid.uuid4()}/alerts/{uuid.uuid4()}/acknowledge",
        )


# ---------------------------------------------------------------------------
# Payment vendors
# ---------------------------------------------------------------------------

class TestPaymentVendorsPostRbac:
    def test_payment_vendors_post_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            "/api/v1/billing/payment-vendors",
            {"vendor_name": "Test Vendor", "vendor_type": "ach"},
        )


class TestPaymentVendorsPutRbac:
    def test_payment_vendors_put_approver_only(self, _client):
        _check_approver_only(
            _client, "put",
            f"/api/v1/billing/payment-vendors/{uuid.uuid4()}",
            {"vendor_name": "Updated Vendor", "vendor_type": "ach"},
        )


# ---------------------------------------------------------------------------
# Bank accounts
# ---------------------------------------------------------------------------

class TestBankAccountsPostRbac:
    def test_bank_accounts_post_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            "/api/v1/billing/bank-accounts",
            {"account_name": "Main", "bank_name": "Test Bank", "routing_number": "021000021", "account_number": "123456789", "account_type": "checking", "purpose": "disbursement"},
        )


class TestBankAccountsPutRbac:
    def test_bank_accounts_put_approver_only(self, _client):
        _check_approver_only(
            _client, "put",
            f"/api/v1/billing/bank-accounts/{uuid.uuid4()}",
            {"account_name": "Updated", "bank_name": "Test Bank", "routing_number": "021000021", "account_number": "987654321", "account_type": "checking", "purpose": "disbursement"},
        )


# ---------------------------------------------------------------------------
# Accounting config
# ---------------------------------------------------------------------------

class TestAccountingConfigPutRbac:
    def test_accounting_config_put_approver_only(self, _client):
        _check_approver_only(
            _client, "put",
            "/api/v1/billing/accounting/config",
            {"accounting_system": "quickbooks"},
        )


# ---------------------------------------------------------------------------
# Remittance configs
# ---------------------------------------------------------------------------

class TestRemittanceConfigsPostRbac:
    def test_remittance_configs_post_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            "/api/v1/billing/remittance-configs",
            {"client_id": str(uuid.uuid4()), "delivery_method": "sftp", "format": "835"},
        )


# ---------------------------------------------------------------------------
# SFTP configs
# ---------------------------------------------------------------------------

class TestSftpConfigsPostRbac:
    def test_sftp_configs_post_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            "/api/v1/billing/sftp-configs",
            {"config_name": "test", "host": "sftp.example.com", "port": 22, "username": "user", "auth_type": "password", "remote_path": "/out"},
        )


class TestSftpConfigsTestRbac:
    def test_sftp_configs_test_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            f"/api/v1/billing/sftp-configs/{uuid.uuid4()}/test",
        )


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------

class TestFundingPutRbac:
    def test_funding_put_approver_only(self, _client):
        _check_approver_only(
            _client, "put",
            f"/api/v1/billing/funding/{uuid.uuid4()}",
            {"funding_model": "prefund"},
        )


class TestFundingDepositRbac:
    def test_funding_deposit_approver_only(self, _client):
        _check_approver_only(
            _client, "post",
            f"/api/v1/billing/funding/{uuid.uuid4()}/deposit",
            {"amount": "50000.00", "deposit_date": "2026-05-01"},
        )
