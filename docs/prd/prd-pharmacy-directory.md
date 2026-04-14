# PRD — Module 3: Pharmacy Directory — FINAL

**Module:** Pharmacy Directory  
**Folder:** `modules/pharmacy-directory/`  
**Priority:** Phase 3  
**Dependencies:** Core Platform (Module 1)  

---

## 1. Purpose

The Pharmacy Directory is the authoritative source for pharmacy data across the platform. Every module that references a pharmacy — adjudication, billing, ReclaimRx, reporting, DataIQ — queries this module. It manages pharmacy demographics, network participation, credentialing, contract terms, and performance tracking.

**Data sources:**
1. **NCPDP Provider Database** — primary (subscription). Pharmacy demographics, NABP number, NPI, store type, services, hours, dispensing capabilities.
2. **NPPES (CMS)** — free. NPI verification, taxonomy codes, practice locations. Monthly full + weekly incremental download.
3. **OIG/SAM/OFAC** — exclusion screening (via Core Platform Module 1).
4. **State Board of Pharmacy** — license verification (manual or API where available).
5. **Pharmacy applications** — pharmacies apply to join networks via portal or file upload.

**What this module provides:**
- Pharmacy lookup by NPI, NABP, name, address, network
- Network management (which pharmacies are in which network for which tenant)
- Credentialing workflow (application → review → approval → ongoing monitoring)
- Contract terms per pharmacy per network (reimbursement rates, dispensing fees)
- Pharmacy performance metrics (cost, quality, adherence, volume)
- Pharmacy type classification (chain, independent, specialty, mail order, LTC, 340B, compounding)
- Geographic access / network adequacy analysis

---

## 2. Data Model

