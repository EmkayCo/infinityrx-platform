# PRD — Module 5: Member Management — FINAL

**Module:** Member Management  
**Folder:** `modules/member-management/`  
**Priority:** Phase 3  
**Dependencies:** Core Platform (Module 1)  

---

## 1. Purpose

Member Management is the enrollment, eligibility, and benefit tracking system. It answers the foundational question for every claim: "Is this person covered, and what are their benefits?" Every module that touches a member — adjudication (eligibility check), billing (invoicing by member), ReclaimRx (member profiling), reporting (member analytics), DataIQ (adherence, high-cost claimant) — queries this module.

**What this module manages:**
- Member enrollment and demographics
- Eligibility (active coverage, effective/termination dates, benefit phases)
- Plan assignment (which plan design applies to which member)
- Group/employer association
- Dependent relationships
- Accumulator tracking (deductible, copay, OOP max, MOOP — both member and family)
- Coverage history (current and historical coverage periods)
- COB (Coordination of Benefits) — primary/secondary/tertiary payer sequencing
- Member ID card data (BIN, PCN, Group, Member ID, Person Code)

**Data sources:**
- Client enrollment files (834 EDI or custom CSV/Excel)
- Real-time enrollment API (client systems push enrollment changes)
- Manual entry (portal or operator)
- 270/271 eligibility transactions (real-time eligibility verification)

---

## 2. Data Model

