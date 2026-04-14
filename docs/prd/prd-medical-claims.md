# PRD — Module 14: Medical Claims — FINAL

**Module:** Medical Claims  
**Folder:** `modules/medical-claims/`  
**Priority:** Phase 4  
**Dependencies:** Core Platform (1), Drug Database (2), Prescriber Directory (4), Member Management (5), EDI & Compliance (13), Billing (11)  

---

## 1. Purpose

Medical Claims processes drug claims that flow through the medical benefit rather than the pharmacy benefit. In a PBM, most claims are pharmacy claims (NCPDP D.0, processed at the pharmacy counter). But a significant and growing subset of drug spend — specialty infusions, physician-administered injectables, buy-and-bill drugs — flows through the medical benefit via CMS-1500 (professional) or UB-04 (institutional) claim forms.

This module matters because medical benefit drug spend now exceeds $150B annually and is the fastest-growing cost category. Health plan clients demand visibility into BOTH pharmacy and medical drug spend for a complete picture.

**What this module handles:**
1. **Medical benefit drug claims** — drugs billed via HCPCS J-codes, Q-codes, C-codes on CMS-1500/UB-04 forms
2. **Claim ingestion** — receive 837P/837I from EDI module, parse into internal claim records
3. **Drug identification** — map HCPCS codes to NDCs, identify the drug, pricing, and therapeutic class
4. **Medical claim adjudication support** — pricing, COB, accumulator impact for medical benefit drugs
5. **Provider-administered drug tracking** — buy-and-bill, white bagging, brown bagging, specialty pharmacy site-of-care
6. **Medical-pharmacy crossover** — unified view of total drug spend across both benefits
7. **340B detection on medical claims** — identify claims where 340B pricing was used
8. **Waste/overfill reporting** — CMS requires NDC and waste units on medical claims for certain drugs

**What this module does NOT do:**
- Does not process pharmacy benefit claims (Billing Module 11 handles NCPDP pharmacy claims)
- Does not handle non-drug medical claims (surgeries, E&M visits, lab work — those are outside PBM scope)
- Does not adjudicate in real-time like the Switch (Module 9) — medical claims are batch-processed

---

## 2. Data Model