```sql
CREATE SCHEMA pharmacy_dir;

-- Master pharmacy record (one per NPI)
CREATE TABLE pharmacy_dir.pharmacies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Identifiers
    npi VARCHAR(10) NOT NULL UNIQUE,
    nabp_number VARCHAR(7),
    ncpdp_id VARCHAR(10),
    dea_number VARCHAR(9),
    state_license_number VARCHAR(50),
    state_license_state VARCHAR(2),
    
    -- Name
    legal_name VARCHAR(500) NOT NULL,
    dba_name VARCHAR(500),
    display_name VARCHAR(500) NOT NULL,
    
    -- Type
    pharmacy_type VARCHAR(50) NOT NULL,
    -- chain, independent, specialty, mail_order, ltc, compounding,
    -- nuclear, home_infusion, clinic, hospital_outpatient, 340b, federal
    
    chain_name VARCHAR(255),
    chain_code VARCHAR(50),
    store_number VARCHAR(50),
    
    -- Location
    address_line_1 VARCHAR(255) NOT NULL,
    address_line_2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(2) NOT NULL,
    zip_code VARCHAR(10) NOT NULL,
    county VARCHAR(100),
    country VARCHAR(2) DEFAULT 'US',
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    
    -- Contact
    phone VARCHAR(20),
    fax VARCHAR(20),
    email VARCHAR(255),
    website VARCHAR(500),
    
    -- Hours
    hours_monday VARCHAR(50),
    hours_tuesday VARCHAR(50),
    hours_wednesday VARCHAR(50),
    hours_thursday VARCHAR(50),
    hours_friday VARCHAR(50),
    hours_saturday VARCHAR(50),
    hours_sunday VARCHAR(50),
    is_24_hour BOOLEAN DEFAULT FALSE,
    
    -- Capabilities
    accepts_electronic_rx BOOLEAN DEFAULT TRUE,
    dispenses_controlled BOOLEAN DEFAULT TRUE,
    offers_delivery BOOLEAN DEFAULT FALSE,
    offers_compounding BOOLEAN DEFAULT FALSE,
    offers_specialty BOOLEAN DEFAULT FALSE,
    offers_340b BOOLEAN DEFAULT FALSE,
    offers_immunizations BOOLEAN DEFAULT FALSE,
    offers_mtm BOOLEAN DEFAULT FALSE,
    offers_covid_testing BOOLEAN DEFAULT FALSE,
    languages_spoken JSONB DEFAULT '["en"]',
    
    -- Ownership (for credentialing and FWA)
    ownership_type VARCHAR(50),                        -- individual, partnership, corporation, llc
    owner_name VARCHAR(255),
    ownership_effective_date DATE,
    previous_owner_name VARCHAR(255),
    ownership_change_date DATE,
    
    -- 340B
    is_340b_entity BOOLEAN DEFAULT FALSE,
    hrsa_id VARCHAR(20),
    covered_entity_type VARCHAR(100),
    
    -- Status
    status VARCHAR(50) DEFAULT 'active',
    -- active, inactive, suspended, terminated, pending_credentialing
    deactivation_date DATE,
    deactivation_reason VARCHAR(255),
    
    -- Data source tracking
    ncpdp_last_updated TIMESTAMPTZ,
    nppes_last_updated TIMESTAMPTZ,
    manual_last_updated TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pharmacy_npi ON pharmacy_dir.pharmacies(npi);
CREATE INDEX idx_pharmacy_nabp ON pharmacy_dir.pharmacies(nabp_number);
CREATE INDEX idx_pharmacy_name ON pharmacy_dir.pharmacies USING gin(to_tsvector('english', display_name));
CREATE INDEX idx_pharmacy_location ON pharmacy_dir.pharmacies(state, city);
CREATE INDEX idx_pharmacy_type ON pharmacy_dir.pharmacies(pharmacy_type);
CREATE INDEX idx_pharmacy_chain ON pharmacy_dir.pharmacies(chain_code);
CREATE INDEX idx_pharmacy_geo ON pharmacy_dir.pharmacies(latitude, longitude);

-- ═══════════════════════════════════════════════
-- NETWORK MANAGEMENT
-- ═══════════════════════════════════════════════

-- Networks (tenant-specific)
CREATE TABLE pharmacy_dir.networks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    name VARCHAR(255) NOT NULL,
    network_code VARCHAR(50) NOT NULL,
    network_type VARCHAR(50) NOT NULL,                 -- retail, specialty, mail_order, ltc, 340b, preferred
    description TEXT,
    
    is_active BOOLEAN DEFAULT TRUE,
    effective_date DATE NOT NULL,
    termination_date DATE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, network_code)
);

-- Pharmacy-network membership
CREATE TABLE pharmacy_dir.network_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pharmacy_id UUID NOT NULL REFERENCES pharmacy_dir.pharmacies(id),
    network_id UUID NOT NULL REFERENCES pharmacy_dir.networks(id),
    
    status VARCHAR(50) DEFAULT 'active',
    -- active, suspended, pending, terminated
    
    effective_date DATE NOT NULL,
    termination_date DATE,
    termination_reason VARCHAR(255),
    
    -- Contract terms
    contract_id UUID,
    reimbursement_type VARCHAR(50),                     -- awp_discount, mac, nadac_plus, cost_plus, flat
    brand_discount DECIMAL(8,4),                       -- e.g., AWP - 15% → 0.1500
    generic_discount DECIMAL(8,4),
    specialty_discount DECIMAL(8,4),
    dispensing_fee DECIMAL(8,2),
    admin_fee DECIMAL(8,2),
    
    -- Performance tier
    performance_tier VARCHAR(50),                       -- preferred, standard, limited
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, pharmacy_id, network_id, effective_date)
);

-- ═══════════════════════════════════════════════
-- CREDENTIALING
-- ═══════════════════════════════════════════════

CREATE TABLE pharmacy_dir.credentialing_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pharmacy_id UUID REFERENCES pharmacy_dir.pharmacies(id),
    
    -- Applicant info (before pharmacy record may exist)
    applicant_npi VARCHAR(10) NOT NULL,
    applicant_name VARCHAR(500) NOT NULL,
    applicant_address TEXT,
    
    -- Application
    network_id UUID NOT NULL REFERENCES pharmacy_dir.networks(id),
    application_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- ReclaimRx risk score (from Module 16)
    credentialing_risk_score INTEGER,
    risk_score_factors JSONB,
    
    -- Verification checklist
    npi_verified BOOLEAN DEFAULT FALSE,
    state_license_verified BOOLEAN DEFAULT FALSE,
    state_license_expiry DATE,
    dea_verified BOOLEAN DEFAULT FALSE,
    dea_expiry DATE,
    oig_sam_screened BOOLEAN DEFAULT FALSE,
    oig_sam_clear BOOLEAN DEFAULT FALSE,
    liability_insurance_verified BOOLEAN DEFAULT FALSE,
    insurance_expiry DATE,
    
    -- Status
    status VARCHAR(50) DEFAULT 'submitted',
    -- submitted, under_review, additional_info_requested,
    -- approved, denied, withdrawn
    
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    denial_reason TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Credentialing document tracking
CREATE TABLE pharmacy_dir.credentialing_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES pharmacy_dir.credentialing_applications(id),
    
    document_type VARCHAR(100) NOT NULL,
    -- state_license, dea_certificate, liability_insurance, w9,
    -- accreditation_certificate, ownership_disclosure, sanctions_attestation
    
    file_id UUID,                                      -- ref to core.files
    
    status VARCHAR(50) DEFAULT 'pending',              -- pending, received, verified, expired
    expiry_date DATE,
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ongoing credentialing monitoring
CREATE TABLE pharmacy_dir.credential_monitoring (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pharmacy_id UUID NOT NULL REFERENCES pharmacy_dir.pharmacies(id),
    
    credential_type VARCHAR(100) NOT NULL,
    current_status VARCHAR(50) NOT NULL,
    expiry_date DATE,
    
    -- Alerts
    alert_days_before_expiry INTEGER DEFAULT 90,
    alert_sent_at TIMESTAMPTZ,
    
    last_verified_at TIMESTAMPTZ,
    next_verification_date DATE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════
-- PAYMENT INFO (for payment processing)
-- ═══════════════════════════════════════════════

CREATE TABLE pharmacy_dir.pharmacy_payment_info (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    pharmacy_id UUID NOT NULL REFERENCES pharmacy_dir.pharmacies(id),
    
    payment_method_preference VARCHAR(50),              -- ach, eft, check, virtual_card
    
    bank_name VARCHAR(255),
    routing_number VARCHAR(9),
    account_number VARCHAR(17),
    account_type VARCHAR(20),
    
    remittance_delivery VARCHAR(50),                    -- sftp, email, portal, fax
    remittance_email VARCHAR(255),
    remittance_sftp_config_id UUID,
    
    w9_on_file BOOLEAN DEFAULT FALSE,
    w9_file_id UUID,
    tax_id VARCHAR(11),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, pharmacy_id)
);

-- ═══════════════════════════════════════════════
-- PSAO (Pharmacy Services Administrative Organization)
-- ═══════════════════════════════════════════════

CREATE TABLE pharmacy_dir.psaos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    name VARCHAR(500) NOT NULL,
    psao_id VARCHAR(50),
    npi VARCHAR(10),
    
    address TEXT,
    contact_name VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    
    payment_consolidated BOOLEAN DEFAULT TRUE,         -- pays on behalf of member pharmacies
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE pharmacy_dir.psao_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_id UUID NOT NULL REFERENCES pharmacy_dir.pharmacies(id),
    psao_id UUID NOT NULL REFERENCES pharmacy_dir.psaos(id),
    
    effective_date DATE NOT NULL,
    termination_date DATE,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 3. Business Logic

### 3.1 Data Refresh Pipeline

**NCPDP Provider Database (subscription, monthly):**
1. Download monthly NCPDP data file
2. Parse per NCPDP spec
3. Upsert into `pharmacies`: create new, update changed, flag deactivated
4. Fields from NCPDP: NPI, NABP, name, address, phone, fax, store type, hours, dispensing capabilities, chain affiliation
5. Track changes: ownership changes → alert ReclaimRx (credentialing risk factor)

**NPPES (free, monthly + weekly incremental):**
1. Download V2 monthly file (or weekly incremental)
2. Filter to pharmacy taxonomy codes (333600000X and subtypes)
3. Cross-reference against existing pharmacies by NPI
4. Update: address, phone, taxonomy, active/deactivated status
5. New pharmacy NPIs not in NCPDP → flag for review (may be newly opened)

**Geocoding:**
1. After address update: geocode to latitude/longitude via Azure Maps or Google Geocoding API
2. Cache geocoding results (address → lat/lng mapping)
3. Used for: network adequacy calculations, geographic search, distance-based pharmacy lookup

### 3.2 Pharmacy Lookup

1. Input: NPI, NABP number, name (partial), address, or geographic coordinates + radius
2. NPI/NABP: exact match, Redis-cached (TTL: 24 hours)
3. Name: full-text search with PostgreSQL tsvector
4. Geographic: PostGIS `ST_DWithin` query for radius search
5. Filters: pharmacy_type, chain, network, state, capabilities (specialty, 340B, compounding)
6. Response: full pharmacy detail + network memberships for the requesting tenant
7. **Performance:** <10ms cache hit, <100ms database, <500ms geographic search

### 3.3 Network Management

1. Tenant creates networks (retail, specialty, mail order, preferred, etc.)
2. Pharmacies added to networks individually or in bulk (CSV upload with NPI list)
3. Membership has effective/termination dates and contract terms
4. Pharmacy can be in multiple networks simultaneously
5. Network changes logged in audit trail
6. Any Willing Pharmacy (2028 mandate): configurable flag per network. When enabled, system auto-approves any pharmacy meeting standard terms.

### 3.4 Credentialing Workflow

1. **Application received** (portal submission, API, or file upload)
2. **ReclaimRx risk score** requested automatically (if ReclaimRx module available)
3. **Automated verification:**
   - NPI: validate against NPPES (active, correct entity type)
   - State license: check state board API (where available) or flag for manual verification
   - DEA: verify number format and status
   - OIG/SAM: screen via Core Platform exclusion service
   - OFAC: screen via Core Platform exclusion service
4. **Risk-based routing:**
   - Low risk (score 0-25, all automated checks pass): fast-track approval queue
   - Medium risk (score 26-50 or any manual verification needed): standard review queue
   - High risk (score 51+, recent ownership change, prior fraud flags): enhanced review queue
5. **Reviewer** examines application, requests additional documents if needed
6. **Decision:** approve → create network membership. Deny → record reason. Request info → notify applicant.
7. **Ongoing monitoring:** credentials tracked with expiry dates. Alerts at 90/60/30 days before expiry. Re-credentialing required per configurable schedule (default: annually).

### 3.5 Network Adequacy Analysis

For health plan clients — regulatory requirement:

1. Calculate: % of members within X miles of a network pharmacy (urban: 2 miles, suburban: 5 miles, rural: 15 miles — configurable)
2. Input: member addresses (from Member Management Module 5) + pharmacy locations + network membership
3. PostGIS spatial query: for each member, find nearest network pharmacy
4. Output: adequacy percentage by region, map visualization, gaps identified
5. Used for: CMS network adequacy requirements, state regulatory filings, network optimization

### 3.6 Pharmacy Performance Metrics

Aggregated from Billing and ReclaimRx modules:

1. **Cost metrics**: average claim cost, AWP discount achieved, generic fill rate, MAC compliance rate
2. **Quality metrics**: reversal rate, FWA flag count, audit findings count, corrective actions outstanding
3. **Volume metrics**: total claims, total dollar volume, unique members served
4. **Adherence contribution**: PDC rates for members primarily using this pharmacy
5. Metrics calculated monthly, stored as snapshots for trending
6. Used by: DataIQ pharmacy scorecard, network performance reporting, tier assignment

### 3.7 Accreditation Tracking

For specialty pharmacies — some plans require accreditation:

1. **Accreditation records**: pharmacy_id, accrediting_body (URAC, ACHC, Joint Commission, CPPA), accreditation_type (specialty, compounding, infusion), status (accredited, provisional, expired, revoked), effective_date, expiry_date
2. **Monitoring**: alert at 90/60/30 days before accreditation expiry
3. **Adjudication integration**: if plan requires accredited specialty pharmacy, verify accreditation status before approving specialty drug claim
4. **Verification**: manual entry or API where accrediting body provides one

### 3.8 Limited Distribution Drug (LDD) Designation

Some drugs can only be dispensed at manufacturer-designated pharmacies:

1. **LDD mapping table**: drug_id (NDC or ingredient), pharmacy_id, manufacturer_authorization, effective_date, termination_date
2. **Adjudication integration**: if drug is LDD-restricted, verify pharmacy is on the authorized list
3. **Source**: manufacturer program configurations, maintained per tenant/program
4. **Overlap with REMS**: some LDD restrictions come from REMS certified pharmacy requirements. Track source.

### 3.9 Contract Rate History

When network reimbursement rates change, historical rates preserved:

1. **Rate effective dating**: every rate change creates a new record with effective_date. Old rate gets termination_date.
2. **Claim pricing**: adjudication uses the rate effective on the claim's date_of_service, NOT the current rate
3. **Audit trail**: full history of rate changes per pharmacy per network, with who changed it and when
4. **Bulk rate updates**: when a network renegotiates, bulk update with new effective date. Old rates preserved.

### 3.10 Pharmacy Closure Handling

When NCPDP marks a pharmacy as closed:

1. **Detection**: NCPDP refresh detects pharmacy status change to closed/inactive
2. **Immediate actions**: mark status `closed`, alert billing (freeze new routing), alert payment processing (flag outstanding payments), alert tenant operators
3. **In-flight claims**: claims adjudicated but not yet paid → route to pay-to waterfall (PSAO or alternate)
4. **Member impact**: flag affected members for outreach with nearest alternative pharmacy

### 3.11 Chain Bulk Credentialing

When adding a chain with thousands of locations:

1. **Chain-level application**: single credentialing application for the chain (corporate level)
2. **Corporate verification**: verify chain's corporate NPI, state registrations, insurance, OIG/SAM
3. **Store-level auto-enrollment**: once chain approved, all stores with matching chain_code added to network
4. **Individual exceptions**: specific stores can be excluded or have different terms
5. **New store detection**: NCPDP refresh shows new store for approved chain → auto-enroll with alert

### 3.12 Pharmacy Taxonomy Auto-Classification

Map NPPES taxonomy subtypes to pharmacy_type automatically: community/retail (3336C0003X), compounding (3336C0004X), home infusion (3336H0001X), institutional (3336I0012X), LTC (3336L0003X), mail order (3336M0002X), nuclear (3336N0007X), specialty (3336S0011X). NCPDP store type overrides NPPES taxonomy when available (more accurate).

### 3.13 DAW Rate Tracking

Per-pharmacy dispense-as-written rate calculated from claims data:

1. DAW rate = (claims with DAW code ≠ 0) / (total claims) per pharmacy per period
2. Calculated monthly from billing claim data
3. High DAW rate → cost indicator (pharmacy not substituting generics)
4. Feeds into: pharmacy scorecard, DataIQ network analytics, ReclaimRx profiling

---

## 4. API Endpoints

```
/api/v1/pharmacies/