```sql
CREATE SCHEMA member_mgmt;

-- ═══════════════════════════════════════════════
-- GROUPS / EMPLOYERS
-- ═══════════════════════════════════════════════

CREATE TABLE member_mgmt.groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    group_number VARCHAR(50) NOT NULL,
    group_name VARCHAR(500) NOT NULL,
    
    -- Employer info
    employer_name VARCHAR(500),
    employer_tax_id VARCHAR(11),
    employer_address TEXT,
    
    -- Plan assignment
    default_plan_id UUID,
    
    -- Contact
    contact_name VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    
    -- Billing
    billing_cycle VARCHAR(50) DEFAULT 'monthly',
    payment_terms_days INTEGER DEFAULT 30,
    
    effective_date DATE NOT NULL,
    termination_date DATE,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, group_number)
);

-- ═══════════════════════════════════════════════
-- MEMBERS
-- ═══════════════════════════════════════════════

CREATE TABLE member_mgmt.members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- Identifiers
    member_id VARCHAR(100) NOT NULL,                   -- primary member identifier
    person_code VARCHAR(5) DEFAULT '01',               -- 01=subscriber, 02=spouse, 03+=dependents
    cardholder_id VARCHAR(100),                        -- subscriber's member_id (for dependents)
    alternate_id VARCHAR(100),                         -- SSN-based or other alternate ID
    
    -- Demographics (PHI — encrypted at rest)
    first_name VARCHAR(255) NOT NULL,
    middle_name VARCHAR(100),
    last_name VARCHAR(255) NOT NULL,
    suffix VARCHAR(20),
    date_of_birth DATE NOT NULL,
    gender VARCHAR(1) NOT NULL,                        -- M, F, U
    ssn_encrypted TEXT,                                -- AES-256 encrypted, never stored in plaintext
    
    -- Address (PHI)
    address_line_1 VARCHAR(255),
    address_line_2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    zip_code VARCHAR(10),
    country VARCHAR(2) DEFAULT 'US',
    
    -- Contact (PHI)
    phone VARCHAR(20),
    email VARCHAR(255),
    preferred_language VARCHAR(10) DEFAULT 'en',
    
    -- Relationship
    relationship_code VARCHAR(5),                      -- self, spouse, child, other
    subscriber_id UUID,                                -- FK to subscriber member record
    
    -- Group
    group_id UUID REFERENCES member_mgmt.groups(id),
    
    -- ID Card
    rx_bin VARCHAR(6) NOT NULL,
    rx_pcn VARCHAR(10),
    rx_group VARCHAR(15),
    
    -- Status
    status VARCHAR(50) DEFAULT 'active',
    -- active, inactive, terminated, cobra, pending
    
    enrollment_date DATE,
    termination_date DATE,
    termination_reason VARCHAR(100),
    
    -- Medicare
    is_medicare BOOLEAN DEFAULT FALSE,
    medicare_beneficiary_id VARCHAR(20),
    medicare_part_d_start DATE,
    lis_level VARCHAR(5),                              -- Low-Income Subsidy level
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, member_id, person_code)
);

CREATE INDEX idx_member_tenant_id ON member_mgmt.members(tenant_id, member_id);
CREATE INDEX idx_member_cardholder ON member_mgmt.members(tenant_id, cardholder_id);
CREATE INDEX idx_member_name ON member_mgmt.members(tenant_id, last_name, first_name);
CREATE INDEX idx_member_dob ON member_mgmt.members(tenant_id, date_of_birth);
CREATE INDEX idx_member_group ON member_mgmt.members(tenant_id, group_id);
CREATE INDEX idx_member_status ON member_mgmt.members(tenant_id, status);
CREATE INDEX idx_member_bin_pcn ON member_mgmt.members(rx_bin, rx_pcn, rx_group);

-- ═══════════════════════════════════════════════
-- COVERAGE PERIODS
-- ═══════════════════════════════════════════════

CREATE TABLE member_mgmt.coverage_periods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    member_id UUID NOT NULL REFERENCES member_mgmt.members(id),
    
    plan_id UUID,                                      -- ref to plan design (Module 6)
    plan_name VARCHAR(255),
    
    coverage_type VARCHAR(50) NOT NULL,                -- pharmacy, medical, dental, vision, pharmacy_medical
    
    effective_date DATE NOT NULL,
    termination_date DATE,
    
    -- Benefit year
    benefit_year_start DATE NOT NULL,
    benefit_year_end DATE NOT NULL,
    
    -- Status
    status VARCHAR(50) DEFAULT 'active',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_coverage_member ON member_mgmt.coverage_periods(tenant_id, member_id, effective_date);

-- ═══════════════════════════════════════════════
-- ACCUMULATORS (deductible, copay, OOP tracking)
-- ═══════════════════════════════════════════════

CREATE TABLE member_mgmt.accumulators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    member_id UUID NOT NULL REFERENCES member_mgmt.members(id),
    coverage_period_id UUID NOT NULL REFERENCES member_mgmt.coverage_periods(id),
    
    accumulator_type VARCHAR(50) NOT NULL,
    -- individual_deductible, family_deductible,
    -- individual_oop_max, family_oop_max,
    -- individual_moop, family_moop,
    -- copay_cap, benefit_max, specialty_accumulator,
    -- troop (True Out-of-Pocket for Part D)
    
    -- Thresholds
    limit_amount DECIMAL(12,2) NOT NULL,               -- the max/cap amount
    
    -- Current accumulation (updated with every claim)
    accumulated_amount DECIMAL(12,2) DEFAULT 0,
    remaining_amount DECIMAL(12,2),
    
    -- Copay assistance impact (accumulator/maximizer tracking)
    copay_assistance_applied DECIMAL(12,2) DEFAULT 0,
    copay_assistance_counted DECIMAL(12,2) DEFAULT 0,  -- how much counted toward accumulator
    
    -- Benefit phase (Part D)
    benefit_phase VARCHAR(50),
    -- deductible, initial_coverage, coverage_gap, catastrophic
    
    last_updated_claim_id UUID,
    last_updated_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, member_id, coverage_period_id, accumulator_type)
);

-- Accumulator transaction ledger (every change tracked)
CREATE TABLE member_mgmt.accumulator_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    accumulator_id UUID NOT NULL REFERENCES member_mgmt.accumulators(id),
    tenant_id UUID NOT NULL,
    
    transaction_type VARCHAR(50) NOT NULL,
    -- claim_applied, claim_reversed, manual_adjustment,
    -- benefit_year_reset, copay_assistance_applied, copay_assistance_excluded
    
    amount DECIMAL(12,2) NOT NULL,
    running_total DECIMAL(12,2) NOT NULL,              -- balance after this transaction
    
    claim_id UUID,
    claim_auth_number VARCHAR(50),
    description TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_accumulator_ledger ON member_mgmt.accumulator_ledger(accumulator_id, created_at);

-- ═══════════════════════════════════════════════
-- COORDINATION OF BENEFITS (COB)
-- ═══════════════════════════════════════════════

CREATE TABLE member_mgmt.cob_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    member_id UUID NOT NULL REFERENCES member_mgmt.members(id),
    
    payer_sequence VARCHAR(10) NOT NULL,                -- primary, secondary, tertiary
    
    other_payer_name VARCHAR(500),
    other_payer_bin VARCHAR(6),
    other_payer_pcn VARCHAR(10),
    other_payer_group VARCHAR(15),
    other_payer_member_id VARCHAR(100),
    other_payer_type VARCHAR(50),                       -- commercial, medicare, medicaid, tricare, va
    
    effective_date DATE NOT NULL,
    termination_date DATE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- ENROLLMENT FILE PROCESSING
-- ═══════════════════════════════════════════════

CREATE TABLE member_mgmt.enrollment_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    file_id UUID NOT NULL,                             -- ref to core.files
    file_name VARCHAR(500),
    file_type VARCHAR(50) NOT NULL,                    -- edi_834, csv, excel, api_batch
    
    -- Processing
    status VARCHAR(50) DEFAULT 'uploaded',
    -- uploaded, validating, validated, processing, completed, failed, partially_completed
    
    total_records INTEGER,
    processed_records INTEGER DEFAULT 0,
    added_records INTEGER DEFAULT 0,
    updated_records INTEGER DEFAULT 0,
    terminated_records INTEGER DEFAULT 0,
    error_records INTEGER DEFAULT 0,
    
    -- Validation
    validation_errors JSONB,                           -- [{row, field, error, value}]
    
    uploaded_by UUID,
    processed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- ELIGIBILITY VERIFICATION LOG
-- ═══════════════════════════════════════════════

CREATE TABLE member_mgmt.eligibility_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- Request
    requested_member_id VARCHAR(100),
    requested_dob DATE,
    requested_bin VARCHAR(6),
    requested_pcn VARCHAR(10),
    requested_group VARCHAR(15),
    
    -- Source
    source VARCHAR(50) NOT NULL,                       -- adjudication, portal, api, 270_271
    correlation_id UUID,
    
    -- Result
    is_eligible BOOLEAN NOT NULL,
    rejection_reason VARCHAR(255),
    
    -- Matched member
    matched_member_id UUID,
    matched_plan_name VARCHAR(255),
    
    response_time_ms INTEGER,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 3. Business Logic

### 3.1 Enrollment File Processing

1. **Upload**: operator uploads enrollment file (834 EDI, CSV, or Excel)
2. **Validation** (before processing):
   - File format matches expected format (configurable per client)
   - Required fields present (member_id, first_name, last_name, DOB, gender, effective_date, BIN/PCN/Group)
   - Field format validation (date formats, state codes, gender values)
   - Duplicate detection (same member_id + person_code in file)
   - Preview: show first 20 records + validation summary before processing
3. **Processing** (after operator confirms):
   - For each record: determine action (add, update, terminate) based on presence in current enrollment
   - **Add**: create member + coverage period + accumulators (initialized to $0)
   - **Update**: update changed demographics. If plan changed → close old coverage period, open new one, carry accumulators if same benefit year.
   - **Terminate**: set termination_date, mark status `terminated`. Do NOT delete.
4. **Results**: summary showing added/updated/terminated/errors. Error records downloadable as file with error descriptions.
5. All changes audit-logged.

### 3.2 Real-Time Eligibility Check

Called by adjudication engine on EVERY claim. Must be FAST.

1. Input: member_id (or cardholder_id + person_code), BIN, PCN, Group, date_of_service
2. Lookup:
   - Match member by: BIN + PCN + Group + member_id (primary path)
   - Or: cardholder_id + person_code (dependent lookup)
3. Verify:
   - Member status = active
   - Coverage period includes date_of_service
   - Coverage type includes pharmacy (or medical, depending on claim type)
4. Return:
   - Eligible: YES/NO
   - If YES: plan_id, plan_name, accumulator balances, COB info, benefit phase
   - If NO: rejection reason (not found, terminated, not effective, coverage gap)
5. Redis-cached: member eligibility cached for configurable TTL (default: 1 hour). Cache invalidated on enrollment change.
6. **Performance: <5ms from cache, <25ms from database**

### 3.3 Accumulator Management

**On claim adjudication (real-time update):**
1. Adjudication engine determines patient_pay amount
2. Call accumulator service: apply `patient_pay` to applicable accumulators (deductible, OOP max)
3. Accumulator service:
   - Check current accumulated_amount
   - If accumulator not yet met: apply amount, update accumulated_amount
   - If accumulator met: patient_pay may be reduced (deductible satisfied)
   - Write ledger entry for every change
4. Return: updated accumulator balances (so adjudication can adjust pricing)
5. **Decimal arithmetic only. ROUND_HALF_UP. Penny-perfect.**

**Copay assistance + accumulator interaction:**
1. If member has copay assistance AND the plan is an accumulator/maximizer plan:
   - Standard: copay assistance counts toward deductible/OOP → member reaches catastrophic faster
   - Accumulator program: copay assistance does NOT count → member must pay full deductible themselves
   - Maximizer program: copay assistance applied until deductible met, then benefit changes to maximize manufacturer payment
2. Track: `copay_assistance_applied` (total assistance received) and `copay_assistance_counted` (how much counted toward accumulators)
3. ReclaimRx Module 16 consumes this data for accumulator/maximizer detection

**Benefit year reset:**
1. Scheduled job at benefit year boundary
2. For each member with new benefit year: reset all accumulators to $0
3. Write ledger entries for each reset
4. Carryover rules: some plans carryover unused deductible credits from Q4 → configurable

**Part D benefit phases:**
1. Track TrOOP (True Out-of-Pocket) per CMS rules
2. Phase transitions: Deductible → Initial Coverage → Coverage Gap → Catastrophic
3. Each phase has different cost-sharing rules
4. Phase tracked on accumulator record, updated with every claim

### 3.4 COB (Coordination of Benefits)

1. Member may have multiple coverage sources (employer + spouse's employer, Medicare + commercial supplement)
2. Payer sequence determines processing order: primary → secondary → tertiary
3. On eligibility check: return COB info so adjudication knows whether to process as primary or secondary
4. COB data from: enrollment file, manual entry, real-time 270/271 response, or claim history (if other payer paid on a claim)
5. COB changes trigger eligibility cache invalidation

### 3.5 Member Search

1. **By member_id**: exact match (most common — from claim data)
2. **By cardholder_id + person_code**: dependent lookup
3. **By name + DOB**: fuzzy matching for operator lookup
4. **By SSN**: exact match against encrypted field (requires PHI access permission)
5. **By BIN/PCN/Group**: list all members in a plan (for client portals)
6. Filters: status, group, plan, state, coverage_type
7. Results always tenant-scoped. PHI fields visible only to authorized roles.

### 3.6 270/271 Eligibility Transaction Support

For real-time eligibility verification from external systems:

1. Receive inbound 270 request (HIPAA X12 270 format)
2. Parse: extract member identifiers, requested eligibility type, date of service
3. Run eligibility check (same logic as 3.2)
4. Build 271 response (HIPAA X12 271 format) with: eligibility status, plan details, accumulator balances, COB info
5. Return 271 response
6. Log in eligibility_checks table

### 3.7 Member Merge (Duplicate Resolution)

When duplicate member records are identified:

1. Operator selects primary record and duplicate record
2. System shows comparison of all fields
3. Operator confirms merge direction (which record survives)
4. Merge: all claims, coverage periods, accumulators, COB records, and history transferred to surviving record
5. Duplicate record marked as `merged` with reference to surviving record
6. Audit trail records the merge with full before/after state

### 3.8 Retroactive Eligibility

Client sends enrollment file showing a member was actually eligible starting 3 months ago:

1. **Detection**: enrollment file contains effective_date in the past for a new or re-enrolled member
2. **Retroactive enrollment**: create member + coverage period with past effective_date
3. **Claim impact analysis**: query billing for claims rejected with "not eligible" for this member during the retroactive period
4. **Re-adjudication queue**: flag affected claims for re-adjudication (emit `member.retroactive_enrollment` event consumed by adjudication module)
5. **Audit trail**: retroactive enrollment clearly logged with reason and source file
6. **Configurable limit**: maximum retroactive period (default: 90 days, configurable per tenant)

### 3.9 Dependent Aging-Out

Dependents reaching coverage age limit:

1. **Age limit rules**: configurable per plan. ACA default: 26 for dependents. Some plans: 19 (unless full-time student), 25 (student extension).
2. **Daily job**: check all active dependents where (today - date_of_birth) reaches age limit
3. **Pre-notification**: 90 days before aging out → alert to group/employer and member
4. **Auto-termination**: on birthday reaching age limit → auto-terminate coverage with reason `dependent_aged_out`
5. **COBRA offer**: if applicable, trigger COBRA notification workflow

### 3.10 Enrollment Period Management

Enrollment changes only during defined windows:

1. **Period definitions**: per plan — open_enrollment (annual window), special_enrollment (qualifying life events), new_hire (initial enrollment)
2. **Qualifying life events**: marriage, birth/adoption, job loss, relocation, divorce — each with configurable enrollment window (typically 30-60 days)
3. **Enforcement**: enrollment API validates that the enrollment/change request falls within an active enrollment period or has an approved qualifying life event
4. **Override**: tenant admin can override enrollment period restrictions with reason (logged in audit trail)

### 3.11 Member Address Validation

USPS address standardization:

1. **On enrollment**: validate member address against USPS Address Validation API
2. **Standardize**: convert to USPS standard format (apartment vs apt, street vs st, correct zip+4)
3. **Undeliverable**: flag addresses that USPS can't validate. Don't reject enrollment — flag for review.
4. **Used for**: ID card mailing, network adequacy calculations (member-to-pharmacy distance), geographic analytics in DataIQ
5. **Batch validation**: on initial load of historical enrollment, batch-validate all addresses

### 3.12 Part D Late Enrollment Penalty (LEP)

For Medicare Part D members:

1. **LEP calculation**: 1% of national base beneficiary premium × months without creditable coverage after initial enrollment period
2. **Tracking**: months_without_coverage field, calculated from coverage gaps
3. **Premium impact**: LEP added to monthly Part D premium permanently
4. **Source**: client enrollment data or CMS data feed
5. **Reporting**: LEP amount per member for client billing and CMS reporting

### 3.13 Member Consent Management

HIPAA authorization and communication consent:

1. **Consent records**: member_id, consent_type (hipaa_release, marketing_communications, data_sharing, research_participation, third_party_disclosure), granted_date, revoked_date, consent_method (written, electronic, verbal), document_file_id
2. **Enforcement**: before sharing member data with third parties, verify active consent exists
3. **Portal self-service**: members can view and manage their consent preferences
4. **Regulatory**: HIPAA requires tracking of all authorizations for PHI disclosure

### 3.14 Disenrollment Reason Coding

Standardized termination reasons:

1. **Code set**: voluntary_withdrawal, involuntary_termination, non_payment, death, group_termination, cobra_exhaustion, dependent_aged_out, moved_out_of_area, plan_termination, retroactive_correction, other
2. **Required**: every termination must include a reason code
3. **Reporting**: disenrollment reasons aggregated for quality reporting and CMS submissions
4. **Used by**: DataIQ (member retention analytics), Reporting (regulatory submissions)

### 3.15 COBRA Continuation Tracking

When an employee loses group coverage:

1. **COBRA event**: triggered by: employment termination, reduction in hours, death of employee, divorce, dependent aging out, employer bankruptcy
2. **COBRA record**: member_id, qualifying_event, cobra_start_date, cobra_max_end_date (18 months standard, 36 months for certain events), cobra_premium, cobra_payment_status
3. **Coverage continuation**: member's existing plan continues during COBRA period
4. **Premium tracking**: COBRA premium (typically 102% of full premium) tracked and billed separately
5. **Exhaustion**: when COBRA period ends → auto-terminate with reason `cobra_exhaustion`
6. **Notifications**: COBRA election notice (required within 14 days), premium due notices, exhaustion warning at 90/60/30 days

---

## 4. API Endpoints

```
/api/v1/members/