```sql
CREATE SCHEMA medical_claims;

-- Medical claim records (one per claim line — service line level)
CREATE TABLE medical_claims.claim_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- Claim identity
    claim_number VARCHAR(50) NOT NULL,
    claim_line_number INTEGER NOT NULL DEFAULT 1,
    claim_type VARCHAR(10) NOT NULL,                   -- professional (CMS-1500), institutional (UB-04)
    
    -- Source
    source_transaction_id UUID,                        -- ref to edi.transaction_records
    source_file_type VARCHAR(10),                      -- 837P, 837I, manual, api
    received_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Patient
    member_id UUID,                                    -- ref to member_mgmt.members
    patient_member_id VARCHAR(100) NOT NULL,
    patient_first_name VARCHAR(255),
    patient_last_name VARCHAR(255),
    patient_dob DATE,
    patient_gender VARCHAR(1),
    
    -- Subscriber (if different from patient)
    subscriber_id VARCHAR(100),
    subscriber_relationship VARCHAR(5),
    
    -- Provider
    rendering_provider_npi VARCHAR(10) NOT NULL,
    rendering_provider_name VARCHAR(500),
    rendering_provider_taxonomy VARCHAR(20),
    
    billing_provider_npi VARCHAR(10),
    billing_provider_name VARCHAR(500),
    billing_provider_tax_id VARCHAR(11),
    
    referring_provider_npi VARCHAR(10),
    
    facility_npi VARCHAR(10),
    facility_name VARCHAR(500),
    
    -- Service
    date_of_service DATE NOT NULL,
    date_of_service_end DATE,
    place_of_service VARCHAR(2),                       -- CMS POS codes (11=office, 21=inpatient, 22=outpatient, etc.)
    type_of_bill VARCHAR(4),                           -- UB-04 only (e.g., 0131, 0121)
    
    -- Procedure
    procedure_code VARCHAR(10) NOT NULL,               -- HCPCS/CPT code
    procedure_code_type VARCHAR(10) DEFAULT 'HCPCS',   -- HCPCS, CPT, CDT
    modifier_1 VARCHAR(5),
    modifier_2 VARCHAR(5),
    modifier_3 VARCHAR(5),
    modifier_4 VARCHAR(5),
    
    revenue_code VARCHAR(4),                           -- UB-04 only
    
    -- Drug identification (the PBM-relevant part)
    ndc VARCHAR(11),                                   -- NDC on medical claim (CMS requires for certain drugs)
    ndc_qualifier VARCHAR(2),                          -- N4
    drug_name VARCHAR(500),
    drug_quantity DECIMAL(10,3),
    drug_unit VARCHAR(5),                              -- UN (unit), ML, GR, etc.
    drug_unit_price DECIMAL(12,6),
    
    -- HCPCS-to-NDC mapping result
    mapped_ndc VARCHAR(11),                            -- NDC from HCPCS crosswalk if claim NDC absent
    mapping_confidence VARCHAR(20),                     -- exact, high, medium, low, manual
    
    -- Diagnosis
    diagnosis_code_1 VARCHAR(10),
    diagnosis_code_2 VARCHAR(10),
    diagnosis_code_3 VARCHAR(10),
    diagnosis_code_4 VARCHAR(10),
    diagnosis_code_qualifier VARCHAR(5) DEFAULT 'ABK',  -- ABK=ICD-10-CM
    diagnosis_pointer VARCHAR(4),                       -- which diagnosis relates to this service line
    
    -- Amounts (ALL Decimal, ROUND_HALF_UP)
    billed_amount DECIMAL(12,2) NOT NULL,
    allowed_amount DECIMAL(12,2),
    paid_amount DECIMAL(12,2),
    patient_responsibility DECIMAL(12,2),
    copay_amount DECIMAL(12,2),
    coinsurance_amount DECIMAL(12,2),
    deductible_amount DECIMAL(12,2),
    
    -- Adjustments
    adjustment_reason_codes JSONB,                     -- [{group, code, amount}]
    
    -- Drug waste
    waste_quantity DECIMAL(10,3),
    waste_amount DECIMAL(12,2),
    
    -- Site of care
    site_of_care VARCHAR(50),                          -- office_infusion, hospital_outpatient, home_infusion, specialty_pharmacy, asc
    administration_method VARCHAR(50),                  -- buy_and_bill, white_bag, brown_bag, self_administered
    
    -- 340B
    is_340b BOOLEAN DEFAULT FALSE,
    entity_340b_id VARCHAR(20),
    
    -- COB
    payer_sequence VARCHAR(10),                         -- primary, secondary, tertiary
    other_payer_paid DECIMAL(12,2),
    
    -- Authorization
    prior_auth_number VARCHAR(50),
    prior_auth_status VARCHAR(50),
    
    -- Processing
    status VARCHAR(50) DEFAULT 'received',
    -- received, validated, priced, adjudicated, paid, denied, appealed, voided
    
    denial_reason_code VARCHAR(10),
    denial_reason_description TEXT,
    
    -- Accumulator impact
    applied_to_deductible DECIMAL(12,2),
    applied_to_oop DECIMAL(12,2),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, claim_number, claim_line_number)
);

CREATE INDEX idx_medical_tenant_date ON medical_claims.claim_records(tenant_id, date_of_service DESC);
CREATE INDEX idx_medical_member ON medical_claims.claim_records(tenant_id, patient_member_id);
CREATE INDEX idx_medical_provider ON medical_claims.claim_records(tenant_id, rendering_provider_npi);
CREATE INDEX idx_medical_ndc ON medical_claims.claim_records(tenant_id, ndc);
CREATE INDEX idx_medical_hcpcs ON medical_claims.claim_records(tenant_id, procedure_code);
CREATE INDEX idx_medical_status ON medical_claims.claim_records(tenant_id, status);
CREATE INDEX idx_medical_claim_num ON medical_claims.claim_records(tenant_id, claim_number);

-- HCPCS-to-NDC crosswalk
CREATE TABLE medical_claims.hcpcs_ndc_crosswalk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    hcpcs_code VARCHAR(10) NOT NULL,
    hcpcs_description VARCHAR(500),
    
    ndc VARCHAR(11) NOT NULL,
    ndc_description VARCHAR(500),
    
    -- Dosage mapping
    hcpcs_dosage_descriptor VARCHAR(255),              -- "per 1 mg", "per 10 units"
    hcpcs_unit_quantity DECIMAL(10,4),
    ndc_package_quantity DECIMAL(10,4),
    conversion_factor DECIMAL(12,6),                   -- HCPCS units → NDC units
    
    -- Validity
    effective_date DATE NOT NULL,
    termination_date DATE,
    
    data_source VARCHAR(50),                           -- cms_asp, manual, fdb
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(hcpcs_code, ndc, effective_date)
);

CREATE INDEX idx_hcpcs_crosswalk ON medical_claims.hcpcs_ndc_crosswalk(hcpcs_code, effective_date DESC);

-- ASP (Average Sales Price) pricing for medical benefit drugs
CREATE TABLE medical_claims.asp_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    hcpcs_code VARCHAR(10) NOT NULL,
    hcpcs_description VARCHAR(500),
    
    asp_per_unit DECIMAL(12,6) NOT NULL,               -- CMS ASP price per HCPCS billing unit
    payment_limit DECIMAL(12,6),                       -- ASP + 6% (Medicare payment limit)
    
    quarter VARCHAR(6) NOT NULL,                       -- YYYY-QN (e.g., 2026-Q1)
    effective_date DATE NOT NULL,
    
    data_source VARCHAR(50) DEFAULT 'cms_asp',
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(hcpcs_code, quarter)
);

-- Medical-pharmacy unified drug spend view
CREATE TABLE medical_claims.unified_drug_spend (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    member_id UUID,
    member_id_display VARCHAR(100),
    
    ndc VARCHAR(11),
    drug_name VARCHAR(500),
    therapeutic_class VARCHAR(255),
    
    benefit_type VARCHAR(20) NOT NULL,                 -- pharmacy, medical
    
    -- Source reference
    pharmacy_claim_id UUID,                            -- ref to billing.claim_records (if pharmacy)
    medical_claim_id UUID,                             -- ref to medical_claims.claim_records (if medical)
    
    date_of_service DATE NOT NULL,
    
    -- Amounts (Decimal)
    billed_amount DECIMAL(12,2),
    allowed_amount DECIMAL(12,2),
    paid_amount DECIMAL(12,2),
    patient_pay DECIMAL(12,2),
    
    -- For analytics
    quantity DECIMAL(10,3),
    days_supply INTEGER,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_unified_spend_tenant ON medical_claims.unified_drug_spend(tenant_id, date_of_service DESC);
CREATE INDEX idx_unified_spend_member ON medical_claims.unified_drug_spend(tenant_id, member_id);
CREATE INDEX idx_unified_spend_ndc ON medical_claims.unified_drug_spend(tenant_id, ndc);
```