# Lookup
GET    /lookup/{npi}                    Pharmacy detail by NPI
GET    /lookup/nabp/{nabp}              Pharmacy by NABP number
GET    /search                          Search by name, address, type, capabilities
GET    /nearby                          Geographic search (lat/lng + radius)
GET    /batch                           Batch lookup (up to 100 NPIs)

# Networks
GET    /networks                        List networks (tenant-scoped)
POST   /networks                        Create network
PUT    /networks/{id}                   Update network
GET    /networks/{id}/pharmacies        List pharmacies in network
POST   /networks/{id}/pharmacies        Add pharmacy(ies) to network
DELETE /networks/{id}/pharmacies/{pharmacy_id}  Remove pharmacy from network
POST   /networks/{id}/bulk-add          Bulk add pharmacies (CSV upload)
GET    /networks/{id}/adequacy          Network adequacy analysis

# Credentialing
GET    /credentialing                   List credentialing applications
POST   /credentialing                   Submit application
GET    /credentialing/{id}              Application detail
PUT    /credentialing/{id}              Update application (reviewer)
POST   /credentialing/{id}/approve      Approve application
POST   /credentialing/{id}/deny         Deny application
GET    /credentialing/monitoring        Credential expiry monitoring dashboard

# Payment Info
GET    /payment-info/{pharmacy_id}      Pharmacy payment info
PUT    /payment-info/{pharmacy_id}      Update payment info

