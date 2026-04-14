"""Billing module API router — /api/v1/billing/"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from src.api.dependencies import DBSession, TenantId
from src.api.schemas.ap import (
    BatchGenerateRequest,
    BatchValidateResponse,
    SettlementRecordRequest,
)
from src.api.schemas.ar import (
    ARAgingResponse,
    ARDisputeRequest,
    ARPaymentRequest,
    ARWriteOffRequest,
    FeeConfigCreateRequest,
    FeeConfigUpdateRequest,
    InvoiceGenerateRequest,
    InvoicingConfigCreateRequest,
)
from src.api.schemas.claims import (
    ClaimSubmitRequest,
)
from src.api.schemas.config import (
    AccountingConfigUpdateRequest,
    BankAccountCreateRequest,
    FundingDepositRequest,
    PaymentVendorCreateRequest,
    RemittanceConfigCreateRequest,
    SFTPConfigCreateRequest,
    SFTPTestResponse,
)
from src.api.schemas.journal import (
    PeriodCloseRequest,
    ProgramBudgetCreateRequest,
    ProgramBudgetUpdateRequest,
)
from src.api.schemas.routing import (
    RoutingRuleCreateRequest,
    RoutingRuleUpdateRequest,
    RoutingTestRequest,
    RoutingTestResponse,
)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


@router.post("/claims", status_code=status.HTTP_201_CREATED, response_model=dict)
async def submit_claim(
    body: ClaimSubmitRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Submit a single claim via API."""
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "status": "ingested",
        "auth_number": body.auth_number,
    }