# Enrollment
POST   /enrollment/upload               Upload enrollment file
GET    /enrollment/upload/{id}/preview   Preview parsed records + validation
POST   /enrollment/upload/{id}/process   Process confirmed enrollment
GET    /enrollment/files                 List enrollment files
GET    /enrollment/files/{id}            File processing status + results

# Member CRUD
GET    /members                         Search/list members (filterable)
POST   /members                         Create member (manual enrollment)
GET    /members/{id}                     Member detail (demographics + coverage + accumulators)
PUT    /members/{id}                     Update member demographics
POST   /members/{id}/terminate           Terminate member with reason
POST   /members/merge                    Merge duplicate members

# Eligibility (real-time — called by adjudication)
GET    /eligibility                      Check eligibility (query params: member_id, bin, pcn, group, dos)
POST   /eligibility/270                  Process inbound 270 request, return 271

# Accumulators
GET    /members/{id}/accumulators        Current accumulator balances
GET    /members/{id}/accumulators/ledger  Accumulator transaction history
POST   /members/{id}/accumulators/adjust  Manual accumulator adjustment (admin)
POST   /accumulators/reset               Trigger benefit year reset (admin/scheduled)

# Coverage
GET    /members/{id}/coverage            Coverage periods (current + historical)
POST   /members/{id}/coverage            Add coverage period
PUT    /members/{id}/coverage/{period_id} Update coverage period