# PSAOs
GET    /psaos                           List PSAOs
GET    /psaos/{id}/pharmacies           Pharmacies in PSAO
POST   /psaos                           Create PSAO

# Performance
GET    /performance/{npi}               Pharmacy performance metrics
GET    /performance/rankings            Pharmacy rankings by metric

# Admin
GET    /refresh/status                  Last data refresh status
POST   /refresh                         Trigger manual refresh
GET    /stats                           Directory statistics
```

---

## 5. Events

### Published
- `pharmacy.created` — new pharmacy added to directory
- `pharmacy.updated` — pharmacy data changed
- `pharmacy.ownership_changed` — ownership change detected (important for ReclaimRx)
- `pharmacy.deactivated` — pharmacy NPI deactivated
- `pharmacy.network_added` — pharmacy added to a network
- `pharmacy.network_removed` — pharmacy removed from network
- `pharmacy.credential_expiring` — credential approaching expiry
- `pharmacy.credentialing_completed` — application approved or denied
- `pharmacy.application_submitted` — new credentialing application (consumed by ReclaimRx for risk scoring)

### Consumed
- `fwa.credentialing_risk_elevated` — from ReclaimRx, update pharmacy risk score in credentialing
- `fwa.pharmacy_risk_elevated` — from ReclaimRx, flag pharmacy for review

---

## 6. Default Implementation

Ships fully functional:

- **NCPDP Provider Database integration** — monthly refresh from subscription feed
- **NPPES integration** — V2 monthly + weekly incremental, filtered to pharmacy taxonomies
- **Geocoding** — address to lat/lng for geographic search and adequacy
- **Pharmacy lookup** — by NPI, NABP, name (full-text), geographic (PostGIS), all Redis-cached
- **Network management** — create networks, add/remove pharmacies, bulk CSV upload, effective dates
- **Credentialing workflow** — application → automated verification → risk-based routing → review → decision
- **ReclaimRx integration** — credentialing risk score requested automatically
- **Ongoing credential monitoring** — expiry tracking with 90/60/30-day alerts
- **Network adequacy analysis** — PostGIS spatial calculation per CMS standards
- **PSAO management** — consolidated payment routing
- **Payment info tracking** — bank details, remittance preferences per pharmacy per tenant
- **Any Willing Pharmacy support** — configurable flag for 2028 mandate readiness
- **Performance metrics** — monthly snapshots from Billing and ReclaimRx data

---

## 7. Performance Requirements

- NPI lookup (cache): <10ms
- NPI lookup (database): <50ms
- Name search: <200ms
- Geographic search (50-mile radius): <500ms
- Network adequacy calculation (100K members): <5 minutes
- Credentialing risk score request: <2 seconds
- NCPDP refresh (~75K pharmacies): <30 minutes
- NPPES refresh (pharmacy filter): <20 minutes

---

## 8. Data Retention

- Pharmacy records: indefinite (reference data — mark inactive, never delete)
- Network memberships: indefinite (historical participation for audit)
- Credentialing applications: 10 years (regulatory requirement)
- Performance metrics: 3 years of monthly snapshots
- Refresh logs: 2 years

---

## 9. Test Scenarios (100% Coverage Required)

### Critical Paths (100%)
- Pharmacy lookup returns correct result for NPI, NABP, and name search
- Geographic search returns pharmacies within specified radius and excludes those outside
- Network membership correctly scoped to tenant (Tenant A can't see Tenant B's networks)
- Credentialing automated checks return correct pass/fail for known test NPIs
- Risk-based routing sends low/medium/high risk applications to correct queues
- Network adequacy calculation produces correct percentages against known test data
- Credential expiry alerts fire at correct days-before threshold

### Edge Cases
- Pharmacy with multiple NPIs (rare but exists) → each NPI is a separate record
- Pharmacy address changes → re-geocode automatically
- PSAO membership terminates → pharmacy payment routes to pharmacy directly
- Credentialing application for pharmacy already in network → reject with clear error
- Network adequacy with zero members in a region → skip region, don't divide by zero

---

## 10. Session Decomposition

1. **Core directory + data sources**: pharmacies table, NCPDP integration, NPPES integration, geocoding, NPI/NABP/name lookup, geographic search (PostGIS), Redis caching, full-text search
2. **Networks + credentialing + payment**: networks table, memberships, credentialing workflow (application → verification → routing → decision), credential monitoring, payment info, PSAOs, bulk CSV upload, network adequacy
3. **Performance + integration**: performance metrics aggregation (from billing/reclaimrx data), pharmacy rankings, ReclaimRx integration (risk score, ownership alerts), event publishing, data refresh pipeline, stats
