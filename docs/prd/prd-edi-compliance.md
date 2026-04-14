# PRD — Module 13: EDI & Compliance — FINAL

**Module:** EDI & Compliance  
**Folder:** `modules/edi-compliance/`  
**Priority:** Phase 4  
**Dependencies:** Core Platform (Module 1), Billing (Module 11), Member Management (Module 5)  

---

## 1. Purpose

The EDI & Compliance module is the transaction processing backbone. It generates, parses, validates, transmits, and tracks every HIPAA-mandated X12 EDI transaction the platform produces or receives. It also handles NCPDP batch transactions for pharmacy claims.

**This module owns:**
- X12 transaction generation (building compliant EDI files)
- X12 transaction parsing (reading inbound EDI files)
- X12 validation (syntax, segment, code set compliance)
- Transaction envelope management (ISA/GS/ST control numbers, acknowledgments)
- Trading partner management (who we exchange EDI with, their configurations)
- Transport (AS2, SFTP, direct connect — how files are transmitted)
- Compliance tracking (what was sent, when, to whom, was it acknowledged)
- NCPDP batch standard support (pharmacy claim batches — distinct from NCPDP D.0 real-time)

**Transaction types supported:**

| Transaction | Standard | Direction | Purpose |
|---|---|---|---|
| 835 | X12 005010X221A1 | Outbound | Remittance advice (payment explanation to providers) |
| 837P | X12 005010X222A2 | Inbound/Outbound | Professional claims (CMS-1500 based) |
| 837I | X12 005010X223A3 | Inbound/Outbound | Institutional claims (UB-04 based) |
| 837D | X12 005010X224A3 | Inbound/Outbound | Dental claims |
| 270/271 | X12 005010X279A1 | Both | Eligibility inquiry/response |
| 276/277 | X12 005010X212 | Both | Claim status request/response |
| 278 | X12 005010X217 | Both | Service review (prior authorization) |
| 834 | X12 005010X220A1 | Inbound | Enrollment/maintenance |
| 820 | X12 005010X306 | Outbound | Premium payment |
| 999 | X12 005010X231A1 | Both | Implementation acknowledgment |
| TA1 | X12 | Both | Interchange acknowledgment |
| NCPDP Batch | NCPDP Batch 1.2 | Both | Pharmacy claim batches |

**What this module does NOT do:**
- Does not adjudicate claims (Adjudication Engine Module 8 does that)
- Does not process payments (Payment Processing Module 12 does that)
- Does not calculate amounts (Billing Module 11 does that)
- This module TRANSPORTS and FORMATS data — it's the translator between internal data structures and external EDI standards

---

## 2. Data Model

