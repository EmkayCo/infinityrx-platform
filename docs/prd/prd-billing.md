# PRD — Module 11: Billing & Financial (v3 — FINAL)

**Module:** Billing & Financial  
**Folder:** `modules/billing/`  
**Priority:** Phase 2, Batch A  
**Dependencies:** Core Platform (Module 1)  

---

## 1. Purpose

The Billing module is the financial engine of the InfinityRx platform. It has four independent subsystems:

1. **Claims Ingestion & Routing** — claims enter, get classified, and routed to the correct payment path
2. **Accounts Payable (AP)** — what you owe pharmacies/providers. Creates AP records, generates payment batches, tracks settlement.
3. **Accounts Receivable (AR)** — what clients owe you. Generates invoices on the client's cycle, creates AR records, tracks client payments.
4. **Financial Journal** — chronological record of every financial event, tagged to client and program. Source of truth for accounting.

AP and AR are SEPARATE processes on SEPARATE cycles. A daily Echo payment creates and settles an AP immediately. That same claim doesn't appear on an invoice until the client's invoicing cycle runs — days or weeks later. The financial journal records both events independently.

---

## 2. Architecture

```
                        CLAIMS INGESTION
                        ════════════════
Adjudication ──┐
               ├──► Ingest ──► Classify ──► Route
Upload ────────┤                   │
API ───────────┘                   │
                                   ├──► AP Record ────► Journal Entry
                                   │
                              ┌────┴────┐
                              │         │
                         AP ENGINE   AR ENGINE
                         ═════════   ═════════
                              │         │
                    Payment Schedule  Invoicing Cycle
                              │         │
                    Payment Batch    Invoice + Fees
                              │         │
                         ┌────┤    ┌────┤
                         │    │    │    │
                    835   Payment  PDF   AR Record
                         │         │
                    Submit to      Deliver to
                    Vendor         Client
                         │         │
                    Settlement  Client Payment
                         │         │
                    AP Settled   AR Settled
                         │         │
                    Journal     Journal
                    Entry       Entry
                              
              PROGRAM FINANCIAL MONITORING
              ════════════════════════════
              Budget │ Spent │ Burn Rate │ Projection │ Alerts
```

---

## 3. Core Concepts

### 3.1 Claims Ingestion
Claims enter from three configurable sources:
- **Internal**: From Module 8 adjudication. Automatic — no upload needed.
- **External upload**: Operator uploads file. Configurable format mapping (any delimiter, any column layout, any file structure).
- **API**: External system pushes claims via REST endpoint.

Claims are processed as they arrive. There is no monolithic "batch close" for ingestion.

### 3.2 Claim Classification & Routing
Every claim is classified on ingestion using a rules engine:

**Payment route** — determined by configurable routing rules evaluated in priority order. Rules match on NRID, program, pharmacy, claim type, payer, or custom fields. First match wins. Routes include:
- Third-party vendor (Echo, Zelis, etc.)
- Check issuance vendor
- Direct ACH
- Excluded (payment outside this system)
- Statement (report only, no payment)

A single program can have claims going to multiple routes simultaneously.

**Pay-to entity** — resolved via configurable waterfall hierarchy per tenant/program (e.g., PSAO → chain → pharmacy NPI, or any custom order).

### 3.3 AP Records
Every payable claim creates an AP record. Even daily vendor payments create APs — they just settle faster than weekly ACH payments. AP is the single record of "we owe this entity this amount for this claim."

States: `CREATED → SCHEDULED → SUBMITTED → SETTLED | RETURNED | FAILED`

### 3.4 Payment Batches
APs are grouped into payment batches per schedule per route. A daily Echo route generates a payment batch every morning with all APs created since the last batch. A weekly ACH route generates one every Friday. Each batch produces one payment per pay-to entity.

### 3.5 AR / Invoicing
Completely separate from AP. The invoicing engine runs on the CLIENT's configured cycle (weekly, semi-monthly, monthly, custom). When triggered, it pulls all claims processed since the last invoice, calculates fees, generates the invoice, and creates an AR record. The AR engine tracks whether the client has paid.

### 3.6 Financial Journal
Every financial event creates a journal entry — tagged to tenant, client, program, entity, and category. The journal is the source of truth for accounting. All accounting exports (QuickBooks, NetSuite, etc.) are generated FROM the journal. Accountants book entries from system reports, not bank statements.

### 3.7 Funding Models
Configurable per client per tenant:
- **Prefund**: Client pre-deposits funds. AP payments draw from prefund. AR invoices trigger replenishment.
- **Claims fund**: Client is invoiced. Client payment funds the next AP cycle.
- **Pass-through**: Platform generates payment instructions. Client funds directly. Platform invoices for fees only.

### 3.8 Automation Levels
Every step configurable between fully manual, semi-automatic, and fully automatic — independently for AP and AR.

---

## 4. Data Model