---

## 3. Business Logic

### 3.1 Claim Ingestion Pipeline

**From EDI module (primary path):**
1. EDI module parses inbound 837P or 837I file
2. EDI emits `edi.837_received` event with transaction_record_id
3. Medical Claims consumes the event
4. For each claim line in the 837: check if it's a drug claim (HCPCS J-code, Q-code, or NDC present)
5. Drug claim → create medical_claims.claim_record
6. Non-drug claim → skip (outside PBM scope) or store as reference depending on tenant config

**From API (secondary path):**
1. Client submits claim via API (JSON, not X12)
2. Validate required fields
3. Create claim record

**From file upload (tertiary path):**
1. Client uploads CSV/Excel of medical claims
2. Parse, validate, create claim records
3. Same configurable format mapping as Billing enrollment files

### 3.2 Drug Identification

The critical challenge: medical claims often don't have an NDC. They have HCPCS codes (J0135, J9035, etc.) which are drug categories, not specific products.

**Step 1 — Direct NDC extraction:**
- CMS requires NDC on medical claims for many drugs (Medicare Part B)
- If claim has NDC in the NDC field → use it directly
- Validate NDC against Drug Database (Module 2)
- Confidence: EXACT

**Step 2 — HCPCS-to-NDC crosswalk:**
- If no NDC on claim, use HCPCS code to look up possible NDCs
- CMS publishes quarterly ASP-NDC crosswalk files
- HCPCS code may map to 10+ NDCs (all brands and generics of the same drug)
- If only one NDC is possible → confidence HIGH
- If multiple NDCs → use prescriber prescribing history, facility formulary, or pricing to narrow
- Confidence: HIGH (single match) / MEDIUM (narrowed from multiple) / LOW (multiple possible)