```sql
CREATE SCHEMA edi;

-- Trading partners (who we exchange EDI with)
CREATE TABLE edi.trading_partners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- Identity
    name VARCHAR(500) NOT NULL,
    partner_type VARCHAR(50) NOT NULL,                 -- payer, provider, clearinghouse, pharmacy, government
    
    -- X12 identifiers
    isa_qualifier VARCHAR(2) NOT NULL,                 -- ISA05/ISA07 qualifier (ZZ, 01, 30, etc.)
    isa_id VARCHAR(15) NOT NULL,                       -- ISA06/ISA08 interchange ID
    gs_id VARCHAR(15),                                 -- GS02/GS03 application code
    
    -- Supported transactions
    supported_transactions JSONB NOT NULL,             -- ["835", "837P", "270", "271"]
    
    -- Transport
    transport_type VARCHAR(50) NOT NULL,               -- as2, sftp, direct_connect, api, manual
    transport_config JSONB NOT NULL,                   -- connection details per transport type
    
    -- Processing
    test_mode BOOLEAN DEFAULT TRUE,                    -- ISA15: T=test, P=production
    companion_guide_ref VARCHAR(255),                   -- reference to partner's companion guide
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_transmission_at TIMESTAMPTZ,
    last_transmission_status VARCHAR(50),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, isa_qualifier, isa_id)
);

-- Control number sequences (ISA, GS, ST — per trading partner)
CREATE TABLE edi.control_number_sequences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    trading_partner_id UUID REFERENCES edi.trading_partners(id),
    
    sequence_type VARCHAR(20) NOT NULL,                -- isa, gs, st
    current_value BIGINT NOT NULL DEFAULT 0,
    max_value BIGINT DEFAULT 999999999,                -- ISA: 9 digits, GS: 9, ST: 4-9 varies
    
    UNIQUE(tenant_id, trading_partner_id, sequence_type)
);

-- Transaction files (every EDI file generated or received)
CREATE TABLE edi.transaction_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    trading_partner_id UUID REFERENCES edi.trading_partners(id),
    
    -- File identity
    direction VARCHAR(10) NOT NULL,                    -- inbound, outbound
    transaction_type VARCHAR(10) NOT NULL,             -- 835, 837P, 837I, 270, 271, etc.
    implementation_guide VARCHAR(50),                   -- 005010X221A1, etc.
    
    -- Envelope control numbers
    isa_control_number VARCHAR(9),
    gs_control_number VARCHAR(9),
    
    -- Content
    file_id UUID,                                      -- ref to core.files
    file_name VARCHAR(500),
    transaction_count INTEGER,
    total_claim_count INTEGER,
    total_amount DECIMAL(15,2),
    
    -- Validation
    validation_status VARCHAR(50) DEFAULT 'pending',
    -- pending, valid, invalid, warnings
    validation_errors JSONB,
    validation_warnings JSONB,
    
    -- Transmission
    transmission_status VARCHAR(50) DEFAULT 'pending',
    -- pending, transmitted, acknowledged, rejected, failed
    transmitted_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    
    -- Acknowledgment tracking
    ack_type VARCHAR(10),                              -- TA1, 999, 277CA
    ack_file_id UUID,
    ack_status VARCHAR(50),                            -- accepted, rejected, accepted_with_errors
    ack_errors JSONB,
    
    -- Processing
    processed_at TIMESTAMPTZ,
    processing_status VARCHAR(50),
    processing_errors JSONB,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_edi_files_tenant ON edi.transaction_files(tenant_id, direction, transaction_type, created_at DESC);
CREATE INDEX idx_edi_files_isa ON edi.transaction_files(isa_control_number);

-- Individual transactions within a file (one 837 file may contain many claims)
CREATE TABLE edi.transaction_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    transaction_file_id UUID NOT NULL REFERENCES edi.transaction_files(id),
    
    st_control_number VARCHAR(9),
    transaction_type VARCHAR(10) NOT NULL,
    
    -- Parsed identifiers
    claim_id VARCHAR(50),                              -- CLM01 for 837, CLP01 for 835
    patient_id VARCHAR(100),
    provider_npi VARCHAR(10),
    payer_id VARCHAR(50),
    
    -- Amounts (Decimal)
    total_amount DECIMAL(12,2),
    paid_amount DECIMAL(12,2),
    
    -- Status
    status VARCHAR(50) DEFAULT 'received',
    -- received, validated, processed, rejected, forwarded
    
    validation_errors JSONB,
    processing_result JSONB,
    
    -- Cross-reference to internal records
    internal_claim_id UUID,                            -- ref to billing.claim_records or medical claim
    internal_payment_id UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_edi_records_file ON edi.transaction_records(transaction_file_id);
CREATE INDEX idx_edi_records_claim ON edi.transaction_records(tenant_id, claim_id);

-- Compliance tracking
CREATE TABLE edi.compliance_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    regulation VARCHAR(100) NOT NULL,                  -- hipaa_5010, ncpdp_d0, ncpdp_batch, state_specific
    requirement VARCHAR(255) NOT NULL,
    
    status VARCHAR(50) NOT NULL,                       -- compliant, non_compliant, remediation_in_progress
    evidence TEXT,
    last_assessed_at TIMESTAMPTZ,
    next_assessment_date DATE,
    
    assessed_by UUID,
    notes TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 3. Business Logic

### 3.1 X12 Transaction Generation Engine

Generates compliant X12 EDI files from internal data:

**Envelope construction:**
1. ISA (Interchange Control Header): sender/receiver IDs from trading partner config, control number from sequence, test/production indicator
2. GS (Functional Group Header): functional identifier code per transaction type (HP for 835, HC for 837, HS for 270, etc.), control number from sequence
3. ST (Transaction Set Header): transaction set identifier, control number, implementation guide reference
4. [Transaction content — loops, segments, elements per implementation guide]
5. SE (Transaction Set Trailer): segment count, control number
6. GE (Functional Group Trailer): transaction count, control number
7. IEA (Interchange Trailer): functional group count, control number

**Pre-built generators:**

| Transaction | Generator | Input Source |
|---|---|---|
| 835 | `generate_835()` | Billing payment batch data |
| 837P | `generate_837p()` | Medical claims data (professional) |
| 837I | `generate_837i()` | Medical claims data (institutional) |
| 270 | `generate_270()` | Eligibility inquiry parameters |
| 271 | `generate_271()` | Member eligibility data |
| 276 | `generate_276()` | Claim status inquiry parameters |
| 277 | `generate_277()` | Claim processing status data |
| 278 | `generate_278()` | Prior authorization request/response |
| 834 | `generate_834()` | Enrollment data |
| 999 | `generate_999()` | Acknowledgment data |

Each generator:
- Accepts internal data structures (Pydantic models)
- Builds segments per the implementation guide
- Validates required fields before generation
- Calculates segment counts and hash totals
- Returns the complete EDI string + metadata

### 3.2 X12 Transaction Parser

Parses inbound X12 EDI files into internal data structures:

1. **Detect delimiters**: ISA segment defines element separator (ISA[3]), subelement separator (ISA[16]), and segment terminator (ISA[105])
2. **Split segments**: by segment terminator
3. **Parse envelope**: extract ISA/GS/ST control numbers, sender/receiver, version
4. **Route by transaction type**: ST01 determines which parser handles the content
5. **Parse content**: segment by segment per implementation guide — loops, qualifiers, code values
6. **Validate**: required segments present, code values valid, amounts parseable
7. **Output**: internal Pydantic model with all parsed fields + validation results

**Pre-built parsers:** 835, 837P, 837I, 837D, 270, 271, 276, 277, 278, 834, 999, TA1

### 3.3 Validation Engine

Three levels of validation:

**Level 1 — Syntax**: X12 structural compliance
- Correct delimiters
- Valid segment IDs
- Correct element counts per segment
- Control number matching (ISA/IEA, GS/GE, ST/SE)
- Segment count matches SE01

**Level 2 — Implementation Guide**: content compliance
- Required segments present per IG
- Required elements populated
- Code values from correct code sets (ICD-10, CPT, HCPCS, NDC, place of service, claim frequency, etc.)
- Conditional elements present when required
- Loop nesting correct

**Level 3 — Business**: data quality
- NPI valid (Luhn check)
- Dates reasonable (not future for DOS, not >1 year old)
- Amounts positive (or correctly signed for adjustments)
- Member ID matches enrollment
- Provider in network

Validation results: VALID, INVALID (with error list), WARNINGS (valid but quality concerns)

### 3.4 Transport Layer

**AS2 (Applicability Statement 2):**
- Industry standard for EDI transport
- Encrypted + signed + MDN (Message Disposition Notification) receipt
- Non-repudiation: proves delivery and receipt
- Used by most clearinghouses and large payers

**SFTP:**
- Secure file transfer with SSH encryption
- Used by smaller trading partners
- Polling for inbound files on schedule

**Direct Connect:**
- Point-to-point API or socket connection
- Used by switch connectivity (Module 9) for real-time transactions

**Manual:**
- File download for manual delivery (portal, email)
- File upload for manual receipt

Transport is configurable per trading partner. The EDI module generates the file — transport delivers it.

### 3.5 Acknowledgment Processing

**TA1 (Interchange Acknowledgment):**
- Confirms ISA/IEA envelope received
- Reports acceptance/rejection at interchange level
- Matched to outbound file by ISA control number

**999 (Implementation Acknowledgment):**
- Confirms functional group and transaction set received
- Reports syntax and IG-level acceptance/rejection
- Segment-level error reporting (which segment, which element, what error)
- Matched to outbound file by GS control number

**277CA (Claim Acknowledgment):**
- Claim-level acceptance/rejection for 837 submissions
- Reports which claims accepted, which rejected, with reason codes
- Matched to outbound 837 by claim ID

**Processing flow:**
1. Receive acknowledgment file (inbound)
2. Parse acknowledgment
3. Match to original outbound file by control numbers
4. Update transaction_files.ack_status
5. For rejected transactions: create error record, alert operator
6. For accepted transactions: update processing status

### 3.6 NCPDP Batch Standard Support

For pharmacy claim batches (distinct from real-time NCPDP D.0):

1. **NCPDP Batch 1.2**: batch submission of pharmacy claims for non-real-time scenarios
2. **Generate**: from billing claim data, formatted per NCPDP Batch specification
3. **Parse**: inbound batch files from pharmacy networks
4. **Validate**: NCPDP field codes, transaction codes, header/detail/trailer records
5. Uses NCPDP field definitions from the D.0 specification you already have

### 3.7 835 Generation (Pharmacy Remittance)

The 835 is the most-generated transaction for pharmacy PBM operations. Detailed spec:

1. **Batching**: one 835 per pay-to entity per payment batch (from Billing module)
2. **Structure**: ISA → GS → ST → BPR (payment info) → TRN (trace) → N1 (payer/payee) → CLP loops (one per claim) → SE → GE → IEA
3. **CLP loop**: claim ID, status (1=processed as primary, 2=processed as secondary), charged amount, paid amount, patient responsibility, claim filing indicator, reference ID
4. **SVC loop** (within CLP): service line detail — procedure code (NDC qualifier N4, Rx number qualifier 1D), charged, paid, quantity
5. **CAS segment**: adjustment reason codes (CO=contractual, OA=other adjustment, PI=payer initiated, PR=patient responsibility) with group/reason codes and amounts
6. **REF segments**: pharmacy NPI (HPI qualifier), BIN (G1), NCPDP number, chain code (PQ)
7. **MOA segment**: reimbursement rate, HCPCS payable amount
8. All amounts: Decimal, ROUND_HALF_UP

### 3.8 Compliance Reporting

Track and report on HIPAA transaction compliance:

1. Transaction volume by type, by trading partner, by period
2. Rejection rates: % of transactions rejected by trading partners
3. First-pass acceptance rate: % accepted on first submission
4. Acknowledgment turnaround: time between submission and acknowledgment
5. Code set compliance: % of transactions using current code sets (ICD-10 updates, CPT annual updates)
6. Trading partner health: per-partner acceptance rates, response times, error patterns

### 3.9 JSON ↔ X12 Bidirectional Translation Layer

Modern integrators expect JSON APIs, not raw X12. Stedi-equivalent capability:

1. **JSON → X12 (outbound)**: accept claim/eligibility/status data as JSON, auto-generate compliant X12 EDI. JSON schema documented per transaction type with OpenAPI spec.
2. **X12 → JSON (inbound)**: parse inbound X12 into structured JSON for downstream processing. Nested loops flattened into readable JSON objects.
3. **Both formats at every endpoint**: every generate/parse API accepts and returns both JSON and raw X12. Client chooses via Content-Type header.
4. **Schema per transaction type**: published JSON schemas for 837P, 837I, 835, 270/271, 276/277, 278, 834
5. **Validation in both formats**: JSON submissions validated against the same rules as X12 before conversion
6. **Why this matters**: eliminates the #1 integration friction — developers shouldn't need to learn X12 segment syntax to submit a claim

### 3.10 Clearinghouse Integration Layer

90%+ of claims route through clearinghouses, not direct to payers:

1. **Clearinghouse adapter interface**: same pattern as payment processing vendor adapters — abstract interface, per-clearinghouse implementation
2. **Pre-built adapters**:
   - **Stedi** — API-first (JSON + X12), 3,400+ payers, modern developer experience
   - **Availity** — SFTP/API, largest payer connectivity network
   - **Change Healthcare (Optum)** — largest volume clearinghouse (despite 2024 attack, still dominant)
   - **Waystar** — strong in claims + eligibility
   - **Direct payer** — AS2/SFTP for payers that accept direct connections
3. **Routing rules**: configurable per payer — which clearinghouse handles which payer_id. Default clearinghouse + per-payer overrides.
4. **Failover**: if primary clearinghouse is down → automatically route through secondary. The 2024 Change Healthcare ransomware attack proved this is not theoretical — 94% of hospitals reported financial strain.
5. **Cost tracking**: per-transaction cost by clearinghouse for invoice reconciliation

### 3.11 Payer Companion Guide Management

Each payer interprets X12 differently:

1. **Companion guide rules table**: payer_id, transaction_type, segment, element, rule_type (required, conditional, forbidden, value_restriction), rule_definition, effective_date
2. **Level 4 validation**: after standard Level 1-3 validation passes, run payer-specific companion guide validation. A claim valid per X12 spec may still be rejected by a specific payer due to companion guide requirements.
3. **Rule examples**:
   - Payer A requires REF*G1 (prior auth number) on all claims >$500
   - Payer B rejects CLM05-3 (claim frequency) value "7" (replacement) — they only accept "1" (original)
   - Payer C requires NM1*82 (rendering provider) at the service line level, not just the claim level
4. **Rule sources**: payer companion guide PDFs (parsed via AI/NLP document intelligence), manual entry, clearinghouse-provided edit libraries
5. **Automated updates**: when a payer publishes an updated companion guide, alert operator. AI/NLP module can diff the old vs new guide and identify changed rules.
6. **Per-payer test mode**: test a claim against a specific payer's rules before live submission

### 3.12 Pre-Adjudication Claim Scrubbing

Validate claims against payer edit libraries BEFORE submission:

1. **Edit library**: configurable rule database containing payer-specific edits. Industry leaders maintain 100M+ edits covering: eligibility checks, coverage validation, contract-level reimbursement rules, modifier combinations, ICD-10 specificity, CPT compatibility, medical necessity, documentation sufficiency.
2. **Scrubbing pipeline**: before generating the X12 837, run the claim through the scrub engine:
   - Code validity: ICD-10, CPT, HCPCS codes exist in current code set version
   - Code pairing: diagnosis-procedure compatibility (is this procedure medically justified by this diagnosis?)
   - Modifier logic: are modifiers valid for this procedure code and place of service?
   - Eligibility: member active on date of service with coverage for this service type?
   - Prior auth: does this procedure require prior auth? Is auth number present and valid?
   - Timely filing: is the claim within the payer's filing deadline?
   - Duplicate: has this claim (same member, same procedure, same date, same provider) already been submitted?
3. **Scrub result**: CLEAN (submit), ERRORS (reject with specific corrections needed), WARNINGS (submit but flag for follow-up)
4. **Impact**: first-pass acceptance rates jump from industry average 85% to 95%+. Reduces denials by 30-40%.

### 3.13 Predictive Denial Scoring

Before submission, predict probability of denial:

1. **Model input**: payer_id, procedure_code, diagnosis_codes, modifiers, place_of_service, provider_npi, member demographics, billed_amount
2. **Model training**: trained on historical claim outcomes (paid vs denied) with denial reason codes as features
3. **Output**: denial_probability (0.0-1.0), predicted_denial_reasons (top 3), recommended_corrections
4. **Routing**: if denial_probability > configurable threshold (default: 0.30), flag for human review BEFORE submission with specific improvement suggestions
5. **Integration**: runs after claim scrubbing, before X12 generation. Scrubbing catches rule violations; denial prediction catches pattern-based risks.
6. **Model retraining**: monthly on rolling 12-month claim outcomes. Per-payer models where volume supports it.

### 3.14 835 Auto-Posting to Billing AR

When an 835 remittance is received and parsed:

1. **Claim matching**: match each CLP loop in the 835 to the original claim in Billing module by claim number (CLP01) or internal reference
2. **Payment posting**: for each matched claim, update AR record with: paid_amount, adjustment_amounts (by CARC/RARC), patient_responsibility, check/EFT number, payment_date
3. **Status update**: mark claim as paid, partially_paid, denied, or adjusted based on CLP02 status code
4. **Adjustment recording**: store each CAS segment adjustment with group code (CO, OA, PI, PR) + reason code + amount
5. **Unmatched handling**: CLP loops that don't match a known claim → queue for manual research
6. **Reconciliation**: total of all CLP paid amounts should equal the BPR payment amount. Flag discrepancies.
7. **Event**: emit `payment.auto_posted` event consumed by Billing for AR update and DataIQ for financial analytics

### 3.15 X12 275 Clinical Attachments Support

CAQH CORE Attachments Infrastructure Rule (February 2026):

1. **275 transaction**: X12 275 Additional Information to Support a Health Care Claim
2. **Content**: clinical documentation (lab results, clinical notes, imaging reports) in HL7 C-CDA format embedded within the X12 275 envelope
3. **Use case**: when a payer requests additional information (via 277 claim request for additional info), respond with 275 containing the supporting documentation
4. **Generation**: AI/NLP module extracts relevant clinical data → format as C-CDA → wrap in X12 275 → transmit via EDI
5. **Parsing**: inbound 275 from providers → extract C-CDA content → route to appropriate processing queue

### 3.16 FHIR-to-X12 Bridge

CMS-0057-F mandates FHIR-based APIs by January 2027:

1. **FHIR R4 → X12 278**: map FHIR Prior Authorization Request to X12 278. Use the published X12/HL7 crosswalk.
2. **FHIR R4 → X12 270/271**: map FHIR Coverage/CoverageEligibilityRequest to X12 270, and X12 271 response back to FHIR CoverageEligibilityResponse
3. **FHIR API endpoints**: accept FHIR resources, convert to X12 internally, process, return FHIR response
4. **Dual support**: during transition period (2026-2028), support both FHIR and X12 for the same transaction types
5. **Readiness**: even if our clients don't require FHIR immediately, having the bridge ready positions InfinityRx for the mandate

### 3.17 Code Set Version Management

Code sets update on different schedules — payers may lag behind:

1. **Code set registry**: ICD-10-CM (annual, Oct 1), ICD-10-PCS (annual, Oct 1), CPT (annual, Jan 1), HCPCS (quarterly), NDC (continuous), revenue codes (periodic)
2. **Per-payer version tracking**: track which code set version each payer currently accepts. Some payers take weeks to update after a new version release.
3. **Grace period handling**: during code set transition periods (e.g., October for ICD-10), both old and new codes may be valid. Configure per-payer acceptance window.
4. **Validation awareness**: claim scrubbing validates codes against the version the TARGET PAYER accepts, not just the latest version
5. **Alerts**: when a new code set version is released, alert operators. When submitting a claim with a code from the new version to a payer that hasn't confirmed support, warn.

### 3.18 ISA Fixed-Width Field Handling

The #1 X12 parsing bug — explicitly required in our parser:

1. **ISA06 and ISA08 are ALWAYS 15 characters**, padded with trailing spaces. MUST NOT trim whitespace from ISA segment fields.
2. **ISA16 is the sub-element separator** — typically `:` or `>`. Read from position 105 of the ISA segment (fixed position).
3. **Segment terminator**: read from the character immediately following ISA16 in the first 106+ characters. Typically `~` but can be any character.
4. **Element separator**: ISA[3] — typically `*` but configurable per file.
5. **Parser MUST**: detect all three delimiters from the ISA segment before parsing any other segment. Never assume `*~:` as defaults.
6. **Generator MUST**: pad ISA06 and ISA08 to exactly 15 characters with trailing spaces. Pad ISA13 to exactly 9 digits with leading zeros.

### 3.19 AS2 Certificate Lifecycle Management

X.509 certificates expire — unmanaged expiry kills ALL transactions with that partner:

1. **Certificate tracking table**: trading_partner_id, cert_type (signing, encryption, TLS), issuer, serial_number, subject, not_before, not_after, fingerprint_sha256, file_id, status (active, staging, expired, revoked)
2. **Automated alerts**: 90/60/30/7 days before expiry → alert operations AND trading partner contact
3. **Rotation workflow**: upload new certificate → test in staging environment → swap to production → archive old certificate
4. **Pre-cutover testing**: before activating a renewed certificate, send a test transaction and verify the trading partner accepts it
5. **Emergency rotation**: if a certificate is compromised, immediate revocation + rotation with audit trail
6. **SHA-256 minimum**: enforce SHA-256 or stronger hashes on all certificates. Reject SHA-1.

### 3.20 Trading Partner Agreement / BAA Tracking

HIPAA requires BAAs with every entity handling PHI in EDI transactions:

1. **Agreement tracking table**: trading_partner_id, agreement_type (BAA, TPA, NDA), executed_date, effective_date, expiry_date, renewal_date, document_file_id, signatory_name, signatory_title
2. **Expiry alerts**: 90/60/30 days before expiry → alert compliance team
3. **Enforcement**: configurable per tenant — block new EDI transactions if BAA is expired, or warn-only mode
4. **Audit readiness**: all agreements stored and retrievable for HIPAA audit

### 3.21 EDI-Specific Role-Based Access Control

Separation of duties for EDI operations:

| Role | Permissions | Cannot |
|---|---|---|
| Submitter | Initiate 837 transfers, view transmission status | Alter translator rules, manage certificates, view raw PHI payloads |
| Validator | Manage edit rules, trading partner configurations, companion guide rules | Access production encryption keys, submit live transactions |
| Operations | Monitor queues, reprocess failures, view DLQ, acknowledge alerts | Modify trading partner configs, manage certificates |
| Security Admin | Manage certificates, IP allowlists, audit configurations, key rotation | Submit transactions, modify business rules |

All roles mapped through Core Platform RBAC system.

### 3.22 Inbound Response SLA Monitoring

Track expected responses and alert when they don't arrive:

1. **Expected response matrix**: after submitting an outbound transaction, the system expects a response:
   - 837 submission → expect 277CA within 24 hours, 835 within 14 days
   - 270 eligibility → expect 271 within 20 seconds (real-time) or 24 hours (batch)
   - 276 claim status → expect 277 within 20 seconds (real-time) or 24 hours (batch)
2. **SLA tracking**: record expected_response_by timestamp on each outbound transaction
3. **Alert**: when expected_response_by passes without a matched response → alert operations
4. **Per-payer SLA dashboard**: track actual response times per payer. Identify payers consistently missing SLAs.
5. **Acceptance rate monitoring**: track per-payer acceptance rates. Alert when acceptance rate drops below threshold (may indicate companion guide change or system issue at the payer).

### 3.23 Real-Time Transaction Monitoring Dashboard

Operational visibility into EDI pipeline:

1. **Transactions in flight**: count by type, by trading partner, by status (pending, transmitted, awaiting ack)
2. **Acceptance rate (24h/7d/30d)**: percentage of transactions accepted vs rejected, by payer, by type
3. **Acknowledgment turnaround**: average/p50/p95 time from submission to acknowledgment, by payer
4. **DLQ depth**: EDI-related events in dead letter queue
5. **Certificate expiry countdown**: trading partners with certificates expiring within 90 days
6. **Error breakdown**: top 10 rejection reason codes with trend arrows
7. **Volume trending**: transactions per hour/day with comparison to historical baseline

---

## 4. API Endpoints

```
/api/v1/edi/