```sql
CREATE SCHEMA billing;

-- ═══════════════════════════════════════════════
-- CLAIMS INGESTION & ROUTING
-- ═══════════════════════════════════════════════

CREATE TABLE billing.claim_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- Source
    source_type VARCHAR(50) NOT NULL,
    source_file_id UUID,
    source_claim_id UUID,
    
    -- Claim identifiers
    auth_number VARCHAR(50) NOT NULL,
    reversal_of_auth VARCHAR(50),
    claim_type VARCHAR(50) NOT NULL,                 -- new, reversal, adjustment, compound
    
    -- Claim data
    member_id VARCHAR(100),
    pharmacy_npi VARCHAR(10) NOT NULL,
    pharmacy_name VARCHAR(255),
    prescriber_npi VARCHAR(10),
    ndc VARCHAR(11),
    drug_name VARCHAR(255),
    quantity DECIMAL(10,3),
    days_supply INTEGER,
    date_of_service DATE NOT NULL,
    date_received TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Program / routing
    program_id UUID,
    program_name VARCHAR(255),
    client_id UUID,
    client_name VARCHAR(255),
    network_reimbursement_id VARCHAR(50),
    
    -- Amounts (ALL Decimal, ROUND_HALF_UP)
    ingredient_cost DECIMAL(12,2) DEFAULT 0,
    dispensing_fee DECIMAL(12,2) DEFAULT 0,
    patient_pay DECIMAL(12,2) DEFAULT 0,
    plan_pay DECIMAL(12,2) DEFAULT 0,
    other_payer_amount DECIMAL(12,2) DEFAULT 0,
    net_amount DECIMAL(12,2) NOT NULL,
    under_reimbursement DECIMAL(12,2) DEFAULT 0,
    
    -- Classification (set during routing)
    payment_route VARCHAR(100),
    payment_vendor_config_id UUID,
    payment_schedule VARCHAR(100),
    pay_to_entity_id UUID,
    pay_to_entity_name VARCHAR(255),
    is_excluded BOOLEAN DEFAULT FALSE,
    exclusion_reason VARCHAR(255),
    is_statement BOOLEAN DEFAULT FALSE,
    
    -- Status
    status VARCHAR(50) DEFAULT 'ingested',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, auth_number)
);

CREATE INDEX idx_claims_tenant_status ON billing.claim_records(tenant_id, status);
CREATE INDEX idx_claims_tenant_dos ON billing.claim_records(tenant_id, date_of_service);
CREATE INDEX idx_claims_tenant_client ON billing.claim_records(tenant_id, client_id);
CREATE INDEX idx_claims_nrid ON billing.claim_records(tenant_id, network_reimbursement_id);

-- Routing rules
CREATE TABLE billing.routing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    
    -- Match criteria (null = match all)
    match_nrid VARCHAR(50),
    match_program_id UUID,
    match_pharmacy_npi VARCHAR(10),
    match_claim_type VARCHAR(50),
    match_client_id UUID,
    match_conditions JSONB,
    
    -- Action
    payment_route VARCHAR(100) NOT NULL,
    payment_vendor_config_id UUID,
    payment_schedule VARCHAR(100),
    notes TEXT,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pay-to waterfall
CREATE TABLE billing.payto_waterfall (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    program_id UUID,
    priority INTEGER NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

-- File format mappings (for external uploads)
CREATE TABLE billing.file_format_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,                  -- csv, fixed_width, excel, custom
    delimiter VARCHAR(5),
    has_header BOOLEAN DEFAULT TRUE,
    column_mappings JSONB NOT NULL,                   -- [{source_column, target_field, transform}, ...]
    validation_rules JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- ACCOUNTS PAYABLE
-- ═══════════════════════════════════════════════

CREATE TABLE billing.ap_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    claim_record_id UUID NOT NULL REFERENCES billing.claim_records(id),
    
    client_id UUID NOT NULL,
    client_name VARCHAR(255),
    program_id UUID,
    program_name VARCHAR(255),
    
    pay_to_entity_id UUID NOT NULL,
    pay_to_entity_name VARCHAR(255) NOT NULL,
    pay_to_npi VARCHAR(10),
    
    amount DECIMAL(12,2) NOT NULL,
    payment_route VARCHAR(100) NOT NULL,
    payment_vendor_config_id UUID,
    payment_schedule VARCHAR(100),
    
    status VARCHAR(50) DEFAULT 'created',
    payment_batch_id UUID,
    settlement_date DATE,
    return_code VARCHAR(10),
    return_reason TEXT,
    
    is_carryover BOOLEAN DEFAULT FALSE,
    carryover_from_id UUID,
    carryover_reason VARCHAR(255),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ap_tenant_status ON billing.ap_records(tenant_id, status);
CREATE INDEX idx_ap_payto ON billing.ap_records(tenant_id, pay_to_entity_id);
CREATE INDEX idx_ap_client ON billing.ap_records(tenant_id, client_id);
CREATE INDEX idx_ap_batch ON billing.ap_records(payment_batch_id);

-- Payment batches
CREATE TABLE billing.payment_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    batch_number VARCHAR(50) NOT NULL,
    
    payment_route VARCHAR(100) NOT NULL,
    payment_vendor_config_id UUID,
    
    total_amount DECIMAL(15,2) NOT NULL,
    payment_count INTEGER NOT NULL,
    ap_count INTEGER NOT NULL,
    
    status VARCHAR(50) DEFAULT 'generated',
    
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    validated_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    approved_by UUID,
    submitted_at TIMESTAMPTZ,
    settled_at TIMESTAMPTZ,
    
    validation_result JSONB,
    validation_warnings JSONB,
    
    payment_file_id UUID,
    
    data_lock BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Individual payments within a batch
CREATE TABLE billing.payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_batch_id UUID NOT NULL REFERENCES billing.payment_batches(id),
    tenant_id UUID NOT NULL,
    
    pay_to_entity_id UUID NOT NULL,
    pay_to_entity_name VARCHAR(255) NOT NULL,
    pay_to_npi VARCHAR(10),
    
    amount DECIMAL(12,2) NOT NULL,
    claim_count INTEGER NOT NULL,
    payment_method VARCHAR(50),
    
    bank_routing_number VARCHAR(9),
    bank_account_number VARCHAR(17),
    bank_account_type VARCHAR(10),
    
    status VARCHAR(50) DEFAULT 'pending',
    settlement_date DATE,
    settlement_reference VARCHAR(255),
    check_number VARCHAR(50),
    return_code VARCHAR(10),
    return_reason TEXT,
    
    remittance_file_id UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- ACCOUNTS RECEIVABLE
-- ═══════════════════════════════════════════════

-- Invoicing cycle configuration
CREATE TABLE billing.invoicing_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    
    frequency VARCHAR(50) NOT NULL,
    cycle_dates JSONB,
    day_of_week INTEGER,
    custom_days INTEGER,
    
    include_programs JSONB,
    include_fees BOOLEAN DEFAULT TRUE,
    
    automation_level VARCHAR(50) DEFAULT 'semi_automatic',
    auto_generate_time TIME,
    
    delivery_method VARCHAR(50) DEFAULT 'email',
    delivery_recipients JSONB,
    
    invoice_template_id UUID,
    detail_level VARCHAR(50) DEFAULT 'program',
    payment_terms_days INTEGER DEFAULT 30,
    
    -- Late payment
    late_fee_enabled BOOLEAN DEFAULT FALSE,
    late_fee_type VARCHAR(50),                       -- flat, percentage
    late_fee_amount DECIMAL(12,2),
    late_fee_percentage DECIMAL(8,4),
    late_fee_grace_days INTEGER DEFAULT 0,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Invoices
CREATE TABLE billing.invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    invoicing_config_id UUID REFERENCES billing.invoicing_configs(id),
    
    invoice_number VARCHAR(50) NOT NULL,
    invoice_type VARCHAR(50) NOT NULL,               -- claims, fees, combined, credit_memo
    
    client_id UUID NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    claims_subtotal DECIMAL(15,2) DEFAULT 0,
    fees_subtotal DECIMAL(15,2) DEFAULT 0,
    adjustments DECIMAL(15,2) DEFAULT 0,
    late_fees DECIMAL(15,2) DEFAULT 0,
    total DECIMAL(15,2) NOT NULL,
    
    claim_count INTEGER DEFAULT 0,
    
    status VARCHAR(50) DEFAULT 'draft',
    
    due_date DATE,
    payment_terms_days INTEGER DEFAULT 30,
    
    paid_amount DECIMAL(15,2) DEFAULT 0,
    
    delivered_at TIMESTAMPTZ,
    delivery_method VARCHAR(50),
    
    pdf_file_id UUID,
    
    generated_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    approved_by UUID,
    sent_at TIMESTAMPTZ,
    voided_at TIMESTAMPTZ,
    voided_by UUID,
    void_reason TEXT,
    
    data_lock BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Invoice line items
CREATE TABLE billing.invoice_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES billing.invoices(id),
    tenant_id UUID NOT NULL,
    
    line_type VARCHAR(50) NOT NULL,                  -- claim, fee, adjustment, credit, late_fee
    description VARCHAR(500) NOT NULL,
    
    program_id UUID,
    program_name VARCHAR(255),
    fee_config_id UUID,
    
    quantity INTEGER,
    unit_amount DECIMAL(12,2),
    amount DECIMAL(12,2) NOT NULL,
    
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- AR records
CREATE TABLE billing.ar_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    invoice_id UUID NOT NULL REFERENCES billing.invoices(id),
    client_id UUID NOT NULL,
    
    amount_due DECIMAL(15,2) NOT NULL,
    amount_paid DECIMAL(15,2) DEFAULT 0,
    amount_outstanding DECIMAL(15,2) NOT NULL,
    
    status VARCHAR(50) DEFAULT 'open',               -- open, partially_paid, paid, overdue, disputed, written_off
    due_date DATE NOT NULL,
    
    days_outstanding INTEGER DEFAULT 0,
    aging_bucket VARCHAR(20),                        -- current, 30, 60, 90, 120_plus
    
    -- Dispute tracking
    dispute_reason TEXT,
    dispute_opened_at TIMESTAMPTZ,
    dispute_resolved_at TIMESTAMPTZ,
    dispute_resolution TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- AR payments received from clients
CREATE TABLE billing.ar_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    ar_record_id UUID NOT NULL REFERENCES billing.ar_records(id),
    
    amount DECIMAL(15,2) NOT NULL,
    payment_method VARCHAR(50),
    payment_reference VARCHAR(255),
    payment_date DATE NOT NULL,
    
    recorded_by UUID,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- FINANCIAL JOURNAL
-- ═══════════════════════════════════════════════

CREATE TABLE billing.journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- When
    entry_date DATE NOT NULL,
    entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- What
    entry_type VARCHAR(100) NOT NULL,
    -- Types: ap_created, ap_settled, ap_returned, ap_voided,
    --        payment_submitted, payment_settled, payment_returned,
    --        invoice_generated, invoice_sent, invoice_voided,
    --        ar_created, ar_payment_received, ar_written_off,
    --        prefund_deposit, prefund_deduction,
    --        fee_calculated, adjustment, credit_memo,
    --        late_fee_applied, carryover_created, carryover_resolved
    
    -- Tags (for filtering, reporting, and accounting export)
    client_id UUID,
    client_name VARCHAR(255),
    program_id UUID,
    program_name VARCHAR(255),
    pay_to_entity_id UUID,
    pay_to_entity_name VARCHAR(255),
    
    -- Amounts
    amount DECIMAL(15,2) NOT NULL,
    
    -- Accounting classification
    category VARCHAR(100) NOT NULL,                  -- claims_payable, claims_receivable, processing_fee, admin_fee, prefund, adjustment, late_fee
    gl_account_code VARCHAR(50),                     -- mapped from accounting config
    gl_class VARCHAR(100),                           -- mapped from accounting config
    
    -- Reference
    reference_type VARCHAR(50),                      -- ap_record, payment, invoice, ar_record, prefund_transaction
    reference_id UUID,
    
    description TEXT NOT NULL,
    
    -- Export tracking
    exported_to_accounting BOOLEAN DEFAULT FALSE,
    exported_at TIMESTAMPTZ,
    export_reference VARCHAR(255),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_journal_tenant_date ON billing.journal_entries(tenant_id, entry_date DESC);
CREATE INDEX idx_journal_client ON billing.journal_entries(tenant_id, client_id, entry_date DESC);
CREATE INDEX idx_journal_program ON billing.journal_entries(tenant_id, program_id, entry_date DESC);
CREATE INDEX idx_journal_type ON billing.journal_entries(tenant_id, entry_type);
CREATE INDEX idx_journal_category ON billing.journal_entries(tenant_id, category);
CREATE INDEX idx_journal_exported ON billing.journal_entries(tenant_id, exported_to_accounting);

-- ═══════════════════════════════════════════════
-- PROGRAM FINANCIAL MONITORING
-- ═══════════════════════════════════════════════

CREATE TABLE billing.program_budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    program_id UUID NOT NULL,
    
    -- Budget
    budget_type VARCHAR(50) NOT NULL,                -- annual, quarterly, monthly, total_cap, unlimited
    budget_amount DECIMAL(15,2),                     -- null for unlimited
    budget_period_start DATE,
    budget_period_end DATE,
    
    -- Current spend
    spent_to_date DECIMAL(15,2) DEFAULT 0,
    remaining DECIMAL(15,2),
    utilization_percentage DECIMAL(8,2) DEFAULT 0,
    
    -- Burn rate (recalculated daily by scheduled job)
    burn_rate_daily DECIMAL(12,2) DEFAULT 0,
    burn_rate_weekly DECIMAL(12,2) DEFAULT 0,
    burn_rate_monthly DECIMAL(12,2) DEFAULT 0,
    
    -- Trend
    burn_rate_7day_avg DECIMAL(12,2) DEFAULT 0,
    burn_rate_30day_avg DECIMAL(12,2) DEFAULT 0,
    burn_rate_trend VARCHAR(20),                     -- increasing, stable, decreasing
    burn_rate_change_pct DECIMAL(8,2),               -- % change from prior period
    
    -- Projections
    projected_depletion_date DATE,
    projected_period_spend DECIMAL(15,2),
    projected_over_budget BOOLEAN DEFAULT FALSE,
    
    -- Alert thresholds
    spend_increase_alert_pct DECIMAL(8,2) DEFAULT 25,    -- alert if burn rate increases by this %
    budget_remaining_alert_pct DECIMAL(8,2) DEFAULT 20,  -- alert when X% budget remaining
    depletion_alert_days INTEGER DEFAULT 30,              -- alert when projected to deplete in X days
    
    last_calculated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE billing.program_budget_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    program_budget_id UUID NOT NULL REFERENCES billing.program_budgets(id),
    
    alert_type VARCHAR(100) NOT NULL,
    -- Types: spend_rate_increase, budget_low, budget_critical, 
    --        projected_depletion, over_budget, unusual_activity
    
    severity VARCHAR(20) NOT NULL,                   -- info, warning, critical
    message TEXT NOT NULL,
    
    -- Data at time of alert
    metric_value DECIMAL(15,2),
    threshold_value DECIMAL(15,2),
    comparison_value DECIMAL(15,2),
    
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID,
    resolution_notes TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Daily snapshot for trend analysis
CREATE TABLE billing.program_budget_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    program_budget_id UUID NOT NULL REFERENCES billing.program_budgets(id),
    tenant_id UUID NOT NULL,
    
    snapshot_date DATE NOT NULL,
    spent_to_date DECIMAL(15,2) NOT NULL,
    daily_spend DECIMAL(12,2) NOT NULL,
    claim_count INTEGER NOT NULL,
    avg_claim_amount DECIMAL(12,2),
    
    UNIQUE(program_budget_id, snapshot_date)
);

-- ═══════════════════════════════════════════════
-- FEES
-- ═══════════════════════════════════════════════

CREATE TABLE billing.fee_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    fee_code VARCHAR(50) NOT NULL,
    
    calculation_type VARCHAR(50) NOT NULL,
    -- per_claim_flat, per_claim_percentage, tiered_volume,
    -- flat_monthly, per_member_per_month, per_transaction,
    -- percentage_of_ingredient_cost, custom
    
    amount DECIMAL(12,4),
    percentage DECIMAL(8,4),
    tiers JSONB,
    custom_formula TEXT,
    
    applies_to_programs JSONB,
    applies_to_claim_types JSONB,
    applies_to_nrids JSONB,
    
    split_rules JSONB,
    
    effective_date DATE NOT NULL,
    termination_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- FUNDING
-- ═══════════════════════════════════════════════

CREATE TABLE billing.funding_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    funding_model VARCHAR(50) NOT NULL,
    
    prefund_balance DECIMAL(15,2) DEFAULT 0,
    alert_threshold DECIMAL(15,2),
    critical_threshold DECIMAL(15,2),
    
    funding_bank_account_id UUID,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE billing.prefund_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    funding_config_id UUID NOT NULL REFERENCES billing.funding_configs(id),
    tenant_id UUID NOT NULL,
    
    transaction_type VARCHAR(50) NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    running_balance DECIMAL(15,2) NOT NULL,
    
    reference_type VARCHAR(50),
    reference_id UUID,
    description TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID
);

-- ═══════════════════════════════════════════════
-- REMITTANCE & DELIVERY
-- ═══════════════════════════════════════════════

CREATE TABLE billing.remittance_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    delivery_method VARCHAR(50) DEFAULT 'sftp',
    sftp_config_id UUID,
    format_type VARCHAR(50) DEFAULT 'hipaa_835',
    include_pos_adjustment BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE billing.sftp_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER DEFAULT 22,
    username VARCHAR(255) NOT NULL,
    auth_type VARCHAR(20) DEFAULT 'key',
    remote_path VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    last_delivery_at TIMESTAMPTZ,
    last_delivery_status VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- PAYMENT VENDORS & BANK ACCOUNTS
-- ═══════════════════════════════════════════════

CREATE TABLE billing.payment_vendor_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    vendor_type VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    api_endpoint VARCHAR(500),
    api_credentials_ref VARCHAR(255),
    file_delivery_method VARCHAR(50),
    file_format VARCHAR(100),
    settlement_method VARCHAR(50),
    expected_settlement_days INTEGER DEFAULT 2,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE billing.bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    account_name VARCHAR(255) NOT NULL,
    bank_name VARCHAR(255) NOT NULL,
    routing_number VARCHAR(9) NOT NULL,
    account_number VARCHAR(17) NOT NULL,
    account_type VARCHAR(20) NOT NULL,
    purpose VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- ACCOUNTING INTEGRATION
-- ═══════════════════════════════════════════════

CREATE TABLE billing.accounting_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    system_type VARCHAR(50) NOT NULL,
    export_format VARCHAR(50),
    connection_config JSONB,
    field_mapping JSONB,
    class_mapping JSONB,
    auto_export_ap BOOLEAN DEFAULT FALSE,
    auto_export_ar BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- SEQUENCES
-- ═══════════════════════════════════════════════

CREATE TABLE billing.sequences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    sequence_type VARCHAR(50) NOT NULL,
    prefix VARCHAR(20),
    current_value BIGINT NOT NULL DEFAULT 0,
    UNIQUE(tenant_id, sequence_type)
);
```