# COB
GET    /members/{id}/cob                 COB records
POST   /members/{id}/cob                 Add COB record
PUT    /members/{id}/cob/{id}            Update COB
DELETE /members/{id}/cob/{id}            Remove COB

# Groups
GET    /groups                           List groups (tenant-scoped)
POST   /groups                           Create group
PUT    /groups/{id}                      Update group
GET    /groups/{id}/members              Members in group

# ID Card
GET    /members/{id}/id-card             ID card data (BIN, PCN, Group, Member ID)

# Admin
GET    /stats                            Enrollment statistics (active members, by group, by plan)
```

---

## 5. Events

### Published
- `member.enrolled` — new member added
- `member.updated` — demographics changed
- `member.terminated` — coverage terminated
- `member.plan_changed` — plan assignment changed
- `member.accumulator_updated` — accumulator balance changed (consumed by adjudication for real-time pricing)
- `member.benefit_phase_changed` — Part D benefit phase transition
- `member.eligibility_checked` — eligibility check performed (for audit)
- `member.cob_changed` — COB record added/changed
- `member.merged` — duplicate members merged

### Consumed
- `claim.adjudicated` — update accumulators based on adjudication result
- `claim.reversed` — reverse accumulator impact

---

## 6. Default Implementation

Ships fully functional:

- **Enrollment file processing** — 834 EDI parser + configurable CSV/Excel parser with validation, preview, and error reporting
- **Real-time eligibility check** — <5ms cached, <25ms database. BIN/PCN/Group/MemberID + person_code lookup.
- **Accumulator management** — deductible, OOP max, MOOP, TrOOP, copay cap, benefit max. Penny-perfect Decimal math. Ledger for every transaction.
- **Copay assistance + accumulator/maximizer interaction** — tracks assistance applied vs counted per accumulator program type
- **Part D benefit phase tracking** — deductible → initial coverage → coverage gap → catastrophic with TrOOP calculation
- **COB management** — primary/secondary/tertiary payer sequencing
- **Member search** — by ID, name+DOB (fuzzy), SSN (encrypted), BIN/PCN/Group
- **270/271 eligibility transaction** — HIPAA X12 format support
- **Benefit year reset** — scheduled job with ledger entries and carryover rules
- **Member merge** — duplicate resolution with full audit trail
- **Enrollment file format mapping** — configurable per client (any CSV/Excel layout)
- **Group/employer management** — group enrollment with default plan assignment
- **PHI encryption** — SSN and sensitive fields encrypted at rest via Core Platform utilities

---

## 7. Performance Requirements

- Eligibility check (cache): <5ms
- Eligibility check (database): <25ms
- Accumulator update: <50ms (including ledger write)
- Enrollment file processing: 10,000 records/minute
- Member search by ID: <10ms
- Member search by name: <200ms
- 270/271 transaction: <500ms end-to-end
- Benefit year reset (100K members): <30 minutes

---

## 8. Data Retention

- Member records: per tenant policy (default: 7 years after termination)
- Coverage periods: indefinite (historical coverage for audit)
- Accumulator ledger: 7 years (financial record)
- Eligibility check logs: 2 years
- Enrollment files: 7 years
- COB records: indefinite (coverage history)

---

## 9. Test Scenarios (100% Coverage Required)

### Critical Paths (100%)
- Eligibility check returns correct result for: active member, terminated member, future effective date, member not found, wrong BIN/PCN/Group
- Accumulator math: claim applied → accumulated_amount increases correctly (Decimal, penny-perfect)
- Accumulator math: claim reversed → accumulated_amount decreases correctly
- Accumulator math: deductible met → subsequent claims have zero deductible applied
- Benefit year reset: all accumulators return to $0, ledger entries created
- Part D phase transition: correct phase determined at each accumulator threshold
- Copay assistance: correctly counted or excluded based on accumulator/maximizer plan type
- Enrollment file: valid file processes all records correctly (add/update/terminate)
- Enrollment file: invalid records rejected with specific error messages, valid records still process
- COB: primary/secondary payer sequence applied correctly
- Member merge: all related records transferred, duplicate marked, audit trail complete
- PHI encryption: SSN stored encrypted, decrypted only for authorized queries

### Edge Cases
- Member with no coverage period on DOS → rejected as "coverage gap"
- Accumulator at exactly $0.01 below limit → correctly applies partial amount
- Family deductible: one family member's claims count toward family accumulator
- Dependent lookup when subscriber is terminated but dependent still active → dependent eligible
- Enrollment file with 100K records, 50 errors → 99,950 processed, 50 in error report
- Same member enrolled, terminated, re-enrolled → three coverage periods, latest is active
- 270 request with invalid member → 271 response with "not found" status code

---

## 10. Session Decomposition

1. **Core member + enrollment**: members table, groups table, enrollment file processing (834 parser, CSV parser, validation, preview), member CRUD API, member search, PHI encryption integration
2. **Eligibility + coverage + COB**: eligibility check service (real-time), Redis caching, coverage periods, COB management, 270/271 transaction support, eligibility logging
3. **Accumulators + benefit phases + advanced**: accumulator management (all types), accumulator ledger, copay assistance tracking, accumulator/maximizer interaction, Part D benefit phase engine, benefit year reset job, member merge workflow, event publishing