# Generation
POST   /generate/835                    Generate 835 from payment batch
POST   /generate/837p                   Generate 837P from professional claims
POST   /generate/837i                   Generate 837I from institutional claims
POST   /generate/270                    Generate 270 eligibility inquiry
POST   /generate/271                    Generate 271 eligibility response
POST   /generate/276                    Generate 276 claim status request
POST   /generate/277                    Generate 277 claim status response
POST   /generate/278                    Generate 278 prior auth request/response
POST   /generate/834                    Generate 834 enrollment
POST   /generate/ncpdp-batch            Generate NCPDP batch

# Parsing (inbound)
POST   /parse                           Upload and parse any X12 file (auto-detect type)
POST   /parse/835                       Parse inbound 835
POST   /parse/837                       Parse inbound 837 (auto-detect P/I/D)
POST   /parse/271                       Parse inbound 271 eligibility response
POST   /parse/277                       Parse inbound 277 claim status response
POST   /parse/999                       Parse inbound 999 acknowledgment
POST   /parse/ncpdp-batch               Parse inbound NCPDP batch

# Validation
POST   /validate                        Validate any X12 file without processing
GET    /validate/code-sets              List supported code sets and versions

# Trading Partners
GET    /trading-partners                List trading partners
POST   /trading-partners                Create trading partner
PUT    /trading-partners/{id}           Update trading partner
POST   /trading-partners/{id}/test      Send test transaction