---

## 5. Business Logic

### 5.1 Claims Ingestion

1. Claims arrive from source (internal event, upload, API)
2. Validate: required fields, valid amounts (Decimal), pharmacy NPI exists in directory
3. Store as `claim_records` with status `ingested`
4. Evaluate routing rules in priority order. First match sets: payment_route, vendor, schedule
5. Resolve pay-to entity via waterfall
6. Update status to `classified`
7. Create AP record (except excluded and statement claims)
8. Write journal entry: `ap_created`, tagged to client + program
9. For statement claims: emit event for statement report generation
10. Emit `claim.ingested` event

### 5.2 AP Payment Cycle

Triggered per schedule per route (or manually):

1. Collect all APs with status `created` for this route/schedule
2. Group by pay-to entity
3. Net reversals: credits offset debits for same pay-to
4. Apply pending carryovers
5. Create payment batch with one payment per pay-to
6. Validate (see 5.7)
7. Approval gate (if semi-automatic, pause for review)
8. Generate payment file (NACHA, Echo 400, Zelis, check — per vendor config)
9. Generate 835 per pay-to per remittance config
10. Submit payment file to vendor
11. Deliver 835s (SFTP, portal, email per config)
12. Deduct from prefund (if applicable), write journal entry
13. Update AP statuses to `submitted`
14. Write journal entries: `payment_submitted` per payment
15. Emit events