@router.get("/claims", response_model=list[dict])
async def list_claims(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    program_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    claim_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List claims with optional filters."""
    return []


@router.get("/claims/{claim_id}", response_model=dict)
async def get_claim(
    claim_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get claim detail by ID."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------


@router.get("/routing-rules", response_model=list[dict])
async def list_routing_rules(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List routing rules ordered by priority."""
    return []


@router.post("/routing-rules", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_routing_rule(
    body: RoutingRuleCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Create a new routing rule."""
    return {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), **body.model_dump()}


@router.put("/routing-rules/{rule_id}", response_model=dict)
async def update_routing_rule(
    rule_id: uuid.UUID,
    body: RoutingRuleUpdateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Update an existing routing rule."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")


@router.post("/routing-rules/test", response_model=RoutingTestResponse)
async def test_routing_rules(
    body: RoutingTestRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> RoutingTestResponse:
    """Test routing rules against sample claims."""
    return RoutingTestResponse(results=[])


# ---------------------------------------------------------------------------
# AP Records
# ---------------------------------------------------------------------------


@router.get("/ap", response_model=list[dict])
async def list_ap_records(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    pay_to_entity_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    payment_route: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List AP records."""
    return []


@router.get("/ap/summary", response_model=list[dict])
async def ap_summary(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """AP summary grouped by entity and status."""
    return []


@router.get("/ap/{ap_id}", response_model=dict)
async def get_ap_record(
    ap_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get AP record detail."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AP record not found")


# ---------------------------------------------------------------------------
# Payment Batches
# ---------------------------------------------------------------------------


@router.get("/payment-batches", response_model=list[dict])
async def list_payment_batches(
    tenant_id: TenantId,
    db: DBSession,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List payment batches."""
    return []


@router.post("/payment-batches/generate", status_code=status.HTTP_201_CREATED, response_model=dict)
async def generate_payment_batch(
    body: BatchGenerateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Generate a payment batch for a given route."""
    return {"id": str(uuid.uuid4()), "status": "generated", "batch_number": body.batch_number}


@router.get("/payment-batches/{batch_id}", response_model=dict)
async def get_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get payment batch detail."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")


@router.post("/payment-batches/{batch_id}/validate", response_model=BatchValidateResponse)
async def validate_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> BatchValidateResponse:
    """Validate a payment batch before submission."""
    return BatchValidateResponse(valid=True, errors=[])


@router.post("/payment-batches/{batch_id}/approve", response_model=dict)
async def approve_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Approve a payment batch."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")


@router.post("/payment-batches/{batch_id}/submit", response_model=dict)
async def submit_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Submit a payment batch to vendor."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")


@router.post("/payment-batches/{batch_id}/void", response_model=dict)
async def void_payment_batch(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Void a payment batch."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")


@router.get("/payment-batches/{batch_id}/payments", response_model=list[dict])
async def list_batch_payments(
    batch_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List payments in a batch."""
    return []


# ---------------------------------------------------------------------------
# Settlement
# ---------------------------------------------------------------------------


@router.post("/settlement/record", status_code=status.HTTP_200_OK, response_model=dict)
async def record_settlement(
    body: SettlementRecordRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Manually record a settlement."""
    return {"payment_id": str(body.payment_id), "status": "settled"}


@router.get("/settlement/unmatched", response_model=list[dict])
async def list_unmatched_payments(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List payments not yet matched to a settlement."""
    return []


# ---------------------------------------------------------------------------
# Invoicing Configs
# ---------------------------------------------------------------------------


@router.get("/invoicing-configs", response_model=list[dict])
async def list_invoicing_configs(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List invoicing configurations."""
    return []


@router.post("/invoicing-configs", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_invoicing_config(
    body: InvoicingConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Create invoicing configuration for a client."""
    return {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), **body.model_dump()}


@router.put("/invoicing-configs/{config_id}", response_model=dict)
async def update_invoicing_config(
    config_id: uuid.UUID,
    body: InvoicingConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Update invoicing configuration."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@router.get("/invoices", response_model=list[dict])
async def list_invoices(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List invoices."""
    return []


@router.post("/invoices/generate", status_code=status.HTTP_201_CREATED, response_model=dict)
async def generate_invoice(
    body: InvoiceGenerateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Generate a new invoice for a client and period."""
    return {"id": str(uuid.uuid4()), "status": "draft", "invoice_number": body.invoice_number}


@router.get("/invoices/{invoice_id}", response_model=dict)
async def get_invoice(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get invoice detail."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.get("/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> Any:
    """Download invoice PDF."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.post("/invoices/{invoice_id}/approve", response_model=dict)
async def approve_invoice(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Approve a draft invoice."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.post("/invoices/{invoice_id}/send", response_model=dict)
async def send_invoice(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Send invoice to client."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.post("/invoices/{invoice_id}/void", response_model=dict)
async def void_invoice(
    invoice_id: uuid.UUID,
    body: dict,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Void an invoice."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


@router.get("/invoices/{invoice_id}/line-items", response_model=list[dict])
async def list_invoice_line_items(
    invoice_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List line items for an invoice."""
    return []


# ---------------------------------------------------------------------------
# AR Records
# ---------------------------------------------------------------------------


@router.get("/ar", response_model=list[dict])
async def list_ar_records(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List AR records."""
    return []


@router.get("/ar/aging", response_model=ARAgingResponse)
async def get_ar_aging(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
) -> ARAgingResponse:
    """Get AR aging report."""
    zero = Decimal("0.00")
    return ARAgingResponse(
        current=zero,
        days_30=zero,
        days_60=zero,
        days_90=zero,
        days_120_plus=zero,
        total_outstanding=zero,
    )


@router.post("/ar/{ar_id}/payment", status_code=status.HTTP_200_OK, response_model=dict)
async def record_ar_payment(
    ar_id: uuid.UUID,
    body: ARPaymentRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Record a payment against an AR record."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AR record not found")


@router.post("/ar/{ar_id}/dispute", status_code=status.HTTP_200_OK, response_model=dict)
async def dispute_ar_record(
    ar_id: uuid.UUID,
    body: ARDisputeRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Open a dispute on an AR record."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AR record not found")


@router.post("/ar/{ar_id}/write-off", status_code=status.HTTP_200_OK, response_model=dict)
async def write_off_ar_record(
    ar_id: uuid.UUID,
    body: ARWriteOffRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Write off an AR record (admin only)."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AR record not found")


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


@router.get("/journal", response_model=list[dict])
async def query_journal(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    program_id: uuid.UUID | None = Query(default=None),
    category: str | None = Query(default=None),
    entry_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    unexported_only: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """Query journal entries with filters."""
    return []


@router.get("/journal/summary", response_model=dict)
async def journal_summary(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, Any]:
    """Get journal period summary."""
    return {}


@router.get("/journal/export", response_model=dict)
async def export_journal(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    """Export journal entries to accounting system."""
    return {"export_reference": "", "entry_count": 0}


@router.post("/journal/close-period", response_model=dict)
async def close_period(
    body: PeriodCloseRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Close an accounting period."""
    return {"period_end": str(body.period_end), "status": "closed"}


# ---------------------------------------------------------------------------
# Fee Configs
# ---------------------------------------------------------------------------


@router.get("/fees", response_model=list[dict])
async def list_fee_configs(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
) -> list[dict]:
    """List fee configurations."""
    return []


@router.post("/fees", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_fee_config(
    body: FeeConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Create a fee configuration."""
    return {"id": str(uuid.uuid4()), **body.model_dump()}


@router.put("/fees/{fee_id}", response_model=dict)
async def update_fee_config(
    fee_id: uuid.UUID,
    body: FeeConfigUpdateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Update a fee configuration."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fee config not found")


# ---------------------------------------------------------------------------
# Program Budgets
# ---------------------------------------------------------------------------


@router.get("/program-budgets", response_model=list[dict])
async def list_program_budgets(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    program_id: uuid.UUID | None = Query(default=None),
) -> list[dict]:
    """List program budgets."""
    return []


@router.post("/program-budgets", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_program_budget(
    body: ProgramBudgetCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Create a program budget."""
    return {"id": str(uuid.uuid4()), "tenant_id": str(tenant_id), **body.model_dump()}


@router.put("/program-budgets/{budget_id}", response_model=dict)
async def update_program_budget(
    budget_id: uuid.UUID,
    body: ProgramBudgetUpdateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Update a program budget."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")


@router.get("/program-budgets/{budget_id}/dashboard", response_model=dict)
async def budget_dashboard(
    budget_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get budget dashboard data."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")


@router.get("/program-budgets/{budget_id}/snapshots", response_model=list[dict])
async def list_budget_snapshots(
    budget_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List budget historical snapshots."""
    return []


@router.get("/program-budgets/{budget_id}/alerts", response_model=list[dict])
async def list_budget_alerts(
    budget_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List alerts for a program budget."""
    return []


@router.post(
    "/program-budgets/{budget_id}/alerts/{alert_id}/acknowledge",
    response_model=dict,
)
async def acknowledge_budget_alert(
    budget_id: uuid.UUID,
    alert_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Acknowledge a budget alert."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")


# ---------------------------------------------------------------------------
# Payment Vendors
# ---------------------------------------------------------------------------


@router.get("/payment-vendors", response_model=list[dict])
async def list_payment_vendors(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List payment vendor configurations."""
    return []


@router.post("/payment-vendors", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_payment_vendor(
    body: PaymentVendorCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Create a payment vendor configuration."""
    return {"id": str(uuid.uuid4()), **body.model_dump()}


@router.put("/payment-vendors/{vendor_id}", response_model=dict)
async def update_payment_vendor(
    vendor_id: uuid.UUID,
    body: PaymentVendorCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Update a payment vendor configuration."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor not found")


# ---------------------------------------------------------------------------
# Bank Accounts
# ---------------------------------------------------------------------------


@router.get("/bank-accounts", response_model=list[dict])
async def list_bank_accounts(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List bank accounts."""
    return []


@router.post("/bank-accounts", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_bank_account(
    body: BankAccountCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Create a bank account."""
    return {"id": str(uuid.uuid4()), "account_number_last4": body.account_number[-4:]}


@router.put("/bank-accounts/{account_id}", response_model=dict)
async def update_bank_account(
    account_id: uuid.UUID,
    body: BankAccountCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Update a bank account."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")


# ---------------------------------------------------------------------------
# Accounting Config
# ---------------------------------------------------------------------------


@router.get("/accounting/config", response_model=dict)
async def get_accounting_config(
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get accounting system configuration."""
    return {}


@router.put("/accounting/config", response_model=dict)
async def update_accounting_config(
    body: AccountingConfigUpdateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Update accounting system configuration."""
    return body.model_dump(exclude_none=True)


# ---------------------------------------------------------------------------
# Remittance Configs
# ---------------------------------------------------------------------------


@router.get("/remittance-configs", response_model=list[dict])
async def list_remittance_configs(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List remittance configurations."""
    return []


@router.post("/remittance-configs", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_remittance_config(
    body: RemittanceConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Create a remittance configuration."""
    return {"id": str(uuid.uuid4()), **body.model_dump()}


# ---------------------------------------------------------------------------
# SFTP Configs
# ---------------------------------------------------------------------------


@router.get("/sftp-configs", response_model=list[dict])
async def list_sftp_configs(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List SFTP configurations."""
    return []


@router.post("/sftp-configs", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_sftp_config(
    body: SFTPConfigCreateRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Create an SFTP configuration."""
    return {"id": str(uuid.uuid4()), "host": body.host, "config_name": body.config_name}


@router.post("/sftp-configs/{config_id}/test", response_model=SFTPTestResponse)
async def test_sftp_config(
    config_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> SFTPTestResponse:
    """Test SFTP connection."""
    return SFTPTestResponse(success=False, message="Config not found")


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


@router.get("/funding", response_model=list[dict])
async def list_funding_configs(
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """List funding configurations."""
    return []


@router.put("/funding/{config_id}", response_model=dict)
async def update_funding_config(
    config_id: uuid.UUID,
    body: dict,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Update funding configuration."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")


@router.get("/funding/{config_id}/ledger", response_model=list[dict])
async def get_funding_ledger(
    config_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> list[dict]:
    """Get prefund ledger for a funding config."""
    return []


@router.post("/funding/{config_id}/deposit", status_code=status.HTTP_200_OK, response_model=dict)
async def record_funding_deposit(
    config_id: uuid.UUID,
    body: FundingDepositRequest,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Record a prefund deposit."""
    return {"config_id": str(config_id), "amount": str(body.amount), "status": "recorded"}


@router.get("/funding/{config_id}/projection", response_model=dict)
async def get_funding_projection(
    config_id: uuid.UUID,
    tenant_id: TenantId,
    db: DBSession,
) -> dict[str, Any]:
    """Get burn rate projection for a funding config."""
    return {}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/reports/ap-summary", response_model=dict)
async def report_ap_summary(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    """AP summary report."""
    return {}


@router.get("/reports/ar-aging", response_model=dict)
async def report_ar_aging(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    """AR aging report."""
    return {}


@router.get("/reports/payment-history", response_model=list[dict])
async def report_payment_history(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict]:
    """Payment history report."""
    return []


@router.get("/reports/fee-summary", response_model=dict)
async def report_fee_summary(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, Any]:
    """Fee summary report."""
    return {}


@router.get("/reports/prefund-history", response_model=list[dict])
async def report_prefund_history(
    tenant_id: TenantId,
    db: DBSession,
    client_id: uuid.UUID | None = Query(default=None),
) -> list[dict]:
    """Prefund history report."""
    return []


@router.get("/reports/cash-flow", response_model=dict)
async def report_cash_flow(
    tenant_id: TenantId,
    db: DBSession,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, Any]:
    """Cash flow report (inflows vs outflows)."""
    return {}


@router.get("/reports/program-performance", response_model=dict)
async def report_program_performance(
    tenant_id: TenantId,
    db: DBSession,
    program_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> dict[str, Any]:
    """Program spend vs budget performance report."""
    return {}


@router.get("/reports/period-close", response_model=dict)
async def report_period_close(
    tenant_id: TenantId,
    db: DBSession,
    period_end: date | None = Query(default=None),
) -> dict[str, Any]:
    """Period close summary report."""
    return {}


@router.get("/reports/1099-data", response_model=list[dict])
async def report_1099_data(
    tenant_id: TenantId,
    db: DBSession,
    tax_year: int = Query(default=2025, ge=2020, le=2099),
) -> list[dict]:
    """1099 data for a tax year."""
    return []
