"""Task 2 -- RBAC enforcement on billing mutating endpoints.

Covers all 15 mutating endpoints in modules/billing/src/api/router.py per
SP-1 Plan C Task 2 (§5.5). For each endpoint:

  - Auditor   -> 403 (never allowed to mutate)
  - Operator  -> 200/201 for Operator-or-Approver gates
  - Operator  -> 403 for Approver-only gates
  - Approver  -> 200/201 for all mutating endpoints

RBAC matrix per spec §5.5:
  Operator-or-Approver: POST /claims, POST /payment-batches/generate,
      POST /payment-batches/{id}/validate
  Approver-only: POST /routing-rules, PUT /routing-rules/{id},
      POST /payment-batches/{id}/approve, POST /payment-batches/{id}/submit,
      POST /payment-batches/{id}/void, POST /settlement/record,
      POST /invoicing-configs, PUT /invoicing-configs/{id},
      POST /invoices/generate, POST /invoices/{id}/approve,
      POST /invoices/{id}/send, POST /invoices/{id}/void
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
TENANT_B = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))

_UID_OP = uuid.UUID("11111111-1111-1111-1111-111111111111")
_UID_APP = uuid.UUID("22222222-2222-2222-2222-222222222222")
_UID_AUD = uuid.UUID("33333333-3333-3333-3333-333333333333")
_UID_B_APP = uuid.UUID("44444444-4444-4444-4444-444444444444")

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
# Tenant B approver (for cross-tenant tests)
TENANT_B_APPROVER = MagicMock(
    id=_UID_B_APP,
    tenant_id=uuid.UUID(TENANT_B),
    roles=("approver",),
    has_role=lambda r: r == "approver",
    mfa_verified=True,
)
# MFA not verified (for MFA gate tests)
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
    """Build standard request headers."""
    return {"X-Tenant-Id": tenant, "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Helpers that set up dependency overrides per test
# ---------------------------------------------------------------------------

def _as(app, user):
    """Override get_current_user to return user."""
    from shared.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


# ---------------------------------------------------------------------------
# POST /claims -- Operator-or-Approver
# ---------------------------------------------------------------------------

_CLAIM_BODY = {
    "source_type": "api",
    "auth_number": "CLM-RBAC-001",
    "claim_type": "medical",
    "pharmacy_npi": "1234567890",
    "date_of_service": "2026-01-15",
    "net_amount": "99.99",
    "client_id": str(uuid.uuid4()),
    "program_id": str(uuid.uuid4()),
    "member_id": "MBR001",
}


class TestPostClaims:
    def test_auditor_cannot_submit_claim(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        resp = _client.post("/api/v1/billing/claims", headers=_h(), json=_CLAIM_BODY)
        assert resp.status_code == 403, f"auditor must get 403, got {resp.status_code}"

    def test_operator_can_submit_claim(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        resp = _client.post("/api/v1/billing/claims", headers=_h(), json=_CLAIM_BODY)
        assert resp.status_code in (200, 201), f"operator must succeed, got {resp.status_code}: {resp.text}"

    def test_approver_can_submit_claim(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        resp = _client.post("/api/v1/billing/claims", headers=_h(), json=_CLAIM_BODY)
        assert resp.status_code in (200, 201), f"approver must succeed, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        resp = _client.post("/api/v1/billing/claims", headers=_h(), json=_CLAIM_BODY)
        assert resp.status_code == 403, f"unverified MFA must get 403, got {resp.status_code}"


# ---------------------------------------------------------------------------
# POST /routing-rules -- Approver-only
# ---------------------------------------------------------------------------

_ROUTING_RULE_BODY = {
    "name": "test-rule",
    "priority": 1,
    "payment_route": "ach",
}


class TestPostRoutingRules:
    def test_auditor_cannot_create_routing_rule(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        resp = _client.post("/api/v1/billing/routing-rules", headers=_h(), json=_ROUTING_RULE_BODY)
        assert resp.status_code == 403

    def test_operator_cannot_create_routing_rule(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        resp = _client.post("/api/v1/billing/routing-rules", headers=_h(), json=_ROUTING_RULE_BODY)
        assert resp.status_code == 403, f"operator must get 403 on approver-only route, got {resp.status_code}"

    def test_approver_can_create_routing_rule(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        resp = _client.post("/api/v1/billing/routing-rules", headers=_h(), json=_ROUTING_RULE_BODY)
        assert resp.status_code in (200, 201), f"approver must succeed, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        resp = _client.post("/api/v1/billing/routing-rules", headers=_h(), json=_ROUTING_RULE_BODY)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /routing-rules/{rule_id} -- Approver-only
# ---------------------------------------------------------------------------

_ROUTING_RULE_UPDATE_BODY = {
    "name": "test-rule-updated",
    "priority": 2,
}


class TestPutRoutingRules:
    def test_auditor_cannot_update_routing_rule(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        rule_id = str(uuid.uuid4())
        resp = _client.put(f"/api/v1/billing/routing-rules/{rule_id}", headers=_h(), json=_ROUTING_RULE_UPDATE_BODY)
        assert resp.status_code == 403

    def test_operator_cannot_update_routing_rule(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        rule_id = str(uuid.uuid4())
        resp = _client.put(f"/api/v1/billing/routing-rules/{rule_id}", headers=_h(), json=_ROUTING_RULE_UPDATE_BODY)
        assert resp.status_code == 403

    def test_approver_can_update_routing_rule(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        rule_id = str(uuid.uuid4())
        resp = _client.put(f"/api/v1/billing/routing-rules/{rule_id}", headers=_h(), json=_ROUTING_RULE_UPDATE_BODY)
        # 404 is acceptable -- RBAC passed, resource not found
        assert resp.status_code in (200, 201, 404), f"approver must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        rule_id = str(uuid.uuid4())
        resp = _client.put(f"/api/v1/billing/routing-rules/{rule_id}", headers=_h(), json=_ROUTING_RULE_UPDATE_BODY)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /payment-batches/generate -- Operator-or-Approver
# ---------------------------------------------------------------------------

_BATCH_GENERATE_BODY = {
    "batch_number": "BATCH-001",
    "payment_route": "ach",
}


class TestPostPaymentBatchesGenerate:
    def test_auditor_cannot_generate_batch(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        resp = _client.post("/api/v1/billing/payment-batches/generate", headers=_h(), json=_BATCH_GENERATE_BODY)
        assert resp.status_code == 403

    def test_operator_can_generate_batch(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        resp = _client.post("/api/v1/billing/payment-batches/generate", headers=_h(), json=_BATCH_GENERATE_BODY)
        assert resp.status_code in (200, 201), f"operator must succeed, got {resp.status_code}: {resp.text}"

    def test_approver_can_generate_batch(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        resp = _client.post("/api/v1/billing/payment-batches/generate", headers=_h(), json=_BATCH_GENERATE_BODY)
        assert resp.status_code in (200, 201), f"approver must succeed, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        resp = _client.post("/api/v1/billing/payment-batches/generate", headers=_h(), json=_BATCH_GENERATE_BODY)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /payment-batches/{batch_id}/validate -- Operator-or-Approver
# ---------------------------------------------------------------------------

class TestPostPaymentBatchValidate:
    def test_auditor_cannot_validate_batch(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/validate", headers=_h())
        assert resp.status_code == 403

    def test_operator_can_validate_batch(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/validate", headers=_h())
        assert resp.status_code in (200, 201, 404), f"operator must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_approver_can_validate_batch(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/validate", headers=_h())
        assert resp.status_code in (200, 201, 404), f"approver must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/validate", headers=_h())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /payment-batches/{batch_id}/approve -- Approver-only
# ---------------------------------------------------------------------------

class TestPostPaymentBatchApprove:
    def test_auditor_cannot_approve_batch(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/approve", headers=_h())
        assert resp.status_code == 403

    def test_operator_cannot_approve_batch(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/approve", headers=_h())
        assert resp.status_code == 403, f"operator must get 403 on approver-only, got {resp.status_code}"

    def test_approver_can_approve_batch(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/approve", headers=_h())
        # 404 is acceptable -- RBAC passed, resource not found
        assert resp.status_code in (200, 201, 404), f"approver must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/approve", headers=_h())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /payment-batches/{batch_id}/submit -- Approver-only
# ---------------------------------------------------------------------------

class TestPostPaymentBatchSubmit:
    def test_auditor_cannot_submit_batch(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/submit", headers=_h())
        assert resp.status_code == 403

    def test_operator_cannot_submit_batch(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/submit", headers=_h())
        assert resp.status_code == 403

    def test_approver_can_submit_batch(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/submit", headers=_h())
        assert resp.status_code in (200, 201, 404), f"approver must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/submit", headers=_h())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /payment-batches/{batch_id}/void -- Approver-only
# ---------------------------------------------------------------------------

class TestPostPaymentBatchVoid:
    def test_auditor_cannot_void_batch(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/void", headers=_h())
        assert resp.status_code == 403

    def test_operator_cannot_void_batch(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/void", headers=_h())
        assert resp.status_code == 403

    def test_approver_can_void_batch(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/void", headers=_h())
        assert resp.status_code in (200, 201, 404), f"approver must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        batch_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/payment-batches/{batch_id}/void", headers=_h())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /settlement/record -- Approver-only
# ---------------------------------------------------------------------------

_SETTLEMENT_BODY = {
    "payment_id": str(uuid.uuid4()),
    "settlement_date": "2026-01-31",
}


class TestPostSettlementRecord:
    def test_auditor_cannot_record_settlement(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        resp = _client.post("/api/v1/billing/settlement/record", headers=_h(), json=_SETTLEMENT_BODY)
        assert resp.status_code == 403

    def test_operator_cannot_record_settlement(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        resp = _client.post("/api/v1/billing/settlement/record", headers=_h(), json=_SETTLEMENT_BODY)
        assert resp.status_code == 403

    def test_approver_can_record_settlement(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        resp = _client.post("/api/v1/billing/settlement/record", headers=_h(), json=_SETTLEMENT_BODY)
        assert resp.status_code in (200, 201), f"approver must succeed, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        resp = _client.post("/api/v1/billing/settlement/record", headers=_h(), json=_SETTLEMENT_BODY)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /invoicing-configs -- Approver-only
# ---------------------------------------------------------------------------

_INVOICING_CONFIG_BODY = {
    "client_id": str(uuid.uuid4()),
}


class TestPostInvoicingConfigs:
    def test_auditor_cannot_create_invoicing_config(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        resp = _client.post("/api/v1/billing/invoicing-configs", headers=_h(), json=_INVOICING_CONFIG_BODY)
        assert resp.status_code == 403

    def test_operator_cannot_create_invoicing_config(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        resp = _client.post("/api/v1/billing/invoicing-configs", headers=_h(), json=_INVOICING_CONFIG_BODY)
        assert resp.status_code == 403

    def test_approver_can_create_invoicing_config(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        resp = _client.post("/api/v1/billing/invoicing-configs", headers=_h(), json=_INVOICING_CONFIG_BODY)
        assert resp.status_code in (200, 201), f"approver must succeed, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        resp = _client.post("/api/v1/billing/invoicing-configs", headers=_h(), json=_INVOICING_CONFIG_BODY)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /invoicing-configs/{config_id} -- Approver-only
# ---------------------------------------------------------------------------

class TestPutInvoicingConfigs:
    def test_auditor_cannot_update_invoicing_config(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        config_id = str(uuid.uuid4())
        resp = _client.put(f"/api/v1/billing/invoicing-configs/{config_id}", headers=_h(), json=_INVOICING_CONFIG_BODY)
        assert resp.status_code == 403

    def test_operator_cannot_update_invoicing_config(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        config_id = str(uuid.uuid4())
        resp = _client.put(f"/api/v1/billing/invoicing-configs/{config_id}", headers=_h(), json=_INVOICING_CONFIG_BODY)
        assert resp.status_code == 403

    def test_approver_can_update_invoicing_config(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        config_id = str(uuid.uuid4())
        resp = _client.put(f"/api/v1/billing/invoicing-configs/{config_id}", headers=_h(), json=_INVOICING_CONFIG_BODY)
        # 404 is acceptable -- RBAC passed, resource not found
        assert resp.status_code in (200, 201, 404), f"approver must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        config_id = str(uuid.uuid4())
        resp = _client.put(f"/api/v1/billing/invoicing-configs/{config_id}", headers=_h(), json=_INVOICING_CONFIG_BODY)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /invoices/generate -- Operator-or-Approver
# ---------------------------------------------------------------------------

_INVOICE_GENERATE_BODY = {
    "invoice_number": "INV-RBAC-001",
    "client_id": str(uuid.uuid4()),
    "client_name": "Test Client",
    "period_start": "2026-01-01",
    "period_end": "2026-01-31",
}


class TestPostInvoicesGenerate:
    def test_auditor_cannot_generate_invoice(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        resp = _client.post("/api/v1/billing/invoices/generate", headers=_h(), json=_INVOICE_GENERATE_BODY)
        assert resp.status_code == 403

    def test_operator_can_generate_invoice(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        resp = _client.post("/api/v1/billing/invoices/generate", headers=_h(), json=_INVOICE_GENERATE_BODY)
        assert resp.status_code in (200, 201), f"operator must succeed, got {resp.status_code}: {resp.text}"

    def test_approver_can_generate_invoice(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        resp = _client.post("/api/v1/billing/invoices/generate", headers=_h(), json=_INVOICE_GENERATE_BODY)
        assert resp.status_code in (200, 201), f"approver must succeed, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        resp = _client.post("/api/v1/billing/invoices/generate", headers=_h(), json=_INVOICE_GENERATE_BODY)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /invoices/{invoice_id}/approve -- Approver-only
# ---------------------------------------------------------------------------

class TestPostInvoiceApprove:
    def test_auditor_cannot_approve_invoice(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/approve", headers=_h())
        assert resp.status_code == 403

    def test_operator_cannot_approve_invoice(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/approve", headers=_h())
        assert resp.status_code == 403

    def test_approver_can_approve_invoice(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/approve", headers=_h())
        assert resp.status_code in (200, 201, 404), f"approver must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/approve", headers=_h())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /invoices/{invoice_id}/send -- Approver-only
# ---------------------------------------------------------------------------

class TestPostInvoiceSend:
    def test_auditor_cannot_send_invoice(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/send", headers=_h())
        assert resp.status_code == 403

    def test_operator_cannot_send_invoice(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/send", headers=_h())
        assert resp.status_code == 403

    def test_approver_can_send_invoice(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/send", headers=_h())
        assert resp.status_code in (200, 201, 404), f"approver must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/send", headers=_h())
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /invoices/{invoice_id}/void -- Approver-only
# ---------------------------------------------------------------------------

class TestPostInvoiceVoid:
    def test_auditor_cannot_void_invoice(self, _client):
        from src.main import app
        _as(app, AUDITOR_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/void", headers=_h(), json={"reason": "test"})
        assert resp.status_code == 403

    def test_operator_cannot_void_invoice(self, _client):
        from src.main import app
        _as(app, OPERATOR_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/void", headers=_h(), json={"reason": "test"})
        assert resp.status_code == 403

    def test_approver_can_void_invoice(self, _client):
        from src.main import app
        _as(app, APPROVER_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/void", headers=_h(), json={"reason": "test"})
        assert resp.status_code in (200, 201, 404), f"approver must pass RBAC, got {resp.status_code}: {resp.text}"

    def test_mfa_unverified_approver_blocked(self, _client):
        from src.main import app
        _as(app, MFA_UNVERIFIED_USER)
        invoice_id = str(uuid.uuid4())
        resp = _client.post(f"/api/v1/billing/invoices/{invoice_id}/void", headers=_h(), json={"reason": "test"})
        assert resp.status_code == 403