### 5.3 Settlement Tracking (AP)

- **Auto-settlement**: Poll vendor APIs for confirmations. Match and settle.
- **File-based**: Operator uploads bank file. System auto-matches by amount + reference.
- **Manual**: Operator settles individual payments.
- **Returns**: ACH return received → AP to `returned` → create carryover → configurable handling (auto-include next batch, hold for review, alert). Write journal entry: `ap_returned`.
- **On settlement**: Write journal entry `ap_settled` or `payment_settled`.
- **Void/reversal**: If a payment needs to be voided after submission but before settlement, operator can void with reason. Void creates offsetting journal entry and new AP record for reprocessing.

### 5.4 Invoicing Flow (AR)

Independent from AP:

1. Invoicing cycle triggers (by schedule or manual)
2. Pull all claim records processed since last invoice for this client/program set
3. Calculate fees per fee configs
4. Generate invoice with line items at configured detail level
5. Apply late fees if enabled and prior invoices are overdue
6. Generate PDF from tenant's branded template
7. Create AR record with due date (based on payment terms)
8. Write journal entries: `invoice_generated`, `ar_created`, `fee_calculated`
9. Approval gate (if semi-automatic)
10. Deliver invoice (email, portal, SFTP, API)
11. Export to accounting system from journal entries
12. Emit events