# Transaction Files
GET    /files                           List transaction files (filterable)
GET    /files/{id}                      File detail with validation results
GET    /files/{id}/download             Download raw EDI file
GET    /files/{id}/records              Individual transactions within file

# Acknowledgments
GET    /acknowledgments                 List pending/received acknowledgments
GET    /acknowledgments/unmatched       Acknowledgments that couldn't be matched

# Transmission
POST   /transmit/{file_id}             Transmit file to trading partner
GET    /transmit/queue                  Files pending transmission
GET    /transmit/history                Transmission history

# Compliance
GET    /compliance                      Compliance dashboard
GET    /compliance/report               Compliance report for period
GET    /compliance/rejection-rates      Rejection rates by partner/type/period
```

---

## 5. Events

### Published
- `edi.file_generated` — EDI file created
- `edi.file_transmitted` — file sent to trading partner
- `edi.file_acknowledged` — acknowledgment received (with accept/reject status)
- `edi.file_rejected` — file rejected by trading partner
- `edi.transaction_parsed` — inbound transaction parsed
- `edi.validation_failed` — file failed validation
- `edi.835_generated` — specifically for 835 (consumed by Billing for remittance tracking)
- `edi.837_received` — inbound claim received (consumed by Medical Claims for processing)
- `edi.271_received` — eligibility response received (consumed by Member Management)
- `edi.834_received` — enrollment file received (consumed by Member Management)

### Consumed
- `payment_batch.submitted` — trigger 835 generation
- `claim.adjudicated` — may trigger outbound 837 for COB
- `member.eligibility_checked` — may trigger 270/271

---

## 6. Default Implementation

Ships fully functional:

- **12 X12 transaction generators** (835, 837P, 837I, 837D, 270, 271, 276, 277, 278, 834, 820, 999) + **X12 275 attachments**
- **12 X12 transaction parsers** with auto-type-detection
- **JSON ↔ X12 bidirectional translation** — every endpoint accepts both JSON and raw X12
- **4-level validation engine** (syntax, implementation guide, business rules, payer companion guide)
- **Pre-adjudication claim scrubbing** with configurable payer edit libraries (30-40% denial reduction)
- **Predictive denial scoring** — ML-based denial probability before submission
- **NCPDP Batch 1.2** generator and parser
- **835 pharmacy remittance** with full HIPAA 005010X221A1 compliance + **835 auto-posting to Billing AR**
- **Clearinghouse integration layer** — adapters for Stedi, Availity, Change Healthcare, direct payer (AS2/SFTP) with failover routing
- **Payer companion guide management** — per-payer rules, Level 4 validation, automated guide diff detection
- **Trading partner management** with per-partner configuration
- **Transport layer**: AS2 (S/MIME encrypted, SHA-256 signed, MDN receipts), SFTP, direct connect, manual
- **AS2 certificate lifecycle management** — tracking, expiry alerting, rotation workflow, staging test
- **Acknowledgment processing**: TA1, 999, 277CA matching and status tracking
- **Control number management**: auto-incrementing ISA/GS/ST sequences per partner with ISA fixed-width field handling
- **FHIR-to-X12 bridge** — 278 PA and 270/271 eligibility mapping for CMS-0057-F 2027 readiness
- **Code set version management** — per-payer code set version tracking with grace period handling
- **Inbound response SLA monitoring** — expected response tracking with alerts
- **Real-time transaction monitoring dashboard** — acceptance rates, turnaround times, error breakdown
- **Compliance reporting**: rejection rates, first-pass acceptance, turnaround times
- **Trading Partner Agreement / BAA tracking** with expiry alerting
- **EDI-specific RBAC** — submitter, validator, operations, security admin roles

---

## 7. Performance Requirements

- 835 generation (1,000 claims): <10 seconds
- 837 parsing (10,000 claims): <30 seconds
- Validation (per file): <5 seconds
- Control number generation: <10ms (must be atomic, no duplicates)

---

## 8. Data Retention

- Transaction files: 7 years (HIPAA requirement)
- Transaction records: 7 years
- Control number sequences: indefinite
- Trading partner configs: indefinite
- Compliance logs: 7 years

---

## 9. Test Scenarios (100% Coverage Required)

### Critical Paths (100%)
- 835 generation produces valid X12 per 005010X221A1 (validate against known-good reference file)
- 837P parsing extracts all claim fields correctly from known test file
- Validation catches: missing required segment, invalid code value, wrong element count, control number mismatch
- Control numbers increment atomically (concurrent generation produces no duplicates)
- Acknowledgment matching: 999 correctly matched to original outbound file
- ISA/GS/ST envelope counts are correct

### Golden Master Tests
- Generate 835 from test data → compare against golden master file
- Generate 837P from test data → compare against golden master file
- Generate 270 from test data → compare against golden master file
- Parse known 835 file → verify extracted amounts match expected values (Decimal, penny-perfect)

### Edge Cases
- File with multiple functional groups → each parsed independently
- 837 with 10,000 claims → generates without memory overflow
- Trading partner in test mode → ISA15 = 'T', no production transmission
- Inbound file with unknown transaction type → logged, not crashed
- Control number reaches max → wraps to 1 (with alert)

---

## 10. Session Decomposition

1. **X12 engine core + 835 + JSON layer**: X12 segment builder/parser framework, envelope management (ISA/GS/ST/SE/GE/IEA), ISA fixed-width field handling, control number sequences, delimiter detection, JSON ↔ X12 bidirectional translation layer (JSON schemas per transaction type), 835 generator (full 005010X221A1), 835 parser, 835 auto-posting to Billing AR, validation engine (4 levels including payer companion guide)
2. **837 + 270/271 + 276/277 + scrubbing**: 837P/837I/837D generators and parsers, 270/271 generators and parsers, 276/277 generators and parsers, code set validation (ICD-10, CPT, HCPCS) with version management, pre-adjudication claim scrubbing engine, payer companion guide rules management, predictive denial scoring model
3. **278 + 275 + 834 + FHIR bridge**: 278 generator/parser, X12 275 clinical attachments (C-CDA), 834 parser, 999/TA1 acknowledgment processing, FHIR-to-X12 bridge (278 PA, 270/271 eligibility), NCPDP batch support
4. **Transport + clearinghouse + monitoring**: AS2 transport (S/MIME, certificates, MDN), SFTP transport, clearinghouse adapter interface + Stedi/Availity/Change adapters, routing rules with failover, AS2 certificate lifecycle management, trading partner management, TPA/BAA tracking, EDI-specific RBAC, inbound response SLA monitoring, real-time transaction monitoring dashboard, compliance reporting