**Step 3 — Manual mapping:**
- If HCPCS code has no crosswalk entry → flag for manual review
- Operator maps HCPCS to NDC and the mapping is saved for future claims
- Confidence: MANUAL

**Output:** Every medical drug claim gets a mapped_ndc and mapping_confidence. This NDC links to Drug Database for pricing, therapeutic class, and interaction data.

### 3.3 Medical Claim Pricing

**ASP-based pricing (Medicare Part B standard):**
1. Look up HCPCS code in asp_pricing table for the quarter containing the date_of_service
2. Payment limit = ASP + 6% (Medicare standard, configurable for commercial)
3. Allowed amount = payment_limit × quantity
4. Compare billed_amount to allowed_amount → pay lesser of

**Contract-based pricing (commercial):**
1. Tenant-specific fee schedules per HCPCS code
2. May be: % of ASP, % of AWP, flat rate per unit, per diem
3. Fee schedule stored per tenant, per network, per place_of_service

**Waste calculation:**
1. CMS requires reporting of drug waste (unused portion of single-use vial)
2. Billed quantity = administered quantity + waste quantity
3. Paid amount based on administered quantity only (waste not reimbursed under most contracts)
4. JW modifier indicates waste units on claim
5. Track waste_quantity and waste_amount per claim

### 3.4 Site-of-Care Analysis

Classify where the drug was administered:

| Place of Service | Code | Site Category | Typical Cost |
|---|---|---|---|
| Physician office | 11 | office_infusion | $$ |
| Hospital outpatient | 22 | hospital_outpatient | $$$$ |
| Ambulatory surgical center | 24 | asc | $$$ |
| Home | 12 | home_infusion | $$ |
| Pharmacy (specialty) | 01 | specialty_pharmacy | $ |

Site-of-care steering is a major cost management strategy. The same infusion drug can cost 3-5x more at a hospital outpatient facility than at a physician office or home infusion setting. This module tracks site-of-care to enable DataIQ analytics and client reporting.

### 3.5 Administration Method Tracking

| Method | Description | Who Buys Drug | Who Administers |
|---|---|---|---|
| Buy-and-bill | Provider purchases drug, bills payer for drug + administration | Provider | Provider |
| White bagging | Specialty pharmacy ships drug to provider site, billed under pharmacy benefit | PBM/Pharmacy | Provider |
| Brown bagging | Specialty pharmacy ships drug to patient, patient brings to provider | PBM/Pharmacy | Provider |
| Self-administered | Patient administers at home (oral, self-injection) | PBM/Pharmacy | Patient |

Tracking administration method enables:
- Identifying opportunities to move buy-and-bill to white/brown bagging (cost savings)
- Detecting 340B arbitrage (provider buys at 340B price, bills at ASP+6%)
- Understanding total cost of therapy (drug + administration fee)

### 3.6 340B Detection on Medical Claims

340B entities (hospitals, clinics) purchase drugs at significant discounts:

1. Check billing_provider_npi against Pharmacy Directory 340B entity list (HRSA database)
2. If billing provider is a 340B entity and drug is 340B-eligible → flag as potential 340B claim
3. CMS requires modifier JG or TB on 340B claims (but compliance varies)
4. Track 340B volume and estimated discount for DataIQ analytics
5. Alert when 340B volume increases unexpectedly (potential program expansion or misuse)

### 3.7 Medical-Pharmacy Crossover View

Unified drug spend across both benefits:

1. For every medical drug claim processed: insert into unified_drug_spend with benefit_type='medical'
2. Billing module emits pharmacy claim events → insert into unified_drug_spend with benefit_type='pharmacy'
3. DataIQ and Reporting modules query unified_drug_spend for total drug spend analytics
4. Per-member drug timeline: all drugs (pharmacy + medical) in chronological order
5. Therapeutic duplication detection: member receiving same drug via both pharmacy and medical benefit
6. Cost comparison: same drug, pharmacy benefit vs medical benefit pricing

### 3.8 Denial Management

Medical claim denials with tracking:

1. **Denial reason codes**: CARC (Claim Adjustment Reason Codes) and RARC (Remittance Advice Remark Codes)
2. **Common denial reasons for medical drugs**: no prior auth, not medically necessary, NDC missing, wrong place of service, provider not in network, 340B billing error
3. **Appeal workflow**: denied claim → operator initiates appeal → appeal letter generated (via AI/NLP module) → resubmit via EDI
4. **Denial analytics**: denial rate by HCPCS code, by provider, by payer, by denial reason → DataIQ

### 3.9 Accumulator Integration

Medical drug claims impact member accumulators:

1. After pricing: determine patient_responsibility (copay + coinsurance + deductible)
2. Call Member Management accumulator service: apply patient_responsibility to deductible and OOP accumulators
3. Track: applied_to_deductible and applied_to_oop on claim record
4. Unified accumulators: pharmacy and medical claims both count toward the same deductible/OOP max

---

## 4. API Endpoints

```
/api/v1/medical-claims/

# Claim Management
GET    /claims                          List/search medical drug claims (filterable)
POST   /claims                          Submit medical claim (JSON)
GET    /claims/{id}                     Claim detail
PUT    /claims/{id}                     Update claim
POST   /claims/upload                   Upload claims file (CSV/Excel)

# Drug Identification
GET    /claims/{id}/drug-mapping        View NDC mapping for claim
POST   /claims/{id}/drug-mapping        Manual NDC mapping override
GET    /crosswalk/{hcpcs_code}          HCPCS-to-NDC crosswalk lookup
GET    /crosswalk/unmapped              Claims pending manual NDC mapping

# Pricing
GET    /asp/{hcpcs_code}               ASP pricing for HCPCS code
GET    /asp/current-quarter             Current quarter ASP file summary
POST   /asp/refresh                     Refresh ASP pricing from CMS

# Unified Spend
GET    /unified-spend                   Unified drug spend (pharmacy + medical)
GET    /unified-spend/member/{member_id} Per-member drug timeline
GET    /unified-spend/duplications      Therapeutic duplications (same drug, both benefits)

# 340B
GET    /340b/claims                     340B-flagged medical claims
GET    /340b/summary                    340B volume and estimated discount summary

# Waste
GET    /waste/report                    Drug waste report by HCPCS, provider, period

# Denial Management
GET    /denials                         Denied claims
GET    /denials/analytics               Denial rates by code/provider/payer/reason
POST   /claims/{id}/appeal              Initiate appeal

# Site of Care
GET    /site-of-care/analysis           Site-of-care distribution and cost comparison
GET    /site-of-care/opportunities      Opportunities for site-of-care steering

# Admin
GET    /stats                           Processing statistics
POST   /refresh/crosswalk               Refresh HCPCS-NDC crosswalk from CMS
```

---

## 5. Events