### 5.5 AR Payment Tracking

1. Client payment received (manual entry, bank feed, or API)
2. Match to AR by invoice number or reference
3. Record `ar_payments` entry
4. Update AR: amount_paid, amount_outstanding, status
5. If fully paid: status → `paid`, write journal entry `ar_payment_received`
6. If partial: status → `partially_paid`, calculate outstanding
7. Daily aging job: update `days_outstanding` and `aging_bucket` for all open ARs
8. Overdue: status → `overdue`, emit `ar.overdue` event
9. Dispute: operator can mark AR as disputed with reason. Pauses aging. Resolution tracked.
10. Write-off: operator can write off uncollectable AR with approval. Journal entry `ar_written_off`.

### 5.6 Financial Journal

Every financial event writes to `billing.journal_entries`. The journal:

- Is append-only — entries are never modified or deleted
- Every entry tagged to: tenant, client, program, pay-to entity, category, GL account
- Every entry has a human-readable description (e.g., "AP payment to CVS Pharmacy #4521 for 23 claims, Program CopayAssist-001, settled via Echo")
- Supports period queries: "show me all journal entries for Client X, Program Y, in March 2026"
- Drives all accounting exports: when you export to QuickBooks, the system queries the journal for unexported entries, maps them to GL accounts per the accounting config, and generates the export file
- Tracks export status: each entry marked as exported with timestamp and reference

**Accounting export flow:**
1. Query journal for entries where `exported_to_accounting = FALSE`
2. Map each entry to GL account and class per tenant's accounting config
3. Generate export file (SaaSant Excel, CSV, API payload, etc.)
4. Mark entries as exported
5. Accountant books from the export — not from bank statements

**Reports from journal:**
- AP summary by period, client, program, pay-to entity
- AR summary by period, client, program
- Fee summary by period, client, fee type
- Cash flow: payments out (AP) vs payments in (AR) by period
- Client profitability: fees collected minus operational costs
- Reconciliation: journal totals vs bank totals (any discrepancy = investigation)

### 5.7 Program Financial Monitoring

Scheduled job runs daily (configurable frequency):

1. For each active program budget:
   - Sum all AP amounts created in the period → `spent_to_date`
   - Calculate `remaining` = budget_amount - spent_to_date
   - Calculate `utilization_percentage`
   - Calculate daily/weekly/monthly burn rates from recent snapshots
   - Calculate 7-day and 30-day moving averages
   - Determine trend (increasing/stable/decreasing) by comparing current 7-day avg to prior 7-day avg
   - Project depletion date based on current burn rate
   - Save daily snapshot for trend history

2. Alert evaluation:
   - **Spend rate increase**: If burn rate increased by more than `spend_increase_alert_pct` from 30-day average → WARNING alert
   - **Budget low**: If remaining budget below `budget_remaining_alert_pct` of total → WARNING alert
   - **Budget critical**: If remaining budget below 10% (hardcoded floor) → CRITICAL alert
   - **Projected depletion**: If projected depletion date within `depletion_alert_days` → WARNING alert
   - **Over budget**: If spent_to_date exceeds budget_amount → CRITICAL alert
   - **Unusual activity**: If daily claim count exceeds 3x the 30-day daily average → WARNING alert

3. Alerts are:
   - Stored in `program_budget_alerts`
   - Pushed via notification system (Module 1) to configured recipients
   - Visible on the program monitoring dashboard
   - Require acknowledgment (who saw it, when, what action taken)

**Dashboard displays (per program):**
- Current balance / budget remaining (gauge)
- Daily spend trend line (last 90 days)
- Burn rate comparison (current vs 30-day avg)
- Projected depletion date
- Claim volume trend
- Active alerts
- Historical snapshots for any date range

### 5.8 Duplicate Ingestion Prevention
- On file upload: calculate SHA-256 hash of file contents. If hash matches a previously processed file for this tenant within configurable window (default: 90 days), BLOCK with "duplicate file" error.
- On claim ingestion (any source): check auth_number uniqueness within tenant. If duplicate auth_number exists and is not a reversal referencing it, BLOCK the claim.
- Idempotency key on API submissions: caller provides a unique key. If key was already processed, return the previous result without reprocessing.

### 5.9 Claim Aging / Prompt Pay Compliance
- Configurable payment deadline per tenant (default: 30 days from claim receipt, overridable per state/contract).
- Daily job checks all classified claims not yet included in a settled payment batch.
- If claim age approaches deadline: WARNING alert at 75% of deadline, CRITICAL alert at 90%.
- State prompt pay rules table: pre-loaded with all 50 states' pharmacy prompt pay deadlines. Configurable per tenant — system auto-applies the stricter of tenant's contract deadline or state law.
- Dashboard: claims approaching prompt pay deadline, grouped by state and urgency.

### 5.10 Escheatment / Unclaimed Payments
- Track payments where settlement fails repeatedly (3+ ACH returns to same entity) or checks go uncashed beyond configurable period (default: 180 days).
- Dormancy tracking: after configurable dormancy period (default: 1 year), flag payment as potentially escheatable.
- State escheatment rules table: pre-loaded with each state's unclaimed property dormancy period and reporting requirements.
- Annual escheatment report: all payments in dormancy status grouped by state with required reporting data.
- Operator workflow: attempt final contact before escheatment, document attempts, process escheatment or reclassify.

### 5.11 Positive Pay File Generation
- For check issuance payments: generate a positive pay file listing all checks issued (check number, amount, payee, date).
- File format configurable per bank (most banks accept a standard CSV or fixed-width format).
- Transmitted to bank via SFTP or bank portal API.
- When bank reports a positive pay exception (presented check not on file), alert operator for review.

### 5.12 Payment Notification to Payee
- When a payment batch is submitted, generate notification to each pay-to entity:
  - Email: "Payment of $X,XXX.XX for XX claims has been submitted via [method]. Expected settlement date: [date]."
  - Portal: notification in pharmacy portal with payment details
- Configurable per tenant: enabled/disabled, email template, portal notification
- Notification does NOT include bank account details or PHI

### 5.13 DIR Fee Handling
- For Medicare Part D clients: DIR (Direct and Indirect Remuneration) fees are retroactive pharmacy payment adjustments.
- DIR fee assessment: create a distinct transaction type in the journal (`dir_fee_assessed`).
- DIR fee reconciliation: compare DIR fees assessed vs DIR fees collected per pharmacy per period.
- DIR fees tracked separately from standard claim payments in AP and journal.
- Configurable: which programs have DIR fees, calculation method, assessment schedule.

### 5.14 Spread Pricing Tracking
- For every claim, the journal captures both sides: what the plan/client paid (receivable) and what the pharmacy received (payable).
- Spread = receivable amount minus payable amount for the same claim.
- Spread tracking is automatic when both AP and AR exist for the same claim.
- 2026 CAA transparency reports pull spread data directly from the journal.
- Spread report: by drug, by pharmacy, by period — supports semiannual regulatory filing.

### 5.15 Retroactive Adjustments / Clawbacks
- When claims are re-adjudicated (eligibility change, audit finding, pricing correction), the system generates adjustment records:
  - Original claim marked as adjusted with reference to adjustment claim
  - New claim record created with corrected amounts
  - Delta calculated (positive = additional payment owed, negative = recoupment needed)
  - Journal entries for both the reversal of original and booking of corrected amount
- Clawback rules: configurable per state. California SB 41 limits retroactive adjustments — must occur within 90 days and meet specific criteria.
- State clawback rules table: pre-loaded with state-specific limitations on retroactive adjustments.

### 5.16 Multi-Entity Billing
- A tenant may operate multiple legal entities (e.g., one entity for manufacturer programs, another for health plan admin).
- Configurable billing entity per program: determines which legal entity name, address, tax ID, and bank account appear on invoices and payment files.
- Journal entries tagged with billing entity for proper GL routing.
- Separate invoice number sequences per billing entity if needed.

### 5.17 Performance Requirements
- Claim ingestion: <500ms per claim (internal source), <5 seconds per 1000 claims (file upload parsing)
- AP payment batch generation: <60 seconds for batches up to 10,000 payments
- Invoice generation: <30 seconds per invoice
- Journal query: <3 seconds for any standard period query
- Prefund balance update: <100ms (must be atomic, no race conditions)

### 5.18 Data Retention
- Configurable per tenant. Default: 7 years (HIPAA minimum).
- Claim records, AP/AR records, journal entries, invoices — all retained per policy.
- After retention period: archive to cold storage (queryable but slower). Never delete financial records without explicit admin authorization.
- Archived data accessible via "archive query" API with slower SLA.

### 5.19 Penny Allocation Algorithm
- When splitting a total amount across multiple items (fee splits, pro-rata allocations), individual rounding may not sum to the total.
- Algorithm: calculate each item's share using Decimal. Round each to 2 decimal places. Calculate the delta between sum of rounded amounts and the original total. Assign the delta (positive or negative pennies) to the first item in the set.
- Example: $100.00 split 3 ways → $33.34, $33.33, $33.33 = $100.00 exactly.
- This algorithm is used everywhere amounts are split: fee splits, pro-rata adjustments, refund allocations.
- Unit tests verify: for any input amount and any number of splits, the sum of allocated amounts equals the original amount exactly.

### 5.20 Concurrent Operation Locking
- Batch generation, invoice generation, and prefund balance updates require exclusive locks to prevent duplicate operations.
- Implementation: PostgreSQL advisory locks keyed on tenant_id + operation_type + cycle identifier.
- If a lock is already held: return "operation in progress" response with the user who initiated it and the start time.
- Locks auto-expire after configurable timeout (default: 30 minutes) to prevent orphaned locks from crashes.
- Applies to: payment batch generation, invoice generation, prefund deposit, period close.

### 5.21 Bank Holiday Calendar
- Pre-loaded US federal holiday calendar (New Year's, MLK, Presidents' Day, Memorial Day, Juneteenth, Independence Day, Labor Day, Columbus Day, Veterans Day, Thanksgiving, Christmas).
- Configurable bank-specific holidays per bank account.
- Payment schedules landing on non-business days auto-shift to the next business day (configurable: next or previous).
- NACHA effective dates validated against the holiday calendar — non-business day effective dates rejected with suggested alternative date.
- Calendar updated annually. Admin can add custom holidays.

### 5.22 Rebate Pass-Through Tracking
- For health plan clients under 2026 CAA: track rebates received from manufacturers and verify 100% pass-through to plan sponsor.
- Rebate receipt: record manufacturer rebate payments with drug/class/period reference.
- Pass-through: track rebate amounts credited to plan sponsor (via invoice credit, direct payment, or prefund deposit).
- Reconciliation report: rebates received vs rebates passed through, by drug, by manufacturer, by period. Any discrepancy flagged.
- Supports semiannual CAA transparency reporting on rebate pass-through.

### 5.23 NACHA 2026 Compliance
- **Fraud monitoring**: log all fraud screening performed on outgoing ACH entries (payment hold checks, OIG/SAM screening, OFAC screening). Documented annually per NACHA requirement effective March 2026.
- **Company Entry Descriptions**: pharmacy payments use CCD (Cash Concentration or Disbursement) SEC code with appropriate Company Entry Description. Configurable per payment type.
- **ACH transaction limits**: same-day ACH capped at $1M per transaction. Payments exceeding $1M auto-routed to standard (next-day) ACH. Bank-specific limits configurable per bank account.

### 5.19 Validation Rules (Pre-Built Defaults)