### Published
- `medical_claim.received` — medical drug claim ingested
- `medical_claim.priced` — claim priced
- `medical_claim.adjudicated` — claim adjudicated (paid or denied)
- `medical_claim.denied` — claim denied with reason
- `medical_claim.appealed` — denial appealed
- `medical_claim.340b_detected` — potential 340B claim identified
- `medical_claim.waste_reported` — waste units reported
- `medical_claim.unified_spend_updated` — unified spend record created/updated
- `medical_claim.therapeutic_duplication` — same drug found on both benefits for same member

### Consumed
- `edi.837_received` — inbound 837P/837I from EDI module
- `claim.adjudicated` (pharmacy) — from Billing, to populate unified_drug_spend
- `member.accumulator_updated` — from Member Management, to reflect current accumulator state

---

## 6. Default Implementation

Ships fully functional:

- **837P/837I claim ingestion** from EDI module with drug claim filtering
- **HCPCS-to-NDC crosswalk** with CMS ASP quarterly data, multi-step mapping (exact NDC → HCPCS crosswalk → manual), confidence scoring
- **ASP-based pricing** with quarterly refresh from CMS
- **Contract-based pricing** configurable per tenant/network/POS
- **Drug waste tracking** with JW modifier detection and waste reporting
- **Site-of-care classification** from POS codes with cost comparison analytics
- **Administration method tracking** (buy-and-bill, white/brown bag, self-administered)
- **340B detection** using HRSA database cross-reference and modifier tracking
- **Medical-pharmacy unified spend view** across both benefits
- **Therapeutic duplication detection** — same drug on pharmacy and medical benefit
- **Denial management** with CARC/RARC reason tracking and appeal workflow
- **Accumulator integration** — medical drug claims impact member deductible/OOP
- **CMS ASP quarterly pricing refresh** automated

---

## 7. Performance Requirements

- Claim ingestion (single claim): <100ms
- Claim ingestion (batch 10,000 claims): <5 minutes
- HCPCS-to-NDC lookup: <50ms
- ASP pricing lookup: <20ms
- Unified spend query (single member): <200ms

---

## 8. Data Retention

- Claim records: 7 years (HIPAA)
- HCPCS-NDC crosswalk: indefinite (reference data, versioned by effective date)
- ASP pricing: indefinite (quarterly snapshots preserved for historical repricing)
- Unified drug spend: 3 years operational, then archive

---

## 9. Test Scenarios (100% Coverage Required)

### Critical Paths (100%)
- 837P claim with NDC → correctly parsed, drug identified, priced, and stored
- 837I claim without NDC → HCPCS crosswalk identifies correct NDC
- ASP pricing returns correct amount for specific quarter
- Waste calculation: billed_quantity - administered_quantity = waste_quantity (Decimal)
- 340B detection flags claims from known 340B entities
- Unified spend correctly merges pharmacy and medical claims for same member
- Therapeutic duplication detected when same NDC appears on both benefits
- Accumulator impact: medical claim correctly updates member deductible

### Edge Cases
- HCPCS code with 50+ possible NDCs → returns all with confidence LOW, flags for manual review
- Claim from future quarter (no ASP pricing yet) → use most recent available quarter with warning
- Member on both pharmacy and medical benefit with same drug same day → not flagged as duplication (COB scenario)
- 837P with revenue code (institutional field on professional form) → ignored, not error
- Zero-dollar claim (capitated payment) → processed, amounts stored as $0.00

---

## 10. Session Decomposition

1. **Core claims + ingestion**: claim_records table, 837P/837I ingestion from EDI events, API/file upload ingestion, claim validation, drug filtering (HCPCS J/Q/C-code detection), claim CRUD API, status management
2. **Drug identification + pricing**: HCPCS-NDC crosswalk table and lookup, CMS ASP pricing integration (quarterly refresh), multi-step drug mapping (NDC → crosswalk → manual), confidence scoring, contract-based pricing, waste calculation, site-of-care classification, administration method tracking
3. **340B + unified spend + denials + accumulators**: 340B detection (HRSA cross-reference), unified_drug_spend population (from medical + pharmacy events), therapeutic duplication detection, denial management (CARC/RARC, appeal workflow), accumulator integration (call Member Management), analytics endpoints