| Rule | Threshold | Severity | Applies To |
|------|-----------|----------|------------|
| Batch total ≠ sum of payments | $0.01 | BLOCK | AP |
| Invoice total ≠ sum of line items | $0.01 | BLOCK | AR |
| AP amount negative (not a credit) | Any | BLOCK | AP |
| Pay-to entity on exclusion list | Any | BLOCK | AP |
| Pay-to entity missing bank details (ACH) | Any | BLOCK | AP |
| Prefund insufficient for batch | Below critical | BLOCK | AP |
| Duplicate auth number in period | Any | BLOCK | Ingestion |
| Pharmacy NPI not in directory | Any | BLOCK | Ingestion |
| Payment batch exceeds 200% historical avg | 200% | WARNING | AP |
| Invoice exceeds 200% historical avg | 200% | WARNING | AR |
| Reversal without matching original auth | Any | WARNING | Ingestion |
| Claim DOS outside expected range | Configurable | WARNING | Ingestion |
| Fee calculation produces $0 | Any | WARNING | AR |

All thresholds configurable per tenant. Tenants can add custom validation rules.

### 5.9 Statement Account Handling

- Configurable per pharmacy per program (not a global pharmacy flag)
- Statement claims create claim records but no AP
- Statement report generated for manufacturer showing claim details
- Mixed pharmacies: non-statement claims get AP normally, statement claims get report only
- All configurable per tenant

### 5.10 Under-Reimbursement / POS Adjustment

- Calculated per tenant's configured formula
- Stored as separate amount on claim record
- Configurable: included in 835 or separate report
- Configurable: included in regular AP payment, separate payment, or deferred
- Journal entry created for POS adjustment amounts

### 5.11 Void and Correction Workflows

**Void a payment batch** (before settlement):
1. Operator initiates void with reason and approval
2. All payments in batch marked `voided`
3. All APs in batch reverted to `created` (available for next batch)
4. Offsetting journal entries created
5. Payment file marked void (vendor notified if already submitted)

**Void an invoice** (before client payment):
1. Operator initiates void with reason and approval
2. Invoice marked `voided`, AR record marked `voided`
3. Offsetting journal entries created
4. Credit memo generated if needed
5. Voided invoice number never reused

**Correct an invoice** (after client payment):
1. Generate credit memo for original invoice
2. Generate corrected invoice with new invoice number
3. Adjust AR accordingly
4. All documented in journal

### 5.12 Period Close

Monthly close process (configurable):
1. Verify all payment batches for the period are settled or accounted for
2. Verify all invoices for the period are sent
3. Generate period summary report from journal
4. Export all unexported journal entries to accounting system
5. Flag period as closed — no new entries for closed periods without admin override
6. Generate 1099 data for applicable pay-to entities (annual)

---

## 6. File Generation (Pre-Built)

| File | Standard | Notes |
|------|----------|-------|
| 835 Remittance | HIPAA 005010X221A1 | Full envelope, all required segments, one per pay-to per payment |
| NACHA/ACH | NACHA standard | Configurable originator, company ID, entry class. Debits = positive |
| Echo Spec 400 | Echo format | Per Echo API/file spec |
| Invoice PDF | Custom template | White-label, configurable detail level, payment terms |
| SaaSant Excel | QB Desktop format | From journal entries |
| Generic GL CSV | Configurable | Any field mapping |
| 1099 data | IRS format | Annual, for applicable pay-to entities |
| POS Adjustment Report | Custom | Under-reimbursement detail |
| Statement Report | Custom | Statement account claims detail |
| Period Close Report | Custom | Full journal summary for period |

---

## 7. Payment Vendor Integrations (Pre-Built Adapters)

| Vendor | Format | Settlement |
|--------|--------|------------|
| Direct ACH | NACHA | File upload or bank API |
| Echo Health | Spec 400 | Echo API for settlement confirmation |
| Zelis | Zelis API | Zelis API for settlement |
| Check Issuance | Configurable | Manual confirmation or vendor API |

Adapter pattern: add new vendors by creating a new adapter class implementing the PaymentVendor interface. No changes to core billing logic.

---

## 8. Accounting System Adapters (Pre-Built)

| System | Method | Format |
|--------|--------|--------|
| QuickBooks Desktop | File | SaaSant Excel, IIF |
| QuickBooks Online | API | QBO API |
| NetSuite | API / CSV | SuiteConnect or CSV |
| Sage | File | CSV with mapping |
| Xero | API | Xero API |
| Generic GL | File | Configurable CSV/Excel |

All exports generated FROM journal entries. Field mapping and GL account assignment configurable per tenant.

---

## 9. API Endpoints

```
/api/v1/billing/

# Claims
POST   /claims/upload                   Upload claims file
POST   /claims/upload/{id}/preview      Preview parsed claims
POST   /claims/upload/{id}/confirm      Confirm upload
POST   /claims                          Submit claim via API
GET    /claims                          List claims (filterable)
GET    /claims/{id}                     Get claim detail

# Routing
GET    /routing-rules                   List rules
POST   /routing-rules                   Create rule
PUT    /routing-rules/{id}              Update rule
POST   /routing-rules/test              Test against sample claims

# AP
GET    /ap                              List AP records
GET    /ap/summary                      Summary by entity/status
GET    /ap/{id}                         AP detail

# Payment Batches
GET    /payment-batches                 List batches
POST   /payment-batches/generate        Generate batch for route/schedule
GET    /payment-batches/{id}            Batch detail
POST   /payment-batches/{id}/validate   Validate
POST   /payment-batches/{id}/approve    Approve
POST   /payment-batches/{id}/submit     Submit to vendor
POST   /payment-batches/{id}/void       Void batch
GET    /payment-batches/{id}/payments   Payments in batch

# Settlement
POST   /settlement/upload               Upload bank file
POST   /settlement/record               Manual settlement
POST   /settlement/returns              Record ACH return
GET    /settlement/unmatched            Unmatched payments

# Invoicing
GET    /invoicing-configs               List configs
POST   /invoicing-configs               Create config
PUT    /invoicing-configs/{id}          Update config

# Invoices
GET    /invoices                        List invoices
POST   /invoices/generate               Generate invoice
GET    /invoices/{id}                   Invoice detail
GET    /invoices/{id}/pdf               Download PDF
POST   /invoices/{id}/approve           Approve
POST   /invoices/{id}/send              Send
POST   /invoices/{id}/void              Void with reason
GET    /invoices/{id}/line-items        Line items

# AR
GET    /ar                              List AR records
GET    /ar/aging                        Aging report
POST   /ar/{id}/payment                 Record payment
POST   /ar/{id}/dispute                 Open dispute
POST   /ar/{id}/write-off              Write off (admin)

# Journal
GET    /journal                         Query journal (filterable by date, client, program, category, type)
GET    /journal/summary                 Period summary
GET    /journal/export                  Export to accounting system
POST   /journal/close-period            Close a period

# Fees
GET    /fees                            List fee configs
POST   /fees                            Create
PUT    /fees/{id}                       Update

# Funding / Prefund
GET    /funding                         List funding configs
PUT    /funding/{id}                    Update
GET    /funding/{id}/ledger             Prefund ledger
POST   /funding/{id}/deposit            Record deposit
GET    /funding/{id}/projection         Burn rate projection

# Program Monitoring
GET    /program-budgets                 List program budgets
POST   /program-budgets                 Create budget
PUT    /program-budgets/{id}            Update budget
GET    /program-budgets/{id}/dashboard  Dashboard data
GET    /program-budgets/{id}/snapshots  Historical snapshots
GET    /program-budgets/{id}/alerts     Alerts for program
POST   /program-budgets/{id}/alerts/{alert_id}/acknowledge   Acknowledge alert

# Vendors / Banks / Accounting / SFTP
GET    /payment-vendors                 List vendor configs
POST   /payment-vendors                 Create
PUT    /payment-vendors/{id}            Update
GET    /bank-accounts                   List
POST   /bank-accounts                   Create
PUT    /bank-accounts/{id}              Update
GET    /accounting/config               Get config
PUT    /accounting/config               Update
GET    /remittance-configs              List
POST   /remittance-configs              Create
GET    /sftp-configs                    List
POST   /sftp-configs                    Create
POST   /sftp-configs/{id}/test          Test connection

# Reports
GET    /reports/ap-summary              AP by period/client/program
GET    /reports/ar-aging                AR aging
GET    /reports/payment-history         Payment history
GET    /reports/fee-summary             Fee summary
GET    /reports/prefund-history         Prefund history
GET    /reports/cash-flow               Cash in vs cash out
GET    /reports/program-performance     Program spend vs budget
GET    /reports/period-close            Period close summary
GET    /reports/1099-data               1099 data for tax year
```

---

## 10. Events

### Published
`claim.ingested`, `claim.classified`, `ap.created`, `ap.settled`, `ap.returned`, `ap.voided`,
`payment_batch.generated`, `payment_batch.submitted`, `payment_batch.settled`, `payment_batch.voided`,
`payment.submitted`, `payment.settled`, `payment.returned`,
`invoice.generated`, `invoice.sent`, `invoice.voided`,
`ar.created`, `ar.payment_received`, `ar.overdue`, `ar.disputed`, `ar.written_off`,
`prefund.low`, `prefund.critical`, `prefund.deposit`,
`program_budget.alert`, `program_budget.over_budget`,
`sftp.delivery_failed`, `journal.period_closed`

### Consumed
`claim.adjudicated` (from adjudication), `claim.reversed`, `exclusion.match_found`

---

## 11. Default Implementation

Ships fully functional:

- **4 subsystems**: Claims Ingestion, AP, AR, Financial Journal — all independent
- **3 funding models**: prefund, claims fund, pass-through
- **3 claims sources**: internal, upload, API
- **Routing rules engine** with priority-based matching
- **Configurable pay-to waterfall**
- **13 validation rules** with defaults
- **4 payment vendor adapters**: ACH/NACHA, Echo, Zelis, check
- **6 accounting adapters**: QB Desktop, QB Online, NetSuite, Sage, Xero, generic GL
- **835 generator**: HIPAA 005010X221A1 compliant
- **NACHA generator**: fully compliant
- **Invoice PDF generator**: white-label ready
- **Financial journal**: append-only, tagged, exportable
- **Program monitoring**: budget tracking, burn rate, projections, 6 alert types
- **Fee engine**: 8 calculation types
- **AR aging**: automatic with overdue alerts
- **Period close workflow**
- **Void/correction workflows** for both AP and AR
- **1099 data generation**

New tenant setup: configure routing rules, invoicing cycle, payment vendor, bank account, and funding model. Everything else works on defaults.

**Additional defaults from audit:**
- **50-state prompt pay deadline table** pre-loaded
- **50-state escheatment rules** pre-loaded
- **50-state clawback limitation rules** pre-loaded
- **Duplicate ingestion prevention** active (file hash + auth number uniqueness)
- **Payment notifications** enabled by default (email to payee on submission)
- **Positive pay file generation** ready for check payments
- **Spread tracking** automatic for all claims with both AP and AR
- **DIR fee support** configurable per program
- **Data retention** defaulting to 7 years with configurable archival

---

## 12. Test Scenarios (100% Coverage Required)

### Financial Precision (100%)
- All Decimal operations use ROUND_HALF_UP
- Batch total = sum of payments (penny-perfect)
- Invoice total = sum of line items (penny-perfect)
- Prefund balance after deduction = prior balance minus batch total (penny-perfect)
- Journal entry amounts sum to zero across offsetting entries (void scenarios)
- Fee calculations produce correct amounts for all 8 types
- AR aging buckets calculated correctly at all boundaries

### Critical Paths (100%)
- Routing rules evaluated in correct priority order
- Pay-to waterfall resolves correctly at each level
- AP → Payment → Settlement full lifecycle
- AR → Invoice → Payment → Settled full lifecycle
- Journal entry created for every financial event (no gaps)
- Data lock prevents modification after approval
- Void creates correct offsetting journal entries
- Period close blocks new entries for closed periods
- 835 validates against HIPAA standard
- NACHA validates against NACHA standard
- Invoice number sequence: no gaps, no duplicates, no reuse
- Carryover created correctly on ACH return

### Edge Cases
- Mixed statement and non-statement claims for same pharmacy
- Batch with all credits (net negative) — correct handling
- Invoice void after partial payment — credit memo generated
- Program budget at exactly 0 remaining — CRITICAL alert
- Simultaneous payment batches for same tenant — sequence integrity
- Routing rule with no match — flags for manual classification
- File upload with format mismatch — clear error, no partial ingestion
- Prefund deposit concurrent with deduction — balance integrity

---

## 13. Session Decomposition

1. **Claims ingestion + routing**: claim_records, routing_rules, pay-to waterfall, file format mapping, upload parser, classification engine
2. **AP engine**: ap_records, payment_batches, payments, scheduling, validation, carryover, void workflow, all Decimal math
3. **AR engine**: invoicing_configs, invoices, line_items, ar_records, ar_payments, fee calculation, aging, dispute, write-off, void workflow, late fees, all Decimal math
4. **Journal + monitoring + files**: journal_entries, program_budgets, snapshots, alerts, burn rate calculation, 835 generator, NACHA generator, Echo 400, invoice PDF, accounting exports, SFTP delivery, settlement, period close, 1099
